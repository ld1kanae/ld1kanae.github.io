"use strict";

(()=>{
  const chart=globalThis.DruMusterChart;
  if(!chart)return;
  const originalDraw=chart.draw;
  const DEFAULT_PX_PER_QUARTER=80;
  const DESKTOP_PX_PER_QUARTER=100;
  const desktopMq=matchMedia("(hover:hover) and (pointer:fine)");

  /* One global chart speed keeps every song and playback mode consistent. */
  function pixelsPerQuarter(){
    return desktopMq.matches?DESKTOP_PX_PER_QUARTER:DEFAULT_PX_PER_QUARTER;
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

    chart.drawMeasureLines(ctx,w,h,judgeX,beatNow,timing,pxPerQuarter);
    ctx.fillStyle="#eef6ff10";ctx.fillRect(judgeX-judgeZoneW/2,0,judgeZoneW,h);
    ctx.strokeStyle="#f3f8ff";ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(judgeX,0);ctx.lineTo(judgeX,h);ctx.stroke();

    const minBeat=beatNow-48/pxPerQuarter,
          maxBeat=beatNow+(w+48-judgeX)/pxPerQuarter,
          search=globalThis.DruMasterNoteSearch,
          range=search?.visibleTickRange?search.visibleTickRange(notes,minBeat*division,maxBeat*division):{start:0,end:notes.length};
    for(let i=range.start;i<range.end;i++){
      const n=notes[i];
      if(skipHit&&n.hit)continue;
      const x=judgeX+(n.tick/division-beatNow)*pxPerQuarter;
      const group=groupMap[n.type],lane=group==="cymbal"?0:group==="hh"?1:group==="drums"?2:3,
            alpha=.48+.52*n.velocity/127,visual=chart.noteVisual(n.type,group);
      ctx.globalAlpha=n.type==="kick"?.32+.28*n.velocity/127:alpha;
      ctx.fillStyle=visual.color;
      if(lane<3){
        const barTop=lane*laneH,barH=laneH;
        if(n.type==="hhOpen"){
          chart.drawOpenHihatTail({ctx,notes,index:i,x,top:barTop,height:barH,beatNow,division,pxPerQuarter,canvasWidth:w,color:visual.color});
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
