"use strict";

// Fill only the genuinely empty space to the left of the unchanged drum-kit image.
// offsetLeft/offsetWidth use the app's logical landscape coordinates even though #app is CSS-rotated on phones.
(function(){
  const mq=matchMedia("(hover:none) and (pointer:coarse) and (max-width:900px)");
  const chart=document.querySelector("#chartWrap");
  const hitLayer=document.querySelector("#hitLayer");
  if(!chart||!hitLayer)return;

  function layout(){
    if(!mq.matches||game.classList.contains("hidden"))return;

    const gameW=game.clientWidth,
          gameH=game.clientHeight,
          left=Math.max(32,Math.round(gameW*.025)),
          gap=Math.max(16,Math.round(gameW*.012)),
          kitLeft=hitLayer.offsetLeft,
          available=kitLeft-left-gap,
          width=Math.max(300,Math.min(Math.round(gameW*.52),available)),
          top=62,
          height=Math.max(280,Math.min(Math.round(gameH*.61),gameH-top-28));

    chart.style.left=left+"px";
    chart.style.width=width+"px";
    chart.style.top=top+"px";
    chart.style.height=height+"px";

    // Resize the canvas after CSS geometry has settled so note positions use the full highway.
    requestAnimationFrame(()=>{
      const r=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;
      if(r.width>0&&r.height>0){
        canvas.width=Math.round(r.width*dpr);
        canvas.height=Math.round(r.height*dpr);
        ctx.setTransform(dpr,0,0,dpr,0,0);
      }
    });
  }

  const observer=new MutationObserver(()=>requestAnimationFrame(layout));
  observer.observe(game,{attributes:true,attributeFilter:["class"]});
  addEventListener("resize",()=>requestAnimationFrame(layout));
  addEventListener("orientationchange",()=>requestAnimationFrame(layout));
  requestAnimationFrame(layout);
})();
