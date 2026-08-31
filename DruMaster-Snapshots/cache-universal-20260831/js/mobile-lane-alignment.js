"use strict";

(()=>{
  const chart=globalThis.DruMusterChart;
  const canvas=document.querySelector("#chart");
  if(!chart||!canvas||typeof chart.draw!=="function")return;

  const LABELS=["CYMBAL","HI-HAT / RIDE / OTHER","SNARE / TOMS"];
  const isMobile=()=>chart.isMobileLayout?chart.isMobileLayout():!!globalThis.matchMedia?.("(hover:none) and (pointer:coarse) and (max-width:900px)")?.matches;
  let cachedFontKey="",cachedStripW=0;

  function geometry(){
    const h=canvas.clientHeight,
          kickH=Math.max(16,h*.12),
          mainH=h-kickH,
          laneH=mainH/3,
          labelFont=Math.max(9,laneH*.13);
    return {kickH,mainH,laneH,labelFont};
  }

  function stripWidth(ctx,labelFont){
    const key=labelFont.toFixed(3);
    if(key===cachedFontKey&&cachedStripW)return cachedStripW;
    ctx.font=`700 ${labelFont}px system-ui,sans-serif`;
    const maxLabelW=Math.max(...LABELS.map(t=>ctx.measureText(t).width),ctx.measureText("KICK · AUTO").width);
    cachedFontKey=key;
    cachedStripW=Math.ceil(maxLabelW+15);
    return cachedStripW;
  }

  /* Mobile only: repaint the label strip after the shared renderer so every
     label sits on the exact vertical centreline of its lane. Text measurement
     is cached until the logical lane height changes. */
  const originalDraw=chart.draw;
  chart.draw=function(args){
    const result=originalDraw(args);
    if(!isMobile())return result;

    const {ctx}=args,{kickH,mainH,laneH,labelFont}=geometry();
    ctx.save();
    const stripW=stripWidth(ctx,labelFont);

    for(let i=0;i<3;i++){
      ctx.fillStyle=i%2===0?"#0d1520":"#0a121c";
      ctx.fillRect(0,laneH*i,stripW,laneH);
      if(i>0){
        ctx.strokeStyle="#53677d";
        ctx.lineWidth=1.2;
        ctx.beginPath();
        ctx.moveTo(0,laneH*i+.5);
        ctx.lineTo(stripW,laneH*i+.5);
        ctx.stroke();
      }
    }

    ctx.fillStyle="#090e15";
    ctx.fillRect(0,mainH,stripW,kickH);
    ctx.strokeStyle="#5b6d82";
    ctx.lineWidth=1.2;
    ctx.beginPath();
    ctx.moveTo(0,mainH+.5);
    ctx.lineTo(stripW,mainH+.5);
    ctx.stroke();

    ctx.font=`700 ${labelFont}px system-ui,sans-serif`;
    ctx.textAlign="left";
    ctx.textBaseline="middle";
    ctx.fillStyle="#8b97a6";
    for(let i=0;i<3;i++)ctx.fillText(LABELS[i],7,laneH*(i+.5));
    ctx.fillStyle="#687483";
    ctx.fillText("KICK · AUTO",7,mainH+kickH/2);
    ctx.restore();
    return result;
  };
})();
