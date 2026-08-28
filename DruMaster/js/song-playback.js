"use strict";

(()=>{
  const song=globalThis.DruMasterSongs?.current;
  if(!song||typeof startGame!=="function")return;

  const activeStemVoices=new Set();
  const fullMixOnly=()=>globalThis.DruMasterSongSource?.isFullMixOnly?.()||false;

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
    return Number.isFinite(configuredOffset)?configuredOffset:0;
  }
  function startStemSet(startAt){
    /* Positive offset advances the source by skipping its beginning. Negative
       offset delays the whole source. This preserves Ray's existing +2 ms
       meaning while allowing the publisher editor to correct in both directions. */
    const offset=stemOffset(),when=startAt+Math.max(0,-offset),sourceOffset=Math.max(0,offset);
    if(fullMixOnly()){
      playAt(buffers.fullmix,trackGain("fullmix",.95),when,sourceOffset);
      return;
    }
    playAt(buffers.base,trackGain("base",.95),when,sourceOffset);
    if($("#vocalToggle").checked)playAt(buffers.vocals,trackGain("vocals",.95),when,sourceOffset);
    if($("#guideToggle").checked)playAt(buffers.drums,trackGain("drums",.70),when,sourceOffset);
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
      globalThis.DruMasterPauseIcon?.render?.(isPaused?"play":"pause");
      pauseButton.setAttribute("aria-label",isPaused?"再生を再開":"一時停止");
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
      if(typeof img.decode==="function"){try{await img.decode()}catch{}}
    }));
    try{await globalThis.DruMasterChartTimingReady}catch{}
    try{await document.fonts?.ready}catch{}
  }

  startGame=async function(){
    if(loading)return;
    loading=true;
    $("#start").disabled=true;
    try{
      await ac.resume();
      if(fullMixOnly()){
        await loadStem("fullmix","原曲");
      }else{
        await loadStem("base","オフボーカル");
        if($("#vocalToggle").checked)await loadStem("vocals","ボーカル");
        if($("#guideToggle").checked)await loadStem("drums","ガイドドラム");
      }
      try{await globalThis.DruMasterResultFanfare?.prepare?.()}
      catch(e){console.warn("Result fanfare preload failed",e)}
      await finishVisualPreload();

      duration=Math.max(0,(Number(song.duration)||duration)-.5);
      rate=+$("#tempo").value/100;
      autoplay=$("#autoToggle").checked;
      resetRunState();

      setup.classList.add("hidden");
      result.classList.add("hidden");
      result.classList.toggle("autoplay",autoplay);
      game.classList.remove("hidden");

      globalThis.DruMasterResultFanfare?.stop?.();
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

  globalThis.DruMasterPlaybackControl={restartFromBeginning,endCurrentRun,stopRunAudio};
})();