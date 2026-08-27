"use strict";

(()=>{
  const select=document.querySelector("#performanceModeSelect");
  if(!select)return;
  if(![...select.options].some(o=>o.value==="score")){
    const opt=document.createElement("option");
    opt.value="score";
    opt.textContent="楽譜再生";
    select.appendChild(opt);
  }

  const touchCapable=(navigator.maxTouchPoints||0)>0||matchMedia("(any-pointer:coarse)").matches||matchMedia("(pointer:coarse)").matches;
  if(!touchCapable){
    for(const value of ["touch","pad"]){
      const opt=[...select.options].find(o=>o.value===value);if(opt){opt.hidden=true;opt.disabled=true}
    }
  }

  const hidden=document.querySelector("#hiddenToggle"),auto=document.querySelector("#autoToggle");
  let scoreLocked=false;
  function sync(){
    const score=select.value==="score";
    document.body.dataset.scoreModeSelected=score?"1":"0";
    if(score){
      scoreLocked=true;
      for(const t of [hidden,auto]){
        if(!t)continue;
        if(t.checked){t.checked=false;t.dispatchEvent(new Event("change",{bubbles:true}))}
        t.disabled=true;
      }
    }else if(scoreLocked){
      scoreLocked=false;
      if(select.value==="normal")for(const t of [hidden,auto])if(t)t.disabled=false;
    }
  }
  select.addEventListener("change",sync);
  sync();
})();
