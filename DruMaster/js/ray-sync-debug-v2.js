"use strict";

(()=>{
  const AUDIO_URL="songs/ray/drums.mp3";
  const MIDI_URL="songs/ray/chart.mid?v=20260826-midi2";
  const PRODUCTION_OFFSET_MS=21.5;
  const $=s=>document.querySelector(s);
  const canvas=$("#timeline"),ctx=canvas.getContext("2d"),status=$("#status"),playBtn=$("#play"),stopBtn=$("#stop"),offsetInput=$("#offset"),offsetReadout=$("#offsetReadout"),zoomInput=$("#zoom"),zoomText=$("#zoomText"),scrollInput=$("#scroll"),midiClick=$("#midiClick");
  let ac=null,audioBuffer=null,notes=[],tempos=[],duration=0,offsetMs=PRODUCTION_OFFSET_MS,pxPerSec=260,viewStart=0;
  let source=null,playing=false,logicalStart=0,contextStart=0,raf=0,clickTimer=0,nextClick=0,drag=null;
  const activeClicks=new Set();
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const round01=v=>Math.round(v*10)/10;
  const fmtMs=v=>`${v>=0?"+":""}${v.toFixed(1)} ms`;
  const fmtTime=t=>{t=Math.max(0,t||0);const m=Math.floor(t/60),s=Math.floor(t%60),ms=Math.floor((t-Math.floor(t))*1000);return `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}.${String(ms).padStart(3,"0")}`};
  const nowLogical=()=>playing?clamp(logicalStart+(ac.currentTime-contextStart),0,duration):logicalStart;

  function ensureAC(){if(!ac)ac=new (window.AudioContext||window.webkitAudioContext)({latencyHint:"interactive"});return ac}

  function parseMidi(ab){
    const d=new DataView(ab);let p=0;
    const str=n=>{let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s};
    const u32=()=>{const v=d.getUint32(p);p+=4;return v};
    const u16=()=>{const v=d.getUint16(p);p+=2;return v};
    const vlq=()=>{let v=0,b,count=0;do{if(p>=d.byteLength)throw Error("MIDIの可変長値が不正です");b=d.getUint8(p++);v=(v<<7)|(b&127);if(++count>4)throw Error("MIDIの可変長値が不正です")}while(b&128);return v};
    if(d.byteLength<14||str(4)!=="MThd")throw Error("MIDIヘッダーが不正です");
    const headerLength=u32();u16();const tracks=u16(),division=u16();
    if(division&0x8000)throw Error("SMPTE形式のMIDIには未対応です");
    p+=headerLength-6;
    const raw=[],tempoRaw=[{tick:0,us:500000}];
    for(let tr=0;tr<tracks;tr++){
      if(p+8>d.byteLength||str(4)!=="MTrk")throw Error(`MIDIトラック${tr+1}が不正です`);
      const len=u32(),end=Math.min(d.byteLength,p+len);let tick=0,runningStatus=0;
      while(p<end){
        tick+=vlq();
        if(p>=end)break;
        const next=d.getUint8(p++);let statusByte;
        if(next<128){if(!runningStatus)throw Error("MIDIランニングステータスが不正です");statusByte=runningStatus;p--}
        else{statusByte=next;if(statusByte<240)runningStatus=statusByte}
        if(statusByte===255){
          if(p>=end)break;const type=d.getUint8(p++),n=vlq();
          if(type===81&&n===3&&p+3<=end)tempoRaw.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});
          p=Math.min(end,p+n);continue;
        }
        if(statusByte===240||statusByte===247){runningStatus=0;const n=vlq();p=Math.min(end,p+n);continue}
        const hi=statusByte&240,ch=statusByte&15;
        if(hi===144||hi===128){
          if(p+2>end)break;const note=d.getUint8(p++),velocity=d.getUint8(p++);
          if(hi===144&&velocity>0&&ch===9)raw.push({tick,note,velocity});
        }else if(hi===192||hi===208){if(p+1>end)break;p+=1}
        else{if(p+2>end)break;p+=2}
      }
      p=end;
    }
    tempoRaw.sort((a,b)=>a.tick-b.tick);
    const dedup=[];for(const t of tempoRaw){if(dedup.length&&dedup.at(-1).tick===t.tick)dedup[dedup.length-1]=t;else dedup.push(t)}
    const tickToSec=tick=>{let sec=0,last=0,us=500000;for(const e of dedup){if(e.tick>=tick)break;sec+=(e.tick-last)*us/division/1e6;last=e.tick;us=e.us}return sec+(tick-last)*us/division/1e6};
    return {notes:raw.map(n=>({...n,time:tickToSec(n.tick)})).sort((a,b)=>a.time-b.time),tempos:dedup};
  }

  function category(note){if(note===35||note===36)return 0;if(note===38||note===40||note===37)return 1;if(note===42||note===44||note===46)return 2;if([41,43,45,47,48,50].includes(note))return 3;if([49,51,52,55,57,59].includes(note))return 4;return 5}
  const laneNames=["KICK","SNARE","HI-HAT","TOMS","CYMBAL","OTHER"];
  const laneColors=["#66c9ff","#ff8db3","#f3d36c","#b28cff","#73e3cf","#96a5b6"];

  function viewportWidth(){return canvas.getBoundingClientRect().width}
  function viewportDuration(){return viewportWidth()/pxPerSec}
  function maxViewStart(){return Math.max(0,duration-viewportDuration())}
  function syncScroll(){scrollInput.value=maxViewStart()>0?String(Math.round(viewStart/maxViewStart()*1000)):"0"}
  function setViewStart(v){viewStart=clamp(v,0,maxViewStart());syncScroll();draw()}
  function xToTime(x){return viewStart+x/pxPerSec}
  function timeToX(t){return (t-viewStart)*pxPerSec}

  function resize(){const r=canvas.getBoundingClientRect(),dpr=Math.min(2,devicePixelRatio||1);canvas.width=Math.max(1,Math.round(r.width*dpr));canvas.height=Math.max(1,Math.round(r.height*dpr));ctx.setTransform(dpr,0,0,dpr,0,0);draw()}

  function drawGrid(w,h,waveTop,waveBottom,midiTop){
    ctx.fillStyle="#070c12";ctx.fillRect(0,0,w,h);
    const visible=viewportDuration(),minor=pxPerSec>=1800?.01:pxPerSec>=700?.05:pxPerSec>=250?.1:.5,major=pxPerSec>=120?1:5;
    const first=Math.floor(viewStart/minor)*minor;
    for(let t=first;t<=viewStart+visible+minor;t+=minor){const x=timeToX(t),isMajor=Math.abs(t/major-Math.round(t/major))<1e-5;ctx.beginPath();ctx.moveTo(x,24);ctx.lineTo(x,h);ctx.strokeStyle=isMajor?"rgba(170,198,224,.18)":"rgba(170,198,224,.05)";ctx.lineWidth=1;ctx.stroke();if(isMajor){ctx.fillStyle="#7d90a5";ctx.font="10px ui-monospace,monospace";ctx.fillText(fmtTime(t).slice(0,8),x+5,16)}}
    ctx.strokeStyle="rgba(255,255,255,.10)";ctx.beginPath();ctx.moveTo(0,waveTop);ctx.lineTo(w,waveTop);ctx.moveTo(0,waveBottom);ctx.lineTo(w,waveBottom);ctx.moveTo(0,midiTop);ctx.lineTo(w,midiTop);ctx.stroke();
  }

  function drawWave(w,waveTop,waveBottom){
    if(!audioBuffer)return;const a=audioBuffer.getChannelData(0),b=audioBuffer.numberOfChannels>1?audioBuffer.getChannelData(1):a,sr=audioBuffer.sampleRate,mid=(waveTop+waveBottom)/2,amp=(waveBottom-waveTop)*.43;
    ctx.save();ctx.beginPath();ctx.rect(0,waveTop,w,waveBottom-waveTop);ctx.clip();ctx.strokeStyle="#63d7ff";ctx.lineWidth=1;ctx.globalAlpha=.92;ctx.beginPath();
    for(let x=0;x<w;x++){const audioT=xToTime(x)+offsetMs/1000;if(audioT<0||audioT>=audioBuffer.duration)continue;const center=Math.floor(audioT*sr),span=Math.max(1,Math.floor(sr/pxPerSec)),step=Math.max(1,Math.floor(span/48));let lo=1,hi=-1;for(let i=Math.max(0,center-span>>1),end=Math.min(a.length,center+(span>>1));i<end;i+=step){const v=(a[i]+b[i])*.5;if(v<lo)lo=v;if(v>hi)hi=v}if(hi<lo){lo=hi=0}ctx.moveTo(x,mid-hi*amp);ctx.lineTo(x,mid-lo*amp)}ctx.stroke();ctx.globalAlpha=1;ctx.restore();
  }

  function drawMidi(w,waveTop,waveBottom,midiTop,h){
    if(!notes.length)return;const laneH=(h-midiTop-8)/laneNames.length;for(let i=0;i<laneNames.length;i++){const y=midiTop+i*laneH;ctx.fillStyle=i%2?"rgba(255,255,255,.012)":"rgba(255,255,255,.026)";ctx.fillRect(0,y,w,laneH);ctx.fillStyle="#78899b";ctx.font="9px system-ui,sans-serif";ctx.fillText(laneNames[i],7,y+12)}
    const t0=viewStart-.02,t1=viewStart+viewportDuration()+.02;let lo=0,hi=notes.length;while(lo<hi){const m=(lo+hi)>>1;if(notes[m].time<t0)lo=m+1;else hi=m}
    for(let i=lo;i<notes.length;i++){const n=notes[i];if(n.time>t1)break;const x=timeToX(n.time),cat=category(n.note),y=midiTop+cat*laneH;ctx.globalAlpha=.22+.60*n.velocity/127;ctx.strokeStyle=laneColors[cat];ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x,waveTop);ctx.lineTo(x,waveBottom);ctx.stroke();ctx.globalAlpha=.96;ctx.fillStyle=laneColors[cat];ctx.fillRect(x-1,y+14,Math.max(2,pxPerSec*.010),Math.max(4,laneH-18))}ctx.globalAlpha=1;
  }

  function draw(){const r=canvas.getBoundingClientRect(),w=r.width,h=r.height,waveTop=25,waveBottom=Math.round(h*.57),midiTop=waveBottom+1;ctx.clearRect(0,0,w,h);drawGrid(w,h,waveTop,waveBottom,midiTop);drawWave(w,waveTop,waveBottom);drawMidi(w,waveTop,waveBottom,midiTop,h);const x=timeToX(nowLogical());if(x>=0&&x<=w){ctx.strokeStyle="#ff6f9d";ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke()}$("#timeText").textContent=`${fmtTime(nowLogical())} / ${fmtTime(duration)}`}

  function stopSource(){if(source){try{source.onended=null;source.stop()}catch{}try{source.disconnect()}catch{}source=null}}
  function stopClicks(){for(const o of activeClicks){try{o.stop()}catch{}try{o.disconnect()}catch{}}activeClicks.clear();if(clickTimer)clearInterval(clickTimer);clickTimer=0}
  function stopPlayback(keep=true){if(playing&&keep)logicalStart=nowLogical();playing=false;stopSource();stopClicks();playBtn.textContent="▶ 再生";draw()}
  function scheduleAudio(logical,when){stopSource();const s=ac.createBufferSource();s.buffer=audioBuffer;s.connect(ac.destination);source=s;const pos=logical+offsetMs/1000;if(pos>=0)s.start(when,Math.min(pos,audioBuffer.duration-.001));else s.start(when-pos,0)}
  function firstNoteAt(t){let lo=0,hi=notes.length;while(lo<hi){const m=(lo+hi)>>1;if(notes[m].time<t)lo=m+1;else hi=m}return lo}
  function clickFreq(n){return [72,210,900,330,680,500][category(n)]}
  function scheduleClicks(){if(!playing||!midiClick.checked)return;const t=nowLogical(),h=t+.14;while(nextClick<notes.length&&notes[nextClick].time<h){const n=notes[nextClick++];if(n.time<t-.02)continue;const when=ac.currentTime+(n.time-t),o=ac.createOscillator(),g=ac.createGain();o.type=category(n.note)===0?"sine":"square";o.frequency.value=clickFreq(n.note);g.gain.setValueAtTime(.0001,when);g.gain.linearRampToValueAtTime(.05*n.velocity/127,when+.001);g.gain.exponentialRampToValueAtTime(.0001,when+.025);o.connect(g).connect(ac.destination);o.start(when);o.stop(when+.03);activeClicks.add(o);o.onended=()=>{activeClicks.delete(o);try{o.disconnect();g.disconnect()}catch{}}}}
  function startPlayback(){if(!audioBuffer)return;ensureAC();ac.resume();if(logicalStart>=duration-.01)logicalStart=0;const t=logicalStart,when=ac.currentTime+.04;contextStart=when;playing=true;scheduleAudio(t,when);nextClick=firstNoteAt(t-.01);stopClicks();clickTimer=setInterval(scheduleClicks,35);scheduleClicks();playBtn.textContent="Ⅱ 一時停止";animate()}
  function restartSame(){if(!playing)return;const t=nowLogical();stopSource();stopClicks();logicalStart=t;contextStart=ac.currentTime+.03;scheduleAudio(t,contextStart);nextClick=firstNoteAt(t-.01);clickTimer=setInterval(scheduleClicks,35);scheduleClicks()}
  function animate(){if(raf)cancelAnimationFrame(raf);const tick=()=>{raf=0;if(!playing)return;const t=nowLogical();if(t<viewStart||t>viewStart+viewportDuration())setViewStart(clamp(t-viewportDuration()*.22,0,maxViewStart()));draw();if(t>=duration){logicalStart=duration;stopPlayback(false);return}raf=requestAnimationFrame(tick)};raf=requestAnimationFrame(tick)}
  function seek(t){logicalStart=clamp(t,0,duration);if(playing)restartSame();draw()}
  function formatSec(ms){const s=round01(ms)/1000;if(!s)return "0";const a=Math.abs(s).toFixed(4).replace(/^0/,"").replace(/0+$/,"");return `${s<0?"-":""}${a}`}
  function setOffset(v,restart=true){offsetMs=round01(clamp(Number(v)||0,-500,500));offsetInput.value=offsetMs.toFixed(1);offsetReadout.textContent=fmtMs(offsetMs);$("#productionCode").textContent=`playback:{stemOffsetSec:${formatSec(offsetMs)}}`;draw();if(restart&&playing)restartSame()}

  playBtn.onclick=()=>playing?stopPlayback(true):startPlayback();stopBtn.onclick=()=>{stopPlayback(false);logicalStart=0;draw()};$("#back1").onclick=()=>seek(nowLogical()-1);$("#forward1").onclick=()=>seek(nowLogical()+1);
  offsetInput.onchange=()=>setOffset(offsetInput.value);document.querySelectorAll("[data-nudge]").forEach(b=>b.onclick=()=>setOffset(offsetMs+Number(b.dataset.nudge)));$("#resetOffset").onclick=()=>setOffset(PRODUCTION_OFFSET_MS);$("#copyOffset").onclick=()=>navigator.clipboard?.writeText(offsetMs.toFixed(1));$("#copyCode").onclick=()=>navigator.clipboard?.writeText($("#productionCode").textContent);
  zoomInput.oninput=()=>{const center=viewStart+viewportDuration()/2;pxPerSec=Number(zoomInput.value);zoomText.textContent=`${pxPerSec} px/s`;viewStart=clamp(center-viewportDuration()/2,0,maxViewStart());syncScroll();draw()};scrollInput.oninput=()=>{viewStart=maxViewStart()*Number(scrollInput.value)/1000;draw()};
  canvas.addEventListener("wheel",e=>{e.preventDefault();const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,anchor=xToTime(x);if(e.ctrlKey){pxPerSec=clamp(Math.round(pxPerSec*(e.deltaY<0?1.2:.84)/10)*10,80,3000);zoomInput.value=String(pxPerSec);zoomText.textContent=`${pxPerSec} px/s`;viewStart=clamp(anchor-x/pxPerSec,0,maxViewStart());syncScroll();draw()}else setViewStart(viewStart+e.deltaY/pxPerSec*1.5)},{passive:false});
  canvas.addEventListener("pointerdown",e=>{const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top,waveBottom=Math.round(r.height*.57);if(y>=25&&y<=waveBottom){drag={id:e.pointerId,startX:x,startOffset:offsetMs,moved:false};canvas.setPointerCapture(e.pointerId);canvas.style.cursor="ew-resize"}else seek(xToTime(x))});
  canvas.addEventListener("pointermove",e=>{if(!drag||drag.id!==e.pointerId)return;const x=e.clientX-canvas.getBoundingClientRect().left,dx=x-drag.startX;if(Math.abs(dx)>1)drag.moved=true;setOffset(drag.startOffset-dx/pxPerSec*1000,false)});
  const endDrag=e=>{if(!drag||drag.id!==e.pointerId)return;const d=drag;drag=null;canvas.style.cursor="crosshair";try{canvas.releasePointerCapture(e.pointerId)}catch{}if(playing)restartSame();if(!d.moved)seek(xToTime(e.clientX-canvas.getBoundingClientRect().left))};canvas.addEventListener("pointerup",endDrag);canvas.addEventListener("pointercancel",endDrag);

  async function load(){try{ensureAC();status.textContent="Rayドラム音源を読み込み中…";const [ar,mr]=await Promise.all([fetch(AUDIO_URL,{cache:"force-cache"}),fetch(MIDI_URL,{cache:"no-store"})]);if(!ar.ok)throw Error(`ドラム音源 HTTP ${ar.status}`);if(!mr.ok)throw Error(`MIDI HTTP ${mr.status}`);const [ab,mb]=await Promise.all([ar.arrayBuffer(),mr.arrayBuffer()]);status.textContent="解析中…";audioBuffer=await ac.decodeAudioData(ab.slice(0));const parsed=parseMidi(mb);notes=parsed.notes;tempos=parsed.tempos;if(!notes.length)throw Error("ドラムノートが見つかりません");duration=Math.max(audioBuffer.duration,notes.at(-1).time);$("#noteCount").textContent=notes.length.toLocaleString();$("#tempoInfo").textContent=[...new Set(tempos.map(t=>(60e6/t.us).toFixed(3).replace(/\.0+$/,"")))].join(" / ")+" BPM";$("#lastNote").textContent=fmtTime(notes.at(-1).time);$("#audioDuration").textContent=fmtTime(audioBuffer.duration);$("#sampleRate").textContent=`${audioBuffer.sampleRate.toLocaleString()} Hz`;playBtn.disabled=stopBtn.disabled=$("#back1").disabled=$("#forward1").disabled=false;status.textContent="READY";setOffset(PRODUCTION_OFFSET_MS,false);resize()}catch(e){console.error(e);status.textContent=`ERROR: ${e.message||e}`}}
  addEventListener("resize",resize);addEventListener("pagehide",()=>{stopPlayback(false);try{ac?.close()}catch{}},{once:true});load();
})();
