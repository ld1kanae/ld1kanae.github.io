"use strict";

(()=>{
  const hitLayer=document.querySelector("#hitLayer");
  if(!hitLayer)return;

  const gauge=document.createElement("div"),fill=document.createElement("div");
  gauge.id="hhOpenGauge";
  gauge.setAttribute("aria-hidden","true");
  fill.id="hhOpenGaugeFill";
  gauge.appendChild(fill);
  hitLayer.appendChild(gauge);

  const HH_TYPES=new Set(["hhClosed","hhOpen","hhPedal"]);
  const VELOCITY_CURVE=Math.log(.5)/Math.log(100/127);
  let cachedNotes=null,cachedTiming=null,events=[];

  const clamp01=value=>Math.max(0,Math.min(1,value));
  const easeInOutSine=value=>-(Math.cos(Math.PI*clamp01(value))-1)/2;
  const velocityToLevel=velocity=>{
    const normalized=Math.max(0,Math.min(127,Number(velocity)||0))/127;
    return normalized<=0?0:Math.pow(normalized,VELOCITY_CURVE);
  };

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
        ?Math.max(event.beat-.5,previousBeat)
        :event.beat-.5;
      events.push({...event,from:previousTarget,rampStart});
      previousBeat=event.beat;
      previousTarget=event.target;
    }
  }

  function valueAtBeat(beat){
    let value=0;
    for(const event of events){
      if(beat<event.rampStart)return value;
      if(beat<event.beat){
        const span=event.beat-event.rampStart;
        if(span<=1e-7)return event.target;
        const progress=(beat-event.rampStart)/span;
        return event.from+(event.target-event.from)*easeInOutSine(progress);
      }
      value=event.target;
    }
    return value;
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
      fill.style.setProperty("--hh-open-gauge-level","0%");
      return;
    }
    const velocity=valueAtBeat(beat),level=velocityToLevel(velocity)*100;
    fill.style.setProperty("--hh-open-gauge-level",`${level.toFixed(3)}%`);
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
