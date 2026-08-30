"use strict";
let beatTiming={division:480,segments:[{tick:0,sec:0,us:500000}]};
const timingReady=fetch(ASSET.midi,{cache:"force-cache"}).then(r=>r.ok?r.arrayBuffer():Promise.reject()).then(ab=>{beatTiming=DruMusterChart.parseTempoTiming(ab)}).catch(()=>{});
globalThis.DruMasterChartTimingReady=timingReady;
if(typeof GROUP!=="undefined")GROUP.hhPedal="kick";
if(typeof PART!=="undefined")PART.hhPedal="autoFoot";
const HIDDEN_CHART_TYPES=new Set(["hhPedal"]);
let footCursor=0,lastRunStart=NaN;

/* Web Audio's currentTime advances ahead of the sample that has physically
   reached the output device. Drawing directly from current() therefore makes
   the goal crossing appear early by the device/browser output latency. Use
   getOutputTimestamp() when available, and latency properties as a fallback,
   so the chart follows the MIDI/audio time that is actually being heard. */
function audibleContextTime(){
  if(typeof ac==="undefined"||!ac||!Number.isFinite(Number(ac.currentTime)))return NaN;
  const now=Number(ac.currentTime);
  try{
    const ts=typeof ac.getOutputTimestamp==="function"?ac.getOutputTimestamp():null,
          contextTime=Number(ts?.contextTime),performanceTime=Number(ts?.performanceTime);
    if(Number.isFinite(contextTime)&&contextTime>=0&&Number.isFinite(performanceTime)&&performanceTime>0&&typeof performance!=="undefined"){
      const presented=contextTime+Math.max(0,(performance.now()-performanceTime)/1000);
      if(Number.isFinite(presented)&&presented<=now+.02)return Math.max(0,presented);
    }
  }catch{}
  const outputLatency=Number(ac.outputLatency),baseLatency=Number(ac.baseLatency),
        latency=Number.isFinite(outputLatency)&&outputLatency>0?outputLatency:Number.isFinite(baseLatency)&&baseLatency>0?baseLatency:0;
  return Math.max(0,now-latency);
}
function chartCurrent(){
  const midiNow=current();
  if(typeof ac==="undefined"||!ac)return midiNow;
  const audible=audibleContextTime(),now=Number(ac.currentTime);
  if(!Number.isFinite(audible)||!Number.isFinite(now))return midiNow;
  const lag=Math.max(0,Math.min(.25,now-audible)),speed=Math.max(.01,Number(rate)||1);
  return midiNow-lag*speed;
}
globalThis.DruMasterChartClock={current:chartCurrent,audibleContextTime};

function lowerBoundFootTime(sec){let lo=0,hi=notes.length;while(lo<hi){const mid=(lo+hi)>>1;if(notes[mid].time<sec)lo=mid+1;else hi=mid}return lo}
function resetFootAutoForRun(){const start=Number(startedAt);if(start===lastRunStart)return;lastRunStart=start;footCursor=lowerBoundFootTime(Math.max(0,current()-.05));if(typeof maxScore!=="undefined"&&typeof weight==="function")maxScore=Math.max(1,notes.filter(n=>n.type!=="kick"&&n.type!=="hhPedal").reduce((s,n)=>s+weight(n.type)*n.velocity/127,0)*1000)}
function asKickGoalNote(n){return n?.type==="hhPedal"?{...n,type:"kick"}:n}
function flashFootGoal(n){try{globalThis.DruMasterJudgement?.flashNote?.(asKickGoalNote(n))}catch{}}
function installFootGoalAdapter(){const j=globalThis.DruMasterJudgement;if(!j?.flashNote){requestAnimationFrame(installFootGoalAdapter);return}if(j.__dmFootGoalAdapter)return;const baseFlash=j.flashNote.bind(j),baseEmit=typeof j.emitForNote==="function"?j.emitForNote.bind(j):null;j.flashNote=note=>baseFlash(asKickGoalNote(note));if(baseEmit)j.emitForNote=(note,label,options={})=>baseEmit(asKickGoalNote(note),label,options);j.__dmFootGoalAdapter=true}
requestAnimationFrame(installFootGoalAdapter);
function processFootAuto(){if(document.body.dataset.scorePlayback==="1")return;resetFootAutoForRun();const t=current();while(footCursor<notes.length&&notes[footCursor].time<=t){const n=notes[footCursor++];if(n.type!=="hhPedal"||n.hit)continue;n.hit=true;if(n.time<t-.08)continue;playDrum(n.note,n.type,n.velocity/127);flashFootGoal(n)}}
const KICK_AUDIO_LOOKAHEAD_SEC=.18,KICK_AUDIO_TIMER_MS=25;
function scheduleKickAudio(){if(document.body.dataset.scorePlayback==="1")return;if(typeof autoplay!=="undefined"&&autoplay)return;if(typeof running==="undefined"||!running||typeof paused!=="undefined"&&paused)return;if(typeof nextKick==="undefined"||typeof startedAt==="undefined"||typeof rate==="undefined"||!Array.isArray(notes))return;const audio=globalThis.DruMasterAudioControl;if(!audio?.scheduleKick||typeof ac==="undefined"||!ac)return;const speed=Math.max(.01,Number(rate)||1),t=current(),limit=t+KICK_AUDIO_LOOKAHEAD_SEC*speed,midiOffset=Number(globalThis.DruMasterSongs?.current?.playback?.midiOffsetSec)||0;while(nextKick<notes.length&&notes[nextKick].time<=limit){const n=notes[nextKick++];if(n.type!=="kick")continue;const when=Number(startedAt)+(n.time+midiOffset)/speed;if(when<ac.currentTime-.08)continue;audio.scheduleKick(n.velocity/127,when)}}
setInterval(scheduleKickAudio,KICK_AUDIO_TIMER_MS);
function visibleFootRange(){if(!Array.isArray(notes)||!notes.length)return {start:0,end:0};const w=canvas.clientWidth,beatNow=DruMusterChart.secondsToBeat(chartCurrent(),beatTiming),division=beatTiming.division||480,judgeX=DruMusterChart.judgementX(w),speed=DruMusterChart.pixelsPerQuarter?.()||DruMusterChart.PIXELS_PER_QUARTER||80,minBeat=beatNow-48/speed,maxBeat=beatNow+(w+48-judgeX)/speed,search=globalThis.DruMasterNoteSearch;return search?.visibleTickRange?search.visibleTickRange(notes,minBeat*division,maxBeat*division):{start:0,end:notes.length}}

