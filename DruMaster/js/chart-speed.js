"use strict";

(()=>{
  const chart=globalThis.DruMusterChart;
  if(!chart)return;
  const originalDraw=chart.draw;
  const DEFAULT_PX_PER_QUARTER=80;
  const desktopMq=matchMedia("(hover:hover) and (pointer:fine)");

  function pixelsPerQuarter(){
    const config=globalThis.DruMasterSongs?.current?.chart,
          desktop=Number(config?.desktopPixelsPerQuarter),
          base=Number(config?.pixelsPerQuarter);
    if(desktopMq.matches&&Number.isFinite(desktop)&&desktop>0)return desktop;
    return Number.isFinite(base)&&base>0?base:DEFAULT_PX_PER_QUARTER;
  }

  function drawMeasureLines(ctx,w,h,judgeX,beatNow,timing,pxPerQuarter){
    const signatures=timing.signatures?.length?timing.signatures:[{beat:0,measureBeats:4}],
          firstVisibleBeat=beatNow-judgeX/pxPerQuarter,
          lastVisibleBeat=beatNow+(w-judgeX)/pxPerQuarter;
    ctx.save();
    ctx.strokeStyle="rgba(255,255,255,.08)";
    ctx.lineWidth=1;
    for(let i=0;i<signatures.length;i++){
      const sig=signatures[i],segmentStart=sig.beat||0,
            segmentEnd=i+1<signatures.length?signatures[i+1].beat:Infinity,
            measureBeats=sig.measureBeats||4;
      let barBeat=segmentStart+Math.ceil((firstVisibleBeat-segmentStart)/measureBeats)*measureBeats;
      if(barBeat<segmentStart)barBeat=segmentStart;
      for(;barBeat<=lastVisibleBeat+.0001&&barBeat<segmentEnd-.0001;barBeat+=measureBeats){
        const x=judgeX+(barBeat-beatNow)*pxPerQuarter;
        if(x<0||x>w)continue;
        const crisp=Math.round(x)+.5;
        ctx.beginPath();ctx.moveTo(crisp,0);ctx.lineTo(crisp,h);ctx.stroke();
      }
    }
    ctx.restore();
  }

  function drawConfigured({ctx,canvas,notes,currentSec,timing,groupMap,skipHit=true}){
    const pxPerQuarter=pixelsPerQuarter(),w=canvas.clientWidth,h=canvas.clientHeight,
          beatNow=chart.secondsToBeat(currentSec,timing),division=timing.division||480,
          judgeX=chart.judgementX(w),judgeZoneW=chart.judgementZoneWidth(w),
          kickH=Math.max(16,h*.12),mainH=h-kickH,laneH=mainH/3,
          labelFont=Math.max(9,laneH*.13),labels=["CYMBAL","HI-HAT / RIDE / OTHER","SNARE / TOMS"];

    ctx.clearRect(0,0,w,h);ctx.fillStyle="#081019";ctx.fillRect(0,0,w,h);
    for(let i=0;i<3;i++){
      ctx.fillStyle=i%2===0?"#0d1520":"#0a121c";ctx.fillRect(0,laneH*i,w,laneH);
      if(i>0){ctx.strokeStyle="#53677d";ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(0,laneH*i+.5);ctx.lineTo(w,laneH*i+.5);ctx.stroke()}
      ctx.fillStyle="#8b97a6";ctx.font=`700 ${labelFont}px system-ui,sans-serif`;ctx.textAlign="left";ctx.textBaseline="top";ctx.fillText(labels[i],7,laneH*i+6);
    }
    ctx.fillStyle="#090e15";ctx.fillRect(0,mainH,w,kickH);
    ctx.strokeStyle="#5b6d82";ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(0,mainH+.5);ctx.lineTo(w,mainH+.5);ctx.stroke();
    ctx.fillStyle="#687483";ctx.font=`700 ${labelFont}px system-ui,sans-serif`;ctx.textAlign="left";ctx.textBaseline="middle";ctx.fillText("KICK · AUTO",7,mainH+kickH/2);

    drawMeasureLines(ctx,w,h,judgeX,beatNow,timing,pxPerQuarter);
    ctx.fillStyle="#eef6ff10";ctx.fillRect(judgeX-judgeZoneW/2,0,judgeZoneW,h);
    ctx.strokeStyle="#f3f8ff";ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(judgeX,0);ctx.lineTo(judgeX,h);ctx.stroke();

    for(const n of notes){
      if(skipHit&&n.hit)continue;
      const x=judgeX+(n.tick/division-beatNow)*pxPerQuarter;
      if(x<judgeX-48||x>w+48)continue;
      const group=groupMap[n.type],lane=group==="cymbal"?0:group==="hh"?1:group==="drums"?2:3,
            alpha=.48+.52*n.velocity/127,visual=chart.noteVisual(n.type,group);
      ctx.globalAlpha=n.type==="kick"?.32+.28*n.velocity/127:alpha;
      ctx.fillStyle=visual.color;
      if(lane<3){
        const barTop=lane*laneH,barH=laneH;
        if(visual.kind==="double"){
          const left=x-visual.totalWidth/2;
          ctx.fillRect(left,barTop,visual.barWidth,barH);
          ctx.fillRect(left+visual.barWidth+visual.gap,barTop,visual.barWidth,barH);
        }else ctx.fillRect(x-visual.totalWidth/2,barTop,visual.barWidth,barH);
      }else ctx.fillRect(x-visual.totalWidth/2,mainH+2,visual.barWidth,kickH-4);
    }
    ctx.globalAlpha=1;ctx.textAlign="start";ctx.textBaseline="alphabetic";
  }

  chart.draw=function(args){
    return pixelsPerQuarter()===DEFAULT_PX_PER_QUARTER?originalDraw(args):drawConfigured(args);
  };
  chart.pixelsPerQuarter=pixelsPerQuarter;
})();
