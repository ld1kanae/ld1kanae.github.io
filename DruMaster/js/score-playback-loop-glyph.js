"use strict";

(()=>{
  const SVG={
    previous:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5v14"/><path class="fill" d="M18 5.5 9 12l9 6.5z"/></svg>',
    next:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 5v14"/><path class="fill" d="m6 5.5 9 6.5-9 6.5z"/></svg>',
    repeat:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m17 4 3 3-3 3"/><path d="M4 11V9a2 2 0 0 1 2-2h14"/><path d="m7 20-3-3 3-3"/><path d="M20 13v2a2 2 0 0 1-2 2H4"/></svg>',
    repeatOne:'<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m17 4 3 3-3 3"/><path d="M4 11V9a2 2 0 0 1 2-2h14"/><path d="m7 20-3-3 3-3"/><path d="M20 13v2a2 2 0 0 1-2 2H4"/><path class="repeat-one-mark" d="m11.1 10.3 1.3-1v5.5"/></svg>',
  };
  const prev=document.querySelector("#scorePrev"),next=document.querySelector("#scoreNext"),loop=document.querySelector("#scoreLoop"),pause=document.querySelector("#pause"),controls=document.querySelector("#scorePlaybackControls");
  if(!pause)return;

  /* Keep the normal gameplay header structurally unchanged. Only while score
     playback is active, move Pause into the same flex row as Prev/Next/Repeat
     so all four buttons are governed by one gap value. */
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

  let syncing=false;
  const hasIcon=(el,name)=>el?.firstElementChild?.classList?.contains("transport-icon")&&el.dataset.icon===name;
  const setIcon=(el,name)=>{if(!el||hasIcon(el,name))return;el.dataset.icon=name;el.innerHTML=SVG[name]};
  const sync=()=>{
    if(syncing)return;syncing=true;
    syncGrouping();
    setIcon(prev,"previous");setIcon(next,"next");
    setIcon(loop,loop?.dataset.loop==="one"?"repeatOne":"repeat");
    /* Pause owns a dedicated always-white icon. Never inject the score
       transport SVG into it, even when the button moves into this row. */
    pause.querySelectorAll(":scope > .transport-icon").forEach(node=>node.remove());
    syncing=false;
  };
  const observer=new MutationObserver(sync);
  observer.observe(document.body,{attributes:true,attributeFilter:["data-score-playback"]});
  for(const el of [prev,next])if(el)observer.observe(el,{childList:true,characterData:true,subtree:true,attributes:true,attributeFilter:["aria-label"]});
  if(loop)observer.observe(loop,{childList:true,characterData:true,subtree:true,attributes:true,attributeFilter:["aria-label","data-loop"]});
  sync();
})();
