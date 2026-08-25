"use strict";

// Shared chart engine used by both production and UI preview.
// All chart geometry and scroll-speed changes must be made here so the two modes stay identical.
globalThis.DruMusterChart=(()=>{
  const PIXELS_PER_QUARTER=80;

  function parseTempoTiming(ab){
    const d=new DataView(ab);let p=0;
    const str=n=>{let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s};
    const u32=()=>{const v=d.getUint32(p);p+=4;return v};
    const u16=()=>{const v=d.getUint16(p);p+=2;return v};
    const vlq=()=>{let v=0,b;do{b=d.getUint8(p++);v=(v<<7)|(b&127)}while(b&128);return v};
    if(str(4)!=="MThd")throw Error("MIDI timing header error");
    const headerLength=u32();u16();const tracks=u16(),division=u16();p+=headerLength-6;
    const tempos=[];
    for(let t=0;t<tracks;t++){
      if(str(4)!=="MTrk")throw Error("MIDI timing track error");
      const trackLength=u32(),end=p+trackLength;let tick=0,runningStatus=0;
      while(p<end){
        tick+=vlq();const first=d.getUint8(p++);let status;
        if(first<128){if(!runningStatus)throw Error("MIDI timing running-status error");status=runningStatus;p--}
        else{status=first;if(status<240)runningStatus=status}
        if(status===255){
          const type=d.getUint8(p++),len=vlq();
          if(type===81&&len===3)tempos.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});
          p+=len;
        }else if(status===240||status===247){
          runningStatus=0;const len=vlq();p+=len;
        }else{
          const hi=status&240;
          p+=(hi===192||hi===208)?1:2;
        }
      }
      p=end;
    }
    tempos.sort((a,b)=>a.tick-b.tick);
    const dedup=[];
    for(const e of tempos){
      if(dedup.length&&dedup[dedup.length-1].tick===e.tick)dedup[dedup.length-1]=e;
      else dedup.push(e);
    }
    const segments=[{tick:0,sec:0,us:500000}];
    let lastTick=0,lastSec=0,us=500000;
    for(const e of dedup){
      lastSec+=(e.tick-lastTick)*us/division/1e6;
      lastTick=e.tick;us=e.us;
      if(e.tick===0)segments[0]={tick:0,sec:0,us};
      else segments.push({tick:e.tick,sec:lastSec,us});
    }
    return {division,segments};
  }

  function secondsToBeat(sec,timing){
    const segs=timing.segments;let seg=segs[0];
    for(let i=1;i<segs.length&&segs[i].sec<=sec;i++)seg=segs[i];
    const tick=seg.tick+(sec-seg.sec)*1e6/seg.us*timing.division;
    return tick/timing.division;
  }

  function draw({ctx,canvas,notes,currentSec,timing,groupMap,skipHit=true}){
    const w=canvas.clientWidth,
          h=canvas.clientHeight,
          beatNow=secondsToBeat(currentSec,timing),
          division=timing.division||480,
          judgeX=w*.11,
          kickH=Math.max(16,h*.12),
          mainH=h-kickH,
          laneH=mainH/3,
          labels=["CYMBAL","HI-HAT / RIDE / OTHER","SNARE / TOMS"],
          laneColors=["#ffd45a","#52dfcf","#8898ff"];

    ctx.clearRect(0,0,w,h);
    ctx.fillStyle="#081019";
    ctx.fillRect(0,0,w,h);

    for(let i=0;i<3;i++){
      ctx.fillStyle=i%2===0?"#0d1520":"#0a121c";
      ctx.fillRect(0,laneH*i,w,laneH);
      if(i>0){
        ctx.strokeStyle="#2c3948";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(0,laneH*i+.5);ctx.lineTo(w,laneH*i+.5);ctx.stroke();
      }
      const y=laneH*(i+.5);
      ctx.strokeStyle=laneColors[i]+"bb";
      ctx.lineWidth=Math.max(2,laneH*.04);
      ctx.beginPath();ctx.arc(judgeX,y,Math.max(12,laneH*.20),0,Math.PI*2);ctx.stroke();
      ctx.fillStyle="#8b97a6";
      ctx.font=`700 ${Math.max(9,laneH*.13)}px system-ui,sans-serif`;
      ctx.textAlign="left";ctx.textBaseline="top";ctx.fillText(labels[i],7,laneH*i+6);
    }

    ctx.fillStyle="#090e15";ctx.fillRect(0,mainH,w,kickH);
    ctx.strokeStyle="#313a46";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(0,mainH+.5);ctx.lineTo(w,mainH+.5);ctx.stroke();
    ctx.fillStyle="#687483";ctx.font=`700 ${Math.max(8,kickH*.43)}px system-ui,sans-serif`;ctx.textAlign="left";ctx.textBaseline="middle";ctx.fillText("KICK · AUTO",7,mainH+kickH/2);

    ctx.fillStyle="#eef6ff10";ctx.fillRect(judgeX-Math.max(5,w*.007),0,Math.max(10,w*.014),h);
    ctx.strokeStyle="#f3f8ff";ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(judgeX,0);ctx.lineTo(judgeX,h);ctx.stroke();

    for(const n of notes){
      if(skipHit&&n.hit)continue;
      const x=judgeX+(n.tick/division-beatNow)*PIXELS_PER_QUARTER;
      if(x<judgeX-48||x>w+48)continue;
      const group=groupMap[n.type],
            lane=group==="cymbal"?0:group==="hh"?1:group==="drums"?2:3,
            y=lane<3?laneH*(lane+.5):mainH+kickH/2,
            alpha=.48+.52*n.velocity/127;

      ctx.globalAlpha=alpha;
      ctx.strokeStyle=ctx.fillStyle=n.type==="snare"?"#38a9ff":n.type.includes("Tom")?"#ad82ff":group==="cymbal"?"#ffd45a":group==="hh"?"#52dfcf":"#a7b0bc";
      ctx.textAlign="center";ctx.textBaseline="middle";

      if(n.type==="snare"||n.type.includes("Tom")){
        const r=Math.max(12,laneH*.20);
        ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();
        ctx.globalAlpha=Math.min(1,alpha+.15);ctx.strokeStyle="#ffffffaa";ctx.lineWidth=1.5;ctx.stroke();
      }else if(n.type==="hhClosed"||n.type==="hhPedal"){
        ctx.font=`900 ${Math.max(28,laneH*.50)}px system-ui,sans-serif`;ctx.fillText("│",x,y);
      }else if(n.type==="hhOpen"){
        ctx.font=`900 ${Math.max(28,laneH*.50)}px system-ui,sans-serif`;ctx.fillText("||",x,y);
      }else if(n.type==="ride"){
        ctx.font=`900 ${Math.max(25,laneH*.43)}px system-ui,sans-serif`;ctx.fillText("△",x,y);
      }else if(n.type==="crash"){
        ctx.font=`900 ${Math.max(30,laneH*.52)}px system-ui,sans-serif`;ctx.fillText("×",x,y);
      }else if(n.type==="kick"){
        ctx.globalAlpha=.32+.28*n.velocity/127;ctx.fillStyle="#a7b0bc";ctx.fillRect(x-2,mainH+2,4,kickH-4);
      }else{
        ctx.font=`900 ${Math.max(25,laneH*.43)}px system-ui,sans-serif`;ctx.fillText("◇",x,y);
      }
    }

    ctx.globalAlpha=1;ctx.textAlign="start";ctx.textBaseline="alphabetic";
  }

  return {PIXELS_PER_QUARTER,parseTempoTiming,secondsToBeat,draw};
})();
