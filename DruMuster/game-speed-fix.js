"use strict";

// Visual note-scroll speed only.
// 42 s across the note highway keeps the user's requested ~10% of the original 4.2 s visual speed.
// Hit timing is still determined solely by note.time and is not changed here.
draw=function(){
  const w=canvas.clientWidth,
        h=canvas.clientHeight,
        t=current(),
        judgeX=w*.13,
        laneH=h/4,
        travel=42,
        labels=["CYM","HH / RIDE","SNARE / TOM","KICK · AUTO"],
        laneColors=["#ffd45a","#52dfcf","#8898ff","#a7b0bc"];

  ctx.clearRect(0,0,w,h);
  ctx.fillStyle="#081019";
  ctx.fillRect(0,0,w,h);

  // High-contrast highway lanes, similar to conventional rhythm-game note tracks.
  for(let i=0;i<4;i++){
    ctx.fillStyle=i%2===0?"#0d1520":"#0a121c";
    ctx.fillRect(0,laneH*i,w,laneH);
    if(i>0){
      ctx.strokeStyle="#2c3948";
      ctx.lineWidth=1;
      ctx.beginPath();
      ctx.moveTo(0,laneH*i+.5);
      ctx.lineTo(w,laneH*i+.5);
      ctx.stroke();
    }

    const y=laneH*(i+.5);
    ctx.strokeStyle=laneColors[i]+"aa";
    ctx.lineWidth=Math.max(2,laneH*.035);
    ctx.beginPath();
    ctx.arc(judgeX,y,Math.max(10,laneH*.15),0,Math.PI*2);
    ctx.stroke();

    ctx.fillStyle="#8b97a6";
    ctx.font=`700 ${Math.max(8,laneH*.12)}px system-ui,sans-serif`;
    ctx.textAlign="left";
    ctx.textBaseline="top";
    ctx.fillText(labels[i],6,laneH*i+7);
  }

  // Fixed judgement frame. Notes are meant to be struck at the center of this frame.
  ctx.fillStyle="#eef6ff12";
  ctx.fillRect(judgeX-Math.max(5,w*.009),0,Math.max(10,w*.018),h);
  ctx.strokeStyle="#f3f8ff";
  ctx.lineWidth=3;
  ctx.beginPath();
  ctx.moveTo(judgeX,0);
  ctx.lineTo(judgeX,h);
  ctx.stroke();

  for(const n of notes){
    if(n.hit||n.time<t-.25||n.time>t+travel)continue;
    const x=judgeX+(n.time-t)/travel*(w-judgeX+28),
          group=GROUP[n.type],
          lane=group==="cymbal"?0:group==="hh"?1:group==="drums"?2:3,
          y=laneH*(lane+.5),
          alpha=.48+.52*n.velocity/127;

    ctx.globalAlpha=alpha;
    ctx.strokeStyle=ctx.fillStyle=n.type==="snare"?"#38a9ff":n.type.includes("Tom")?"#ad82ff":group==="cymbal"?"#ffd45a":group==="hh"?"#52dfcf":"#a7b0bc";
    ctx.textAlign="center";
    ctx.textBaseline="middle";

    if(n.type==="snare"||n.type.includes("Tom")){
      const r=Math.max(9,laneH*.16);
      ctx.beginPath();
      ctx.arc(x,y,r,0,Math.PI*2);
      ctx.fill();
      ctx.globalAlpha=Math.min(1,alpha+.15);
      ctx.strokeStyle="#ffffffaa";
      ctx.lineWidth=1.5;
      ctx.stroke();
    }else if(n.type==="hhClosed"||n.type==="hhPedal"){
      ctx.font=`900 ${Math.max(22,laneH*.40)}px system-ui,sans-serif`;
      ctx.fillText("│",x,y);
    }else if(n.type==="hhOpen"){
      ctx.font=`900 ${Math.max(22,laneH*.40)}px system-ui,sans-serif`;
      ctx.fillText("||",x,y);
    }else if(n.type==="ride"){
      ctx.font=`900 ${Math.max(20,laneH*.34)}px system-ui,sans-serif`;
      ctx.fillText("△",x,y);
    }else if(n.type==="crash"){
      ctx.font=`900 ${Math.max(24,laneH*.42)}px system-ui,sans-serif`;
      ctx.fillText("×",x,y);
    }else if(n.type==="kick"){
      ctx.globalAlpha=.30+.30*n.velocity/127;
      ctx.font=`900 ${Math.max(24,laneH*.42)}px system-ui,sans-serif`;
      ctx.fillText("┃",x,y);
    }else{
      ctx.font=`900 ${Math.max(20,laneH*.34)}px system-ui,sans-serif`;
      ctx.fillText("◇",x,y);
    }
  }

  ctx.globalAlpha=1;
  ctx.textAlign="start";
  ctx.textBaseline="alphabetic";
};
