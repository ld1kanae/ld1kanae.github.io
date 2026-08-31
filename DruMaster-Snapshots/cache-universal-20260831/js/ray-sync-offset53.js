"use strict";
(()=>{
  const apply=()=>{
    const input=document.querySelector("#offset"),readout=document.querySelector("#offsetReadout"),reset=document.querySelector("#resetOffset"),prod=document.querySelector("#productionCode");
    if(!input)return;
    input.value="5.3";
    input.dispatchEvent(new Event("change",{bubbles:true}));
    if(readout)readout.textContent="+5.3 ms";
    if(reset){
      reset.textContent="本番値 5.3ms";
      reset.onclick=()=>{input.value="5.3";input.dispatchEvent(new Event("change",{bubbles:true}))};
    }
    document.querySelectorAll(".info-grid dd").forEach(dd=>{if(dd.textContent.trim()==="+21.5 ms")dd.textContent="+5.3 ms"});
    if(prod)prod.textContent="playback:{stemOffsetSec:.0053}";
  };
  if(document.readyState==="loading")addEventListener("DOMContentLoaded",apply,{once:true});else apply();
})();
