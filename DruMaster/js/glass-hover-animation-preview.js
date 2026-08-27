"use strict";
(()=>{
  const demos=[...document.querySelectorAll(".hover-demo")];
  const replay=document.querySelector("#replayNow");
  if(!demos.length)return;

  const ACTIVE_MS=1350;
  const INTERVAL_MS=3000;
  let timer=0;
  const removers=new WeakMap();

  function pulse(el){
    const old=removers.get(el);
    if(old)clearTimeout(old);
    el.classList.remove("demo-active");
    void el.offsetWidth;
    el.classList.add("demo-active");
    removers.set(el,setTimeout(()=>el.classList.remove("demo-active"),ACTIVE_MS));
  }

  function pulseAll(){
    demos.forEach(pulse);
  }

  function restartTimer(){
    clearInterval(timer);
    timer=setInterval(pulseAll,INTERVAL_MS);
  }

  demos.forEach(el=>{
    el.addEventListener("mouseenter",()=>pulse(el));
    el.addEventListener("focus",()=>pulse(el));
    el.querySelector("button")?.addEventListener("click",e=>e.preventDefault());
  });

  replay?.addEventListener("click",()=>{
    pulseAll();
    restartTimer();
  });

  setTimeout(()=>{
    pulseAll();
    restartTimer();
  },500);
})();
