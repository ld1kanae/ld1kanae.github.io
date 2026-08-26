"use strict";

(()=>{
  /* Real-time playback must never compete with network work. All required song
     data is fetched and decoded before running becomes true. Network access is
     restored while paused and after finish so future sync/admin work remains
     possible outside the timing-critical section. */
  const isPlaybackLocked=()=>{
    try{
      return typeof running!=="undefined"&&typeof paused!=="undefined"&&running&&!paused;
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
