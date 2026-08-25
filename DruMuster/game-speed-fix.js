"use strict";

// Visual note-scroll speed only.
// 8.4 s across the highway is half the original visual speed (4.2 s crossing),
// but avoids the severe note congestion caused by the previous 42 s setting.
// Hit timing still uses note.time and is not changed here.
draw=function(){
  const w=canvas.clientWidth,
        h=canvas.clientHeight,
        t=current(),
        judgeX=w*.11,
        laneH=h/4,
        travel=8.4,
        labels=["CYM","HH / RIDE","SNARE / TOM","KICK · AUTO"],
        laneColors=["#ffd45a","#52dfcf","#8898ff","#a7b0bc"];

  ctx.clearRect(0,0,w,h);
  ctx.fillStyle="#081019";
  ctx.fillRect(0,0,w,h);

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
    ctx.fillText(labels[i],6,laneH*i+6);
  }

  // Stable Taiko-like hit zone near the left side of the horizontal highway.
  ctx.fillStyle="#eef6ff10";
  ctx.fillRect(judgeX-Math.max(5,w*.007),0,Math.max(10,w*.014),h);
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
      const r=Math.max(8,laneH*.15);
      ctx.beginPath();
      ctx.arc(x,y,r,0,Math.PI*2);
      ctx.fill();
      ctx.globalAlpha=Math.min(1,alpha+.15);
      ctx.strokeStyle="#ffffffaa";
      ctx.lineWidth=1.5;
      ctx.stroke();
    }else if(n.type==="hhClosed"||n.type==="hhPedal"){
      ctx.font=`900 ${Math.max(20,laneH*.38)}px system-ui,sans-serif`;
      ctx.fillText("│",x,y);
    }else if(n.type==="hhOpen"){
      ctx.font=`900 ${Math.max(20,laneH*.38)}px system-ui,sans-serif`;
      ctx.fillText("||",x,y);
    }else if(n.type==="ride"){
      ctx.font=`900 ${Math.max(19,laneH*.33)}px system-ui,sans-serif`;
      ctx.fillText("△",x,y);
    }else if(n.type==="crash"){
      ctx.font=`900 ${Math.max(22,laneH*.40)}px system-ui,sans-serif`;
      ctx.fillText("×",x,y);
    }else if(n.type==="kick"){
      ctx.globalAlpha=.26+.25*n.velocity/127;
      ctx.font=`900 ${Math.max(21,laneH*.38)}px system-ui,sans-serif`;
      ctx.fillText("┃",x,y);
    }else{
      ctx.font=`900 ${Math.max(19,laneH*.33)}px system-ui,sans-serif`;
      ctx.fillText("◇",x,y);
    }
  }

  ctx.globalAlpha=1;
  ctx.textAlign="start";
  ctx.textBaseline="alphabetic";
};
