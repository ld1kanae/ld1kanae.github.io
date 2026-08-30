"use strict";

(()=>{
  const hitLayer=document.querySelector("#hitLayer");
  if(!hitLayer)return;

  const gauge=document.createElement("div"),
        fill=document.createElement("div"),
        handle=document.createElement("div");
  gauge.id="hhOpenGauge";
  gauge.setAttribute("aria-hidden","true");
  fill.id="hhOpenGaugeFill";
  handle.id="hhOpenGaugeHandle";
  gauge.append(fill,handle);
  hitLayer.appendChild(gauge);

  const HH_TYPES=new Set(["hhClosed","hhOpen","hhPedal"]);
  const VELOCITY_CURVE=Math.log(.4)/Math.log(100/127);
  const DISPLAY_SMOOTH_MS=35;
  const OPEN_RAMP_BEATS=.25;
  let cachedNotes=null,cachedTiming=null,events=[];
  let displayedLevel=0,lastFrameMs=performance.now(),lastBeat=NaN;

  const clamp01=value=>Math.max(0,Math.min(1,value));
  const easeOutQuart=value=>1-Math.pow(1-clamp01(value),4);
  const velocityToLevel=velocity=>{
    const normalized=Math.max(0,Math.min(127,Number(velocity)||0))/127;
    return normalized<=0?0:Math.pow(normalized,VELOCITY_CURVE);
  };

  function upperBoundBeat(list,beat){
    let lo=0,hi=list.length;
    while(lo<hi){const mid=(lo+hi)>>>1;if(list[mid].beat<=beat)lo=mid+1;else hi=mid}
    return lo;
  }

  function rebuildEnvelope(source,timing){
    const division=Number(timing?.division)||480;
    const actual=[];
    for(const note of source){
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
      if(event.target>0&&(!next||next.beat-event.beat>2)){
        timeline.push({beat:event.beat+2,target:0,synthetic:true});
      }
    }
    timeline.sort((a,b)=>a.beat-b.beat||(a.synthetic?1:-1));

    events=[];
    let previousBeat=-Infinity,previousTarget=0;
    for(const event of timeline){
      if(events.length&&Math.abs(events[events.length-1].beat-event.beat)<1e-7){
        const prior=events.pop();
        previousTarget=prior.from;
        previousBeat=events.length?events[events.length-1].beat:-Infinity;
      }
      const rampStart=Number.isFinite(previousBeat)
        ?Math.max(event.beat-OPEN_RAMP_BEATS,previousBeat)
        :event.beat-OPEN_RAMP_BEATS;
      events.push({...event,from:previousTarget,rampStart});
      previousBeat=event.beat;
      previousTarget=event.target;
    }
  }

  function valueAtBeat(beat){
    const nextIndex=upperBoundBeat(events,beat),previous=events[nextIndex-1],next=events[nextIndex];
    let value=previous?.target||0;
    if(next&&beat>=next.rampStart&&beat<next.beat){
      const span=next.beat-next.rampStart;
      if(span<=1e-7)return next.target;
      const progress=(beat-next.rampStart)/span;
      value=next.from+(next.target-next.from)*easeOutQuart(progress);
    }
    return value;
  }

  function resetGauge(){
    displayedLevel=0;
    lastBeat=NaN;
    lastFrameMs=performance.now();
    fill.style.setProperty("--hh-open-gauge-scale","0");
    fill.style.setProperty("--hh-open-gauge-opacity",".3");
    handle.style.bottom="0%";
  }

  function smoothLevel(target,beat){
    const now=performance.now();
    const dt=Math.min(100,Math.max(0,now-lastFrameMs));
    lastFrameMs=now;
    if(!Number.isFinite(lastBeat)||beat<lastBeat-.05||Math.abs(beat-lastBeat)>1){
      displayedLevel=target;
    }else{
      const alpha=1-Math.exp(-dt/DISPLAY_SMOOTH_MS);
      displayedLevel+=(target-displayedLevel)*alpha;
      if(Math.abs(target-displayedLevel)<.01)displayedLevel=target;
    }
    lastBeat=beat;
    return displayedLevel;
  }

  function updateGauge(){
    let source,timing,beat;
    try{
      source=Array.isArray(notes)?notes:null;
      timing=typeof beatTiming!=="undefined"?beatTiming:null;
      if(!source||!timing||typeof current!=="function")throw Error();
      if(source!==cachedNotes||timing!==cachedTiming){
        cachedNotes=source;
        cachedTiming=timing;
        rebuildEnvelope(source,timing);
      }
      beat=globalThis.DruMusterChart.secondsToBeat(current(),timing);
    }catch{
      resetGauge();
      return;
    }
    const velocity=valueAtBeat(beat),baseLevel=velocityToLevel(velocity)*100;
    const level=smoothLevel(baseLevel,beat);
    fill.style.setProperty("--hh-open-gauge-scale",(level/100).toFixed(5));
    fill.style.setProperty("--hh-open-gauge-opacity",(0.3+0.7*level/100).toFixed(3));
    handle.style.bottom=level.toFixed(3)+"%";
  }

  if(typeof draw==="function"){
    const baseDraw=draw;
    draw=function(){
      const result=baseDraw();
      updateGauge();
      return result;
    };
  }
  updateGauge();
})();
