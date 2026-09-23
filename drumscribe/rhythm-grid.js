// Musical grid reconstruction for exported MIDI.
// Detected drum classes/timestamps are never rewritten upstream. This module
// only decides score ticks and a tempo map for MIDI export.
//
// Design:
//   1. Assume straight 16ths by default; allow 32nds when 16th fit is weak.
//   2. Switch to a triplet grid only when local timing evidence is clearly
//      stronger than the straight grid.
//   3. Estimate slow grid-phase drift in overlapping windows. Drift becomes a
//      MIDI tempo map, while note starts are snapped to score subdivisions.
//   4. Keep MIDI tick zero fixed: bar/downbeat alignment from transcription is
//      not moved by this module.

export const GRID_PPQ=480;

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const mean=a=>a.length?a.reduce((x,y)=>x+y,0)/a.length:0;

function noteWeight(note){
  if([35,36,37,38,39,40].includes(note))return 3.0; // kick/snare
  if([41,43,45,47,48,50].includes(note))return 1.7; // toms
  if([49,51,52,53,55,57,58,59].includes(note))return 1.25; // cymbals
  return .75; // hats/other repeated timekeepers
}

function circularWindow(events,center,halfWidth,step){
  let c=0,s=0,w=0;
  for(const e of events){
    if(Math.abs(e.q-center)>halfWidth)continue;
    const a=2*Math.PI*e.q/step;
    c+=e.weight*Math.cos(a);
    s+=e.weight*Math.sin(a);
    w+=e.weight;
  }
  if(w<6)return null;
  return {
    phase:Math.atan2(s,c)*step/(2*Math.PI),
    concentration:Math.hypot(c,s)/w,
    weight:w
  };
}

function localConcentration(events,step,maxQ){
  const values=[];
  for(let center=4;center<=maxQ;center+=8){
    const x=circularWindow(events,center,8,step);
    if(x)values.push(x.concentration);
  }
  return values.length?mean(values):0;
}

function unwrapPhases(points,step){
  if(!points.length)return points;
  // MIDI score origin is already a detected bar boundary. Preserve it.
  points[0].phase=0;
  for(let i=1;i<points.length;i++){
    let p=points[i].phase;
    const prev=points[i-1].phase;
    while(p-prev>step/2)p-=step;
    while(p-prev<-step/2)p+=step;
    points[i].phase=p;
  }
  return points;
}

function smoothPhases(points,passes=2){
  let out=points.map(x=>({...x}));
  for(let pass=0;pass<passes;pass++){
    const next=out.map(x=>({...x}));
    for(let i=1;i+1<out.length;i++){
      next[i].phase=(out[i-1].phase+2*out[i].phase+out[i+1].phase)/4;
    }
    next[0].phase=0;
    out=next;
  }
  return out;
}

function interpolate(points,key,valueKey,x){
  if(!points.length)return 0;
  if(x<=points[0][key])return points[0][valueKey];
  if(x>=points[points.length-1][key])return points[points.length-1][valueKey];
  let lo=0,hi=points.length-1;
  while(lo+1<hi){
    const mid=(lo+hi)>>1;
    if(points[mid][key]<=x)lo=mid;else hi=mid;
  }
  const a=points[lo],b=points[hi];
  const f=(x-a[key])/(b[key]-a[key]||1);
  return a[valueKey]+(b[valueKey]-a[valueKey])*f;
}

function chooseGrid(events,maxQ){
  const fit8=localConcentration(events,.5,maxQ);
  const fit16=localConcentration(events,.25,maxQ);
  const fit32=localConcentration(events,.125,maxQ);
  const fit8t=localConcentration(events,1/3,maxQ);
  const fit16t=localConcentration(events,1/6,maxQ);

  // Triplet/shuffle must win clearly. A finer triplet grid can otherwise fit
  // ordinary straight material by chance.
  const bestStraight=Math.max(fit16,fit32);
  const bestTriplet=Math.max(fit8t,fit16t);
  const triplet=bestTriplet>=.72&&bestTriplet>bestStraight+.10;

  if(triplet){
    const step=fit8t>=.90&&fit8t>=fit16t-.02?1/3:1/6;
    return {
      family:'triplet',
      step,
      label:step===1/3?'1/8T':'1/16T',
      fit:{straight8:fit8,straight16:fit16,straight32:fit32,triplet8:fit8t,triplet16:fit16t}
    };
  }

  // 16ths cover the great majority of the reference charts. Only make 32nds
  // the global base grid when the 16th phase is genuinely diffuse. Isolated
  // 32nd fills are handled per note later.
  const use32=fit16<.78&&fit32>fit16+.10;
  return {
    family:'straight',
    step:use32?.125:.25,
    label:use32?'1/32':'1/16',
    fit:{straight8:fit8,straight16:fit16,straight32:fit32,triplet8:fit8t,triplet16:fit16t}
  };
}

