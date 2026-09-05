"use strict";

(()=>{
  /* Real-time gameplay must never compete with network work. All required song
     data is fetched and decoded before running becomes true. Once a run starts,
     keep normal network access disabled for the entire run, including pause.

     Ranking sync is special: it is allowed to be requested by the ranking layer,
     but the actual fetch is deferred until gameplay ends. This avoids treating
     the intentional gameplay network lock as a ranking-sync failure while still
     guaranteeing that no ranking network traffic competes with gameplay. */
  const RANKING_API_PREFIX="https://drumaster-ranking-api.aoka45utau.workers.dev/";

  const isPlaybackLocked=()=>{
    try{
      return typeof running!=="undefined"&&running;
    }catch{return false}
  };

  const blockedError=()=>new DOMException("Network access is disabled during gameplay","InvalidStateError");

  function requestUrl(input){
    try{
      if(typeof input==="string")return new URL(input,location.href).href;
      if(input instanceof URL)return input.href;
      if(input&&typeof input.url==="string")return new URL(input.url,location.href).href;
    }catch{}
    return "";
  }

  const isRankingRequest=input=>requestUrl(input).startsWith(RANKING_API_PREFIX);

  function setRankingStatusHidden(hidden){
    const el=document.getElementById("rankingSyncState");
    if(el)el.style.display=hidden?"none":"";
  }

  function waitForPlaybackUnlock(){
    return new Promise(resolve=>{
      const check=()=>{
        if(!isPlaybackLocked()){
          setRankingStatusHidden(false);
          resolve();
          return;
        }
        setTimeout(check,150);
      };
      check();
    });
  }

  const baseFetch=globalThis.fetch?.bind(globalThis);
  if(baseFetch){
    globalThis.fetch=function(input,init){
      if(!isPlaybackLocked())return baseFetch(input,init);

      // Ranking sync may be scheduled by its retry timer while a song is being
      // played. Keep it pending rather than failing; execute immediately after
      // the run finishes and the network lock is released.
      if(isRankingRequest(input)){
        setRankingStatusHidden(true);
        return waitForPlaybackUnlock().then(()=>baseFetch(input,init));
      }

      return Promise.reject(blockedError());
    };
  }

  if(globalThis.XMLHttpRequest?.prototype?.send){
    const baseSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(...args){
      if(isPlaybackLocked())throw blockedError();
      return baseSend.apply(this,args);
    };
  }

  if(globalThis.navigator?.sendBeacon){
    const baseBeacon=navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon=function(...args){
      if(isPlaybackLocked())return false;
      return baseBeacon(...args);
    };
  }

  globalThis.DruMasterOfflinePlayback={
    isLocked:isPlaybackLocked
  };
})();
