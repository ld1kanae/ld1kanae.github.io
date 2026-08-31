"use strict";

(()=>{
  const node=document.querySelector("#score");
  if(!node)return;
  const numeric=s=>/^\d+$/.test(String(s||"").trim())?Number(String(s).trim()):null;
  let previous=numeric(node.textContent)??0,animation=null;

  function flash(){
    animation?.cancel();
    animation=node.animate([
      {filter:"brightness(1)",textShadow:"0 0 10px #71c8ff99",transform:"scale(1)",offset:0},
      {filter:"brightness(1.85)",textShadow:"0 0 2px #fff,0 0 8px #9eeaff,0 0 18px #6aaeff,0 0 28px #b57cff",transform:"scale(1.11)",offset:.18},
      {filter:"brightness(1.35)",textShadow:"0 0 2px #fff,0 0 10px #71dfff,0 0 20px #8a7cff",transform:"scale(1.035)",offset:.48},
      {filter:"brightness(1)",textShadow:"0 0 10px #71c8ff99",transform:"scale(1)",offset:1}
    ],{duration:280,easing:"cubic-bezier(.16,.84,.24,1)"});
  }

  new MutationObserver(()=>{
    const value=numeric(node.textContent);
    if(value===null)return;
    if(value>previous)flash();
    previous=value;
  }).observe(node,{childList:true,characterData:true,subtree:true});
})();
