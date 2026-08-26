"use strict";

(()=>{
  const song=globalThis.DruMasterSongs?.current;
  if(!song||typeof startGame!=="function")return;

  const activeStemVoices=new Set();

  function trackGain(name,fallback){
    const v=song.mix?.[name];
    return Number.isFinite(v)?v:fallback;
  }
  function playAt(buf,gain,when,offset=0){
    const source=ac.createBufferSource(),g=ac.createGain(),voice={source,gain:g};
    source.buffer=buf;
    source.playbackRate.value=rate;
    g.gain.value=gain;
    source.connect(g).connect(masterBus);
    activeStemVoices.add(voice);
    source.onended=()=>{
      activeStemVoices.delete(voice);
      try{source.disconnect()}catch{}
      try{g.disconnect()}catch{}
    };
    source.start(when,Math.max(0,offset));
    return source;
  }
  function stopStemVoices(){
    const now=ac?.currentTime||0;
    for(const voice of [...activeStemVoices]){
      activeStemVoices.delete(voice);
      try{voice.source.onended=null;voice.source.stop(now)}catch{}
      try{voice.source.disconnect()}catch{}
      try{voice.gain.disconnect()}catch{}
    }
  }
  function stopRunAudio(){
    stopStemVoices();
    globalThis.DruMasterAudioControl?.stopAllDrumVoices?.();
  }
  function stemOffset(){
    const configuredOffset=Number(song.playback?.stemOffsetSec);
    return Number.isFinite(configuredOffset)?Math.max(0,configuredOffset):0;
  }
  function startStemSet(startAt){
    const offset=stemOffset();
    playAt(buffers.base,trackGain("base",.95),startAt,offset);
    if($("#vocalToggle").checked)playAt(buffers.vocals,trackGain("vocals",.95),startAt,offset);
    if($("#guideToggle").checked)playAt(buffers.drums,trackGain("drums",.70),startAt,offset);
  }
  function resetRunState(){
    notes.forEach(n=>n.hit=false);
    score=0;
    counts={perfect:0,great:0,good:0,miss:0};
    nextKick=0;nextAuto=0;missCursor=0;
    const scoreNode=$("#score");
    if(scoreNode)scoreNode.textContent=autoplay?"AUTO":"000000";
    const fx=$("#judgementFx");
    fx?.classList.remove("play");
  }
  function setPauseUi(isPaused){
    $("#pausePanel")?.classList.toggle("hidden",!isPaused);
    const pauseButton=$("#pause");
    if(pauseButton){
      pauseButton.textContent=isPaused?"▶":"Ⅱ";
      pauseButton.setAttribute("aria-label",isPaused?"再生を再開":"再生を停止");
    }
  }
  async function restartFromBeginning(){
    if(!running)return;
    cancelAnimationFrame(raf);
    stopRunAudio();
    resetRunState();
    try{await ac.resume()}catch{}
    const startAt=ac.currentTime+.055;
    startStemSet(startAt);
    startedAt=startAt;
    paused=false;
    running=true;
    setPauseUi(false);
    resize();
    loop();
  }
  function endCurrentRun(){
    if(!running)return;
    cancelAnimationFrame(raf);
    stopRunAudio();
    paused=false;
    setPauseUi(false);
    if(typeof finish==="function")finish();
  }
  function installPauseActions(){
    const panel=$("#pausePanel"),resume=$("#resume"),restart=$("#quit");
    if(!panel||!resume||!restart)return;
    resume.textContent="演奏を再開";
    restart.textContent="最初から";
    restart.setAttribute("aria-label","曲頭から演奏をやり直す");
    let end=$("#endRun");
    if(!end){
      end=document.createElement("button");
      end.id="endRun";
      end.type="button";
      end.textContent="終了";
      end.setAttribute("aria-label","現在のスコアで演奏を終了する");
      restart.insertAdjacentElement("afterend",end);
    }
    restart.onclick=()=>{void restartFromBeginning()};
    end.onclick=endCurrentRun;
  }
  async function finishVisualPreload(){
    const images=[...document.images];
    await Promise.all(images.map(async img=>{
      if(!img.complete){
        await new Promise(resolve=>{
          img.addEventListener("load",resolve,{once:true});
          img.addEventListener("error",resolve,{once:true});
        });
      }
      if(typeof img.decode==="function"){
        try{await img.decode()}catch{}
      }
    }));
    /* game-chart.js performs one timing-MIDI request during page setup. Await it
       explicitly so no already-started network request can overlap gameplay. */
    try{await globalThis.DruMasterChartTimingReady}catch{}
    try{await document.fonts?.ready}catch{}
  }

  /* All stems share one AudioContext timestamp. Per-song source offsets live in
     song-manager.js so timing adjustments do not require editing playback code. */
  startGame=async function(){
    if(loading)return;
    loading=true;
    $("#start").disabled=true;
    try{
      await ac.resume();
      await loadStem("base","オフボーカル");
      if($("#vocalToggle").checked)await loadStem("vocals","ボーカル");
      if($("#guideToggle").checked)await loadStem("drums","ガイドドラム");
      /* Ensure static artwork/font requests are also finished before the timing-
         critical section begins. No resource load is intentionally left active. */
      await finishVisualPreload();

      /* app.js's legacy loop waits until duration + 0.5s before finish().
         Rebuild this value from the song config on every run so repeated RETRY
         actions do not shorten the song by another 0.5s each time. */
      duration=Math.max(0,(Number(song.duration)||duration)-.5);

      rate=+$("#tempo").value/100;
      autoplay=$("#autoToggle").checked;
      resetRunState();

      setup.classList.add("hidden");
      result.classList.add("hidden");
      result.classList.toggle("autoplay",autoplay);
      game.classList.remove("hidden");

      stopRunAudio();
      const startAt=ac.currentTime+.055;
      startStemSet(startAt);

      startedAt=startAt;
      running=true;
      paused=false;
      setPauseUi(false);
      resize();
      loop();
    }catch(e){
      console.error(e);
      $("#loadState").textContent=e.message||"音源の読み込みに失敗しました";
      $("#start").disabled=false;
    }finally{
      loading=false;
    }
  };

  installPauseActions();
  const start=document.querySelector("#start");
  if(start)start.onclick=startGame;

  globalThis.DruMasterPlaybackControl={
    restartFromBeginning,
    endCurrentRun,
    stopRunAudio
  };
})();