"use strict";

(()=>{
  const URL="assets/fanfare_01.mp3";
  let buffer=null,loadingPromise=null,voice=null,gainNode=null;

  async function prepare(){
    if(buffer)return buffer;
    if(loadingPromise)return loadingPromise;
    if(typeof ac==="undefined"||!ac)throw Error("AudioContext is not ready");
    loadingPromise=(async()=>{
      const response=await fetch(URL,{cache:"force-cache"});
      if(!response.ok)throw Error(`リザルトファンファーレを取得できません（HTTP ${response.status}）`);
      const encoded=await response.arrayBuffer();
      buffer=await ac.decodeAudioData(encoded.slice(0));
      return buffer;
    })();
    try{return await loadingPromise}
    catch(e){loadingPromise=null;throw e}
  }

  function stop(){
    if(voice){
      try{voice.onended=null;voice.stop()}catch{}
      try{voice.disconnect()}catch{}
    }
    try{gainNode?.disconnect()}catch{}
    voice=null;gainNode=null;
  }

  function startPrepared(){
    if(!buffer||typeof ac==="undefined"||!ac)return false;
    stop();
    try{
      const source=ac.createBufferSource(),gain=ac.createGain();
      source.buffer=buffer;
      gain.gain.value=.7;
      source.connect(gain).connect(typeof masterBus!=="undefined"&&masterBus?masterBus:ac.destination);
      source.onended=()=>{
        if(voice!==source)return;
        try{source.disconnect()}catch{}
        try{gain.disconnect()}catch{}
        voice=null;gainNode=null;
      };
      voice=source;gainNode=gain;
      source.start(ac.currentTime);
      return true;
    }catch(e){
      console.warn("Result fanfare playback failed",e);
      stop();
      return false;
    }
  }

  function play(){
    if(!buffer||typeof ac==="undefined"||!ac)return false;
    if(ac.state==="running")return startPrepared();
    ac.resume().then(startPrepared,e=>console.warn("Result fanfare resume failed",e));
    return true;
  }

  globalThis.DruMasterResultFanfare={prepare,play,stop,isReady:()=>!!buffer};
})();
