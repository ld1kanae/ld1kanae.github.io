"use strict";

(()=>{
  /* Real-time gameplay must never compete with network work. All required song
     data is fetched and decoded before running becomes true. Once a run starts,
     keep network access disabled for the entire run, including pause, and only
     restore it after RESULT / HOME so nothing can wake the radio mid-session. */
  const isPlaybackLocked=()=>{
    try{
      return typeof running!=="undefined"&&running;
    }catch{return false}
  };

  const blockedError=()=>new DOMException("Network access is disabled during gameplay","InvalidStateError");

  const baseFetch=globalThis.fetch?.bind(globalThis);
  if(baseFetch){
    globalThis.fetch=function(input,init){
      if(isPlaybackLocked())return Promise.reject(blockedError());
      return baseFetch(input,init);
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