function buildPhaseCurve(events,maxQ,step){
  const points=[];
  for(let center=0;center<=maxQ+4;center+=4){
    const x=circularWindow(events,center,8,step);
    if(x)points.push({q:center,phase:x.phase,concentration:x.concentration});
  }
  if(!points.length)return [{q:0,phase:0,concentration:0}];
  if(points[0].q!==0)points.unshift({q:0,phase:0,concentration:points[0].concentration});
  return smoothPhases(unwrapPhases(points,step),2);
}

function movingMean(values,radius=2){
  return values.map((_,i)=>{
    let s=0,n=0;
    for(let j=Math.max(0,i-radius);j<=Math.min(values.length-1,i+radius);j++){s+=values[j];n++;}
    return s/Math.max(1,n);
  });
}

export function buildRhythmGrid(events,bpm=120,timing={}){
  bpm=Number.isFinite(bpm)&&bpm>=30&&bpm<=300?bpm:120;
  const ppq=GRID_PPQ;
  const numerator=Number.isFinite(timing?.numerator)?Math.max(1,Math.round(timing.numerator)):4;
  const denominator=Number.isFinite(timing?.denominator)?Math.max(1,Math.round(timing.denominator)):4;
  const beatSec=60/bpm*4/denominator;
  const barSec=beatSec*numerator;
  const rawPhase=Number(timing?.barPhaseSec);
  const hasPhase=Number.isFinite(rawPhase)&&barSec>0;
  const phase=hasPhase?((rawPhase%barSec)+barSec)%barSec:0;
  const align=timing?.alignToBar!==false&&hasPhase;

  let barPad=0;
  if(align&&events?.length){
    let minMusical=Infinity;
    for(const e of events)minMusical=Math.min(minMusical,Number(e.time)-phase);
    if(Number.isFinite(minMusical)&&minMusical<0)barPad=Math.ceil(-minMusical/barSec);
  }
  const exportOffsetSec=align?barPad*barSec-phase:0;

  const usable=(events||[]).map((e,index)=>{
    const musicalTime=Number(e.time)+exportOffsetSec;
    return {
      index,
      q:musicalTime/beatSec,
      time:musicalTime,
      note:Number(e.note),
      weight:noteWeight(Number(e.note))
    };
  }).filter(e=>Number.isFinite(e.q)&&Number.isFinite(e.note)&&e.q>=-.5);

  if(!usable.length){
    return {
      ppq,bpm,numerator,denominator,beatSec,barSec,phase,barPad,exportOffsetSec,
      eventTicks:[],tempoMap:[{tick:0,bpm,us:Math.round(60000000/bpm)}],
      info:{enabled:false,reason:'no-events'}
    };
  }

  const maxQ=Math.max(4,...usable.map(e=>e.q));
  const grid=chooseGrid(usable,maxQ);
  const curve=buildPhaseCurve(usable,maxQ,grid.step);
  const delta=q=>interpolate(curve,'q','phase',q);

  const rawQForScore=score=>{
    let raw=score;
    for(let i=0;i<7;i++)raw=score+delta(raw);
    return raw;
  };

  const correctedQ=raw=>raw-delta(raw);
  const snapQ=raw=>{
    const q=correctedQ(raw);
    if(grid.family==='triplet'||grid.step===.125)return Math.round(q/grid.step)*grid.step;
    const q16=Math.round(q/.25)*.25;
    const d16=Math.abs(q-q16);
    const q32=Math.round(q/.125)*.125;
    const d32=Math.abs(q-q32);
    // A true 32nd midpoint is .125 beat away from a 16th. Require the event
    // to be clearly outside ordinary timing jitter before retaining it as 32nd.
    return d16>.10&&d32<=.035?q32:q16;
  };

  // Convert the phase-drift derivative into quarter-note BPM values. q is a
  // denominator-beat coordinate, while MIDI set_tempo always describes a
  // quarter note.
  const maxBeat=Math.ceil(maxQ+4);
  const rawBeatTimes=[];
  for(let b=0;b<=maxBeat;b++)rawBeatTimes.push(rawQForScore(b)*beatSec);
  let localBpms=[];
  for(let b=0;b<rawBeatTimes.length-1;b++){
    const sec=rawBeatTimes[b+1]-rawBeatTimes[b];
    const denominatorBeatBpm=sec>0?60/sec:bpm*denominator/4;
    localBpms.push(denominatorBeatBpm*4/denominator);
  }
  localBpms=movingMean(localBpms,2);
  // Tempo changes caused by phase-noise should not create implausible jumps.
  // ±3% is deliberately conservative; future rubato-specific work can widen it.
  localBpms=localBpms.map(x=>clamp(x,bpm*.97,bpm*1.03));

  // MIDI tempo changes are emitted no more often than once per measure.
  // Preserve the total duration of each measure by replacing its beat-level
  // BPMs with one duration-equivalent BPM. This keeps bar boundaries locked
  // while avoiding a new tempo event on every beat.
  const beatsPerBar=Math.max(1,numerator);
  const tempoBars=[];
  const playbackBpms=Array(localBpms.length).fill(bpm);
  for(let start=0;start<localBpms.length;start+=beatsPerBar){
    const end=Math.min(localBpms.length,start+beatsPerBar);
    let durationSec=0,quarterBeats=0;
    for(let b=start;b<end;b++){
      durationSec+=60/localBpms[b]*4/denominator;
      quarterBeats+=4/denominator;
    }
    const equivalent=durationSec>0?60*quarterBeats/durationSec:bpm;
    const barBpm=clamp(equivalent,bpm*.97,bpm*1.03);
    tempoBars.push({startBeat:start,endBeat:end,bpm:barBpm});
    for(let b=start;b<end;b++)playbackBpms[b]=barBpm;
  }

  // Reintegrate the bar-level tempo sequence so score ticks map to the same
  // continuous timeline used by exported MIDI and preview playback.
  const beatTimes=[0];
  for(const x of playbackBpms)beatTimes.push(beatTimes[beatTimes.length-1]+60/x*4/denominator);

  const timeForScore=q=>{
    if(q<=0)return q*60/(playbackBpms[0]||bpm)*4/denominator;
    const i=Math.floor(q),f=q-i;
    if(i>=beatTimes.length-1){
      const tail=playbackBpms[playbackBpms.length-1]||bpm;
      return beatTimes[beatTimes.length-1]+(q-(beatTimes.length-1))*60/tail*4/denominator;
    }
    return beatTimes[i]+f*(beatTimes[i+1]-beatTimes[i]);
  };

  const eventTicks=Array(events?.length||0).fill(0);
  let straight16Count=0,straight32OnlyCount=0;
  for(const e of usable){
    const scoreQ=snapQ(e.q);
    const tick=Math.max(0,Math.round(scoreQ*ppq*4/denominator));
    eventTicks[e.index]=tick;
    if(tick%(ppq/4)===0)straight16Count++;
    else if(tick%(ppq/8)===0)straight32OnlyCount++;
  }

  const tempoMap=[];
  let previousUs=null;
  const ticksPerBeat=ppq*4/denominator;
  for(const bar of tempoBars){
    const us=Math.round(60000000/bar.bpm);
    if(previousUs===null||us!==previousUs){
      tempoMap.push({tick:Math.round(bar.startBeat*ticksPerBeat),bpm:bar.bpm,us});
      previousUs=us;
    }
  }
  if(!tempoMap.length)tempoMap.push({tick:0,bpm,us:Math.round(60000000/bpm)});

  const meanConcentration=mean(curve.map(x=>x.concentration));
  const subdivision=grid.family==='straight'&&grid.step===.25&&straight32OnlyCount>0?'1/16+1/32':grid.label;
  return {
    ppq,bpm,numerator,denominator,beatSec,barSec,phase,barPad,exportOffsetSec,
    eventTicks,tempoMap,timeForScore,
    info:{
      enabled:true,
      family:grid.family,
      subdivision,
      stepBeats:grid.step,
      fit:grid.fit,
      phaseConcentration:meanConcentration,
      tempoEvents:tempoMap.length,
      tempoResolution:'bar',
      tempoBeatsPerMeasure:beatsPerBar,
      tempoMin:Math.min(...tempoBars.map(x=>x.bpm)),
      tempoMax:Math.max(...tempoBars.map(x=>x.bpm)),
      tempoMean:mean(playbackBpms),
      straight16Share:straight16Count/Math.max(1,usable.length),
      straight32OnlyShare:straight32OnlyCount/Math.max(1,usable.length)
    }
  };
}
