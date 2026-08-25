"use strict";

(()=>{
  const node=document.querySelector("#score");
  if(!node)return;
  const numeric=s=>/^\d+$/.test(String(s||"").trim())?Number(String(s).trim()):null;
  let previous=numeric(node.textContent)??0;

  new MutationObserver(()=>{
    const value=numeric(node.textContent);
    if(value===null)return;
    if(value>previous){
      node.classList.remove("score-gain-flash");
      void node.offsetWidth;
      node.classList.add("score-gain-flash");
    }
    previous=value;
  }).observe(node,{childList:true,characterData:true,subtree:true});

  node.addEventListener("animationend",()=>node.classList.remove("score-gain-flash"));
})();
