"use strict";
(()=>{
  const apply=()=>{
    const input=document.querySelector("#offset"),readout=document.querySelector("#offsetReadout"),reset=document.querySelector("#resetOffset"),prod=document.querySelector("#productionCode");
    if(!input)return;
    input.value="2.0";
    input.dispatchEvent(new Event("change",{bubbles:true}));
    if(readout)readout.textContent="+2.0 ms";
    if(reset){
      reset.textContent="本番値 2.0ms";
      reset.onclick=()=>{input.value="2.0";input.dispatchEvent(new Event("change",{bubbles:true}))};
    }
    document.querySelectorAll(".info-grid dd").forEach(dd=>{if(/^[+-]?(21\.5|5\.3) ms$/.test(dd.textContent.trim()))dd.textContent="+2.0 ms"});
    if(prod)prod.textContent="playback:{stemOffsetSec:0.002}";
  };
  if(document.readyState==="loading")addEventListener("DOMContentLoaded",apply,{once:true});else apply();
})();
