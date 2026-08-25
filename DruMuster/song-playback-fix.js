"use strict";

(()=>{
  const song=globalThis.DruMasterSongs?.current;
  if(!song)return;

  /* Shift gameplay time later without adding latency to manual drum hits.
     This moves chart timing, AUTO and auto-kick scheduling together. */
  if(typeof current==="function"&&song.timingOffsetSec){
    const nativeCurrent=current;
    current=function(){
      return Math.max(0,nativeCurrent()-song.timingOffsetSec);
    };
  }

  /* Apply per-song stem mix and measured guide-drum alignment. */
  if(typeof playBuffer==="function"){
    const nativePlayBuffer=playBuffer;
    playBuffer=function(buf,gain){
      const mix=song.mix||{},delays=song.stemDelaySec||{};
      let stem=null;
      if(typeof buffers!=="undefined"){
        if(buf===buffers.base)stem="base";
        else if(buf===buffers.vocals)stem="vocals";
        else if(buf===buffers.drums)stem="drums";
      }
      if(stem&&Number.isFinite(mix[stem]))gain=mix[stem];
      const delay=stem&&Number.isFinite(delays[stem])?Math.max(0,delays[stem]):0;
      if(!delay)return nativePlayBuffer(buf,gain);

      const source=ac.createBufferSource(),g=ac.createGain();
      source.buffer=buf;
      source.playbackRate.value=rate;
      g.gain.value=gain;
      source.connect(g).connect(masterBus);
      source.start(ac.currentTime+delay);
      return source;
    };
  }
})();
