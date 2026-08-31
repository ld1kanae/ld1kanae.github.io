"use strict";

(()=>{
  if(typeof flashPart!=="function")return;
  const fxByTarget=new WeakMap();

  const ORIGINS={
    "crash left":["61.1%","79.1%"],
    "crash right":["34.6%","78.6%"],
    hh:["69.9%","64.9%"],
    ride:["30.1%","55.9%"],
    high:["49.9%","52%"],
    mid:["52.1%","44.9%"],
    snare:["44.4%","43.5%"],
    floor:["55.9%","45.6%"],
    special:["50%","50%"]
  };

  function targetFor(part,el){
    return el||document.querySelector(`#hitLayer [data-part="${part}"]:not(.inactive)`);
  }

  function originFor(target){
    if(target.classList.contains("crash")){
      return target.classList.contains("right")?ORIGINS["crash right"]:ORIGINS["crash left"];
    }
    for(const name of["hh","ride","high","mid","snare","floor","special"]){
      if(target.classList.contains(name))return ORIGINS[name];
    }
    return["50%","50%"];
  }

  function ensureFx(target){
    let slot=fxByTarget.get(target);
    if(slot)return slot;
    const fx=document.createElement("span");
    const [left,top]=originFor(target);
    fx.setAttribute("aria-hidden","true");
    Object.assign(fx.style,{
      position:"absolute",left,top,width:"42%",aspectRatio:"1",
      borderRadius:"50%",transform:"translate(-50%,-50%) scale(.7)",opacity:"0",
      pointerEvents:"none",background:"radial-gradient(circle,#fff 0 10%,rgba(170,255,244,.98) 25%,rgba(82,223,207,.48) 47%,rgba(108,215,255,.18) 58%,transparent 70%)",
      boxShadow:"0 0 34px rgba(108,215,255,1),0 0 52px rgba(82,223,207,.72),0 0 72px rgba(82,223,207,.28)",zIndex:"1"
    });
    target.appendChild(fx);
    slot={fx,animation:null};
    fxByTarget.set(target,slot);
    return slot;
  }

  function rawFlashPart(part,el){
    const target=targetFor(part,el);
    if(!target)return;
    const slot=ensureFx(target);
    slot.animation?.cancel();
    slot.animation=slot.fx.animate([
      {opacity:1,transform:"translate(-50%,-50%) scale(.4)"},
      {opacity:0,transform:"translate(-50%,-50%) scale(1.5)"}
    ],{duration:240,easing:"ease-out"});
  }

  flashPart=rawFlashPart;

  /* Performance-test-only raw entry point. judgement.js later wraps the global
     flashPart() to add goal-line feedback; score playback already emits that
     feedback separately, so it needs the raw reusable kit flash without a
     second judgement pass or a forced layout. */
  globalThis.DruMasterHitFlash={flash:rawFlashPart};
})();
