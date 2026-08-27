"use strict";

(()=>{
  const prev=document.querySelector("#scorePrev"),next=document.querySelector("#scoreNext"),loop=document.querySelector("#scoreLoop");
  if(!prev||!next||!loop)return;

  let syncing=false;
  const sync=()=>{
    if(syncing)return;
    syncing=true;
    if(prev.textContent!=="◀")prev.textContent="◀";
    if(next.textContent!=="▶")next.textContent="▶";
    if(loop.textContent!=="↻")loop.textContent="↻";
    syncing=false;
  };

  const observer=new MutationObserver(sync);
  observer.observe(prev,{childList:true,characterData:true,subtree:true});
  observer.observe(next,{childList:true,characterData:true,subtree:true});
  observer.observe(loop,{childList:true,characterData:true,subtree:true});
  loop.addEventListener("click",()=>queueMicrotask(sync));
  sync();
})();
