"use strict";

(()=>{
  const canvas=document.getElementById("canvas");
  if(!canvas)return;
  const timeline=canvas.closest(".timeline");
  if(!timeline)return;

  const REPO="ld1kanae/ld1kanae.github.io",ROOT="DruMaster/songs",BRANCH="main",RAW="https://raw.githubusercontent.com/ld1kanae/ld1kanae.github.io/main/DruMaster/";
  const $=id=>document.getElementById(id),params=new URLSearchParams(location.search),songId=params.get("song");
  const style=document.createElement("style");
  style.id="dmRayTimelineStyle";
  style.textContent=`
    .timeline{height:min(44vh,430px)!important;min-height:320px!important;border:1px solid #283747!important;border-radius:12px!important;background:#090f17!important;overflow:hidden!important;display:grid!important;grid-template-rows:38px minmax(0,1fr) 52px!important}
    .timeline-head{display:flex!important;align-items:center!important;justify-content:space-between!important;padding:0 12px!important;border-bottom:1px solid #243141!important;background:#0f1721!important;color:#aab9c9!important;min-height:0!important}
    .timeline-head>div:first-child{display:flex!important;align-items:baseline!important;gap:10px!important}.timeline-head br,.timeline-head small{display:none!important}.timeline-head b{font-size:10px!important;letter-spacing:.11em!important}
    .legend{display:flex!important;gap:11px!important;font-size:8px!important}.legend span{position:relative!important;padding-left:12px!important}.legend i{position:absolute!important;left:0!important;top:50%!important;width:8px!important;height:2px!important;margin:0!important;border-radius:0!important;transform:translateY(-50%)!important}
    .legend .wave i{background:#64d7ff!important}.legend .midi i{background:linear-gradient(90deg,#ffd45a,#52dfcf,#ff3d73,#8875ff,#aeb9c7)!important}.legend .play i{background:#ff6e9b!important}
    .dm-ray-canvas-wrap{position:relative!important;min-height:0!important;width:100%!important;height:100%!important;background:#070c12!important;overflow:hidden!important}.dm-ray-canvas-wrap>#canvas{position:absolute!important;inset:0!important;width:100%!important;height:100%!important;opacity:0!important;z-index:1!important;cursor:crosshair!important;touch-action:none!important}.dm-ray-overlay{position:absolute!important;inset:0!important;width:100%!important;height:100%!important;z-index:2!important;pointer-events:none!important;background:#070c12!important}
    .timeline .view{display:grid!important;grid-template-columns:1fr 1fr!important;gap:16px!important;padding:7px 12px!important;border-top:1px solid #1f2a37!important;background:#0c131c!important;min-height:0!important}.timeline .view label{display:grid!important;grid-template-columns:54px 1fr 72px!important;align-items:center!important;gap:6px!important;color:#a9b6c4!important;font-size:9px!important}.timeline .view input[type=range]{width:100%!important;accent-color:#4fc5ff!important}.timeline .view output{min-width:58px!important;text-align:right!important;font:700 9px/1 ui-monospace,monospace!important;color:#9aabba!important}
    @media(max-width:850px){.timeline{height:400px!important}.timeline .view{grid-template-columns:1fr!important;gap:3px!important;padding:5px 10px!important}.timeline{grid-template-rows:38px minmax(0,1fr) 68px!important}}
  `;
  document.head.appendChild(style);

  const wrap=document.createElement("div");wrap.className="dm-ray-canvas-wrap";
  canvas.parentNode.insertBefore(wrap,canvas);wrap.appendChild(canvas);
  const overlay=document.createElement("canvas");overlay.className="dm-ray-overlay";overlay.setAttribute("aria-hidden","true");wrap.appendChild(overlay);
  const ctx=overlay.getContext("2d"),staticCanvas=document.createElement("canvas"),sctx=staticCanvas.getContext("2d");

  let draft=null,notes=[],measureSec=2,audioBuffer=null,currentSource="",loadingSource="",raf=0,lastSignature="",lastW=0,lastH=0;
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  function decodeContent(s){const bin=atob(String(s||"").replace(/\n/g,"")),u=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);return new TextDecoder().decode(u)}
  async function apiGet(path){const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}`,{headers:{Accept:"application/vnd.github+json"},cache:"no-store"});if(!r.ok)throw Error(`GitHub API ${r.status}: ${path}`);return r.json()}
  async function fetchRaw(path){const r=await fetch(`${RAW}${path}?t=${Date.now()}`,{cache:"no-store"});if(!r.ok)throw Error(`Asset HTTP ${r.status}: ${path}`);return r.arrayBuffer()}
  function fmtTime(t){t=Math.max(0,Number(t)||0);const m=Math.floor(t/60),s=Math.floor(t%60),ms=Math.floor((t-Math.floor(t))*1000);return `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}.${String(ms).padStart(3,"0")}`}
  function parseClock(text){const m=String(text||"").match(/(\d+):(\d+)\.(\d+)/);if(!m)return 0;return Number(m[1])*60+Number(m[2])+Number(`0.${m[3]}`)}
  function parseMidi(ab){
    const d=new DataView(ab);let p=0;const need=(n,end=d.byteLength)=>{if(p+n>end)throw Error("MIDIが途中で切れています")},str=n=>{need(n);let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s},u32=()=>{need(4);const v=d.getUint32(p);p+=4;return v},u16=()=>{need(2);const v=d.getUint16(p);p+=2;return v},vlq=end=>{let v=0,b,c=0;do{need(1,end);b=d.getUint8(p++);v=(v<<7)|(b&127);if(++c>4)throw Error("MIDI VLQ error")}while(b&128);return v};
    if(str(4)!=="MThd")throw Error("MIDIヘッダーが不正です");const hl=u32();u16();const tracks=u16(),division=u16();if(division&0x8000)throw Error("SMPTE MIDIには未対応です");p=8+hl;const raw=[],tempoRaw=[{tick:0,us:500000}],sigs=[];
    for(let tr=0;tr<tracks;tr++){need(8);if(str(4)!=="MTrk")throw Error("MIDIトラックが不正です");const len=u32(),end=p+len;let tick=0,run=0;while(p<end){tick+=vlq(end);need(1,end);let first=d.getUint8(p++),status;if(first<128){if(!run)throw Error("MIDI running status error");status=run;p--}else{status=first;if(status<240)run=status}if(status===255){need(1,end);const type=d.getUint8(p++),n=vlq(end);need(n,end);if(type===81&&n===3)tempoRaw.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});if(type===88&&n>=2)sigs.push({tick,numerator:d.getUint8(p),denominator:2**d.getUint8(p+1)});p+=n;continue}if(status===240||status===247){run=0;const n=vlq(end);need(n,end);p+=n;continue}const hi=status&240,ch=status&15,bytes=(hi===192||hi===208)?1:2;need(bytes,end);const a=d.getUint8(p++),b=bytes===2?d.getUint8(p++):0;if(hi===144&&b>0&&ch===9)raw.push({tick,note:a,velocity:b})}p=end}
    tempoRaw.sort((a,b)=>a.tick-b.tick);const ded=[];for(const x of tempoRaw){if(ded.length&&ded.at(-1).tick===x.tick)ded[ded.length-1]=x;else ded.push(x)}const seg=[];let lt=0,ls=0,us=500000;for(const e of ded){ls+=(e.tick-lt)*us/division/1e6;lt=e.tick;us=e.us;if(e.tick===0&&seg.length===0)seg.push({tick:0,sec:0,us});else if(e.tick>0)seg.push({tick:e.tick,sec:ls,us})}if(!seg.length)seg.push({tick:0,sec:0,us:500000});const tickToSec=t=>{let e=seg[0];for(let i=1;i<seg.length&&seg[i].tick<=t;i++)e=seg[i];return e.sec+(t-e.tick)*e.us/division/1e6};sigs.sort((a,b)=>a.tick-b.tick);const sig=sigs.find(x=>x.tick===0)||sigs[0]||{numerator:4,denominator:4},measureTicks=division*sig.numerator*4/sig.denominator;return {measureSec:tickToSec(measureTicks)-tickToSec(0),notes:raw.map(n=>({...n,time:tickToSec(n.tick)})).sort((a,b)=>a.time-b.time)};
  }

  const laneNames=["CYMBAL","HI-HAT","SNARE","TOMS","KICK","OTHER"];
  function laneForNote(note){if([49,52,55,57].includes(note))return 0;if([42,44,46,51,53,59].includes(note))return 1;if(note===38||note===40)return 2;if([41,43,45,47,48,50].includes(note))return 3;if(note===35||note===36)return 4;return 5}
  function noteColor(note){
    if(note===38||note===40)return "#ff3d73";
    if(note===48||note===50)return "#d76bff";
    if(note===45||note===47)return "#8875ff";
    if(note===41||note===43)return "#329cff";
    if([49,52,55,57].includes(note))return "#ffd45a";
    if([42,44,46,51,53,59].includes(note))return "#52dfcf";
    if(note===35||note===36)return "#aeb9c7";
    return "#a7b0bc";
  }
  function pxPerSec(){return Number($("zoom")?.value)||260}
  function viewportDuration(){return Math.max(.001,overlay.clientWidth/pxPerSec())}
  function maxView(){return Math.max(0,(Number(draft?.duration)||0)-viewportDuration())}
  function viewStart(){return maxView()*(Number($("scroll")?.value)||0)/1000}
  function audioOffsetMs(){return Number($("audioOffset")?.value)||0}
  function midiMeasureOffset(){const m=String($("midiRead")?.textContent||"").match(/([+-]?\d+)/);return m?Number(m[1]):0}
  function midiOffsetSec(){return midiMeasureOffset()*measureSec}
  function timeToX(t){return (t-viewStart())*pxPerSec()}
  function xToTime(x){return viewStart()+x/pxPerSec()}

  async function loadSource(key){
    if(!draft?.stems?.[key]||loadingSource===key)return;
    loadingSource=key;
    try{const ab=await fetchRaw(draft.stems[key].path),ac=new (window.AudioContext||window.webkitAudioContext)();audioBuffer=await ac.decodeAudioData(ab.slice(0));try{await ac.close()}catch{}currentSource=key;lastSignature=""}catch(e){console.warn("Ray timeline waveform load failed",e)}finally{loadingSource=""}
  }
  function ensureSize(){
    const r=wrap.getBoundingClientRect(),dpr=Math.min(2,devicePixelRatio||1),w=Math.max(1,Math.round(r.width*dpr)),h=Math.max(1,Math.round(r.height*dpr));
    if(w===overlay.width&&h===overlay.height)return false;overlay.width=staticCanvas.width=w;overlay.height=staticCanvas.height=h;ctx.setTransform(dpr,0,0,dpr,0,0);sctx.setTransform(dpr,0,0,dpr,0,0);lastW=r.width;lastH=r.height;lastSignature="";return true;
  }
  function drawGrid(c,w,h,waveTop,waveBottom){
    c.fillStyle="#070c12";c.fillRect(0,0,w,h);const visible=viewportDuration(),pps=pxPerSec(),minor=pps>=1800?.01:pps>=700?.05:pps>=250?.1:.5,major=pps>=120?1:5,first=Math.floor(viewStart()/minor)*minor;
    for(let t=first;t<=viewStart()+visible+minor;t+=minor){const x=timeToX(t),isMajor=Math.abs(t/major-Math.round(t/major))<1e-5;c.beginPath();c.moveTo(x,24);c.lineTo(x,h);c.strokeStyle=isMajor?"rgba(170,198,224,.18)":"rgba(170,198,224,.05)";c.lineWidth=1;c.stroke();if(isMajor){c.fillStyle="#7d90a5";c.font="10px ui-monospace,monospace";c.fillText(fmtTime(t).slice(0,8),x+5,16)}}
    c.strokeStyle="rgba(255,255,255,.10)";c.beginPath();c.moveTo(0,waveBottom);c.lineTo(w,waveBottom);c.stroke();
  }
  function drawWave(c,w,waveTop,waveBottom){
    if(!audioBuffer)return;const a=audioBuffer.getChannelData(0),b=audioBuffer.numberOfChannels>1?audioBuffer.getChannelData(1):a,sr=audioBuffer.sampleRate,mid=(waveTop+waveBottom)/2,amp=(waveBottom-waveTop)*.43,pps=pxPerSec();c.save();c.beginPath();c.rect(0,waveTop,w,waveBottom-waveTop);c.clip();c.strokeStyle="#63d7ff";c.lineWidth=1;c.globalAlpha=.92;c.beginPath();
    for(let x=0;x<w;x++){const audioT=xToTime(x)+audioOffsetMs()/1000;if(audioT<0||audioT>=audioBuffer.duration)continue;const center=Math.floor(audioT*sr),span=Math.max(1,Math.floor(sr/pps)),step=Math.max(1,Math.floor(span/48));let lo=1,hi=-1,start=Math.max(0,center-(span>>1)),end=Math.min(a.length,center+(span>>1));for(let i=start;i<end;i+=step){const v=(a[i]+b[i])*.5;if(v<lo)lo=v;if(v>hi)hi=v}if(hi<lo){lo=hi=0}c.moveTo(x,mid-hi*amp);c.lineTo(x,mid-lo*amp)}c.stroke();c.globalAlpha=1;c.restore();
  }
  function drawMidi(c,w,waveTop,waveBottom,midiTop,h){
    const laneH=(h-midiTop-8)/laneNames.length;for(let i=0;i<laneNames.length;i++){const y=midiTop+i*laneH;c.fillStyle=i%2?"rgba(255,255,255,.012)":"rgba(255,255,255,.026)";c.fillRect(0,y,w,laneH);c.fillStyle="#78899b";c.font="9px system-ui,sans-serif";c.fillText(laneNames[i],7,y+12)}
    if(!notes.length)return;const off=midiOffsetSec(),t0=viewStart()-off-.02,t1=viewStart()+viewportDuration()-off+.02;let lo=0,hi=notes.length;while(lo<hi){const m=(lo+hi)>>1;if(notes[m].time<t0)lo=m+1;else hi=m}
    for(let i=lo;i<notes.length;i++){const n=notes[i],t=n.time+off;if(t>viewStart()+viewportDuration()+.02)break;const x=timeToX(t);if(x<-3||x>w+3)continue;const lane=laneForNote(n.note),y=midiTop+lane*laneH,color=noteColor(n.note);c.globalAlpha=.22+.60*n.velocity/127;c.strokeStyle=color;c.lineWidth=1;c.beginPath();c.moveTo(x,waveTop);c.lineTo(x,waveBottom);c.stroke();c.globalAlpha=.96;c.fillStyle=color;c.fillRect(x-1,y+14,Math.max(2,pxPerSec()*.010),Math.max(4,laneH-18))}c.globalAlpha=1;
  }
  function renderStatic(){
    ensureSize();const w=lastW||wrap.clientWidth,h=lastH||wrap.clientHeight,waveTop=25,waveBottom=Math.round(h*.54),midiTop=waveBottom+1;sctx.clearRect(0,0,w,h);drawGrid(sctx,w,h,waveTop,waveBottom);drawWave(sctx,w,waveTop,waveBottom);drawMidi(sctx,w,waveTop,waveBottom,midiTop,h);
  }
  function drawFrame(){
    const w=lastW||wrap.clientWidth,h=lastH||wrap.clientHeight;ctx.clearRect(0,0,w,h);ctx.drawImage(staticCanvas,0,0,staticCanvas.width,staticCanvas.height,0,0,w,h);const x=timeToX(parseClock($("time")?.textContent));if(x>=0&&x<=w){ctx.strokeStyle="#ff6f9d";ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke()}
  }
  function tick(){
    const source=$("source")?.value||"";if(source&&source!==currentSource&&source!==loadingSource)void loadSource(source);
    const sig=[Math.round(wrap.clientWidth),Math.round(wrap.clientHeight),pxPerSec(),$("scroll")?.value,audioOffsetMs().toFixed(1),midiMeasureOffset(),currentSource,audioBuffer?.duration||0].join("|");
    if(sig!==lastSignature){lastSignature=sig;renderStatic()}else ensureSize()&&renderStatic();drawFrame();raf=requestAnimationFrame(tick);
  }
  async function init(){
    try{if(!songId)throw Error("song IDがありません");const meta=await apiGet(`${ROOT}/${songId}/song-draft.json`);draft=JSON.parse(decodeContent(meta.content));const midiAb=await fetchRaw(draft.midi),parsed=parseMidi(midiAb);notes=parsed.notes;measureSec=parsed.measureSec||2;const source=$("source")?.value||["drums","fullmix","base","vocals"].find(k=>draft.stems?.[k]);if(source)await loadSource(source);renderStatic();drawFrame();raf=requestAnimationFrame(tick)}catch(e){console.warn("Ray timeline layer unavailable",e);canvas.style.opacity="1"}
  }
  addEventListener("beforeunload",()=>cancelAnimationFrame(raf));init();
})();
