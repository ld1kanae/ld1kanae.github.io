"use strict";

// UI preview: same chart MIDI, same CSS, same shared chart renderer as production.
const MIDI_PATH="songs/nanairo/chart.mid";
const MIDI_MAP={35:"kick",36:"kick",38:"snare",40:"snare",41:"floorTom",43:"floorTom",45:"midTom",47:"midTom",48:"highTom",50:"highTom",42:"hhClosed",44:"hhPedal",46:"hhOpen",49:"crash",52:"crash",55:"crash",57:"crash",51:"ride",53:"ride",59:"ride"};
const GROUP={kick:"kick",snare:"drums",floorTom:"drums",midTom:"drums",highTom:"drums",hhClosed:"hh",hhPedal:"hh",hhOpen:"hh",ride:"hh",crash:"cymbal",special:"hh"};
const PART={kick:"kick",snare:"snare",floorTom:"floorTom",midTom:"midTom",highTom:"highTom",hhClosed:"hh",hhPedal:"hh",hhOpen:"hh",ride:"ride",crash:"crash",special:"special"};

const chartWrap=document.querySelector("#chartWrap"),canvas=document.querySelector("#chart"),ctx=canvas.getContext("2d"),pauseBtn=document.querySelector("#pause"),pausePanel=document.querySelector("#pausePanel"),resumeBtn=document.querySelector("#resume"),quitBtn=document.querySelector("#quit"),subtitle=document.querySelector(".song-hud small"),judgementFx=document.querySelector("#judgementFx"),judge=document.querySelector("#judge");
let notes=[],timing={division:480,segments:[{tick:0,sec:0,us:500000}]},duration=0,previewStart=0,timeOffset=0,startPerf=0,pausedAt=0,paused=false,hitCursor=0,raf=0,ready=false;

function parseDrumNotes(ab){
  const d=new DataView(ab);let p=0;
  const str=n=>{let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s};
  const u32=()=>{const v=d.getUint32(p);p+=4;return v};
  const u16=()=>{const v=d.getUint16(p);p+=2;return v};
  const vlq=()=>{let v=0,b;do{b=d.getUint8(p++);v=(v<<7)|(b&127)}while(b&128);return v};
  if(str(4)!=="MThd")throw Error("MIDI header error");
  const headerLength=u32();u16();const tracks=u16();const division=u16();p+=headerLength-6;
  const raw=[];
  for(let tr=0;tr<tracks;tr++){
    if(str(4)!=="MTrk")throw Error(`MIDI track ${tr+1} error`);
    const trackLength=u32(),end=p+trackLength;let tick=0,runningStatus=0;
    while(p<end){
      tick+=vlq();const first=d.getUint8(p++);let status;
      if(first<128){if(!runningStatus)throw Error("MIDI running-status error");status=runningStatus;p--}
      else{status=first;if(status<240)runningStatus=status}
      if(status===255){const type=d.getUint8(p++),len=vlq();p+=len}
      else if(status===240||status===247){runningStatus=0;const len=vlq();p+=len}
      else{
        const hi=status&240,ch=status&15;
        if(hi===144||hi===128){
          const note=d.getUint8(p++),velocity=d.getUint8(p++);
          if(hi===144&&velocity>0&&ch===9)raw.push({tick,note,velocity,type:MIDI_MAP[note]||"special"});
        }else p+=(hi===192||hi===208)?1:2;
      }
    }
    p=end;
  }
  return {division,raw};
}

function tickToSec(tick){
  let seg=timing.segments[0];
  for(let i=1;i<timing.segments.length&&timing.segments[i].tick<=tick;i++)seg=timing.segments[i];
  return seg.sec+(tick-seg.tick)*seg.us/timing.division/1e6;
}

