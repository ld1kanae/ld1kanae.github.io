"use strict";

(()=>{
  if(typeof flashPart!=="function")return;
  const fxByTarget=new WeakMap();

  // Keep the performance-friendly reusable span, but restore the calibrated
  // strike-light origins that were previously defined on each .hit::after.
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
      pointerEvents:"none",background:"radial-gradient(circle,#fff 0 8%,#9ce8ffcc 24%,transparent 67%)",
      boxShadow:"0 0 28px #6cd7ff,0 0 42px rgba(108,215,255,.34)",zIndex:"1"
    });
    target.appendChild(fx);
    slot={fx,animation:null};
    fxByTarget.set(target,slot);
    return slot;
  }

  flashPart=function(part,el){
    const target=targetFor(part,el);
    if(!target)return;
    const slot=ensureFx(target);
    slot.animation?.cancel();
    slot.animation=slot.fx.animate([
      {opacity:1,transform:"translate(-50%,-50%) scale(.4)"},
      {opacity:0,transform:"translate(-50%,-50%) scale(1.5)"}
    ],{duration:240,easing:"ease-out"});
  };
})();
