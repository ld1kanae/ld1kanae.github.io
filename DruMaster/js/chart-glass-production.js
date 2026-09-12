"use strict";

/* Keep the production chart canvas transparent so the chart glass CSS can
   reveal the gameplay background beneath it. chart-core still owns labels,
   separators, measure lines, judgement line, and note rendering. */
(()=>{
  const chart=globalThis.DruMusterChart;
  if(!chart||typeof chart.draw!=="function"||chart.__glassTransparentPatch)return;
  const originalDraw=chart.draw;
  chart.draw=function(args){
    const ctx=args?.ctx;
    if(!ctx)return originalDraw(args);
    const originalFillRect=ctx.fillRect;
    const canvasHeight=Number(args?.canvas?.clientHeight)||0;
    ctx.fillRect=function(x,y,w,h){
      const fill=String(this.fillStyle).replace(/\s+/g,"").toLowerCase();
      const isLegacyBase=fill==="#030507"||fill==="rgb(3,5,7)"||fill==="rgba(3,5,7,1)";
      if(isLegacyBase)return;

      /* Kick notes must touch both edges of the KICK lane. chart-core derives
         mainH/kickH from fractional CSS pixels, which can leave a visible
         sub-pixel gap after canvas scaling. Snap the kick bar outward to whole
         pixels so it exactly covers the lane from its top boundary to bottom. */
      const isKickNote=fill==="#aeb9c7"||fill==="rgb(174,185,199)"||fill==="rgba(174,185,199,1)";
      if(isKickNote&&canvasHeight>0&&y>canvasHeight*.7){
        const top=Math.floor(y),bottom=Math.ceil(canvasHeight);
        return originalFillRect.call(this,x,top,w,Math.max(1,bottom-top));
      }

      return originalFillRect.call(this,x,y,w,h);
    };
    try{return originalDraw(args)}finally{ctx.fillRect=originalFillRect}
  };
  chart.__glassTransparentPatch=true;
})();
