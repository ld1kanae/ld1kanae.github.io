"use strict";

// Mobile is rendered as a CSS-rotated landscape stage. getBoundingClientRect() therefore
// reports the post-transform dimensions (width/height swapped), which must NOT be used
// for the canvas backing store. Always size from logical clientWidth/clientHeight.
(function(){
  const chart=document.querySelector("#chartWrap");
  const canvas=document.querySelector("#chart");
  if(!chart||!canvas)return;
  const chartCtx=canvas.getContext("2d");

  function syncCanvasSize(){
    const w=Math.max(1,Math.round(canvas.clientWidth));
    const h=Math.max(1,Math.round(canvas.clientHeight));
    const dpr=Math.max(1,Math.min(3,window.devicePixelRatio||1));
    const bw=Math.round(w*dpr),bh=Math.round(h*dpr);
    if(canvas.width!==bw||canvas.height!==bh){
      canvas.width=bw;
      canvas.height=bh;
    }
    chartCtx.setTransform(dpr,0,0,dpr,0,0);
  }

  // Replace app.js's rotation-unsafe resize(). startGame() calls this name directly.
  resize=syncCanvasSize;

  // app.js registered the old resize callback before this file loaded, so also run the
  // corrected sizing after every viewport change and whenever the game becomes visible.
  const ro=new ResizeObserver(()=>requestAnimationFrame(syncCanvasSize));
  ro.observe(chart);
  ro.observe(canvas);
  const mo=new MutationObserver(()=>{
    if(!game.classList.contains("hidden"))requestAnimationFrame(()=>requestAnimationFrame(syncCanvasSize));
  });
  mo.observe(game,{attributes:true,attributeFilter:["class"]});
  addEventListener("resize",()=>requestAnimationFrame(syncCanvasSize),{passive:true});

  // AUTO PLAY already appears in the score HUD. Do not flash a giant AUTO judgement
  // on every autoplay note; keep judgement FX only for actual PERFECT/GREAT/GOOD/MISS.
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

  requestAnimationFrame(()=>requestAnimationFrame(syncCanvasSize));
})();
