"use strict";
(()=>{
  const apply=()=>{
    const input=document.querySelector("#offset"),readout=document.querySelector("#offsetReadout"),reset=document.querySelector("#resetOffset"),prod=document.querySelector("#productionCode");
    if(!input)return;
    input.value="0.0";
    input.dispatchEvent(new Event("change",{bubbles:true}));
    if(readout)readout.textContent="+0.0 ms";
    if(reset){
      reset.textContent="本番値 0.0ms";
      reset.onclick=()=>{input.value="0.0";input.dispatchEvent(new Event("change",{bubbles:true}))};
    }
    document.querySelectorAll(".info-grid dd").forEach(dd=>{if(/^[+-]?(21\.5|5\.3) ms$/.test(dd.textContent.trim()))dd.textContent="+0.0 ms"});
    if(prod)prod.textContent="playback:{stemOffsetSec:0}";
  };
  if(document.readyState==="loading")addEventListener("DOMContentLoaded",apply,{once:true});else apply();
})();
