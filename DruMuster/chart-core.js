"use strict";

// Shared chart engine used by both production and UI preview.
// All chart geometry and scroll-speed changes must be made here so the two modes stay identical.
globalThis.DruMusterChart=(()=>{
  const PIXELS_PER_QUARTER=80;
  const NOTE_BAR_WIDTH=4;
  const OPEN_HH_BAR_WIDTH=3;
  const OPEN_HH_GAP=1;

  function judgementZoneWidth(width){
    return Math.max(10,width*.014);
  }

  function parseTempoTiming(ab){
    const d=new DataView(ab);let p=0;
    const str=n=>{let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s};
    const u32=()=>{const v=d.getUint32(p);p+=4;return v};
    const u16=()=>{const v=d.getUint16(p);p+=2;return v};
    const vlq=()=>{let v=0,b;do{b=d.getUint8(p++);v=(v<<7)|(b&127)}while(b&128);return v};
    if(str(4)!=="MThd")throw Error("MIDI timing header error");
    const headerLength=u32();u16();const tracks=u16(),division=u16();p+=headerLength-6;
    const tempos=[],timeSignatures=[];
    for(let t=0;t<tracks;t++){
      if(str(4)!=="MTrk")throw Error("MIDI timing track error");
      const trackLength=u32(),end=p+trackLength;let tick=0,runningStatus=0;
      while(p<end){
        tick+=vlq();const first=d.getUint8(p++);let status;
        if(first<128){if(!runningStatus)throw Error("MIDI timing running-status error");status=runningStatus;p--}
        else{status=first;if(status<240)runningStatus=status}
        if(status===255){
          const type=d.getUint8(p++),len=vlq();
          if(type===81&&len===3){
            tempos.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});
          }else if(type===88&&len>=2){
            const numerator=d.getUint8(p),denominator=2**d.getUint8(p+1);
            timeSignatures.push({tick,numerator,denominator});
          }
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

    timeSignatures.sort((a,b)=>a.tick-b.tick);
    const sigDedup=[];
    for(const e of timeSignatures){
      if(sigDedup.length&&sigDedup[sigDedup.length-1].tick===e.tick)sigDedup[sigDedup.length-1]=e;
      else sigDedup.push(e);
    }
    if(!sigDedup.length||sigDedup[0].tick>0)sigDedup.unshift({tick:0,numerator:4,denominator:4});
    const signatures=sigDedup.map(e=>({
      ...e,
      beat:e.tick/division,
      measureBeats:e.numerator*4/e.denominator
    }));

    return {division,segments,signatures};
  }

  function secondsToBeat(sec,timing){
    const segs=timing.segments;let seg=segs[0];
    for(let i=1;i<segs.length&&segs[i].sec<=sec;i++)seg=segs[i];
    const tick=seg.tick+(sec-seg.sec)*1e6/seg.us*timing.division;
    return tick/timing.division;
  }

  function drawMeasureLines(ctx,w,h,judgeX,beatNow,timing){
    const signatures=timing.signatures?.length?timing.signatures:[{beat:0,measureBeats:4}],
          firstVisibleBeat=beatNow-judgeX/PIXELS_PER_QUARTER,
          lastVisibleBeat=beatNow+(w-judgeX)/PIXELS_PER_QUARTER;

    ctx.save();
    // Deliberately very faint: structural guide only, not another note lane.
    ctx.strokeStyle="rgba(255,255,255,.08)";
    ctx.lineWidth=1;
    for(let i=0;i<signatures.length;i++){
      const sig=signatures[i],
            segmentStart=sig.beat||0,
            segmentEnd=i+1<signatures.length?signatures[i+1].beat:Infinity,
            measureBeats=sig.measureBeats||4;
      let barBeat=segmentStart+Math.ceil((firstVisibleBeat-segmentStart)/measureBeats)*measureBeats;
      if(barBeat<segmentStart)barBeat=segmentStart;
      for(;barBeat<=lastVisibleBeat+.0001&&barBeat<segmentEnd-.0001;barBeat+=measureBeats){
        const x=judgeX+(barBeat-beatNow)*PIXELS_PER_QUARTER;
        if(x<0||x>w)continue;
        const crisp=Math.round(x)+.5;
        ctx.beginPath();ctx.moveTo(crisp,0);ctx.lineTo(crisp,h);ctx.stroke();
      }
    }
    ctx.restore();
  }

  function draw({ctx,canvas,notes,currentSec,timing,groupMap,skipHit=true}){
    const w=canvas.clientWidth,
          h=canvas.clientHeight,
          beatNow=secondsToBeat(currentSec,timing),
          division=timing.division||480,
          judgeX=w*.11,
          judgeZoneW=judgementZoneWidth(w),
          kickH=Math.max(16,h*.12),
          mainH=h-kickH,
          laneH=mainH/3,
          labelFont=Math.max(9,laneH*.13),
          labels=["CYMBAL","HI-HAT / RIDE / OTHER","SNARE / TOMS"];

    ctx.clearRect(0,0,w,h);
    ctx.fillStyle="#081019";
    ctx.fillRect(0,0,w,h);

    for(let i=0;i<3;i++){
      ctx.fillStyle=i%2===0?"#0d1520":"#0a121c";
      ctx.fillRect(0,laneH*i,w,laneH);
      if(i>0){
        // Stronger than before so lane boundaries stay legible under full-height notes.
        ctx.strokeStyle="#53677d";ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(0,laneH*i+.5);ctx.lineTo(w,laneH*i+.5);ctx.stroke();
      }
      ctx.fillStyle="#8b97a6";
      ctx.font=`700 ${labelFont}px system-ui,sans-serif`;
      ctx.textAlign="left";ctx.textBaseline="top";ctx.fillText(labels[i],7,laneH*i+6);
    }

    ctx.fillStyle="#090e15";ctx.fillRect(0,mainH,w,kickH);
    ctx.strokeStyle="#5b6d82";ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(0,mainH+.5);ctx.lineTo(w,mainH+.5);ctx.stroke();
    ctx.fillStyle="#687483";ctx.font=`700 ${labelFont}px system-ui,sans-serif`;ctx.textAlign="left";ctx.textBaseline="middle";ctx.fillText("KICK · AUTO",7,mainH+kickH/2);

    drawMeasureLines(ctx,w,h,judgeX,beatNow,timing);

    // The glow overlay uses this exact same zone width via judgementZoneWidth().
    ctx.fillStyle="#eef6ff10";ctx.fillRect(judgeX-judgeZoneW/2,0,judgeZoneW,h);
    ctx.strokeStyle="#f3f8ff";ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(judgeX,0);ctx.lineTo(judgeX,h);ctx.stroke();

    for(const n of notes){
      if(skipHit&&n.hit)continue;
      const x=judgeX+(n.tick/division-beatNow)*PIXELS_PER_QUARTER;
      if(x<judgeX-48||x>w+48)continue;
      const group=groupMap[n.type],
            lane=group==="cymbal"?0:group==="hh"?1:group==="drums"?2:3,
            alpha=.48+.52*n.velocity/127,
            color=n.type==="snare"?"#38a9ff":n.type.includes("Tom")?"#ad82ff":group==="cymbal"?"#ffd45a":group==="hh"?"#52dfcf":"#a7b0bc";

      ctx.globalAlpha=n.type==="kick"?.32+.28*n.velocity/127:alpha;
      ctx.fillStyle=color;

      if(lane<3){
        const barTop=lane*laneH,
              barH=laneH;
        if(n.type==="hhOpen"){
          const total=OPEN_HH_BAR_WIDTH*2+OPEN_HH_GAP,
                left=x-total/2;
          ctx.fillRect(left,barTop,OPEN_HH_BAR_WIDTH,barH);
          ctx.fillRect(left+OPEN_HH_BAR_WIDTH+OPEN_HH_GAP,barTop,OPEN_HH_BAR_WIDTH,barH);
        }else{
          ctx.fillRect(x-NOTE_BAR_WIDTH/2,barTop,NOTE_BAR_WIDTH,barH);
        }
      }else{
        ctx.fillRect(x-NOTE_BAR_WIDTH/2,mainH+2,NOTE_BAR_WIDTH,kickH-4);
      }
    }

    ctx.globalAlpha=1;ctx.textAlign="start";ctx.textBaseline="alphabetic";
  }

  return {PIXELS_PER_QUARTER,judgementZoneWidth,parseTempoTiming,secondsToBeat,draw};
})();
