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

function asKickGoalNote(n){return n?.type==="hhPedal"?{...n,type:"kick"}:n}
function flashFootGoal(n){try{globalThis.DruMasterJudgement?.flashNote?.(asKickGoalNote(n))}catch{}}

/* judgement.js is loaded after this adapter. Once available, make its shared
   flash entry point understand foot-pedal notes too. This also covers score
   playback, which emits note-synchronised flashes through the same API. */
function installFootGoalAdapter(){
  const j=globalThis.DruMasterJudgement;
  if(!j?.flashNote){requestAnimationFrame(installFootGoalAdapter);return}
  if(j.__dmFootGoalAdapter)return;
  const baseFlash=j.flashNote.bind(j),baseEmit=typeof j.emitForNote==="function"?j.emitForNote.bind(j):null;
  j.flashNote=note=>baseFlash(asKickGoalNote(note));
  if(baseEmit)j.emitForNote=(note,label,options={})=>baseEmit(asKickGoalNote(note),label,options);
  j.__dmFootGoalAdapter=true;
}
requestAnimationFrame(installFootGoalAdapter);

function processFootAuto(){
  if(document.body.dataset.scorePlayback==="1")return;
  resetFootAutoForRun();
  const t=current();
  while(footCursor<notes.length&&notes[footCursor].time<=t+.012){
    const n=notes[footCursor++];
    if(n.type!=="hhPedal")continue;
    /* AUTO foot notes must never become player MISSes. Mark them consumed even
       after a dropped frame; only suppress the sound when it is already too late. */
    if(n.hit)continue;
    n.hit=true;
    if(n.time<t-.08)continue;
    playDrum(n.note,n.type,n.velocity/127);
    flashFootGoal(n);
  }
}

function visibleFootRange(){
  if(!Array.isArray(notes)||!notes.length)return {start:0,end:0};
  const w=canvas.clientWidth,
        beatNow=DruMusterChart.secondsToBeat(current(),beatTiming),
        division=beatTiming.division||480,
        judgeX=DruMusterChart.judgementX(w),
        speed=DruMusterChart.pixelsPerQuarter?.()||DruMusterChart.PIXELS_PER_QUARTER||80,
        minBeat=beatNow-48/speed,maxBeat=beatNow+(w+48-judgeX)/speed,
        search=globalThis.DruMasterNoteSearch;
  return search?.visibleTickRange?search.visibleTickRange(notes,minBeat*division,maxBeat*division):{start:0,end:notes.length};
}

function drawFootPedals(){
  if(!Array.isArray(notes)||!notes.length)return;
  const w=canvas.clientWidth,h=canvas.clientHeight,
        beatNow=DruMusterChart.secondsToBeat(current(),beatTiming),
        division=beatTiming.division||480,
        judgeX=DruMusterChart.judgementX(w),
        kickH=Math.max(16,h*.12),mainH=h-kickH,
        speed=DruMusterChart.pixelsPerQuarter?.()||DruMusterChart.PIXELS_PER_QUARTER||80,
        isDesktop=globalThis.matchMedia?.("(hover:hover) and (pointer:fine)")?.matches,
        barWidth=isDesktop?6:4,
        range=visibleFootRange();
  ctx.save();
  ctx.fillStyle="#55bdc1";
  for(let i=range.start;i<range.end;i++){
    const n=notes[i];if(n.type!=="hhPedal")continue;
    const x=judgeX+(n.tick/division-beatNow)*speed;
    ctx.globalAlpha=.24+.18*n.velocity/127;
    ctx.fillRect(x-barWidth/2,mainH,barWidth,kickH);
  }
  ctx.restore();
}

const baseDraw=DruMusterChart.draw.bind(DruMusterChart);
draw=function(){
  /* Only the currently visible note window needs temporary pedal suppression.
     The old implementation scanned the complete song every animation frame. */
  const temporary=[],range=visibleFootRange();
  for(let i=range.start;i<range.end;i++){
    const n=notes[i];
    if(n.type==="hhPedal"&&!n.hit){temporary.push(n);n.hit=true}
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
  for(const n of temporary)n.hit=false;
  drawFootPedals();
};

if(typeof loop==="function"){
  const baseLoop=loop;
  loop=function(){
    if(running&&!paused)processFootAuto();
    return baseLoop();
  };
}
