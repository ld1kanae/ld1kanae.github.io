"use strict";

// Visual note-scroll speed only. 42 s across the lane is ~10% of the original 4.2 s speed.
draw=function(){
  const w=canvas.clientWidth,
        h=canvas.clientHeight,
        t=current(),
        judgeX=w*.09,
        laneH=h/4,
        travel=42;
  ctx.clearRect(0,0,w,h);
  ctx.fillStyle="#0b1017";
  ctx.fillRect(0,0,w,h);
  ctx.strokeStyle="#28313d";
  ctx.lineWidth=1;
  for(let i=1;i<4;i++){
    ctx.beginPath();
    ctx.moveTo(0,laneH*i);
    ctx.lineTo(w,laneH*i);
    ctx.stroke();
  }
  ctx.fillStyle="#5e6876";
  ctx.font=`${Math.max(8,laneH*.16)}px sans-serif`;
  ["CYMBAL","HI-HAT / RIDE / OTHER","SNARE / TOMS","BASS DRUM · AUTO"].forEach((s,i)=>ctx.fillText(s,6,laneH*i+12));
  ctx.strokeStyle="#ecf3fb";
  ctx.lineWidth=3;
  ctx.beginPath();
  ctx.moveTo(judgeX,0);
  ctx.lineTo(judgeX,h);
  ctx.stroke();

  for(const n of notes){
    if(n.hit||n.time<t-.25||n.time>t+travel)continue;
    const x=judgeX+(n.time-t)/travel*(w-judgeX+35),
          group=GROUP[n.type],
          lane=group==="cymbal"?0:group==="hh"?1:group==="drums"?2:3,
          y=laneH*(lane+.58),
          alpha=.45+.55*n.velocity/127;
    ctx.globalAlpha=alpha;
    ctx.lineWidth=Math.max(3,laneH*.07);
    ctx.strokeStyle=ctx.fillStyle=n.type==="snare"?"#38a9ff":n.type.includes("Tom")?"#ad82ff":group==="cymbal"?"#ffd45a":group==="hh"?"#52dfcf":"#9da5af";
    ctx.font=`900 ${Math.max(18,laneH*.38)}px sans-serif`;
    ctx.textAlign="center";
    ctx.textBaseline="middle";
    if(n.type==="snare"||n.type.includes("Tom")){
      ctx.beginPath();
      ctx.arc(x,y,Math.max(7,laneH*.15),0,Math.PI*2);
      ctx.fill();
    }else if(n.type==="hhClosed"||n.type==="hhPedal")ctx.fillText("│",x,y);
    else if(n.type==="hhOpen")ctx.fillText("||",x,y);
    else if(n.type==="ride")ctx.fillText("△",x,y);
    else if(n.type==="crash")ctx.fillText("×",x,y);
    else if(n.type==="kick"){
      ctx.globalAlpha=.22+.25*n.velocity/127;
      ctx.font=`900 ${Math.max(20,laneH*.46)}px sans-serif`;
      ctx.fillText("┃",x,y);
    }else ctx.fillText("◇",x,y);
  }
  ctx.globalAlpha=1;
  ctx.textAlign="start";
};
