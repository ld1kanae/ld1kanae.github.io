"use strict";

(()=>{
  const nativeMatchMedia=window.matchMedia.bind(window);
  const legacyMobileQuery="(hover:none) and (pointer:coarse) and (max-width:900px)";
  const compact=s=>String(s||"").replace(/\s+/g,"").toLowerCase();
  const legacyCompact=compact(legacyMobileQuery);

  function isTouchCapable(){
    return (navigator.maxTouchPoints||0)>0 ||
      nativeMatchMedia("(any-pointer:coarse)").matches ||
      nativeMatchMedia("(pointer:coarse)").matches;
  }

  /* Performance mode used to equate 'mobile' with <=900 CSS px. In landscape
     that disables touch input on perfectly valid phones/tablets. Preserve the
     old query everywhere else, but make its JS .matches true on real touch
     hardware regardless of viewport width. CSS media queries are untouched. */
  window.matchMedia=function(query){
    const list=nativeMatchMedia(query);
    if(compact(query)!==legacyCompact || !isTouchCapable())return list;
    return new Proxy(list,{
      get(target,prop){
        if(prop==="matches")return true;
        const value=Reflect.get(target,prop,target);
        return typeof value==="function"?value.bind(target):value;
      }
    });
  };

  globalThis.DruMasterTouchCapable=isTouchCapable;

  function installTouchInput(){
    const game=document.querySelector("#game"),mode=document.querySelector("#performanceModeSelect");
    if(!game||!mode)return;
    game.style.touchAction="none";

    document.addEventListener("pointerdown",e=>{
      if(!isTouchCapable() || e.pointerType==="mouse")return;
      if(!game.contains(e.target))return;
      if(mode.value!=="touch")return;
      if(e.target.closest("#pause,#pausePanel button,.mic-debug-controls,button:not(.hit),select,input"))return;
      const api=globalThis.DruMasterPerformanceMode;
      if(!api || api.getRunMode?.()!=="touch")return;
      const ok=api.consumeNearest?.();
      if(!ok)return;
      e.preventDefault();
      e.stopImmediatePropagation();
    },true);
  }

  if(document.readyState==="loading")addEventListener("DOMContentLoaded",()=>setTimeout(installTouchInput,0),{once:true});
  else setTimeout(installTouchInput,0);
})();
