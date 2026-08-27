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

  function lockForScore(toggle){
    if(!toggle)return;
    if(toggle.checked){toggle.checked=false;toggle.dispatchEvent(new Event("change",{bubbles:true}))}
    toggle.disabled=true;
    toggle.closest("label")?.classList.add("mode-locked");
  }

  function unlockAfterScore(toggle){
    if(!toggle)return;
    /* touch/pad modes manage these same controls in performance-mode-v5.js.
       Only normal mode should explicitly unlock them here. */
    if(select.value==="normal"){
      toggle.disabled=false;
      toggle.closest("label")?.classList.remove("mode-locked");
    }
  }

  function sync(){
    const score=select.value==="score";
    document.body.dataset.scoreModeSelected=score?"1":"0";
    if(score){
      scoreLocked=true;
      for(const t of [hidden,auto])lockForScore(t);
    }else if(scoreLocked){
      scoreLocked=false;
      for(const t of [hidden,auto])unlockAfterScore(t);
    }
  }
  select.addEventListener("change",sync);
  sync();

  /* settings-persistence.js runs after this file. If a phone-only mode was
     saved previously, normalize it after restore on non-touch desktop. */
  if(!touchCapable)setTimeout(()=>{
    if(select.value==="touch"||select.value==="pad"){
      select.value="normal";
      select.dispatchEvent(new Event("change",{bubbles:true}));
      globalThis.DruMasterSettings?.save?.();
    }
  },0);
})();
