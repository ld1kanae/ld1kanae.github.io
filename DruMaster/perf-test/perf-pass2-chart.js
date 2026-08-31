"use strict";

(()=>{
  if(typeof DruMusterChart!=="object"||typeof draw!=="function")return;

  const baseDraw=DruMusterChart.draw.bind(DruMusterChart);
  const hiddenTypes=new Set(["hhPedal"]);
  const HH_TYPES=new Set(["hhClosed","hhOpen","hhPedal"]);
  const VELOCITY_CURVE=Math.log(.4)/Math.log(100/127);
  const OPEN_RAMP_BEATS=.1875;
  const CLOSE_LEAD_BEATS=.0625;
  const CLOSE_RAMP_BEATS=.25;
  let graphNotes=null,graphTiming=null,graphEvents=[];

  const stats={frames:0,samples:0};
  const clamp01=value=>Math.max(0,Math.min(1,value));
  const easeOutQuart=value=>1-Math.pow(1-clamp01(value),4);
  const easeInOutQuart=value=>{const t=clamp01(value);return t<.5?8*t*t*t*t:1-Math.pow(-2*t+2,4)/2};
  const velocityToLevel=velocity=>{
    const normalized=Math.max(0,Math.min(127,Number(velocity)||0))/127;
    return normalized<=0?0:Math.pow(normalized,VELOCITY_CURVE);
  };

  function upperBound(beat){
    let lo=0,hi=graphEvents.length;
    while(lo<hi){const mid=(lo+hi)>>>1;if(graphEvents[mid].rampEnd<=beat)lo=mid+1;else hi=mid}
    return lo;
  }

  function rebuildEnvelope(){
    if(graphNotes===notes&&graphTiming===beatTiming)return;
    graphNotes=notes;
    graphTiming=beatTiming;
    const division=Number(beatTiming?.division)||480,actual=[];
    for(const note of notes){
      if(!HH_TYPES.has(note.type))continue;
      actual.push({
        beat:Number(note.tick)/division,
        target:note.type==="hhOpen"?Math.max(0,Math.min(127,Number(note.velocity)||0)):0,
        synthetic:false
      });
    }
    actual.sort((a,b)=>a.beat-b.beat);
    const timeline=[];
    for(let i=0;i<actual.length;i++){
      const event=actual[i],next=actual[i+1];
      timeline.push(event);
      if(event.target>0&&(!next||next.beat-event.beat>2))timeline.push({beat:event.beat+2,target:0,synthetic:true});
    }
    timeline.sort((a,b)=>a.beat-b.beat||(a.synthetic?1:-1));
    graphEvents=[];
    let previousBeat=-Infinity,previousTarget=0;
    for(let i=0;i<timeline.length;i++){
      const event=timeline[i],following=timeline[i+1];
      if(graphEvents.length&&Math.abs(graphEvents[graphEvents.length-1].beat-event.beat)<1e-7){
        const prior=graphEvents.pop();
        previousTarget=prior.from;
        previousBeat=graphEvents.length?graphEvents[graphEvents.length-1].beat:-Infinity;
      }
      const closing=event.target<previousTarget;
      const rampStart=closing
        ?(Number.isFinite(previousBeat)?Math.max(event.beat-CLOSE_LEAD_BEATS,previousBeat):event.beat-CLOSE_LEAD_BEATS)
        :(Number.isFinite(previousBeat)?Math.max(event.beat-OPEN_RAMP_BEATS,previousBeat):event.beat-OPEN_RAMP_BEATS);
      const rampEnd=closing?Math.min(rampStart+CLOSE_RAMP_BEATS,following?.beat??Infinity):event.beat;
      graphEvents.push({...event,from:previousTarget,rampStart,rampEnd,closing});
      previousBeat=event.beat;
      previousTarget=event.target;
    }
  }

  function velocityAtBeat(beat){
    const nextIndex=upperBound(beat),previous=graphEvents[nextIndex-1],next=graphEvents[nextIndex];
    let value=previous?.target||0;
    if(next&&beat>=next.rampStart&&beat<next.rampEnd){
      const span=next.rampEnd-next.rampStart;
      if(span<=1e-7)return next.target;
      const progress=(beat-next.rampStart)/span;
      const eased=next.closing?easeInOutQuart(progress):easeOutQuart(progress);
      value=next.from+(next.target-next.from)*eased;
    }
    return value;
  }

  function drawGraph(){
    if(!Array.isArray(notes)||!notes.length)return;
    rebuildEnvelope();
    if(!graphEvents.length)return;

    const w=canvas.clientWidth,h=canvas.clientHeight;
    const beatNow=DruMusterChart.secondsToBeat(current(),beatTiming);
    const judgeX=DruMusterChart.judgementX(w);
    const kickH=Math.max(16,h*.12),mainH=h-kickH;
    const speed=DruMusterChart.pixelsPerQuarter?.()||DruMusterChart.PIXELS_PER_QUARTER||80;
    const bottom=h,span=kickH;
    const samplePx=DruMusterChart.isMobileLayout?.()?9:3;
    const fullOpacity=document.body.dataset.scorePlayback==="1"||(typeof autoplay!=="undefined"&&autoplay);
    const graphAlpha=fullOpacity?.42:.20;
    const cyan=`rgba(82,223,207,${graphAlpha})`;
    let frameSamples=0;

    ctx.save();
    ctx.beginPath();ctx.rect(0,mainH,w,kickH);ctx.clip();
    ctx.fillStyle=cyan;
    ctx.strokeStyle=cyan;
    ctx.lineWidth=1.2;
    ctx.lineJoin="round";
    ctx.lineCap="round";

    if(typeof Path2D==="function"){
      const fillPath=new Path2D(),strokePath=new Path2D();
      let active=false,lastX=0;
      for(let x=0;x<=w+samplePx;x+=samplePx){
        frameSamples++;
        const beat=beatNow+(x-judgeX)/speed;
        const velocity=velocityAtBeat(beat);
        if(velocity<1){
          if(active){fillPath.lineTo(lastX,bottom);fillPath.closePath();active=false}
          continue;
        }
        const y=bottom-velocityToLevel(velocity)*span;
        if(!active){
          fillPath.moveTo(x,bottom);fillPath.lineTo(x,y);
          strokePath.moveTo(x,y);
          active=true;
        }else{
          fillPath.lineTo(x,y);
          strokePath.lineTo(x,y);
        }
        lastX=x;
      }
      if(active){fillPath.lineTo(lastX,bottom);fillPath.closePath()}
      ctx.fill(fillPath);
      ctx.stroke(strokePath);
    }else{
      const runs=[];let run=[];
      for(let x=0;x<=w+samplePx;x+=samplePx){
        frameSamples++;
        const beat=beatNow+(x-judgeX)/speed,velocity=velocityAtBeat(beat);
        if(velocity<1){if(run.length){runs.push(run);run=[]}continue}
        run.push({x,y:bottom-velocityToLevel(velocity)*span});
      }
      if(run.length)runs.push(run);
      for(const points of runs){
        const first=points[0],last=points[points.length-1];
        ctx.beginPath();ctx.moveTo(first.x,bottom);ctx.lineTo(first.x,first.y);
        for(let i=1;i<points.length;i++)ctx.lineTo(points[i].x,points[i].y);
        ctx.lineTo(last.x,bottom);ctx.closePath();ctx.fill();
        ctx.beginPath();ctx.moveTo(first.x,first.y);
        for(let i=1;i<points.length;i++)ctx.lineTo(points[i].x,points[i].y);
        ctx.stroke();
      }
    }
    ctx.restore();
    stats.frames++;
    stats.samples+=frameSamples;
  }

  function redrawKickAutoNotes(){
    if(!Array.isArray(notes)||!notes.length)return;
    const w=canvas.clientWidth,h=canvas.clientHeight;
    const beatNow=DruMusterChart.secondsToBeat(current(),beatTiming),division=beatTiming.division||480;
    const judgeX=DruMusterChart.judgementX(w),speed=DruMusterChart.pixelsPerQuarter?.()||DruMusterChart.PIXELS_PER_QUARTER||80;
    const kickH=Math.max(16,h*.12),mainH=h-kickH,minBeat=beatNow-48/speed,maxBeat=beatNow+(w+48-judgeX)/speed;
    const search=globalThis.DruMasterNoteSearch;
    const range=search?.visibleTickRange?search.visibleTickRange(notes,minBeat*division,maxBeat*division):{start:0,end:notes.length};
    const isDesktop=!!globalThis.matchMedia?.("(hover:hover) and (pointer:fine)")?.matches,noteWidthScale=isDesktop?1.5:1;
    const offsets=DruMusterChart.simultaneousNoteOffsets?.(notes,range.start,range.end,true,GROUP,noteWidthScale,hiddenTypes)||new WeakMap();
    const barTop=isDesktop?mainH+2:mainH,barH=isDesktop?Math.max(1,kickH-4):kickH;
    ctx.save();
    for(let i=range.start;i<range.end;i++){
      const n=notes[i];
      if(n.hit||hiddenTypes.has(n.type)||GROUP[n.type]!=="kick")continue;
      const x=judgeX+(n.tick/division-beatNow)*speed+(offsets.get(n)||0);
      const visual=DruMusterChart.noteVisual(n.type,GROUP[n.type],noteWidthScale);
      const alpha=n.type==="kick"?.32+.28*n.velocity/127:.48+.52*n.velocity/127;
      ctx.globalAlpha=alpha;ctx.fillStyle=visual.color;ctx.fillRect(x-visual.totalWidth/2,barTop,visual.barWidth,barH);
    }
    ctx.restore();
  }

  draw=function(){
    baseDraw({ctx,canvas,notes,currentSec:current(),timing:beatTiming,groupMap:GROUP,skipHit:true,hiddenTypes});
    drawGraph();
    redrawKickAutoNotes();
  };

  globalThis.DruMasterPerfChartPass2={version:"20260901-pass2",stats};
})();
