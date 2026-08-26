"use strict";

(()=>{
  const mobileQuery=matchMedia("(hover:none) and (pointer:coarse) and (max-width:900px)"),
        game=document.querySelector("#game");
  if(!mobileQuery.matches||!game)return;

  const layer=document.createElement("div");
  layer.id="mobileTapFxLayer";
  layer.setAttribute("aria-hidden","true");
  document.body.appendChild(layer);

  function showAt(x,y){
    const fx=document.createElement("span");
    fx.className="mobile-tap-hit-fx";
    fx.style.left=`${x}px`;
    fx.style.top=`${y}px`;
    layer.appendChild(fx);
    const remove=()=>fx.remove();
    fx.addEventListener("animationend",remove,{once:true});
    setTimeout(remove,500);
  }

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
