"use strict";
(()=>{
  const api=globalThis.DruMasterSongs;
  if(!api)return;
  let live=api.current;
  Object.defineProperty(api,"current",{
    configurable:true,
    enumerable:true,
    get(){return live},
    set(song){
      live=song;
      queueMicrotask(()=>globalThis.DruMasterSongSource?.applySourceAvailability?.(song));
    }
  });
})();
