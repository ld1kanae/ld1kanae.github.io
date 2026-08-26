"use strict";

(()=>{
  const mobileQuery=matchMedia("(hover:none) and (pointer:coarse) and (max-width:900px)"),
        game=document.querySelector("#game");
  if(!mobileQuery.matches||!game)return;

  const layer=document.createElement("div");
  layer.id="mobileTapFxLayer";
  layer.setAttribute("aria-hidden","true");
  document.body.appendChild(layer);

  const POOL_SIZE=8,pool=[];
  let cursor=0;
  for(let i=0;i<POOL_SIZE;i++){
    const fx=document.createElement("span");
    fx.className="mobile-tap-hit-fx";
    fx.style.animation="none";
    fx.style.opacity="0";
    layer.appendChild(fx);
    pool.push({fx,animation:null});
  }

  function showAt(x,y){
    if(!Number.isFinite(x)||!Number.isFinite(y))return;
    const slot=pool[cursor++%POOL_SIZE],fx=slot.fx;
    slot.animation?.cancel();
    fx.style.left=`${x}px`;
    fx.style.top=`${y}px`;
    slot.animation=fx.animate([
      {opacity:.9,transform:"translate(-50%,-50%) scale(.4)"},
      {opacity:0,transform:"translate(-50%,-50%) scale(1.5)"}
    ],{duration:240,easing:"ease-out"});
  }

  function showElement(el){
    if(!(el instanceof Element))return;
    const r=el.getBoundingClientRect();
    showAt(r.left+r.width/2,r.top+r.height/2);
  }

  globalThis.DruMasterMobileTapEffect={showAt,showElement};

  /* Window capture runs before performance-mode's game capture handler, so
     touch feedback still appears when a nearest note consumes the event. */
  addEventListener("pointerdown",e=>{
    if(!mobileQuery.matches)return;
    const target=e.target;
    if(!(target instanceof Element)||!target.closest("#game"))return;
    if(target.closest("#pause,#pausePanel,#pausePanel button"))return;
    if(typeof running!=="undefined"&&!running)return;
    if(typeof paused!=="undefined"&&paused)return;
    showAt(e.clientX,e.clientY);
  },true);
})();
