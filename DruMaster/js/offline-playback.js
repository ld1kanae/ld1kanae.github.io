"use strict";

(()=>{
  /* Real-time gameplay must never compete with network work. The ranking client
     now syncs only at startup and after RESULT, so no ranking request needs to be
     held open during a run. All network APIs are simply blocked while playing. */
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

// One shared client is used by Web, Windows and Android. It owns the single
// durable local play database and performs event-driven cloud delta sync.
(()=>{
  if(globalThis.DruMasterRanking||document.querySelector('script[data-drumaster-ranking-sync]'))return;
  const s=document.createElement('script');
  s.src='js/ranking-sync.js?v=20260907-localfirst1';
  s.async=false;
  s.dataset.drumasterRankingSync='1';
  document.head.appendChild(s);
})();
