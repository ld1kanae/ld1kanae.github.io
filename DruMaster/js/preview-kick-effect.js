"use strict";

(()=>{
  const baseFlashPart=typeof flashPart==="function"?flashPart:null;
  let kickAnimation=null;

  function flashKick(){
    const fx=document.querySelector("#kickFx");
    if(!fx)return;
    fx.classList.remove("hit","auto-hit");
    kickAnimation?.cancel();
    kickAnimation=fx.animate([
      {opacity:.9,transform:"translate(-50%,-50%) scale(.4)"},
      {opacity:0,transform:"translate(-50%,-50%) scale(1.5)"}
    ],{duration:240,easing:"ease-out"});
  }

  /* Preview has no drum-audio playback path, so mirror production's kick
     feedback from the chart-hit path. This wrapper loads after the optimized
     flashPart implementation so kick cannot be swallowed by the generic
     hit-target lookup. */
  flashPart=function(part,el){
    if(part==="kick"){
      flashKick();
      return;
    }
    return baseFlashPart?.(part,el);
  };
})();
