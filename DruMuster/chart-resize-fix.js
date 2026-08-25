"use strict";

// Keep the canvas backing store in the same aspect ratio/resolution as its CSS box.
// This avoids the default 300x150 canvas being stretched inside the very wide rhythm-game highway.
(function(){
  const chart=document.querySelector("#chartWrap");
  const canvas=document.querySelector("#chart");
  if(!chart||!canvas)return;
  const ctx=canvas.getContext("2d");

  function syncCanvasSize(){
    const w=Math.max(1,Math.round(canvas.clientWidth));
    const h=Math.max(1,Math.round(canvas.clientHeight));
    const dpr=Math.max(1,Math.min(3,window.devicePixelRatio||1));
    const bw=Math.round(w*dpr),bh=Math.round(h*dpr);
    if(canvas.width!==bw||canvas.height!==bh){
      canvas.width=bw;
      canvas.height=bh;
    }
    ctx.setTransform(dpr,0,0,dpr,0,0);
  }

  const ro=new ResizeObserver(()=>requestAnimationFrame(syncCanvasSize));
  ro.observe(chart);
  ro.observe(canvas);
  addEventListener("resize",()=>requestAnimationFrame(syncCanvasSize),{passive:true});
  requestAnimationFrame(()=>requestAnimationFrame(syncCanvasSize));
})();
