"use strict";

(()=>{
  function updateRange(el){
    const min=Number(el.min||0),max=Number(el.max||100),value=Number(el.value||0);
    const span=max-min;
    const progress=span>0?Math.max(0,Math.min(100,(value-min)/span*100)):0;
    el.style.setProperty("--dm-tool-range-progress",`${progress}%`);
    el.style.setProperty("--dm-tool-range-mid",`${progress*.52}%`);
  }

  function bindRange(el){
    if(el.dataset.dmToolRangeBound==="1"){
      updateRange(el);
      return;
    }
    el.dataset.dmToolRangeBound="1";
    const sync=()=>updateRange(el);
    el.addEventListener("input",sync);
    el.addEventListener("change",sync);
    updateRange(el);
  }

  function scan(){
    document.querySelectorAll('input[type="range"]').forEach(bindRange);
  }

  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",scan,{once:true});
  else scan();

  const observer=new MutationObserver(scan);
  observer.observe(document.documentElement,{childList:true,subtree:true});
  setTimeout(scan,0);
  setTimeout(scan,300);
})();
