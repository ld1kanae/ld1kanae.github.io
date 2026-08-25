"use strict";

(()=>{
  const song=globalThis.DruMasterSongs?.current;
  if(!song||typeof startGame!=="function")return;

  function trackGain(name,fallback){
    const v=song.mix?.[name];
    return Number.isFinite(v)?v:fallback;
  }
  function playAt(buf,gain,when,offset=0){
    const source=ac.createBufferSource(),g=ac.createGain();
    source.buffer=buf;
    source.playbackRate.value=rate;
    g.gain.value=gain;
    source.connect(g).connect(masterBus);
    source.start(when,Math.max(0,offset));
    return source;
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

      rate=+$("#tempo").value/100;
      autoplay=$("#autoToggle").checked;
      notes.forEach(n=>n.hit=false);
      score=0;
      counts={perfect:0,great:0,good:0,miss:0};
      nextKick=0;nextAuto=0;missCursor=0;

      setup.classList.add("hidden");
      result.classList.add("hidden");
      result.classList.toggle("autoplay",autoplay);
      game.classList.remove("hidden");
      $("#score").textContent=autoplay?"AUTO":"000000";

      const startAt=ac.currentTime+.055;
      const configuredOffset=Number(song.playback?.stemOffsetSec);
      const stemOffset=Number.isFinite(configuredOffset)?Math.max(0,configuredOffset):0;
      playAt(buffers.base,trackGain("base",.95),startAt,stemOffset);
      if($("#vocalToggle").checked)playAt(buffers.vocals,trackGain("vocals",.95),startAt,stemOffset);
      if($("#guideToggle").checked)playAt(buffers.drums,trackGain("drums",.70),startAt,stemOffset);

      startedAt=startAt;
      running=true;
      paused=false;
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

  const start=document.querySelector("#start");
  if(start)start.onclick=startGame;
})();