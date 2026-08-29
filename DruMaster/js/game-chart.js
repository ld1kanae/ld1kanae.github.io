"use strict";

// Production adapter for the shared chart engine. Preview uses the same engine/file.
let beatTiming={division:480,segments:[{tick:0,sec:0,us:500000}]};
const timingReady=fetch(ASSET.midi,{cache:"force-cache"})
  .then(r=>r.ok?r.arrayBuffer():Promise.reject())
  .then(ab=>{beatTiming=DruMusterChart.parseTempoTiming(ab)})
  .catch(()=>{});

globalThis.DruMasterChartTimingReady=timingReady;

/* Hi-hat pedal (GM note 44) is a foot-operated AUTO note, like kick.
   Keep the MIDI note for audio, but remove it from hand judgement and draw it
   in the KICK · AUTO lane with a quieter cyan bar. */
if(typeof GROUP!=="undefined")GROUP.hhPedal="kick";
if(typeof PART!=="undefined")PART.hhPedal="autoFoot";

const playedFootPedals=new WeakSet();
let footCursor=0,lastRunStart=NaN;

function lowerBoundFootTime(sec){
  let lo=0,hi=notes.length;
  while(lo<hi){const mid=(lo+hi)>>1;if(notes[mid].time<sec)lo=mid+1;else hi=mid}
  return lo;
}

function resetFootAutoForRun(){
  const start=Number(startedAt);
  if(start===lastRunStart)return;
  lastRunStart=start;
  footCursor=lowerBoundFootTime(Math.max(0,current()-.05));
  if(typeof maxScore!=="undefined"&&typeof weight==="function"){
    maxScore=Math.max(1,notes.filter(n=>n.type!=="kick"&&n.type!=="hhPedal").reduce((s,n)=>s+weight(n.type)*n.velocity/127,0)*1000);
  }
}

function flashFootGoal(n){
  /* Reuse the kick goal-line effect so AUTO foot notes get the same timing cue
     without entering judgement/scoring. The chart note itself stays hhPedal. */
  try{globalThis.DruMasterJudgement?.flashNote?.({...n,type:"kick"})}catch{}
}

function processFootAuto(){
  if(document.body.dataset.scorePlayback==="1")return;
  resetFootAutoForRun();
  const t=current();
  while(footCursor<notes.length&&notes[footCursor].time<=t+.012){
    const n=notes[footCursor++];
    if(n.type!=="hhPedal"||n.time<t-.04||playedFootPedals.has(n))continue;
    playedFootPedals.add(n);
    playDrum(n.note,n.type,n.velocity/127);
    flashFootGoal(n);
  }
}

function drawFootPedals(){
  if(!Array.isArray(notes)||!notes.length)return;
  const w=canvas.clientWidth,h=canvas.clientHeight,
        beatNow=DruMusterChart.secondsToBeat(current(),beatTiming),
        division=beatTiming.division||480,
        judgeX=DruMusterChart.judgementX(w),
        kickH=Math.max(16,h*.12),mainH=h-kickH,
        speed=DruMusterChart.PIXELS_PER_QUARTER||80,
        minBeat=beatNow-48/speed,maxBeat=beatNow+(w+48-judgeX)/speed;
  const search=globalThis.DruMasterNoteSearch,
        range=search?.visibleTickRange?search.visibleTickRange(notes,minBeat*division,maxBeat*division):{start:0,end:notes.length};
  ctx.save();
  ctx.fillStyle="#55bdc1";
  for(let i=range.start;i<range.end;i++){
    const n=notes[i];if(n.type!=="hhPedal")continue;
    const x=judgeX+(n.tick/division-beatNow)*speed;
    ctx.globalAlpha=.24+.18*n.velocity/127;
    ctx.fillRect(x-2,mainH,4,kickH);
  }
  ctx.restore();
}

const baseDraw=DruMusterChart.draw.bind(DruMusterChart);
draw=function(){
  const temporary=[];
  for(const n of notes){
    if(n.type==="hhPedal"){
      temporary.push([n,n.hit]);
      n.hit=true; // suppress the normal HH/kick-color rendering; custom AUTO bar is drawn below.
    }
  }
  baseDraw({
    ctx,
    canvas,
    notes,
    currentSec:current(),
    timing:beatTiming,
    groupMap:GROUP,
    skipHit:true
  });
  for(const [n,hit] of temporary)n.hit=hit;
  drawFootPedals();
};

if(typeof loop==="function"){
  const baseLoop=loop;
  loop=function(){
    if(running&&!paused){
      processFootAuto();
      const temporary=[];
      for(const n of notes){
        if(n.type==="hhPedal"&&playedFootPedals.has(n)&&!n.hit){temporary.push(n);n.hit=true}
      }
      try{return baseLoop()}
      finally{for(const n of temporary)n.hit=false}
    }
    return baseLoop();
  };
}
