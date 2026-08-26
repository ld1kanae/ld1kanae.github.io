"use strict";

(()=>{
  if(typeof playDrum!=="function")return;
  const basePlayDrum=playDrum;

  function flashAutoKick(){
    const fx=document.querySelector("#kickFx");
    if(!fx)return;
    fx.classList.remove("auto-hit");
    void fx.offsetWidth;
    fx.classList.add("auto-hit");
  }

  playDrum=function(note,type,v=.75){
    const out=basePlayDrum(note,type,v);
    if(type==="kick"&&typeof autoplay!=="undefined"&&autoplay)flashAutoKick();
    return out;
  };
})();
