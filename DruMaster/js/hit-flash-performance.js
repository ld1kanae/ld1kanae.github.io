"use strict";

(()=>{
  if(typeof flashPart!=="function")return;
  const fxByTarget=new WeakMap();

  function targetFor(part,el){
    return el||document.querySelector(`#hitLayer [data-part="${part}"]:not(.inactive)`);
  }

  function ensureFx(target){
    let slot=fxByTarget.get(target);
    if(slot)return slot;
    const fx=document.createElement("span");
    fx.setAttribute("aria-hidden","true");
    Object.assign(fx.style,{
      position:"absolute",left:"50%",top:"50%",width:"42%",aspectRatio:"1",
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
