"use strict";
(()=>{
  if(!matchMedia?.("(hover:hover) and (pointer:fine)")?.matches)return;

  const SELECTOR="#start,#pause,#scorePlaybackControls button,#pausePanel button,.result-actions button,.mic-cal-actions button";

  function stack(pos){
    const s=document.createElement("span");
    s.className=`glass-inner-stack ${pos}`;
    for(const cls of ["tail","shoulder","core"]){
      const i=document.createElement("i");
      i.className=cls;
      s.appendChild(i);
    }
    return s;
  }

  function enhance(button){
    if(!button||button.dataset.glassHoverFinal==="1")return;
    button.dataset.glassHoverFinal="1";

    button.prepend(stack("bottom"));
    button.prepend(stack("top"));

    const wrap=document.createElement("span");
    wrap.className="glass-hover-wrap";
    if(button.id==="start")wrap.classList.add("start-wrap");

    const glow=document.createElement("i");
    glow.className="glass-hover-drop";

    const parent=button.parentNode;
    parent.insertBefore(wrap,button);
    wrap.appendChild(glow);
    wrap.appendChild(button);
  }

  function scan(root=document){
    if(root.matches?.(SELECTOR))enhance(root);
    root.querySelectorAll?.(SELECTOR).forEach(enhance);
  }

  scan();
  new MutationObserver(records=>{
    for(const record of records)for(const node of record.addedNodes)if(node.nodeType===1)scan(node);
  }).observe(document.documentElement,{childList:true,subtree:true});
})();
