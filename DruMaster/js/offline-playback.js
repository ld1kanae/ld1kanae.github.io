"use strict";

(()=>{
  /* Real-time gameplay must never compete with network work. Ranking Internet
     sync is armed only by the transition into RESULT, and all network APIs stay
     blocked for the entire active run, including pause. */
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

  globalThis.DruMasterOfflinePlayback={isLocked:isPlaybackLocked};
})();

// Web, Windows and Android all load the exact same local-first ranking engine.
// During document parsing, synchronous tags guarantee that old cached dynamic
// loaders later in the page cannot race ahead and install a previous client.
(()=>{
  const rankingSrc='js/ranking-sync.js?v=20260914-resultonly1';
  const bridgeSrc='js/ranking-best-bridge.js?v=20260907-unified2';

  if(document.readyState==='loading'){
    if(!globalThis.DruMasterRanking&&!document.querySelector('script[data-drumaster-ranking-sync]')){
      document.write(`<script src="${rankingSrc}" data-drumaster-ranking-sync="1"><\/script>`);
    }
    if(!document.querySelector('script[data-drumaster-ranking-bridge]')){
      document.write(`<script src="${bridgeSrc}" data-drumaster-ranking-bridge="1"><\/script>`);
    }
    return;
  }

  const loadBridge=()=>{
    if(document.querySelector('script[data-drumaster-ranking-bridge]'))return;
    const b=document.createElement('script');
    b.src=bridgeSrc;
    b.dataset.drumasterRankingBridge='1';
    document.head.appendChild(b);
  };

  if(globalThis.DruMasterRanking){
    loadBridge();
    return;
  }
  if(document.querySelector('script[data-drumaster-ranking-sync]')){
    const wait=()=>globalThis.DruMasterRanking?loadBridge():setTimeout(wait,20);
    wait();
    return;
  }
  const s=document.createElement('script');
  s.src=rankingSrc;
  s.async=false;
  s.dataset.drumasterRankingSync='1';
  s.onload=loadBridge;
  document.head.appendChild(s);
})();
