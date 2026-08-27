"use strict";

(()=>{
  const SVG={
    previous:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5v14"/><path class="fill" d="M18 5.5 9 12l9 6.5z"/></svg>',
    next:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 5v14"/><path class="fill" d="m6 5.5 9 6.5-9 6.5z"/></svg>',
    loop:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M7.5 7h8.2c2.2 0 4 1.8 4 4v.4"/><path d="m16.7 4 3 3-3 3"/><path d="M16.5 17H8.3c-2.2 0-4-1.8-4-4v-.4"/><path d="m7.3 20-3-3 3-3"/></svg>',
    pause:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true"><rect class="fill" x="7" y="5" width="3.5" height="14" rx="1"/><rect class="fill" x="13.5" y="5" width="3.5" height="14" rx="1"/></svg>',
    play:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true"><path class="fill" d="M8 5.5 18 12 8 18.5z"/></svg>'
  };
  const prev=document.querySelector("#scorePrev"),next=document.querySelector("#scoreNext"),loop=document.querySelector("#scoreLoop"),pause=document.querySelector("#pause");
  if(!pause)return;
  let syncing=false;
  const hasIcon=(el,name)=>el?.firstElementChild?.classList?.contains("transport-icon")&&el.dataset.icon===name;
  const setIcon=(el,name)=>{if(!el||hasIcon(el,name))return;el.dataset.icon=name;el.innerHTML=SVG[name]};
  const sync=()=>{
    if(syncing)return;syncing=true;
    setIcon(prev,"previous");setIcon(next,"next");setIcon(loop,"loop");
    setIcon(pause,pause.getAttribute("aria-label")==="再生を再開"?"play":"pause");
    syncing=false;
  };
  const observer=new MutationObserver(sync);
  for(const el of [prev,next,loop,pause])if(el)observer.observe(el,{childList:true,characterData:true,subtree:true,attributes:true,attributeFilter:["aria-label"]});
  sync();
})();
