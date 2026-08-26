"use strict";

(()=>{
  if(typeof playDrum!=="function")return;
  const basePlayDrum=playDrum;

  function flashKick(){
    const fx=document.querySelector("#kickFx");
    if(!fx)return;
    fx.classList.remove("hit","auto-hit");
    void fx.offsetWidth;
    fx.classList.add("hit");
  }

  /* Kick playback is automatic in both normal play and AUTO mode. Trigger the
     visual from the common audio path so every actually-played bass-drum note
     produces the same effect. Queue it after the current call stack so app.js's
     legacy same-frame class toggle cannot cancel the restart. */
  playDrum=function(note,type,v=.75){
    const out=basePlayDrum(note,type,v);
    if(type==="kick")queueMicrotask(flashKick);
    return out;
  };
})();
