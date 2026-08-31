"use strict";

(function(){
  const chart=document.querySelector("#chartWrap");
  const canvas=document.querySelector("#chart");
  if(!chart||!canvas)return;
  const chartCtx=canvas.getContext("2d");

  function isTouchDevice(){
    return (navigator.maxTouchPoints||0)>0 ||
      !!globalThis.matchMedia?.("(any-pointer:coarse)")?.matches ||
      !!globalThis.matchMedia?.("(pointer:coarse)")?.matches;
  }

  function syncCanvasSize(){
    const w=Math.max(1,Math.round(canvas.clientWidth));
    const h=Math.max(1,Math.round(canvas.clientHeight));
    /* Performance test pass 4: reduce only the backing-store resolution on
       touch hardware. All chart geometry remains CSS-pixel based. */
    const dprCap=isTouchDevice()?1.5:3;
    const dpr=Math.max(1,Math.min(dprCap,window.devicePixelRatio||1));
    const bw=Math.round(w*dpr),bh=Math.round(h*dpr);
    if(canvas.width!==bw||canvas.height!==bh){
      canvas.width=bw;
      canvas.height=bh;
    }
    chartCtx.setTransform(dpr,0,0,dpr,0,0);
  }

  resize=syncCanvasSize;

  const ro=new ResizeObserver(()=>requestAnimationFrame(syncCanvasSize));
  ro.observe(chart);
  ro.observe(canvas);
  const mo=new MutationObserver(()=>{
    if(!game.classList.contains("hidden"))requestAnimationFrame(()=>requestAnimationFrame(syncCanvasSize));
  });
  mo.observe(game,{attributes:true,attributeFilter:["class"]});
  addEventListener("resize",()=>requestAnimationFrame(syncCanvasSize),{passive:true});

  const baseShowJudge=showJudge;
  showJudge=function(label){
    if(label==="AUTO")return;
    baseShowJudge(label);
  };
  const fx=document.querySelector("#judgementFx");
  if(fx){
    fx.classList.remove("play");
    const j=fx.querySelector("#judge");
    if(j&&j.textContent==="AUTO")j.textContent="";
  }

  globalThis.DruMasterPerfCanvasPass4={
    version:"20260901-pass4",
    get dpr(){return canvas.clientWidth?canvas.width/canvas.clientWidth:null}
  };

  requestAnimationFrame(()=>requestAnimationFrame(syncCanvasSize));
})();
