"use strict";

(()=>{
  const modeSelect=document.querySelector("#performanceModeSelect"),startButton=document.querySelector("#start"),
        setupEl=document.querySelector("#setup"),gameEl=document.querySelector("#game"),resultEl=document.querySelector("#result"),
        chartWrap=document.querySelector("#chartWrap"),pauseButton=document.querySelector("#pause");
  const songApi=globalThis.DruMasterSongs;
  if(!modeSelect||!startButton||!setupEl||!gameEl||!chartWrap||!songApi?.songs)return;

  const songList=Object.values(songApi.songs),nativeFetch=songApi.nativeFetch||globalThis.fetch.bind(globalThis),cache=new Map();
  const initialSong=songApi.current;
  const baseStartHandler=startButton.onclick,
        baseInput=typeof input==="function"?input:null,
        baseTogglePause=typeof togglePause==="function"?togglePause:null,
        baseFinish=typeof finish==="function"?finish:null;

  let active=false,currentSong=initialSong,stemVoices=new Set(),kickCursor=0,ending=false,prefetchFor="",switching=false,
      scrubbing=false,scrubTarget=0,scrubWasPaused=false,dragPointer=null,dragStartX=0,dragStartSec=0,restartGeneration=0;
  let loopMode="off";
  try{const saved=localStorage.getItem("drumasterScorePlaybackLoop");if(["off","all","one"].includes(saved))loopMode=saved}catch{}

  const header=pauseButton?.parentElement;
  const controls=document.createElement("div");
  controls.id="scorePlaybackControls";
  controls.innerHTML='<button id="scorePrev" type="button" aria-label="前の曲" title="前の曲">⏮</button><button id="scoreNext" type="button" aria-label="次の曲" title="次の曲">⏭</button><button id="scoreLoop" type="button" aria-label="ループ設定" title="ループ設定">↻ OFF</button>';
  header?.insertBefore(controls,pauseButton||null);

  const seekWrap=document.createElement("div");
  seekWrap.id="scoreSeekWrap";
  seekWrap.innerHTML='<input id="scoreSeek" type="range" min="0" max="1" step="0.05" value="0" aria-label="再生位置"><span id="scoreSeekTime">0:00 / 0:00</span>';
  chartWrap.appendChild(seekWrap);
  const busy=document.createElement("span");busy.id="scorePlaybackBusy";busy.textContent="LOADING NEXT SONG";chartWrap.appendChild(busy);
  const seek=seekWrap.querySelector("#scoreSeek"),seekTime=seekWrap.querySelector("#scoreSeekTime"),loopButton=controls.querySelector("#scoreLoop");

  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const formatTime=value=>{const s=Math.max(0,Math.floor(Number(value)||0)),m=Math.floor(s/60);return `${m}:${String(s%60).padStart(2,"0")}`};
  const songDuration=s=>Math.max(.1,Number(s?.duration)||0);
  const stemGain=(song,name,fallback)=>Number.isFinite(song?.mix?.[name])?song.mix[name]:fallback;
  const selectedStemNames=()=>["base",...(document.querySelector("#vocalToggle")?.checked?["vocals"]:[]),...(document.querySelector("#guideToggle")?.checked?["drums"]:[])];

  function setLoading(on,text="LOADING NEXT SONG"){
    document.body.dataset.scoreLoading=on?"1":"0";
    busy.textContent=text;
  }
  function updateLoopButton(){
    const label=loopMode==="all"?"↻ ALL":loopMode==="one"?"↻ 1":"↻ OFF";
    loopButton.textContent=label;loopButton.dataset.loop=loopMode;
    loopButton.title=loopMode==="all"?"全曲ループ":loopMode==="one"?"一曲ループ":"ループなし";
    loopButton.setAttribute("aria-label",loopButton.title);
  }
  updateLoopButton();

  async function loadMidi(song,entry){
    if(entry.notes)return;
    if(entry.midiPromise)return entry.midiPromise;
    entry.midiPromise=(async()=>{
      const r=await nativeFetch(song.midiGzip,{cache:"force-cache"});
      if(!r.ok)throw Error(`${song.title} の楽譜を取得できません（HTTP ${r.status}）`);
      if(typeof DecompressionStream!=="function")throw Error("このブラウザではMIDI展開機能を利用できません");
      const ab=await new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
      entry.notes=parseMidi(ab);
      entry.timing=globalThis.DruMusterChart?.parseTempoTiming?globalThis.DruMusterChart.parseTempoTiming(ab):null;
    })();
    try{await entry.midiPromise}finally{entry.midiPromise=null}
  }
  async function loadStemFor(song,entry,name){
    if(entry.buffers[name])return;
    if(entry.stemPromises[name])return entry.stemPromises[name];
    const spec=song.stems?.[name];if(!spec)throw Error(`${song.title} の ${name} stem がありません`);
    entry.stemPromises[name]=(async()=>{
      const r=await nativeFetch(spec.path,{cache:"force-cache"});
      if(!r.ok)throw Error(`${song.title} の伴奏を取得できません（HTTP ${r.status}）`);
      const ab=await r.arrayBuffer();
      if(Number.isFinite(spec.bytes)&&spec.bytes>0&&ab.byteLength!==spec.bytes)throw Error(`${song.title} の伴奏データが不完全です`);
      entry.buffers[name]=await ac.decodeAudioData(ab.slice(0));
    })();
    try{await entry.stemPromises[name]}finally{delete entry.stemPromises[name]}
  }
  async function ensureSongData(song){
    let entry=cache.get(song.id);
    if(!entry){entry={song,notes:null,timing:null,buffers:{},stemPromises:{},midiPromise:null};cache.set(song.id,entry)}
    await loadMidi(song,entry);
    await Promise.all(selectedStemNames().map(name=>loadStemFor(song,entry,name)));
    return entry;
  }

  function stopStemVoices(){
    const now=ac?.currentTime||0;
    for(const v of [...stemVoices]){
      stemVoices.delete(v);
      try{v.source.onended=null;v.source.stop(now)}catch{}
      try{v.source.disconnect()}catch{}try{v.gain.disconnect()}catch{}
    }
  }
  function playStem(entry,name,gainValue,when,logicalOffset){
    const buf=entry.buffers[name];if(!buf)return;
    const stemOffset=Math.max(0,Number(currentSong.playback?.stemOffsetSec)||0),offset=clamp(logicalOffset+stemOffset,0,Math.max(0,buf.duration-.001));
    if(offset>=buf.duration-.001)return;
    const source=ac.createBufferSource(),gain=ac.createGain(),voice={source,gain};
    source.buffer=buf;source.playbackRate.value=rate;gain.gain.value=gainValue;source.connect(gain).connect(masterBus);
    stemVoices.add(voice);source.onended=()=>{stemVoices.delete(voice);try{source.disconnect()}catch{}try{gain.disconnect()}catch{}};
    source.start(when,offset);
  }
  function startStemSet(entry,when,logicalOffset){
    playStem(entry,"base",stemGain(currentSong,"base",.95),when,logicalOffset);
    if(document.querySelector("#vocalToggle")?.checked)playStem(entry,"vocals",stemGain(currentSong,"vocals",.95),when,logicalOffset);
    if(document.querySelector("#guideToggle")?.checked)playStem(entry,"drums",stemGain(currentSong,"drums",.70),when,logicalOffset);
  }

  function lowerBoundTime(sec){
    let lo=0,hi=notes.length;while(lo<hi){const mid=(lo+hi)>>1;if(notes[mid].time<sec)lo=mid+1;else hi=mid}return lo;
  }
  function resetKickCursor(sec){kickCursor=lowerBoundTime(Math.max(0,sec-.05))}
  function updateSeekUi(sec){
    if(!seek||!seekTime)return;
    const d=songDuration(currentSong),t=clamp(sec,0,d);
    seek.max=String(d);if(!scrubbing)seek.value=String(t);
    seekTime.textContent=`${formatTime(t)} / ${formatTime(d)}`;
  }
  function updateSongLabels(){
    songApi.current=currentSong;
    const titleNodes=[document.querySelector(".song-card h1"),document.querySelector(".song-hud b")],artistNodes=[document.querySelector(".song-card p"),document.querySelector(".song-hud small")];
    titleNodes.forEach(n=>{if(n)n.textContent=currentSong.title});artistNodes.forEach(n=>{if(n)n.textContent=currentSong.artist});
    const percent=Number(document.querySelector("#tempo")?.value||100),bpm=`♪＝${Math.round((Number(currentSong.bpm)||0)*percent/100)}`;
    document.querySelectorAll(".setup-bpm,.hud-bpm").forEach(n=>n.textContent=bpm);
    const songSelect=document.querySelector("#songSelect");if(songSelect)songSelect.value=currentSong.id;
    const url=new URL(location.href);url.searchParams.set("song",currentSong.id);history.replaceState(null,"",url);
  }
  function applySong(song,entry){
    currentSong=song;songApi.current=song;
    notes=entry.notes.map(n=>({...n,hit:false}));duration=songDuration(song);
    try{if(entry.timing)beatTiming=entry.timing}catch{}
    score=0;counts={perfect:0,great:0,good:0,miss:0};nextKick=0;nextAuto=0;missCursor=0;
    resetKickCursor(0);setKit?.();updateSongLabels();updateSeekUi(0);resize?.();draw?.();
  }
  function setPauseUi(isPaused){
    document.querySelector("#pausePanel")?.classList.toggle("hidden",!isPaused);
    if(pauseButton){pauseButton.textContent=isPaused?"▶":"Ⅱ";pauseButton.setAttribute("aria-label",isPaused?"再生を再開":"再生を停止")}
  }

  async function restartAt(sec,shouldPlay=true){
    const generation=++restartGeneration,song=currentSong,target=clamp(sec,0,songDuration(song));
    cancelAnimationFrame(raf);stopStemVoices();
    const entry=await ensureSongData(song);
    if(generation!==restartGeneration||!active||currentSong!==song)return;
    resetKickCursor(target);ending=false;prefetchFor="";
    if(shouldPlay){
      try{await ac.resume()}catch{}
      if(generation!==restartGeneration||!active||currentSong!==song)return;
      stopStemVoices();
      const when=ac.currentTime+.045;startStemSet(entry,when,target);startedAt=when-target/rate;paused=false;setPauseUi(false);raf=requestAnimationFrame(scoreLoop);
    }else{
      if(generation!==restartGeneration||!active||currentSong!==song)return;
      stopStemVoices();
      const when=ac.currentTime;startStemSet(entry,when,target);startedAt=when-target/rate;paused=true;setPauseUi(true);draw?.();updateSeekUi(target);
    }
  }

  function nextSong(delta=1){
    const i=Math.max(0,songList.findIndex(s=>s.id===currentSong.id));return songList[(i+delta+songList.length)%songList.length];
  }
  async function switchSong(delta){
    if(!active||switching)return;restartGeneration++;switching=true;setLoading(true,"LOADING SONG");
    try{
      const target=nextSong(delta),wasPaused=paused,entry=await ensureSongData(target);
      cancelAnimationFrame(raf);stopStemVoices();currentSong=target;applySong(target,entry);
      rate=+document.querySelector("#tempo")?.value/100||1;
      if(wasPaused){const when=ac.currentTime;startStemSet(entry,when,0);startedAt=when;paused=true;setPauseUi(true);draw?.()}
      else{try{await ac.resume()}catch{}const when=ac.currentTime+.045;startStemSet(entry,when,0);startedAt=when;paused=false;setPauseUi(false);raf=requestAnimationFrame(scoreLoop)}
      prefetchFor="";ending=false;
    }catch(e){console.error(e);const load=document.querySelector("#loadState");if(load)load.textContent=e?.message||"曲の切り替えに失敗しました"}
    finally{switching=false;setLoading(false)}
  }

  async function handleTrackEnd(){
    if(!active||ending)return;restartGeneration++;ending=true;cancelAnimationFrame(raf);stopStemVoices();
    if(loopMode==="one"){
      ending=false;await restartAt(0,true);return;
    }
    if(loopMode==="all"){
      const target=nextSong(1);setLoading(true,"LOADING NEXT SONG");
      try{
        const entry=await ensureSongData(target);currentSong=target;applySong(target,entry);rate=+document.querySelector("#tempo")?.value/100||1;
        try{await ac.resume()}catch{}const when=ac.currentTime+.045;startStemSet(entry,when,0);startedAt=when;paused=false;setPauseUi(false);prefetchFor="";ending=false;setLoading(false);raf=requestAnimationFrame(scoreLoop);return;
      }catch(e){console.error(e);setLoading(false)}
    }
    goHome();
  }

  function scoreLoop(){
    if(!active||!running||paused||scrubbing)return;
    const t=current(),d=songDuration(currentSong);
    while(kickCursor<notes.length&&notes[kickCursor].time<=t+.012){
      const n=notes[kickCursor++];if(n.type==="kick"&&n.time>=t-.05)playDrum(n.note,n.type,n.velocity/127);
    }
    draw?.();updateSeekUi(t);
    if(loopMode==="all"&&d-t<=5&&d-t>=0&&prefetchFor!==currentSong.id){
      prefetchFor=currentSong.id;const target=nextSong(1);void ensureSongData(target).catch(e=>console.warn("Next song prefetch failed",e));
    }
    if(t>=d){void handleTrackEnd();return}
    raf=requestAnimationFrame(scoreLoop);
  }

  function beginScrub(startSec=current()){
    if(!active||scrubbing)return;
    restartGeneration++;scrubWasPaused=paused;scrubTarget=clamp(startSec,0,songDuration(currentSong));scrubbing=true;cancelAnimationFrame(raf);stopStemVoices();
  }
  function previewScrub(sec){
    if(!active)return;if(!scrubbing)beginScrub(sec);scrubTarget=clamp(sec,0,songDuration(currentSong));
    const oldStarted=startedAt;startedAt=ac.currentTime-scrubTarget/rate;draw?.();startedAt=oldStarted;
    seek.value=String(scrubTarget);updateSeekUi(scrubTarget);
  }
  async function commitScrub(){
    if(!active||!scrubbing)return;const target=scrubTarget,wasPaused=scrubWasPaused;scrubbing=false;await restartAt(target,!wasPaused);
  }

  seek.addEventListener("pointerdown",()=>beginScrub(current()));
  seek.addEventListener("input",()=>previewScrub(+seek.value||0));
  seek.addEventListener("change",()=>{void commitScrub()});
  seek.addEventListener("pointerup",()=>{void commitScrub()});

  chartWrap.addEventListener("pointerdown",e=>{
    if(!active||e.target.closest("#scoreSeekWrap")||e.button>0)return;
    dragPointer=e.pointerId;dragStartX=e.clientX;dragStartSec=current();beginScrub(dragStartSec);chartWrap.setPointerCapture?.(e.pointerId);e.preventDefault();
  },true);
  chartWrap.addEventListener("pointermove",e=>{
    if(!active||dragPointer!==e.pointerId||!scrubbing)return;
    const ppq=Number(globalThis.DruMusterChart?.pixelsPerQuarter?.()||80),secPerPx=60/Math.max(1,Number(currentSong.bpm)||120)/Math.max(20,ppq),target=dragStartSec-(e.clientX-dragStartX)*secPerPx;
    previewScrub(target);e.preventDefault();
  },true);
  const endDrag=e=>{if(dragPointer!==e.pointerId)return;dragPointer=null;try{chartWrap.releasePointerCapture?.(e.pointerId)}catch{}void commitScrub()};
  chartWrap.addEventListener("pointerup",endDrag,true);chartWrap.addEventListener("pointercancel",endDrag,true);

  function installRunActions(){
    controls.querySelector("#scorePrev").onclick=()=>{void switchSong(-1)};
    controls.querySelector("#scoreNext").onclick=()=>{void switchSong(1)};
    loopButton.onclick=()=>{
      loopMode=loopMode==="off"?"all":loopMode==="all"?"one":"off";updateLoopButton();prefetchFor="";
      try{localStorage.setItem("drumasterScorePlaybackLoop",loopMode)}catch{}
    };
    const restart=document.querySelector("#quit"),end=document.querySelector("#endRun"),resume=document.querySelector("#resume");
    if(restart){restart.textContent="最初から";restart.onclick=()=>{void restartAt(0,true)}}
    if(end){end.textContent="終了";end.onclick=goHome}
    if(resume)resume.onclick=()=>{void togglePause(true)};
  }

  async function startScorePlayback(){
    if(active||loading)return;
    restartGeneration++;active=true;document.body.dataset.scorePlayback="1";document.body.dataset.scoreLoading="0";ending=false;prefetchFor="";
    startButton.disabled=true;const load=document.querySelector("#loadState"),oldLoad=load?.textContent||"";if(load)load.textContent="楽譜再生データを準備中…";
    try{
      try{await ac.resume()}catch{}
      globalThis.DruMasterPerformanceMode?.stopMic?.();
      const song=songApi.current||initialSong,entry=await ensureSongData(song);currentSong=song;applySong(song,entry);
      rate=+document.querySelector("#tempo")?.value/100||1;autoplay=false;
      globalThis.DruMasterResultFanfare?.stop?.();globalThis.DruMasterPlaybackControl?.stopRunAudio?.();stopStemVoices();
      setupEl.classList.add("hidden");resultEl?.classList.add("hidden");gameEl.classList.remove("hidden");
      const label=document.querySelector(".score small"),value=document.querySelector("#score");if(label)label.textContent="PLAYBACK";if(value)value.textContent="--";
      installRunActions();running=true;paused=false;setPauseUi(false);resize?.();
      const when=ac.currentTime+.055;startStemSet(entry,when,0);startedAt=when;resetKickCursor(0);updateSeekUi(0);raf=requestAnimationFrame(scoreLoop);
      if(load)load.textContent=oldLoad;
    }catch(e){
      console.error(e);active=false;document.body.dataset.scorePlayback="0";setupEl.classList.remove("hidden");gameEl.classList.add("hidden");startButton.disabled=false;if(load)load.textContent=e?.message||"楽譜再生を開始できません";
    }
  }

  function goHome(){
    if(!active)return;restartGeneration++;active=false;running=false;paused=false;scrubbing=false;cancelAnimationFrame(raf);stopStemVoices();setPauseUi(false);document.body.dataset.scorePlayback="0";document.body.dataset.scoreLoading="0";
    const url=new URL(location.href);url.searchParams.set("song",currentSong.id);url.searchParams.delete("v");url.searchParams.delete("micdebug");location.href=url.toString();
  }

  startButton.onclick=function(e){
    if(modeSelect.value==="score")return startScorePlayback();
    return baseStartHandler?.call(this,e);
  };

  if(baseInput){
    input=function(part,visualEl){
      if(!active)return baseInput(part,visualEl);
      if(!running||paused||scrubbing)return;
      const type=DEFAULT_TYPE[part]||part,note=DEFAULT_NOTE[type];playDrum(note,type,.82);flashPart(part,visualEl);
    };
  }
  if(baseTogglePause){
    togglePause=async function(forceResume=false){
      if(!active)return baseTogglePause(forceResume);
      if(!running||scrubbing)return;
      if(!paused&&!forceResume){paused=true;cancelAnimationFrame(raf);try{await ac.suspend()}catch{}setPauseUi(true)}
      else{try{await ac.resume()}catch{}paused=false;setPauseUi(false);raf=requestAnimationFrame(scoreLoop)}
    };
  }
  if(baseFinish){
    finish=function(){if(active){void handleTrackEnd();return}return baseFinish()};
  }

  document.querySelector("#tempo")?.addEventListener("input",()=>{if(active)updateSongLabels()});
  globalThis.DruMasterScorePlayback={isActive:()=>active,getLoopMode:()=>loopMode,seekTo:sec=>restartAt(sec,!paused),next:()=>switchSong(1),previous:()=>switchSong(-1)};
})();