const HH_GRAPH_TYPES=new Set(["hhClosed","hhOpen","hhPedal"]),HH_GRAPH_VELOCITY_CURVE=Math.log(.4)/Math.log(100/127),HH_GRAPH_RAMP_BEATS=.25;
let hhGraphNotes=null,hhGraphTiming=null,hhGraphEvents=[];
const hhGraphClamp01=value=>Math.max(0,Math.min(1,value)),hhGraphEaseOutQuart=value=>1-Math.pow(1-hhGraphClamp01(value),4),hhGraphEaseInOutQuart=value=>{const t=hhGraphClamp01(value);return t<.5?8*t*t*t*t:1-Math.pow(-2*t+2,4)/2},hhGraphVelocityToLevel=velocity=>{const normalized=Math.max(0,Math.min(127,Number(velocity)||0))/127;return normalized<=0?0:Math.pow(normalized,HH_GRAPH_VELOCITY_CURVE)};
function hhGraphUpperBound(beat){let lo=0,hi=hhGraphEvents.length;while(lo<hi){const mid=(lo+hi)>>>1;if(hhGraphEvents[mid].rampEnd<=beat)lo=mid+1;else hi=mid}return lo}
function rebuildHiHatGraphEnvelope(){if(hhGraphNotes===notes&&hhGraphTiming===beatTiming)return;hhGraphNotes=notes;hhGraphTiming=beatTiming;const division=Number(beatTiming?.division)||480,actual=[];for(const note of notes){if(!HH_GRAPH_TYPES.has(note.type))continue;actual.push({beat:Number(note.tick)/division,target:note.type==="hhOpen"?Math.max(0,Math.min(127,Number(note.velocity)||0)):0,synthetic:false})}actual.sort((a,b)=>a.beat-b.beat);const timeline=[];for(let i=0;i<actual.length;i++){const event=actual[i],next=actual[i+1];timeline.push(event);if(event.target>0&&(!next||next.beat-event.beat>2))timeline.push({beat:event.beat+2,target:0,synthetic:true})}timeline.sort((a,b)=>a.beat-b.beat||(a.synthetic?1:-1));hhGraphEvents=[];let previousBeat=-Infinity,previousTarget=0;for(let i=0;i<timeline.length;i++){const event=timeline[i],following=timeline[i+1];if(hhGraphEvents.length&&Math.abs(hhGraphEvents[hhGraphEvents.length-1].beat-event.beat)<1e-7){const prior=hhGraphEvents.pop();previousTarget=prior.from;previousBeat=hhGraphEvents.length?hhGraphEvents[hhGraphEvents.length-1].beat:-Infinity}const closing=event.target<previousTarget,rampStart=closing?event.beat:(Number.isFinite(previousBeat)?Math.max(event.beat-HH_GRAPH_RAMP_BEATS,previousBeat):event.beat-HH_GRAPH_RAMP_BEATS),rampEnd=closing?Math.min(event.beat+HH_GRAPH_RAMP_BEATS,following?.beat??Infinity):event.beat;hhGraphEvents.push({...event,from:previousTarget,rampStart,rampEnd,closing});previousBeat=event.beat;previousTarget=event.target}}
function hiHatGraphVelocityAtBeat(beat){const nextIndex=hhGraphUpperBound(beat),previous=hhGraphEvents[nextIndex-1],next=hhGraphEvents[nextIndex];let value=previous?.target||0;if(next&&beat>=next.rampStart&&beat<next.rampEnd){const span=next.rampEnd-next.rampStart;if(span<=1e-7)return next.target;const progress=(beat-next.rampStart)/span,eased=next.closing?hhGraphEaseInOutQuart(progress):hhGraphEaseOutQuart(progress);value=next.from+(next.target-next.from)*eased}return value}
function drawHiHatOpennessGraph(){if(!Array.isArray(notes)||!notes.length)return;rebuildHiHatGraphEnvelope();if(!hhGraphEvents.length)return;const w=canvas.clientWidth,h=canvas.clientHeight,beatNow=DruMusterChart.secondsToBeat(chartCurrent(),beatTiming),judgeX=DruMusterChart.judgementX(w),kickH=Math.max(16,h*.12),mainH=h-kickH,speed=DruMusterChart.pixelsPerQuarter?.()||DruMusterChart.PIXELS_PER_QUARTER||80,bottom=h,span=kickH,samplePx=3,runs=[],fullOpacity=document.body.dataset.scorePlayback==="1"||(typeof autoplay!=="undefined"&&autoplay),graphAlpha=fullOpacity?.42:.20;let run=[];for(let x=0;x<=w+samplePx;x+=samplePx){const beat=beatNow+(x-judgeX)/speed,velocity=hiHatGraphVelocityAtBeat(beat);if(velocity<1){if(run.length){runs.push(run);run=[]}continue}const level=hhGraphVelocityToLevel(velocity);run.push({x,y:bottom-level*span})}if(run.length)runs.push(run);if(!runs.length)return;ctx.save();ctx.beginPath();ctx.rect(0,mainH,w,kickH);ctx.clip();for(const points of runs){const first=points[0],last=points[points.length-1],cyan=`rgba(82,223,207,${graphAlpha})`;ctx.beginPath();ctx.moveTo(first.x,bottom);ctx.lineTo(first.x,first.y);for(let i=1;i<points.length;i++)ctx.lineTo(points[i].x,points[i].y);ctx.lineTo(last.x,bottom);ctx.closePath();ctx.fillStyle=cyan;ctx.fill();ctx.beginPath();ctx.moveTo(first.x,first.y);for(let i=1;i<points.length;i++)ctx.lineTo(points[i].x,points[i].y);ctx.strokeStyle=cyan;ctx.lineWidth=1.2;ctx.lineJoin="round";ctx.lineCap="round";ctx.stroke()}ctx.restore()}
function redrawKickAutoNotes(){if(!Array.isArray(notes)||!notes.length)return;const w=canvas.clientWidth,h=canvas.clientHeight,beatNow=DruMusterChart.secondsToBeat(chartCurrent(),beatTiming),division=beatTiming.division||480,judgeX=DruMusterChart.judgementX(w),speed=DruMusterChart.pixelsPerQuarter?.()||DruMusterChart.PIXELS_PER_QUARTER||80,kickH=Math.max(16,h*.12),mainH=h-kickH,minBeat=beatNow-48/speed,maxBeat=beatNow+(w+48-judgeX)/speed,search=globalThis.DruMusterNoteSearch,range=search?.visibleTickRange?search.visibleTickRange(notes,minBeat*division,maxBeat*division):{start:0,end:notes.length},isDesktop=!!globalThis.matchMedia?.("(hover:hover) and (pointer:fine)")?.matches,noteWidthScale=isDesktop?1.5:1,offsets=DruMusterChart.simultaneousNoteOffsets?.(notes,range.start,range.end,true,GROUP,noteWidthScale,HIDDEN_CHART_TYPES)||new WeakMap(),barTop=isDesktop?mainH+2:mainH,barH=isDesktop?Math.max(1,kickH-4):kickH;ctx.save();for(let i=range.start;i<range.end;i++){const n=notes[i];if(n.hit||HIDDEN_CHART_TYPES.has(n.type)||GROUP[n.type]!=="kick")continue;const x=judgeX+(n.tick/division-beatNow)*speed+(offsets.get(n)||0),visual=DruMusterChart.noteVisual(n.type,GROUP[n.type],noteWidthScale),alpha=n.type==="kick"?.32+.28*n.velocity/127:.48+.52*n.velocity/127;ctx.globalAlpha=alpha;ctx.fillStyle=visual.color;ctx.fillRect(x-visual.totalWidth/2,barTop,visual.barWidth,barH)}ctx.restore()}

const baseDraw=DruMusterChart.draw.bind(DruMusterChart);
draw=function(){baseDraw({ctx,canvas,notes,currentSec:chartCurrent(),timing:beatTiming,groupMap:GROUP,skipHit:true,hiddenTypes:HIDDEN_CHART_TYPES});drawHiHatOpennessGraph();redrawKickAutoNotes()};
if(typeof loop==="function"){const baseLoop=loop;loop=function(){if(running&&!paused){scheduleKickAudio();processFootAuto()}return baseLoop()}}
