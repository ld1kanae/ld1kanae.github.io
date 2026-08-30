"use strict";

globalThis.DruMusterChart=(()=>{
  const PIXELS_PER_QUARTER=80;
  const NOTE_BAR_WIDTH=4;
  const OPEN_HH_BAR_WIDTH=2;
  const OPEN_HH_GAP=1;
  const DESKTOP_NOTE_WIDTH_SCALE=1.5;
  const MOBILE_JUDGE_OFFSET=80;
  const signatureCache=new WeakMap();

  function isMobileLayout(){
    return !!globalThis.matchMedia?.("(hover:none) and (pointer:coarse) and (max-width:900px)")?.matches;
  }
  function judgementX(width){
    return Math.min(width-16,width*.11+(isMobileLayout()?MOBILE_JUDGE_OFFSET:0));
  }
  function judgementZoneWidth(width){return Math.max(10,width*.014)}

  function noteColor(type,group){
    if(type==="snare")return "#ff3d73";
    if(type==="highTom")return "#d76bff";
    if(type==="midTom")return "#8875ff";
    if(type==="floorTom")return "#329cff";
    if(type==="ride")return "#63d66f";
    if(type==="hhPedal")return "#52dfcf";
    if(group==="cymbal")return "#ffd45a";
    if(group==="hh")return "#52dfcf";
    if(type==="kick"||group==="kick")return "#aeb9c7";
    return "#a7b0bc";
  }

  function noteVisual(type,group,scale=1){
    const isOpen=type==="hhOpen",
          barWidth=(isOpen?OPEN_HH_BAR_WIDTH:NOTE_BAR_WIDTH)*scale,
          gap=(isOpen?OPEN_HH_GAP:0)*scale,
          totalWidth=(isOpen?OPEN_HH_BAR_WIDTH*2+OPEN_HH_GAP:NOTE_BAR_WIDTH)*scale,
          color=noteColor(type,group);
    return {kind:isOpen?"double":"single",barWidth,gap,totalWidth,color};
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
            timeSignatures.push({tick,numerator:d.getUint8(p),denominator:2**d.getUint8(p+1)});
          }
          p+=len;
        }else if(status===240||status===247){
          runningStatus=0;const len=vlq();p+=len;
        }else{
          const hi=status&240;p+=(hi===192||hi===208)?1:2;
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
    const signatures=sigDedup.map(e=>({...e,beat:e.tick/division,measureBeats:e.numerator*4/e.denominator}));
    return {division,segments,signatures};
  }

  function secondsToBeat(sec,timing){
    const segs=timing.segments;let seg=segs[0];
    for(let i=1;i<segs.length&&segs[i].sec<=sec;i++)seg=segs[i];
    const tick=seg.tick+(sec-seg.sec)*1e6/seg.us*timing.division;
    return tick/timing.division;
  }

  /* Measure lines are a chart invariant, not a song-specific feature.
     Valid MIDI time signatures are respected; missing or malformed data falls
     back to 4/4 so every song always has one separator per measure. */
  function normalizedSignatures(timing){
    if(timing&&typeof timing==="object"&&signatureCache.has(timing))return signatureCache.get(timing);
    const raw=Array.isArray(timing?.signatures)?timing.signatures:[],out=[];
    for(const sig of raw){
      const beat=Number(sig?.beat),measureBeats=Number(sig?.measureBeats);
      if(!Number.isFinite(beat)||beat<0||!Number.isFinite(measureBeats)||measureBeats<=0)continue;
      const entry={beat,measureBeats};
      if(out.length&&Math.abs(out[out.length-1].beat-beat)<1e-7)out[out.length-1]=entry;
      else out.push(entry);
    }
    if(!out.length||out[0].beat>1e-7)out.unshift({beat:0,measureBeats:4});
    if(timing&&typeof timing==="object")signatureCache.set(timing,out);
    return out;
  }

  function drawMeasureLines(ctx,w,h,judgeX,beatNow,timing,pxPerQuarter=PIXELS_PER_QUARTER){
    const speed=Number.isFinite(pxPerQuarter)&&pxPerQuarter>0?pxPerQuarter:PIXELS_PER_QUARTER,
          signatures=normalizedSignatures(timing),
          firstVisibleBeat=beatNow-judgeX/speed,
          lastVisibleBeat=beatNow+(w-judgeX)/speed;
    ctx.save();
    ctx.strokeStyle="rgba(255,255,255,.245)";
    ctx.lineWidth=1;
    for(let i=0;i<signatures.length;i++){
      const sig=signatures[i],segmentStart=sig.beat,
            segmentEnd=i+1<signatures.length?signatures[i+1].beat:Infinity,
            measureBeats=sig.measureBeats;
      let barBeat=segmentStart+Math.ceil((firstVisibleBeat-segmentStart)/measureBeats)*measureBeats;
      if(barBeat<segmentStart)barBeat=segmentStart;
      for(;barBeat<=lastVisibleBeat+.0001&&barBeat<segmentEnd-.0001;barBeat+=measureBeats){
        const x=judgeX+(barBeat-beatNow)*speed;
        if(x<0||x>w)continue;
        const crisp=Math.round(x)+.5;
        ctx.beginPath();ctx.moveTo(crisp,0);ctx.lineTo(crisp,h);ctx.stroke();
      }
    }
    ctx.restore();
  }

  function visibleRange(notes,minTick,maxTick){
    const search=globalThis.DruMasterNoteSearch;
    if(search?.visibleTickRange)return search.visibleTickRange(notes,minTick,maxTick);
    return {start:0,end:notes.length};
  }

  function laneForGroup(group){return group==="cymbal"?0:group==="hh"?1:group==="drums"?2:3}

  function simultaneousNoteOffsets(notes,start,end,skipHit,groupMap,noteWidthScale){
    const buckets=new Map(),offsets=new WeakMap(),gap=1;
    for(let i=start;i<end;i++){
      const note=notes[i];
      if(skipHit&&note.hit)continue;
      const group=groupMap[note.type],lane=laneForGroup(group),key=`${note.tick}|${lane}`,
            midiNote=Number(note.note),
            slotKey=Number.isFinite(midiNote)?`midi:${midiNote}`:`type:${note.type}`;
      let bucket=buckets.get(key);
      if(!bucket){bucket=new Map();buckets.set(key,bucket)}
      let slot=bucket.get(slotKey);
      if(!slot){
        slot={width:noteVisual(note.type,group,noteWidthScale).totalWidth,notes:[],midiNote,type:note.type};
        bucket.set(slotKey,slot);
      }
      slot.notes.push(note);
    }
    for(const bucket of buckets.values()){
      if(bucket.size<2)continue;
      const slots=[...bucket.values()].sort((a,b)=>{
        const aMidi=Number.isFinite(a.midiNote)?a.midiNote:Infinity,
              bMidi=Number.isFinite(b.midiNote)?b.midiNote:Infinity;
        return aMidi-bMidi||String(a.type).localeCompare(String(b.type));
      }),totalWidth=slots.reduce((sum,slot)=>sum+slot.width,0)+gap*(slots.length-1);
      let cursor=-totalWidth/2;
      for(const slot of slots){
        const offset=cursor+slot.width/2;
        for(const note of slot.notes)offsets.set(note,offset);
        cursor+=slot.width+gap;
      }
    }
    return offsets;
  }

  function draw({ctx,canvas,notes,currentSec,timing,groupMap,skipHit=true}){
    const w=canvas.clientWidth,h=canvas.clientHeight,beatNow=secondsToBeat(currentSec,timing),division=timing.division||480,
          judgeX=judgementX(w),judgeZoneW=judgementZoneWidth(w),kickH=Math.max(16,h*.12),mainH=h-kickH,laneH=mainH/3,
          labelFont=Math.max(9,laneH*.13),labels=["CYMBAL","HI-HAT / RIDE / OTHER","SNARE / TOMS"],
          noteWidthScale=isMobileLayout()?1:DESKTOP_NOTE_WIDTH_SCALE;
    ctx.clearRect(0,0,w,h);ctx.fillStyle="#030507";ctx.fillRect(0,0,w,h);
    for(let i=0;i<3;i++){
      ctx.fillStyle="#030507";ctx.fillRect(0,laneH*i,w,laneH);
      if(i>0){ctx.strokeStyle="#53677d";ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(0,laneH*i+.5);ctx.lineTo(w,laneH*i+.5);ctx.stroke()}
      ctx.fillStyle="#8b97a6";ctx.font=`700 ${labelFont}px system-ui,sans-serif`;ctx.textAlign="left";ctx.textBaseline="top";ctx.fillText(labels[i],7,laneH*i+6);
    }
    ctx.fillStyle="#030507";ctx.fillRect(0,mainH,w,kickH);
    ctx.strokeStyle="#5b6d82";ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(0,mainH+.5);ctx.lineTo(w,mainH+.5);ctx.stroke();
    ctx.fillStyle="#687483";ctx.font=`700 ${labelFont}px system-ui,sans-serif`;ctx.textAlign="left";ctx.textBaseline="middle";ctx.fillText("KICK · AUTO",7,mainH+kickH/2);
    drawMeasureLines(ctx,w,h,judgeX,beatNow,timing,PIXELS_PER_QUARTER);
    ctx.fillStyle="#eef6ff10";ctx.fillRect(judgeX-judgeZoneW/2,0,judgeZoneW,h);
    ctx.strokeStyle="#f3f8ff";ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(judgeX,0);ctx.lineTo(judgeX,h);ctx.stroke();

    const minBeat=beatNow-48/PIXELS_PER_QUARTER,
          maxBeat=beatNow+(w+48-judgeX)/PIXELS_PER_QUARTER,
          {start,end}=visibleRange(notes,minBeat*division,maxBeat*division),
          noteOffsets=simultaneousNoteOffsets(notes,start,end,skipHit,groupMap,noteWidthScale);
    for(let i=start;i<end;i++){
      const n=notes[i];
      if(skipHit&&n.hit)continue;
      const x=judgeX+(n.tick/division-beatNow)*PIXELS_PER_QUARTER+(noteOffsets.get(n)||0);
      const group=groupMap[n.type],lane=laneForGroup(group),alpha=.48+.52*n.velocity/127,visual=noteVisual(n.type,group,noteWidthScale);
      ctx.globalAlpha=n.type==="hhPedal"?.24+.18*n.velocity/127:n.type==="kick"?.32+.28*n.velocity/127:alpha;ctx.fillStyle=visual.color;
      if(lane<3){
        const barTop=lane*laneH,barH=laneH;
        if(visual.kind==="double"){
          const left=x-visual.totalWidth/2;ctx.fillRect(left,barTop,visual.barWidth,barH);ctx.fillRect(left+visual.barWidth+visual.gap,barTop,visual.barWidth,barH);
        }else ctx.fillRect(x-visual.totalWidth/2,barTop,visual.barWidth,barH);
      }else ctx.fillRect(x-visual.totalWidth/2,mainH,visual.barWidth,kickH);
    }
    ctx.globalAlpha=1;ctx.textAlign="start";ctx.textBaseline="alphabetic";
  }

  return {PIXELS_PER_QUARTER,MOBILE_JUDGE_OFFSET,isMobileLayout,judgementX,judgementZoneWidth,noteColor,noteVisual,parseTempoTiming,secondsToBeat,drawMeasureLines,simultaneousNoteOffsets,draw};
})();
