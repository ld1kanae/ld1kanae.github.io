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

/* Bass drum audio used to be started by the render loop with only 12 ms of
   headroom. A single slow mobile frame could therefore make a kick late or
   skip it entirely. Keep gameplay/visual timing unchanged, but reserve the
   actual kick AudioBufferSource on the Web Audio clock well ahead of time.
   AUTO mode intentionally stays on app.js's direct playDrum path: advancing
   nextKick here would consume the kick before the AUTO render loop can play it. */
const KICK_AUDIO_LOOKAHEAD_SEC=.18;
const KICK_AUDIO_TIMER_MS=25;
function scheduleKickAudio(){
  if(document.body.dataset.scorePlayback==="1")return;
  if(typeof autoplay!=="undefined"&&autoplay)return;
  if(typeof running==="undefined"||!running||typeof paused!=="undefined"&&paused)return;
  if(typeof nextKick==="undefined"||typeof startedAt==="undefined"||typeof rate==="undefined"||!Array.isArray(notes))return;
  const audio=globalThis.DruMasterAudioControl;
  if(!audio?.scheduleKick||typeof ac==="undefined"||!ac)return;
  const speed=Math.max(.01,Number(rate)||1),t=current(),limit=t+KICK_AUDIO_LOOKAHEAD_SEC*speed;
  while(nextKick<notes.length&&notes[nextKick].time<=limit){
    const n=notes[nextKick++];
    if(n.type!=="kick")continue;
    const when=Number(startedAt)+n.time/speed;
    if(when<ac.currentTime-.08)continue;
    audio.scheduleKick(n.velocity/127,when);
  }
}
setInterval(scheduleKickAudio,KICK_AUDIO_TIMER_MS);

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

/* The opening gauge has a musical base envelope plus small hit pulses. The
   chart graph intentionally shows only that base envelope. Keep this curve in
   sync with hihat-open-gauge.js: open notes set the target velocity, closed or
   pedal notes set zero, each transition begins up to half a beat early, and an
   isolated open note closes automatically two beats later. */
const HH_GRAPH_TYPES=new Set(["hhClosed","hhOpen","hhPedal"]);
const HH_GRAPH_VELOCITY_CURVE=Math.log(.4)/Math.log(100/127);
let hhGraphNotes=null,hhGraphTiming=null,hhGraphEvents=[];
const hhGraphClamp01=value=>Math.max(0,Math.min(1,value));
const hhGraphEaseOutQuart=value=>1-Math.pow(1-hhGraphClamp01(value),4);
const hhGraphVelocityToLevel=velocity=>{
  const normalized=Math.max(0,Math.min(127,Number(velocity)||0))/127;
  return normalized<=0?0:Math.pow(normalized,HH_GRAPH_VELOCITY_CURVE);
};
function hhGraphUpperBound(beat){
  let lo=0,hi=hhGraphEvents.length;
  while(lo<hi){const mid=(lo+hi)>>>1;if(hhGraphEvents[mid].beat<=beat)lo=mid+1;else hi=mid}
  return lo;
}
function rebuildHiHatGraphEnvelope(){
  if(hhGraphNotes===notes&&hhGraphTiming===beatTiming)return;
  hhGraphNotes=notes;
  hhGraphTiming=beatTiming;
  const division=Number(beatTiming?.division)||480,actual=[];
  for(const note of notes){
    if(!HH_GRAPH_TYPES.has(note.type))continue;
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
  hhGraphEvents=[];
  let previousBeat=-Infinity,previousTarget=0;
  for(const event of timeline){
    if(hhGraphEvents.length&&Math.abs(hhGraphEvents[hhGraphEvents.length-1].beat-event.beat)<1e-7){
      const prior=hhGraphEvents.pop();
      previousTarget=prior.from;
      previousBeat=hhGraphEvents.length?hhGraphEvents[hhGraphEvents.length-1].beat:-Infinity;
    }
    const rampStart=Number.isFinite(previousBeat)?Math.max(event.beat-.5,previousBeat):event.beat-.5;
    hhGraphEvents.push({...event,from:previousTarget,rampStart});
    previousBeat=event.beat;
    previousTarget=event.target;
  }
}
function hiHatGraphVelocityAtBeat(beat){
  const nextIndex=hhGraphUpperBound(beat),previous=hhGraphEvents[nextIndex-1],next=hhGraphEvents[nextIndex];
  let value=previous?.target||0;
  if(next&&beat>=next.rampStart&&beat<next.beat){
    const span=next.beat-next.rampStart;
    if(span<=1e-7)return next.target;
    const progress=(beat-next.rampStart)/span;
    value=next.from+(next.target-next.from)*hhGraphEaseOutQuart(progress);
  }
  return value;
}
function drawHiHatOpennessGraph(){
  if(!Array.isArray(notes)||!notes.length)return;
  rebuildHiHatGraphEnvelope();
  if(!hhGraphEvents.length)return;
  const w=canvas.clientWidth,h=canvas.clientHeight,
        beatNow=DruMusterChart.secondsToBeat(current(),beatTiming),
        judgeX=DruMusterChart.judgementX(w),
        kickH=Math.max(16,h*.12),mainH=h-kickH,
        speed=DruMusterChart.pixelsPerQuarter?.()||DruMusterChart.PIXELS_PER_QUARTER||80,
        top=mainH+4,bottom=h-4,span=Math.max(1,bottom-top),samplePx=3;
  ctx.save();
  ctx.beginPath();
  ctx.rect(0,mainH,w,kickH);
  ctx.clip();
  ctx.beginPath();
  let first=true;
  for(let x=0;x<=w+samplePx;x+=samplePx){
    const beat=beatNow+(x-judgeX)/speed,
          velocity=hiHatGraphVelocityAtBeat(beat),
          level=hhGraphVelocityToLevel(velocity),
          y=bottom-level*span;
    if(first){ctx.moveTo(x,y);first=false}else ctx.lineTo(x,y);
  }
  /* A very soft dark under-stroke keeps the cyan readable over measure lines
     without turning the openness curve into a dominant gameplay element. */
  ctx.strokeStyle="rgba(3,5,7,.55)";
  ctx.lineWidth=3;
  ctx.lineJoin="round";
  ctx.lineCap="round";
  ctx.stroke();
  ctx.strokeStyle="rgba(82,223,207,.48)";
  ctx.lineWidth=1.25;
  ctx.stroke();
  ctx.restore();
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
  drawHiHatOpennessGraph();
  drawFootPedals();
};

if(typeof loop==="function"){
  const baseLoop=loop;
  loop=function(){
    if(running&&!paused){
      scheduleKickAudio();
      processFootAuto();
    }
    return baseLoop();
  };
}
