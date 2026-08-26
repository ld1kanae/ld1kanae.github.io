"use strict";

(()=>{
  if(typeof playDrum!=="function")return;
  const basePlayDrum=playDrum;
  let kickAnimation=null;

  function flashKick(){
    const fx=document.querySelector("#kickFx");
    if(!fx)return;
    fx.classList.remove("hit","auto-hit");
    kickAnimation?.cancel();
    kickAnimation=fx.animate([
      {opacity:.8,transform:"translate(-50%,-50%) scale(.4)"},
      {opacity:0,transform:"translate(-50%,-50%) scale(1.5)"}
    ],{duration:240,easing:"ease-out"});
  }

  /* Kick playback is automatic in both normal play and AUTO mode. Trigger the
     visual from the common audio path so every actually-played bass-drum note
     produces the same effect. Queue it after app.js's legacy same-frame class
     toggle, then replace that CSS animation with one Web Animation restart. */
  playDrum=function(note,type,v=.75){
    const out=basePlayDrum(note,type,v);
    if(type==="kick")queueMicrotask(flashKick);
    return out;
  };
})();
