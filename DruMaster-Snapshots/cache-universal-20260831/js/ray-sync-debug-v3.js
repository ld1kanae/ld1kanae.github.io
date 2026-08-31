"use strict";

(()=>{
  const STEM_URL="songs/ray/drums.mp3";
  const MIDI_GZIP_URL="songs/ray/chart.mid.gz?v=20260826-midi2";
  const DRUM_MANIFEST_URL="assets/drumsound-manifest.json";
  const PRODUCTION_OFFSET_MS=21.5;
  const LOOKAHEAD_SEC=.20;
  const SCHEDULER_MS=30;
  const DRUM_GAIN={kick:1.4,crash:1.2};
  const MIDI_MAP={35:"kick",36:"kick",38:"snare",40:"snare",41:"floorTom",43:"floorTom",45:"midTom",47:"midTom",48:"highTom",50:"highTom",42:"hhClosed",44:"hhPedal",46:"hhOpen",49:"crash",52:"crash",55:"crash",57:"crash",51:"ride",53:"ride",59:"ride"};
  const DEFAULT_NOTE={kick:36,snare:38,floorTom:41,midTom:45,highTom:48,hhClosed:42,hhPedal:44,hhOpen:46,ride:51,crash:49,special:37};
  const $=s=>document.querySelector(s);
  const canvas=$("#timeline"),ctx=canvas.getContext("2d"),status=$("#status"),playBtn=$("#play"),stopBtn=$("#stop"),offsetInput=$("#offset"),offsetReadout=$("#offsetReadout"),zoomInput=$("#zoom"),zoomText=$("#zoomText"),scrollInput=$("#scroll");
  const staticCanvas=document.createElement("canvas"),staticCtx=staticCanvas.getContext("2d");
  const nativeFetch=globalThis.fetch.bind(globalThis),nativeBeacon=navigator.sendBeacon?.bind(navigator),xhrOpen=XMLHttpRequest.prototype.open;
  let networkLocked=false;
  globalThis.fetch=(...args)=>networkLocked?Promise.reject(new Error("再生中の通信は無効です")):nativeFetch(...args);
  XMLHttpRequest.prototype.open=function(...args){if(networkLocked)throw Error("再生中の通信は無効です");return xhrOpen.apply(this,args)};
  if(nativeBeacon)navigator.sendBeacon=(...args)=>networkLocked?false:nativeBeacon(...args);

  let ac=null,stemBuffer=null,drumBuffer=null,drumRegions={},drumSourceVelocity=100;
  let notes=[],tempos=[],duration=0,offsetMs=PRODUCTION_OFFSET_MS,pxPerSec=260,viewStart=0;
  let stemSource=null,playing=false,logicalStart=0,contextStart=0,raf=0,scheduler=0,nextMidi=0,drag=null,renderRaf=0;
  const activeMidiVoices=new Set(),openHatVoices=[];
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const round01=v=>Math.round(v*10)/10;
  const fmtMs=v=>`${v>=0?"+":""}${v.toFixed(1)} ms`;
  const fmtTime=t=>{t=Math.max(0,t||0);const m=Math.floor(t/60),s=Math.floor(t%60),ms=Math.floor((t-Math.floor(t))*1000);return `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}.${String(ms).padStart(3,"0")}`};
  const nowLogical=()=>playing?clamp(logicalStart+Math.max(0,ac.currentTime-contextStart),0,duration):logicalStart;
  function ensureAC(){if(!ac)ac=new (window.AudioContext||window.webkitAudioContext)({latencyHint:"interactive"});return ac}

  function parseMidi(ab){
    const d=new DataView(ab);let p=0;
    const need=(n,end=d.byteLength)=>{if(p+n>end)throw Error("MIDIデータが途中で切れています")};
    const str=n=>{need(n);let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s};
    const u32=()=>{need(4);const v=d.getUint32(p);p+=4;return v};
    const u16=()=>{need(2);const v=d.getUint16(p);p+=2;return v};
    const vlq=end=>{let v=0,b,count=0;do{need(1,end);b=d.getUint8(p++);v=(v<<7)|(b&127);if(++count>4)throw Error("MIDIの可変長値が不正です")}while(b&128);return v};
    if(d.byteLength<14||str(4)!=="MThd")throw Error("MIDIヘッダーが不正です");
    const headerLength=u32();u16();const tracks=u16(),division=u16();
    if(headerLength<6||8+headerLength>d.byteLength)throw Error("MIDIヘッダー長が不正です");
    if(division&0x8000)throw Error("SMPTE形式のMIDIには未対応です");
    p=8+headerLength;
    const raw=[],tempoRaw=[{tick:0,us:500000}];
    for(let tr=0;tr<tracks;tr++){
      need(8);
      if(str(4)!=="MTrk")throw Error(`MIDIトラック${tr+1}が不正です`);
      const len=u32(),end=p+len;
      if(end>d.byteLength)throw Error(`MIDIトラック${tr+1}が途中で切れています`);
      let tick=0,runningStatus=0;
      while(p<end){
        tick+=vlq(end);need(1,end);
        const first=d.getUint8(p++);let statusByte;
        if(first<128){if(!runningStatus)throw Error("MIDIランニングステータスが不正です");statusByte=runningStatus;p--}
        else{statusByte=first;if(statusByte<240)runningStatus=statusByte}
        if(statusByte===255){
          need(1,end);const type=d.getUint8(p++),n=vlq(end);need(n,end);
          if(type===81&&n===3)tempoRaw.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});
          p+=n;continue;
        }
        if(statusByte===240||statusByte===247){runningStatus=0;const n=vlq(end);need(n,end);p+=n;continue}
        if(statusByte>=240){
          const systemLengths={0xf1:1,0xf2:2,0xf3:1,0xf6:0,0xf8:0,0xfa:0,0xfb:0,0xfc:0,0xfe:0};
          const n=systemLengths[statusByte];if(n==null)throw Error(`未対応のMIDIイベント 0x${statusByte.toString(16)}`);need(n,end);p+=n;continue;
        }
        const hi=statusByte&240,ch=statusByte&15,bytes=(hi===192||hi===208)?1:2;
        need(bytes,end);const a=d.getUint8(p++),b=bytes===2?d.getUint8(p++):0;
        if(hi===144&&b>0&&ch===9)raw.push({tick,note:a,velocity:b});
      }
      p=end;
    }
    tempoRaw.sort((a,b)=>a.tick-b.tick);
    const dedup=[];for(const t of tempoRaw){if(dedup.length&&dedup.at(-1).tick===t.tick)dedup[dedup.length-1]=t;else dedup.push(t)}
    const segments=[];let lastTick=0,lastSec=0,us=500000;
    for(const e of dedup){lastSec+=(e.tick-lastTick)*us/division/1e6;lastTick=e.tick;us=e.us;if(e.tick===0&&segments.length===0)segments.push({tick:0,sec:0,us});else if(e.tick>0)segments.push({tick:e.tick,sec:lastSec,us})}
    if(!segments.length)segments.push({tick:0,sec:0,us:500000});
    const tickToSec=tick=>{let lo=0,hi=segments.length-1,idx=0;while(lo<=hi){const m=(lo+hi)>>1;if(segments[m].tick<=tick){idx=m;lo=m+1}else hi=m-1}const e=segments[idx];return e.sec+(tick-e.tick)*e.us/division/1e6};
    return {notes:raw.map(n=>({...n,time:tickToSec(n.tick),type:MIDI_MAP[n.note]||"special"})).sort((a,b)=>a.time-b.time),tempos:dedup,division};
  }

  async function loadGzipMidi(url){
    const r=await nativeFetch(url,{cache:"force-cache"});if(!r.ok)throw Error(`MIDI HTTP ${r.status}`);
    if(typeof DecompressionStream!=="function")throw Error("このブラウザではgzip MIDIを展開できません");
    const ab=await new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
    if(ab.byteLength<14||String.fromCharCode(...new Uint8Array(ab.slice(0,4)))!=="MThd")throw Error("展開したMIDIが不正です");
    return ab;
  }
  async function fetchJoined(spec){
    const paths=spec.paths||Array.from({length:spec.parts},(_,i)=>`${spec.pathPrefix}${String(i).padStart(spec.digits||3,"0")}`),parts=[];
    for(let i=0;i<paths.length;i+=8){
      status.textContent=`ゲーム内ドラム音源を読み込み中… ${i}/${paths.length}`;
      const batch=await Promise.all(paths.slice(i,i+8).map(async path=>{const r=await nativeFetch(path,{cache:"force-cache"});if(!r.ok)throw Error(`ドラム音源 HTTP ${r.status}`);return r.arrayBuffer()}));
      parts.push(...batch);
    }
    const size=parts.reduce((s,b)=>s+b.byteLength,0);if(spec.bytes&&size!==spec.bytes)throw Error(`ゲーム内ドラム音源が不完全です（${size}/${spec.bytes} bytes）`);
    const out=new Uint8Array(size);let at=0;for(const part of parts){out.set(new Uint8Array(part),at);at+=part.byteLength}return out.buffer;
  }
  async function loadDrumKit(){
    const mr=await nativeFetch(DRUM_MANIFEST_URL,{cache:"force-cache"});if(!mr.ok)throw Error(`ドラムmanifest HTTP ${mr.status}`);const manifest=await mr.json();
    const [wav,sourceMidi]=await Promise.all([fetchJoined(manifest.wav),nativeFetch(manifest.midi.path,{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error(`ドラムMIDI HTTP ${r.status}`);return r.arrayBuffer()})]);
    drumBuffer=await ac.decodeAudioData(wav.slice(0));drumSourceVelocity=manifest.sourceVelocity||100;
    const src=parseMidi(sourceMidi).notes;if(!src.length)throw Error("ゲーム内ドラム音源MIDIにノートがありません");
    drumRegions={};src.forEach((n,i)=>{const end=i+1<src.length?src[i+1].time:drumBuffer.duration;if(end>n.time)drumRegions[String(n.note)]={offset:n.time,duration:end-n.time}});
    const missing=[...new Set(Object.values(DEFAULT_NOTE))].filter(n=>!drumRegions[String(n)]);if(missing.length)throw Error(`ゲーム内ドラム音源に必要な音がありません（${missing.join(",")}）`);
  }

  function category(note){if(note===35||note===36)return 0;if(note===38||note===40||note===37)return 1;if(note===42||note===44||note===46)return 2;if([41,43,45,47,48,50].includes(note))return 3;if([49,51,52,55,57,59].includes(note))return 4;return 5}
  const laneNames=["KICK","SNARE","HI-HAT","TOMS","CYMBAL","OTHER"];
  const laneColors=["#66c9ff","#ff8db3","#f3d36c","#b28cff","#73e3cf","#96a5b6"];
  function viewportWidth(){return canvas.getBoundingClientRect().width}
  function viewportDuration(){return viewportWidth()/pxPerSec}
  function maxViewStart(){return Math.max(0,duration-viewportDuration())}
  function syncScroll(){scrollInput.value=maxViewStart()>0?String(Math.round(viewStart/maxViewStart()*1000)):"0"}
  function xToTime(x){return viewStart+x/pxPerSec}
  function timeToX(t){return (t-viewStart)*pxPerSec}
  function requestStaticRender(){if(renderRaf)return;renderRaf=requestAnimationFrame(()=>{renderRaf=0;renderStatic();drawFrame()})}
  function setViewStart(v){viewStart=clamp(v,0,maxViewStart());syncScroll();requestStaticRender()}

  function resize(){
    const r=canvas.getBoundingClientRect(),dpr=Math.min(2,devicePixelRatio||1),w=Math.max(1,Math.round(r.width*dpr)),h=Math.max(1,Math.round(r.height*dpr));
    if(canvas.width!==w||canvas.height!==h){canvas.width=staticCanvas.width=w;canvas.height=staticCanvas.height=h;ctx.setTransform(dpr,0,0,dpr,0,0);staticCtx.setTransform(dpr,0,0,dpr,0,0)}
    renderStatic();drawFrame();
  }
  function drawGrid(c,w,h,waveTop,waveBottom,midiTop){
    c.fillStyle="#070c12";c.fillRect(0,0,w,h);const visible=viewportDuration(),minor=pxPerSec>=1800?.01:pxPerSec>=700?.05:pxPerSec>=250?.1:.5,major=pxPerSec>=120?1:5,first=Math.floor(viewStart/minor)*minor;
    for(let t=first;t<=viewStart+visible+minor;t+=minor){const x=timeToX(t),isMajor=Math.abs(t/major-Math.round(t/major))<1e-5;c.beginPath();c.moveTo(x,24);c.lineTo(x,h);c.strokeStyle=isMajor?"rgba(170,198,224,.18)":"rgba(170,198,224,.05)";c.lineWidth=1;c.stroke();if(isMajor){c.fillStyle="#7d90a5";c.font="10px ui-monospace,monospace";c.fillText(fmtTime(t).slice(0,8),x+5,16)}}
    c.strokeStyle="rgba(255,255,255,.10)";c.beginPath();c.moveTo(0,waveBottom);c.lineTo(w,waveBottom);c.stroke();
  }
  function drawWave(c,w,waveTop,waveBottom){
    if(!stemBuffer)return;const a=stemBuffer.getChannelData(0),b=stemBuffer.numberOfChannels>1?stemBuffer.getChannelData(1):a,sr=stemBuffer.sampleRate,mid=(waveTop+waveBottom)/2,amp=(waveBottom-waveTop)*.43;
    c.save();c.beginPath();c.rect(0,waveTop,w,waveBottom-waveTop);c.clip();c.strokeStyle="#63d7ff";c.lineWidth=1;c.globalAlpha=.92;c.beginPath();
    for(let x=0;x<w;x++){const audioT=xToTime(x)+offsetMs/1000;if(audioT<0||audioT>=stemBuffer.duration)continue;const center=Math.floor(audioT*sr),span=Math.max(1,Math.floor(sr/pxPerSec)),step=Math.max(1,Math.floor(span/48));let lo=1,hi=-1,start=Math.max(0,center-(span>>1)),end=Math.min(a.length,center+(span>>1));for(let i=start;i<end;i+=step){const v=(a[i]+b[i])*.5;if(v<lo)lo=v;if(v>hi)hi=v}if(hi<lo){lo=hi=0}c.moveTo(x,mid-hi*amp);c.lineTo(x,mid-lo*amp)}c.stroke();c.globalAlpha=1;c.restore();
  }
  function drawMidi(c,w,waveTop,waveBottom,midiTop,h){
    if(!notes.length)return;const laneH=(h-midiTop-8)/laneNames.length;for(let i=0;i<laneNames.length;i++){const y=midiTop+i*laneH;c.fillStyle=i%2?"rgba(255,255,255,.012)":"rgba(255,255,255,.026)";c.fillRect(0,y,w,laneH);c.fillStyle="#78899b";c.font="9px system-ui,sans-serif";c.fillText(laneNames[i],7,y+12)}
    const t0=viewStart-.02,t1=viewStart+viewportDuration()+.02;let lo=0,hi=notes.length;while(lo<hi){const m=(lo+hi)>>1;if(notes[m].time<t0)lo=m+1;else hi=m}
    for(let i=lo;i<notes.length;i++){const n=notes[i];if(n.time>t1)break;const x=timeToX(n.time),cat=category(n.note),y=midiTop+cat*laneH;c.globalAlpha=.22+.60*n.velocity/127;c.strokeStyle=laneColors[cat];c.lineWidth=1;c.beginPath();c.moveTo(x,waveTop);c.lineTo(x,waveBottom);c.stroke();c.globalAlpha=.96;c.fillStyle=laneColors[cat];c.fillRect(x-1,y+14,Math.max(2,pxPerSec*.010),Math.max(4,laneH-18))}c.globalAlpha=1;
  }
  function renderStatic(){
    const r=canvas.getBoundingClientRect(),w=r.width,h=r.height,dpr=Math.min(2,devicePixelRatio||1),waveTop=25,waveBottom=Math.round(h*.54),midiTop=waveBottom+1;staticCtx.setTransform(dpr,0,0,dpr,0,0);staticCtx.clearRect(0,0,w,h);drawGrid(staticCtx,w,h,waveTop,waveBottom,midiTop);drawWave(staticCtx,w,waveTop,waveBottom);drawMidi(staticCtx,w,waveTop,waveBottom,midiTop,h);
  }
  function drawFrame(){
    const r=canvas.getBoundingClientRect(),w=r.width,h=r.height,dpr=Math.min(2,devicePixelRatio||1);ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);ctx.drawImage(staticCanvas,0,0,staticCanvas.width,staticCanvas.height,0,0,w,h);const x=timeToX(nowLogical());if(x>=0&&x<=w){ctx.strokeStyle="#ff6f9d";ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke()}$("#timeText").textContent=`${fmtTime(nowLogical())} / ${fmtTime(duration)}`;
  }

  function stopStem(){if(stemSource){try{stemSource.onended=null;stemSource.stop()}catch{}try{stemSource.disconnect()}catch{}stemSource=null}}
  function stopMidiVoices(){while(openHatVoices.length)openHatVoices.pop();for(const v of [...activeMidiVoices]){activeMidiVoices.delete(v);try{v.source.onended=null;v.source.stop()}catch{}try{v.source.disconnect();v.gain.disconnect()}catch{}}}
  function scheduleStem(logical,when){stopStem();const s=ac.createBufferSource(),g=ac.createGain();s.buffer=stemBuffer;g.gain.value=.62;s.connect(g).connect(ac.destination);stemSource=s;const pos=logical+offsetMs/1000;if(pos>=0)s.start(when,Math.min(pos,stemBuffer.duration-.001));else s.start(when-pos,0);s.onended=()=>{try{s.disconnect();g.disconnect()}catch{}}}
  function chokeOpenHat(when){for(const voice of openHatVoices){try{voice.gain.gain.cancelScheduledValues(when);voice.gain.gain.setValueAtTime(Math.max(.001,voice.level),when);voice.gain.gain.exponentialRampToValueAtTime(.001,when+.025);voice.source.stop(when+.03)}catch{}}openHatVoices.length=0}
  function scheduleDrum(note,when){
    const type=note.type||MIDI_MAP[note.note]||"special";if(type==="hhClosed"||type==="hhPedal")chokeOpenHat(when);const sampleNote=DEFAULT_NOTE[type]||DEFAULT_NOTE.special,region=drumRegions[String(sampleNote)];if(!region)return;
    const source=ac.createBufferSource(),gain=ac.createGain(),mix=DRUM_GAIN[type]||1,sourceVelocity=drumSourceVelocity/127,velocityGain=Math.min(1.25,Math.pow(Math.max(.04,note.velocity/127)/sourceVelocity,.8)),level=.85*velocityGain*mix;source.buffer=drumBuffer;gain.gain.value=level;source.connect(gain).connect(ac.destination);const tracked={source,gain};activeMidiVoices.add(tracked);if(type==="hhOpen")openHatVoices.push({source,gain,level});source.onended=()=>{activeMidiVoices.delete(tracked);const i=openHatVoices.findIndex(v=>v.source===source);if(i>=0)openHatVoices.splice(i,1);try{source.disconnect();gain.disconnect()}catch{}};source.start(when,region.offset,region.duration);
  }
  function firstNoteAt(t){let lo=0,hi=notes.length;while(lo<hi){const m=(lo+hi)>>1;if(notes[m].time<t)lo=m+1;else hi=m}return lo}
  function pumpScheduler(){if(!playing)return;const logicalNow=nowLogical(),horizon=logicalNow+LOOKAHEAD_SEC;while(nextMidi<notes.length&&notes[nextMidi].time<=horizon){const n=notes[nextMidi++];if(n.time<logicalStart-.001)continue;const when=contextStart+(n.time-logicalStart);if(when>=ac.currentTime-.01)scheduleDrum(n,Math.max(ac.currentTime,when))}}
  function beginSchedulers(t){nextMidi=firstNoteAt(t-.001);scheduler=setInterval(pumpScheduler,SCHEDULER_MS);pumpScheduler()}
  function stopSchedulers(){if(scheduler)clearInterval(scheduler);scheduler=0;stopMidiVoices()}
  function startPlayback(){
    if(!stemBuffer||!drumBuffer||!notes.length)return;ensureAC();ac.resume();if(logicalStart>=duration-.01)logicalStart=0;const t=logicalStart,when=ac.currentTime+.08;contextStart=when;playing=true;networkLocked=true;scheduleStem(t,when);beginSchedulers(t);playBtn.textContent="Ⅱ 一時停止";animate();status.textContent="PLAYING · OFFLINE";
  }
  function stopPlayback(keep=true){const t=playing&&keep?nowLogical():logicalStart;playing=false;networkLocked=false;if(raf)cancelAnimationFrame(raf);raf=0;stopStem();stopSchedulers();logicalStart=t;playBtn.textContent="▶ 再生";status.textContent="READY · 再生中は通信なし";drawFrame()}
  function restartSame(){if(!playing)return;const t=nowLogical();stopStem();stopSchedulers();logicalStart=t;contextStart=ac.currentTime+.06;scheduleStem(t,contextStart);beginSchedulers(t)}
  function animate(){if(raf)cancelAnimationFrame(raf);const tick=()=>{raf=0;if(!playing)return;const t=nowLogical();if(t>viewStart+viewportDuration()*.92)setViewStart(clamp(t-viewportDuration()*.18,0,maxViewStart()));drawFrame();if(t>=duration){logicalStart=duration;stopPlayback(false);return}raf=requestAnimationFrame(tick)};raf=requestAnimationFrame(tick)}
  function seek(t){logicalStart=clamp(t,0,duration);if(playing)restartSame();drawFrame()}
  function formatSec(ms){const s=round01(ms)/1000;if(!s)return "0";const a=Math.abs(s).toFixed(4).replace(/^0/,"").replace(/0+$/,"");return `${s<0?"-":""}${a}`}
  function setOffset(v,restart=true){offsetMs=round01(clamp(Number(v)||0,-500,500));offsetInput.value=offsetMs.toFixed(1);offsetReadout.textContent=fmtMs(offsetMs);$("#productionCode").textContent=`playback:{stemOffsetSec:${formatSec(offsetMs)}}`;requestStaticRender();if(restart&&playing)restartSame()}

  playBtn.onclick=()=>playing?stopPlayback(true):startPlayback();
  stopBtn.onclick=()=>{stopPlayback(false);logicalStart=0;drawFrame()};
  $("#back1").onclick=()=>seek(nowLogical()-1);$("#forward1").onclick=()=>seek(nowLogical()+1);
  offsetInput.onchange=()=>setOffset(offsetInput.value);
  document.querySelectorAll("[data-nudge]").forEach(b=>b.onclick=()=>setOffset(offsetMs+Number(b.dataset.nudge)));
  $("#resetOffset").onclick=()=>setOffset(PRODUCTION_OFFSET_MS);
  $("#copyOffset").onclick=()=>navigator.clipboard?.writeText(offsetMs.toFixed(1));$("#copyCode").onclick=()=>navigator.clipboard?.writeText($("#productionCode").textContent);
  zoomInput.oninput=()=>{const center=viewStart+viewportDuration()/2;pxPerSec=Number(zoomInput.value);zoomText.textContent=`${pxPerSec} px/s`;viewStart=clamp(center-viewportDuration()/2,0,maxViewStart());syncScroll();requestStaticRender()};
  scrollInput.oninput=()=>{viewStart=maxViewStart()*Number(scrollInput.value)/1000;requestStaticRender()};
  canvas.addEventListener("wheel",e=>{e.preventDefault();const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,anchor=xToTime(x);if(e.ctrlKey){pxPerSec=clamp(Math.round(pxPerSec*(e.deltaY<0?1.2:.84)/10)*10,80,3000);zoomInput.value=String(pxPerSec);zoomText.textContent=`${pxPerSec} px/s`;viewStart=clamp(anchor-x/pxPerSec,0,maxViewStart());syncScroll();requestStaticRender()}else setViewStart(viewStart+e.deltaY/pxPerSec*1.5)},{passive:false});
  canvas.addEventListener("pointerdown",e=>{const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top,waveBottom=Math.round(r.height*.54);if(y>=25&&y<=waveBottom){drag={id:e.pointerId,startX:x,startOffset:offsetMs,moved:false};canvas.setPointerCapture(e.pointerId);canvas.style.cursor="ew-resize"}else seek(xToTime(x))});
  canvas.addEventListener("pointermove",e=>{if(!drag||drag.id!==e.pointerId)return;const x=e.clientX-canvas.getBoundingClientRect().left,dx=x-drag.startX;if(Math.abs(dx)>1)drag.moved=true;setOffset(drag.startOffset-dx/pxPerSec*1000,false)});
  const endDrag=e=>{if(!drag||drag.id!==e.pointerId)return;const d=drag;drag=null;canvas.style.cursor="crosshair";try{canvas.releasePointerCapture(e.pointerId)}catch{}if(playing)restartSame();if(!d.moved)seek(xToTime(e.clientX-canvas.getBoundingClientRect().left))};canvas.addEventListener("pointerup",endDrag);canvas.addEventListener("pointercancel",endDrag);

  async function load(){
    try{
      ensureAC();playBtn.disabled=true;stopBtn.disabled=true;
      status.textContent="Rayドラムstem / MIDIを読み込み中…";
      const [stemRes,midiAB]=await Promise.all([nativeFetch(STEM_URL,{cache:"force-cache"}),loadGzipMidi(MIDI_GZIP_URL)]);if(!stemRes.ok)throw Error(`ドラムstem HTTP ${stemRes.status}`);
      const stemAB=await stemRes.arrayBuffer();status.textContent="音源をデコード中…";stemBuffer=await ac.decodeAudioData(stemAB.slice(0));const parsed=parseMidi(midiAB);notes=parsed.notes;tempos=parsed.tempos;if(!notes.length)throw Error("Ray MIDIにドラムノートがありません");
      status.textContent="ゲーム内ドラム音源を準備中…";await loadDrumKit();duration=Math.max(stemBuffer.duration,notes.at(-1).time);
      $("#noteCount").textContent=notes.length.toLocaleString();$("#tempoInfo").textContent=[...new Set(tempos.map(t=>(60e6/t.us).toFixed(3).replace(/\.0+$/,"")).filter(Boolean))].join(" / ")+" BPM";$("#lastNote").textContent=fmtTime(notes.at(-1).time);$("#audioDuration").textContent=fmtTime(stemBuffer.duration);$("#sampleRate").textContent=`${stemBuffer.sampleRate.toLocaleString()} Hz`;
      playBtn.disabled=stopBtn.disabled=$("#back1").disabled=$("#forward1").disabled=false;status.textContent="READY · 再生中は通信なし";setOffset(PRODUCTION_OFFSET_MS,false);resize();
    }catch(e){console.error(e);status.textContent=`ERROR: ${e.message||e}`}
  }
  addEventListener("resize",resize);addEventListener("pagehide",()=>{stopPlayback(false);try{ac?.close()}catch{}},{once:true});load();
})();