function syncCanvas(){
  const w=Math.round(chartWrap.offsetWidth),h=Math.round(chartWrap.offsetHeight);
  if(w<100||h<40)return false;
  if(canvas.width!==w)canvas.width=w;
  if(canvas.height!==h)canvas.height=h;
  canvas.style.width=w+"px";canvas.style.height=h+"px";
  ctx.setTransform(1,0,0,1,0,0);
  return true;
}
function waitForLayout(){return new Promise(resolve=>{let tries=0;const tick=()=>{if(syncCanvas()||tries++>90)resolve();else requestAnimationFrame(tick)};requestAnimationFrame(()=>requestAnimationFrame(tick))})}
function current(){return paused?pausedAt:timeOffset+(performance.now()-startPerf)/1000}
function draw(){
  DruMusterChart.draw({ctx,canvas,notes,currentSec:current(),timing,groupMap:GROUP,skipHit:false});
}
function showPreviewJudge(label="PERFECT"){
  if(!judgementFx||!judge)return;
  judge.textContent=label;
  judgementFx.dataset.grade=label.toLowerCase();
  judgementFx.classList.remove("play");
  void judgementFx.offsetWidth;
  judgementFx.classList.add("play");
}
function flashPart(part){
  if(part==="kick")return;
  const el=document.querySelector(`#hitLayer [data-part="${part}"]:not(.inactive)`);if(!el)return;el.classList.remove("struck");void el.offsetWidth;el.classList.add("struck");
}
function updateHits(t){
  let showPerfect=false;
  while(hitCursor<notes.length&&notes[hitCursor].time<=t){
    const n=notes[hitCursor++];
    if(n.time>=t-.08){
      flashPart(PART[n.type]);
      if(n.type!=="kick")showPerfect=true;
    }
  }
  if(showPerfect)showPreviewJudge("PERFECT");
}
function setKit(){const used=new Set(notes.map(n=>PART[n.type]));document.querySelectorAll("#hitLayer [data-part]").forEach(el=>el.classList.toggle("inactive",!used.has(el.dataset.part)))}
function restart(){if(!ready)return;paused=false;pausePanel.classList.add("hidden");pauseBtn.textContent="Ⅱ";timeOffset=previewStart;startPerf=performance.now();hitCursor=notes.findIndex(n=>n.time>=previewStart);if(hitCursor<0)hitCursor=0;cancelAnimationFrame(raf);loop()}
function togglePause(forceResume=false){if(!ready)return;if(!paused&&!forceResume){pausedAt=current();paused=true;pausePanel.classList.remove("hidden");pauseBtn.textContent="▶";cancelAnimationFrame(raf)}else if(paused){timeOffset=pausedAt;startPerf=performance.now();paused=false;pausePanel.classList.add("hidden");pauseBtn.textContent="Ⅱ";loop()}}
function loop(){if(paused||!ready)return;const t=current();updateHits(t);draw();if(t>duration+1){restart();return}raf=requestAnimationFrame(loop)}

async function init(){
  try{
    subtitle.textContent="MIDI loading…";
    const r=await fetch(MIDI_PATH,{cache:"no-store"});if(!r.ok)throw Error(`MIDI HTTP ${r.status}`);
    const ab=await r.arrayBuffer();
    timing=DruMusterChart.parseTempoTiming(ab);
    const parsed=parseDrumNotes(ab);
    if(parsed.division!==timing.division)throw Error("MIDI division mismatch");
    notes=parsed.raw.map(n=>({...n,time:tickToSec(n.tick)})).sort((a,b)=>a.time-b.time);
    if(!notes.length)throw Error("drum notes not found");
    duration=notes[notes.length-1].time+1;
    previewStart=Math.max(0,(notes.find(n=>n.type!=="kick")?.time||notes[0].time)-3);
    subtitle.textContent=`BUMP OF CHICKEN · ${notes.length.toLocaleString()} notes · ${DruMusterChart.PIXELS_PER_QUARTER}px/♩`;
    setKit();await waitForLayout();
    if(canvas.width<100||canvas.height<40)throw Error(`canvas size ${canvas.width}×${canvas.height}`);
    ready=true;restart();
  }catch(e){console.error(e);subtitle.textContent=`PREVIEW ERROR: ${e.message||e}`}
}

pauseBtn.addEventListener("click",()=>togglePause());resumeBtn.addEventListener("click",()=>togglePause(true));quitBtn.addEventListener("click",restart);
document.querySelectorAll("#hitLayer [data-part]").forEach(b=>b.addEventListener("pointerdown",e=>{e.preventDefault();flashPart(b.dataset.part)}));
new ResizeObserver(()=>{if(syncCanvas()&&ready)draw()}).observe(chartWrap);
addEventListener("resize",()=>requestAnimationFrame(()=>{if(syncCanvas()&&ready)draw()}),{passive:true});
init();
