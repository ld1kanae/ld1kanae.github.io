"use strict";

/* Keep the production chart canvas transparent so the chart glass CSS can
   reveal the gameplay background beneath it. chart-core still owns labels,
   separators, measure lines, judgement line, and note rendering. */
(()=>{
  const chart=globalThis.DruMusterChart;
  if(!chart||typeof chart.draw!=="function"||chart.__glassTransparentPatch)return;
  const originalDraw=chart.draw;
  chart.draw=function(args){
    const ctx=args?.ctx,canvas=args?.canvas;
    if(!ctx)return originalDraw(args);
    const originalFillRect=ctx.fillRect;
    ctx.fillRect=function(x,y,w,h){
      const fill=String(this.fillStyle).replace(/\s+/g,"").toLowerCase();
      const isLegacyBase=fill==="#030507"||fill==="rgb(3,5,7)"||fill==="rgba(3,5,7,1)";
      if(isLegacyBase){
        const canvasH=Number(canvas?.clientHeight)||0,
              isKickLane=canvasH>0&&y>0&&h<=canvasH*.2&&Math.abs(y+h-canvasH)<2;
        if(isKickLane){
          const previousFill=this.fillStyle;
          this.fillStyle="rgba(255,255,255,.020)";
          try{return originalFillRect.call(this,x,y,w,h)}finally{this.fillStyle=previousFill}
        }
        return;
      }
      return originalFillRect.call(this,x,y,w,h);
    };
    try{return originalDraw(args)}finally{ctx.fillRect=originalFillRect}
  };
  chart.__glassTransparentPatch=true;
})();
