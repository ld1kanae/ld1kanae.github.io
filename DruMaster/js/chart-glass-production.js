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
    ctx.fillRect=function(x,y,w,h){
      const fill=String(this.fillStyle).replace(/\s+/g,"").toLowerCase();
      const isLegacyBase=fill==="#030507"||fill==="rgb(3,5,7)"||fill==="rgba(3,5,7,1)";
      if(isLegacyBase)return;
      return originalFillRect.call(this,x,y,w,h);
    };
    try{return originalDraw(args)}finally{ctx.fillRect=originalFillRect}
  };
  chart.__glassTransparentPatch=true;
})();
