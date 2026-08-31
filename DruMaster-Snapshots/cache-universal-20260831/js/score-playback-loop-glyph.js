"use strict";

(()=>{
  const SVG={
    previous:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 5v14"/><path class="fill" d="M18 5.5 9 12l9 6.5z"/></svg>',
    next:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M18 5v14"/><path class="fill" d="m6 5.5 9 6.5-9 6.5z"/></svg>',
    repeat:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m17 4 3 3-3 3"/><path d="M4 11V9a2 2 0 0 1 2-2h14"/><path d="m7 20-3-3 3-3"/><path d="M20 13v2a2 2 0 0 1-2 2H4"/></svg>',
    repeatOne:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m17 4 3 3-3 3"/><path d="M4 11V9a2 2 0 0 1 2-2h14"/><path d="m7 20-3-3 3-3"/><path d="M20 13v2a2 2 0 0 1-2 2H4"/><path class="repeat-one-mark" d="m11.1 10.3 1.3-1v5.5"/></svg>',
  };
  const prev=document.querySelector("#scorePrev"),next=document.querySelector("#scoreNext"),loop=document.querySelector("#scoreLoop"),pause=document.querySelector("#pause"),controls=document.querySelector("#scorePlaybackControls"),seek=document.querySelector("#scoreSeek");
  if(!pause)return;

  const pauseParent=pause.parentNode,pauseNext=pause.nextSibling;
  function syncGrouping(){
    const scoreActive=document.body.dataset.scorePlayback==="1";
    if(scoreActive){
      if(controls&&pause.parentNode!==controls)controls.appendChild(pause);
    }else if(pauseParent&&pause.parentNode!==pauseParent){
      const anchor=pauseNext&&pauseNext.parentNode===pauseParent?pauseNext:null;
      pauseParent.insertBefore(pause,anchor);
    }
  }

  let seekRaf=0;
  function syncSeekGradient(){
    if(!seek)return;
    const min=Number(seek.min||0),max=Number(seek.max||1),value=Number(seek.value||min);
    const pct=max===min?0:Math.max(0,Math.min(100,(value-min)/(max-min)*100));
    seek.style.setProperty("--score-range-progress",`${pct}%`);
    seek.style.setProperty("--score-range-mid",`${pct*.52}%`);
  }
  function stopSeekLoop(){if(seekRaf){cancelAnimationFrame(seekRaf);seekRaf=0}}
  function runSeekLoop(){
    stopSeekLoop();
    if(!seek)return;
    const tick=()=>{
      syncSeekGradient();
      if(document.body.dataset.scorePlayback==="1")seekRaf=requestAnimationFrame(tick);
      else seekRaf=0;
    };
    tick();
  }

  const removeDirectText=el=>{
    if(!el)return;
    for(const node of [...el.childNodes])if(node.nodeType===Node.TEXT_NODE)node.remove();
  };

  const hasIcon=(el,name)=>el?.querySelector(":scope > .transport-icon")&&el.dataset.icon===name;
  const setIcon=(el,name)=>{
    if(!el)return;
    removeDirectText(el);
    if(hasIcon(el,name))return;
    const template=document.createElement("template");
    template.innerHTML=SVG[name].trim();
    const icon=template.content.firstElementChild;
    const old=el.querySelector(":scope > .transport-icon");
    if(old)old.replaceWith(icon);else el.appendChild(icon);
    el.dataset.icon=name;
  };

  function syncPauseIcon(){
    removeDirectText(pause);
    pause.querySelectorAll(":scope > .transport-icon,:scope > .pause-transport-icon,:scope > .pause-css-icon").forEach(node=>node.remove());
    const state=pause.getAttribute("aria-label")==="再生を再開"?"play":"pause";
    if(globalThis.DruMasterPauseIcon?.render)globalThis.DruMasterPauseIcon.render(state);
    else pause.dataset.transportIcon=state;
  }

  let syncing=false;
  const sync=()=>{
    if(syncing)return;syncing=true;
    syncGrouping();
    setIcon(prev,"previous");
    setIcon(next,"next");
    setIcon(loop,loop?.dataset.loop==="one"?"repeatOne":"repeat");
    syncPauseIcon();
    if(document.body.dataset.scorePlayback==="1")runSeekLoop();else{stopSeekLoop();syncSeekGradient()}
    syncing=false;
  };

  const observer=new MutationObserver(sync);
  observer.observe(document.body,{attributes:true,attributeFilter:["data-score-playback"]});
  for(const el of [prev,next])if(el)observer.observe(el,{childList:true,characterData:true,subtree:true,attributes:true,attributeFilter:["aria-label"]});
  if(loop)observer.observe(loop,{childList:true,characterData:true,subtree:true,attributes:true,attributeFilter:["aria-label","data-loop"]});
  observer.observe(pause,{childList:true,characterData:true,subtree:true,attributes:true,attributeFilter:["aria-label"]});
  if(seek){seek.addEventListener("input",syncSeekGradient,{passive:true});seek.addEventListener("change",syncSeekGradient,{passive:true})}
  syncSeekGradient();
  sync();
})();
