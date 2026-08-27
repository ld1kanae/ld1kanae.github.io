"use strict";

(()=>{
  const button=document.querySelector("#scoreLoop");
  if(!button)return;

  let syncing=false;
  const sync=()=>{
    if(syncing||button.textContent==="↻")return;
    syncing=true;
    button.textContent="↻";
    syncing=false;
  };

  const observer=new MutationObserver(sync);
  observer.observe(button,{childList:true,characterData:true,subtree:true});
  button.addEventListener("click",()=>queueMicrotask(sync));
  sync();
})();
