"use strict";

(()=>{
  const AUDIO_URL="songs/ray/drums.mp3",MIDI_URL="songs/ray/chart.mid?v=20260826-midi2",PRODUCTION_OFFSET_MS=21.5;
  const $=s=>document.querySelector(s),canvas=$("#timeline"),ctx=canvas.getContext("2d"),status=$("#status"),playBtn=$("#play"),stopBtn=$("#stop"),offsetInput=$("#offset"),offsetReadout=$("#offsetReadout"),zoomInput=$("#zoom"),zoomText=$("#zoomText"),scrollInput=$("#scroll"),midiClick=$("#midiClick");
  let ac=null,audioBuffer=null,midiNotes=[],tempoEvents=[],duration=0,offsetMs=PRODUCTION_OFFSET_MS,pxPerSec=180,viewStart=0;
  let source=null,playing=false,logicalStart=0,contextStart=0,raf=0,clickTimer=0,nextClickIndex=0,activeClicks=new Set();
  let drag=null;

  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const round01=v=>Math.round(v*10)/10;
  const fmtMs=v=>`${v>=0?"+":""}${v.toFixed(1)} ms`;
  const fmtTime=t=>{t=Math.max(0,t||0);const m=Math.floor(t/60),s=Math.floor(t%60),ms=Math.floor((t-Math.floor(t))*1000);return `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}.${String(ms).padStart(3,"0")}`};
  const currentTime=()=>playing?clamp(logicalStart+(ac.currentTime-contextStart),0,duration):logicalStart;

  function ensureAudioContext(){
    if(!ac)ac=new (window.AudioContext||window.webkitAudioContext)({latencyHint:"interactive"});
    return ac;
  }

  function readVar(data,state){
    let v=0,b=0,count=0;
    do{if(state.i>=data.length)throw Error("MIDIの可変長値が不正です");b=data[state.i++];v=(v<<7)|(b&127);if(++count>4)throw Error("MIDIの可変長値が長すぎます")}while(b&128);
    return v;
  }
  function parseMidi(ab){
    const d=new DataView(ab),bytes=new Uint8Array(ab);
    const cc=i=>String.fromCharCode(bytes[i],bytes[i+1],bytes[i+2],bytes[i+3]);
    if(ab.byteLength<14||cc(0)!=="MThd")throw Error("MIDIヘッダーが不正です");
    const headerLen=d.getUint32(4,false),tracks=d.getUint16(10,false),division=d.getUint16(12,false);
    if(division&0x8000)throw Error("SMPTE time divisionには未対応です");
    const ppq=division,rawNotes=[],tempos=[{tick:0,us:500000}],rawEvents=[];
    let pos=8+headerLen;
    for(let tr=0;tr<tracks;tr++){
      if(pos+8>bytes.length||cc(pos)!=="MTrk")throw Error(`MIDI track ${tr+1} が不正です`);
      const len=d.getUint32(pos+4,false),end=pos+8+len;let i=pos+8,tick=0,running=0;
      while(i<end){
        const st={i};tick+=readVar(bytes,st);i=st.i;
        let statusByte=bytes[i];
        if(statusByte<0x80){if(!running)throw Error("MIDI running statusが不正です");statusByte=running}else{i++;if(statusByte<0xf0)running=statusByte}
        if(statusByte===0xff){
          if(i>=end)break;const type=bytes[i++],s={i},n=readVar(bytes,s);i=s.i;
          if(type===0x51&&n===3&&i+3<=end){const us=(bytes[i]<<16)|(bytes[i+1]<<8)|bytes[i+2];tempos.push({tick,us})}
          i+=n;continue;
        }
        if(statusByte===0xf0||statusByte===0xf7){const s={i},n=readVar(bytes,s);i=s.i+n;running=0;continue}
        const hi=statusByte&0xf0,need=(hi===0xc0||hi===0xd0)?1:2;
        if(i+need>end)break;
        const a=bytes[i++],b=need===2?bytes[i++]:0;
        if(hi===0x90&&b>0)rawNotes.push({tick,note:a,velocity:b,track:tr});
        rawEvents.push({tick,status:statusByte,a,b});
      }
      pos=end;
    }
    tempos.sort((a,b)=>a.tick-b.tick);
    const dedup=[];for(const t of tempos){if(dedup.length&&dedup.at(-1).tick===t.tick)dedup[dedup.length-1]=t;else dedup.push(t)}
    let lastTick=0,lastSec=0,lastUs=500000;
    for(const t of dedup){lastSec+=(t.tick-lastTick)*lastUs/1e6/ppq;t.sec=lastSec;lastTick=t.tick;lastUs=t.us}
    function tickToSec(tick){
      let lo=0,hi=dedup.length-1,idx=0;while(lo<=hi){const mid=(lo+hi)>>1;if(dedup[mid].tick<=tick){idx=mid;lo=mid+1}else hi=mid-1}
      const e=dedup[idx];return e.sec+(tick-e.tick)*e.us/1e6/ppq;
    }
    return {notes:rawNotes.map(n=>({...n,time:tickToSec(n.tick)})).sort((a,b)=>a.time-b.time),tempos:dedup,ppq};
  }

  function category(note){
    if(note===35||note===36)return 0;
    if(note===38||note===40||note===37)return 1;
    if(note===42||note===44||note===46)return 2;
    if([41,43,45,47,48,50].includes(note))return 3;
    if([49,51,52,55,57,59].includes(note))return 4;
    return 5;
  }
  const laneNames=["KICK","SNARE","HI-HAT","TOMS","CYMBAL","OTHER"];
  const laneColors=["#78cfff","#ff8bb6","#f5d76d","#b894ff","#77e5ce","#9daaba"];

  function resizeCanvas(){
    const r=canvas.getBoundingClientRect(),dpr=Math.min(2,devicePixelRatio||1),w=Math.max(1,Math.round(r.width*dpr)),h=Math.max(1,Math.round(r.height*dpr));
    if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;ctx.setTransform(dpr,0,0,dpr,0,0)}
    draw();
  }
  function viewportWidth(){return canvas.getBoundingClientRect().width}
  function viewportDuration(){return viewportWidth()/pxPerSec}
  function maxViewStart(){return Math.max(0,duration-viewportDuration())}
  function syncScrollFromView(){scrollInput.value=maxViewStart()>0?String(Math.round(viewStart/maxViewStart()*1000)):"0"}
  function setViewStart(v){viewStart=clamp(v,0,maxViewStart());syncScrollFromView();draw()}
  function timeToX(t){return (t-viewStart)*pxPerSec}
  function xToTime(x){return viewStart+x/pxPerSec}

  function drawGrid(w,h,waveTop,waveBottom,midiTop){
    ctx.fillStyle="#070c12";ctx.fillRect(0,0,w,h);
    const visible=viewportDuration(),fine=pxPerSec>=900?.01:pxPerSec>=260?.1:.5,major=pxPerSec>=120?1:5;
    const first=Math.floor(viewStart/fine)*fine;
    for(let t=first;t<=viewStart+visible+fine;t+=fine){
      const x=timeToX(t),isMajor=Math.abs(t/major-Math.round(t/major))<1e-5;
      ctx.beginPath();ctx.moveTo(x,26);ctx.lineTo(x,h);ctx.strokeStyle=isMajor?"rgba(151,177,204,.18)":"rgba(151,177,204,.055)";ctx.lineWidth=1;ctx.stroke();
      if(isMajor){ctx.fillStyle="#7f91a4";ctx.font="10px ui-monospace,monospace";ctx.fillText(fmtTime(t).slice(0,8),x+4,17)}
    }
    ctx.strokeStyle="rgba(255,255,255,.10)";ctx.beginPath();ctx.moveTo(0,waveTop);ctx.lineTo(w,waveTop);ctx.moveTo(0,waveBottom);ctx.lineTo(w,waveBottom);ctx.moveTo(0,midiTop);ctx.lineTo(w,midiTop);ctx.stroke();
  }

  function drawWaveform(w,waveTop,waveBottom){
    if(!audioBuffer)return;
    const ch0=audioBuffer.getChannelData(0),ch1=audioBuffer.numberOfChannels>1?audioBuffer.getChannelData(1):ch0,sr=audioBuffer.sampleRate,mid=(waveTop+waveBottom)/2,amp=(waveBottom-waveTop)*.45;
    ctx.save();ctx.beginPath();ctx.rect(0,waveTop,w,waveBottom-waveTop);ctx.clip();
    ctx.strokeStyle="#65d8ff";ctx.lineWidth=1;ctx.globalAlpha=.86;ctx.beginPath();
    for(let x=0;x<w;x++){
      const logical=xToTime(x),audioTime=logical+offsetMs/1000;
      if(audioTime<0||audioTime>=audioBuffer.duration)continue;
      const center=audioTime*sr,samplesPerPx=Math.max(1,sr/pxPerSec),span=Math.max(1,Math.floor(samplesPerPx)),step=Math.max(1,Math.floor(span/64));let lo=1,hi=-1;
      const a=Math.max(0,Math.floor(center-span*.5)),b=Math.min(ch0.length,Math.ceil(center+span*.5));
      for(let i=a;i<b;i+=step){const v=(ch0[i]+ch1[i])*.5;if(v<lo)lo=v;if(v>hi)hi=v}
      if(hi<lo){lo=hi=0}
      ctx.moveTo(x,mid-hi*amp);ctx.lineTo(x,mid-lo*amp);
    }
    ctx.stroke();ctx.globalAlpha=1;
    const zeroX=timeToX(-offsetMs/1000);if(zeroX>=0&&zeroX<=w){ctx.strokeStyle="rgba(255,218,110,.7)";ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(zeroX,waveTop);ctx.lineTo(zeroX,waveBottom);ctx.stroke();ctx.setLineDash([])}
    ctx.restore();
  }

  function drawMidi(w,waveTop,waveBottom,midiTop,h){
    if(!midiNotes.length)return;
    const laneH=(h-midiTop-10)/laneNames.length;
    for(let i=0;i<laneNames.length;i++){
      const y=midiTop+i*laneH;ctx.fillStyle=i%2?"rgba(255,255,255,.014)":"rgba(255,255,255,.028)";ctx.fillRect(0,y,w,laneH);
      ctx.fillStyle="#75879a";ctx.font="9px system-ui,sans-serif";ctx.fillText(laneNames[i],7,y+12);
    }
    const t0=viewStart-.01,t1=viewStart+viewportDuration()+.01;
    let lo=0,hi=midiNotes.length;while(lo<hi){const m=(lo+hi)>>1;if(midiNotes[m].time<t0)lo=m+1;else hi=m}
    for(let i=lo;i<midiNotes.length;i++){
      const n=midiNotes[i];if(n.time>t1)break;const x=timeToX(n.time),cat=category(n.note),y=midiTop+cat*laneH;
      ctx.strokeStyle=laneColors[cat];ctx.globalAlpha=.24+.55*n.velocity/127;ctx.lineWidth=Math.max(1,Math.min(3,pxPerSec/260));ctx.beginPath();ctx.moveTo(x,waveTop);ctx.lineTo(x,waveBottom);ctx.stroke();
      ctx.globalAlpha=.95;ctx.fillStyle=laneColors[cat];ctx.fillRect(x-1,y+16,Math.max(2,pxPerSec*.012),Math.max(4,laneH-20));
    }
    ctx.globalAlpha=1;
  }

  function drawPlayhead(w,h){
    const t=currentTime(),x=timeToX(t);if(x<0||x>w)return;
    ctx.strokeStyle="#ff6f9d";ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();ctx.fillStyle="#ff6f9d";ctx.beginPath();ctx.moveTo(x-5,0);ctx.lineTo(x+5,0);ctx.lineTo(x,7);ctx.closePath();ctx.fill();
  }

  function draw(){
    const r=canvas.getBoundingClientRect(),w=r.width,h=r.height,waveTop=27,waveBottom=Math.round(h*.62),midiTop=waveBottom+1;
    ctx.clearRect(0,0,w,h);drawGrid(w,h,waveTop,waveBottom,midiTop);drawWaveform(w,waveTop,waveBottom);drawMidi(w,waveTop,waveBottom,midiTop,h);drawPlayhead(w,h);
    $("#timeText").textContent=`${fmtTime(currentTime())} / ${fmtTime(duration)}`;
  }

  function stopSource(){if(source){try{source.onended=null;source.stop()}catch{}try{source.disconnect()}catch{}source=null}}
  function stopClicks(){for(const o of activeClicks){try{o.stop()}catch{}try{o.disconnect()}catch{}}activeClicks.clear();if(clickTimer)clearInterval(clickTimer);clickTimer=0}
  function stopPlayback(keepPosition=true){
    if(playing&&keepPosition)logicalStart=currentTime();playing=false;stopSource();stopClicks();playBtn.textContent="▶ 再生";draw();
  }
  function scheduleAudio(logical,when){
    stopSource();const s=ac.createBufferSource();s.buffer=audioBuffer;s.connect(ac.destination);source=s;
    const audioPos=logical+offsetMs/1000;
    if(audioPos>=0)s.start(when,Math.min(audioPos,audioBuffer.duration-.001));
    else s.start(when-audioPos,0);
    s.onended=()=>{if(source===s&&playing&&currentTime()>=duration-.02){logicalStart=duration;stopPlayback(false)}};
  }
  function firstNoteAt(t){let lo=0,hi=midiNotes.length;while(lo<hi){const m=(lo+hi)>>1;if(midiNotes[m].time<t)lo=m+1;else hi=m}return lo}
  function clickFreq(note){const c=category(note);return [75,210,950,320,660,500][c]}
  function scheduleClicks(){
    if(!playing||!midiClick.checked)return;const nowLogical=currentTime(),horizon=nowLogical+.13;
    while(nextClickIndex<midiNotes.length&&midiNotes[nextClickIndex].time<horizon){
      const n=midiNotes[nextClickIndex++];if(n.time<nowLogical-.02)continue;
      const when=ac.currentTime+(n.time-nowLogical),o=ac.createOscillator(),g=ac.createGain();o.frequency.value=clickFreq(n.note);o.type=category(n.note)===0?"sine":"square";g.gain.setValueAtTime(0,when);g.gain.linearRampToValueAtTime(.055*(n.velocity/127),when+.001);g.gain.exponentialRampToValueAtTime(.0001,when+.026);o.connect(g).connect(ac.destination);o.start(when);o.stop(when+.03);activeClicks.add(o);o.onended=()=>{activeClicks.delete(o);try{o.disconnect();g.disconnect()}catch{}};
    }
  }
  function startPlayback(){
    if(!audioBuffer)return;ensureAudioContext();ac.resume();if(currentTime()>=duration-.01)logicalStart=0;
    const t=logicalStart,when=ac.currentTime+.045;contextStart=when;logicalStart=t;playing=true;scheduleAudio(t,when);nextClickIndex=firstNoteAt(t-.01);stopClicks();clickTimer=setInterval(scheduleClicks,35);scheduleClicks();playBtn.textContent="Ⅱ 一時停止";animate();
  }
  function restartAtSameLogical(){if(!playing)return;const t=currentTime();stopSource();stopClicks();logicalStart=t;contextStart=ac.currentTime+.035;scheduleAudio(t,contextStart);nextClickIndex=firstNoteAt(t-.01);clickTimer=setInterval(scheduleClicks,35);scheduleClicks()}
  function animate(){if(raf)cancelAnimationFrame(raf);const tick=()=>{raf=0;if(playing){const t=currentTime(),end=viewStart+viewportDuration();if(t<viewStart||t>end){setViewStart(clamp(t-viewportDuration()*.25,0,maxViewStart()))}draw();if(t>=duration){logicalStart=duration;stopPlayback(false);return}raf=requestAnimationFrame(tick)}};raf=requestAnimationFrame(tick)}

  function seek(t){logicalStart=clamp(t,0,duration);if(playing)restartAtSameLogical();draw()}
  function setOffset(v,restart=true){offsetMs=round01(clamp(Number(v)||0,-500,500));offsetInput.value=offsetMs.toFixed(1);offsetReadout.textContent=fmtMs(offsetMs);$("#productionCode").textContent=`playback:{stemOffsetSec:${formatSec(offsetMs)}}`;draw();if(restart&&playing)restartAtSameLogical()}
  function formatSec(ms){const s=round01(ms)/1000;if(s===0)return "0";const abs=Math.abs(s).toFixed(4).replace(/^0/,"").replace(/0+$/,"");return `${s<0?"-":""}${abs}`}

  playBtn.onclick=()=>playing?stopPlayback(true):startPlayback();stopBtn.onclick=()=>{stopPlayback(false);logicalStart=0;draw()};$("#back1").onclick=()=>seek(currentTime()-1);$("#forward1").onclick=()=>seek(currentTime()+1);
  offsetInput.addEventListener("change",()=>setOffset(offsetInput.value));offsetInput.addEventListener("keydown",e=>{if(e.key==="Enter"){setOffset(offsetInput.value);offsetInput.blur()}});
  document.querySelectorAll("[data-nudge]").forEach(b=>b.onclick=()=>setOffset(offsetMs+Number(b.dataset.nudge)));
  $("#resetOffset").onclick=()=>setOffset(PRODUCTION_OFFSET_MS);
  $("#copyOffset").onclick=async()=>{await navigator.clipboard?.writeText(offsetMs.toFixed(1));$("#copyOffset").textContent="コピー済";setTimeout(()=>$("#copyOffset").textContent="値をコピー",800)};
  $("#copyCode").onclick=async()=>{await navigator.clipboard?.writeText($("#productionCode").textContent);$("#copyCode").textContent="コピー済";setTimeout(()=>$("#copyCode").textContent="コードをコピー",800)};
  midiClick.onchange=()=>{if(playing){stopClicks();nextClickIndex=firstNoteAt(currentTime());if(midiClick.checked){clickTimer=setInterval(scheduleClicks,35);scheduleClicks()}}};

  zoomInput.oninput=()=>{const old=pxPerSec,center=viewStart+viewportDuration()/2;pxPerSec=Number(zoomInput.value);zoomText.textContent=`${pxPerSec} px/s`;viewStart=clamp(center-viewportDuration()/2,0,maxViewStart());syncScrollFromView();draw()};
  scrollInput.oninput=()=>{const m=maxViewStart();viewStart=m*Number(scrollInput.value)/1000;draw()};
  canvas.addEventListener("wheel",e=>{
    e.preventDefault();const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,anchor=xToTime(x);
    if(e.ctrlKey){pxPerSec=clamp(Math.round(pxPerSec*(e.deltaY<0?1.22:.82)/10)*10,60,6000);zoomInput.value=String(pxPerSec);zoomText.textContent=`${pxPerSec} px/s`;viewStart=clamp(anchor-x/pxPerSec,0,maxViewStart());syncScrollFromView();draw()}
    else setViewStart(viewStart+e.deltaY/pxPerSec*1.8);
  },{passive:false});

  canvas.addEventListener("pointerdown",e=>{
    const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top,waveBottom=Math.round(r.height*.62);
    if(y>=27&&y<=waveBottom){drag={id:e.pointerId,startX:x,startOffset:offsetMs,moved:false};canvas.setPointerCapture(e.pointerId);canvas.style.cursor="ew-resize"}
    else seek(xToTime(x));
  });
  canvas.addEventListener("pointermove",e=>{
    if(!drag||drag.id!==e.pointerId)return;const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,dx=x-drag.startX;if(Math.abs(dx)>1)drag.moved=true;
    /* Dragging the waveform right means delaying it, i.e. decreasing the positive source-skip offset. */
    setOffset(drag.startOffset-dx/pxPerSec*1000,false);
  });
  function finishDrag(e){if(!drag||drag.id!==e.pointerId)return;const d=drag;drag=null;canvas.style.cursor="crosshair";try{canvas.releasePointerCapture(e.pointerId)}catch{}if(playing)restartAtSameLogical();if(!d.moved){const r=canvas.getBoundingClientRect();seek(xToTime(e.clientX-r.left))}}
  canvas.addEventListener("pointerup",finishDrag);canvas.addEventListener("pointercancel",finishDrag);

  async function load(){
    try{
      if(matchMedia("(hover:none) and (pointer:coarse)").matches||innerWidth<1100){$("#pcOnly").hidden=false;return}
      ensureAudioContext();status.textContent="Rayドラム音源を読み込み中…";
      const [audioRes,midiRes]=await Promise.all([fetch(AUDIO_URL,{cache:"force-cache"}),fetch(MIDI_URL,{cache:"no-store"})]);
      if(!audioRes.ok)throw Error(`ドラム音源 HTTP ${audioRes.status}`);if(!midiRes.ok)throw Error(`MIDI HTTP ${midiRes.status}`);
      const [audioAB,midiAB]=await Promise.all([audioRes.arrayBuffer(),midiRes.arrayBuffer()]);
      status.textContent="音源をデコード中…";audioBuffer=await ac.decodeAudioData(audioAB.slice(0));
      const parsed=parseMidi(midiAB);midiNotes=parsed.notes;tempoEvents=parsed.tempos;duration=Math.max(audioBuffer.duration,midiNotes.at(-1)?.time||0);
      $("#noteCount").textContent=midiNotes.length.toLocaleString();$("#tempoInfo").textContent=tempoEvents.map(t=>(60e6/t.us).toFixed(3).replace(/\.0+$/,"")).filter((v,i,a)=>a.indexOf(v)===i).join(" / ")+" BPM";$("#lastNote").textContent=fmtTime(midiNotes.at(-1)?.time||0);$("#audioDuration").textContent=fmtTime(audioBuffer.duration);$("#sampleRate").textContent=`${audioBuffer.sampleRate.toLocaleString()} Hz`;
      playBtn.disabled=stopBtn.disabled=$("#back1").disabled=$("#forward1").disabled=false;status.textContent="READY";setOffset(PRODUCTION_OFFSET_MS,false);resizeCanvas();
    }catch(e){console.error(e);status.textContent=`ERROR: ${e.message||e}`}
  }

  addEventListener("resize",resizeCanvas);addEventListener("pagehide",()=>{stopPlayback(false);try{ac?.close()}catch{}},{once:true});
  load();
})();
