"use strict";

const MIDI_PATH="songs/nanairo/chart.mid";
const PIXELS_PER_QUARTER=10;
const MIDI_MAP={35:"kick",36:"kick",38:"snare",40:"snare",41:"floorTom",43:"floorTom",45:"midTom",47:"midTom",48:"highTom",50:"highTom",42:"hhClosed",44:"hhPedal",46:"hhOpen",49:"crash",52:"crash",55:"crash",57:"crash",51:"ride",53:"ride",59:"ride"};
const GROUP={kick:"kick",snare:"drums",floorTom:"drums",midTom:"drums",highTom:"drums",hhClosed:"hh",hhPedal:"hh",hhOpen:"hh",ride:"hh",crash:"cymbal",special:"hh"};
const PART={kick:"kick",snare:"snare",floorTom:"floorTom",midTom:"midTom",highTom:"highTom",hhClosed:"hh",hhPedal:"hh",hhOpen:"hh",ride:"ride",crash:"crash",special:"special"};

const game=document.querySelector("#game"),chartWrap=document.querySelector("#chartWrap"),canvas=document.querySelector("#chart"),ctx=canvas.getContext("2d"),pauseBtn=document.querySelector("#pause"),pausePanel=document.querySelector("#pausePanel"),resumeBtn=document.querySelector("#resume"),quitBtn=document.querySelector("#quit"),subtitle=document.querySelector(".song-hud small");
let notes=[],division=480,tempoSegments=[{tick:0,sec:0,us:500000}],duration=0,previewStart=0,timeOffset=0,startPerf=0,pausedAt=0,paused=false,hitCursor=0,raf=0,ready=false;

function parseMidi(ab){
  const d=new DataView(ab);let p=0;
  const str=n=>{let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s};
  const u32=()=>{const v=d.getUint32(p);p+=4;return v};
  const u16=()=>{const v=d.getUint16(p);p+=2;return v};
  const vlq=()=>{let v=0,b;do{b=d.getUint8(p++);v=(v<<7)|(b&127)}while(b&128);return v};
  if(str(4)!=="MThd")throw Error("MIDI header error");
  const headerLength=u32();u16();const tracks=u16();division=u16();p+=headerLength-6;
  const raw=[],tempos=[{tick:0,us:500000}];

  for(let tr=0;tr<tracks;tr++){
    if(str(4)!=="MTrk")throw Error(`MIDI track ${tr+1} error`);
    const trackLength=u32(),end=p+trackLength;let tick=0,runningStatus=0;
    while(p<end){
      tick+=vlq();
      const first=d.getUint8(p++);let status;
      if(first<128){if(!runningStatus)throw Error("MIDI running-status error");status=runningStatus;p--}
      else{status=first;if(status<240)runningStatus=status}

      if(status===255){
        const type=d.getUint8(p++),len=vlq();
        if(type===81&&len===3)tempos.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});
        p+=len;
      }else if(status===240||status===247){
        runningStatus=0;const len=vlq();p+=len;
      }else if(status>=248){
        // MIDI realtime messages have no data bytes.
      }else if(status===241||status===243){
        p+=1;runningStatus=0;
      }else if(status===242){
        p+=2;runningStatus=0;
      }else if(status===246){
        runningStatus=0;
      }else{
        const hi=status&240,ch=status&15;
        if(hi===144||hi===128){
          const note=d.getUint8(p++),velocity=d.getUint8(p++);
          if(hi===144&&velocity>0&&ch===9)raw.push({tick,note,velocity,type:MIDI_MAP[note]||"special"});
        }else p+=(hi===192||hi===208)?1:2;
      }
    }
    p=end;
  }

  tempos.sort((a,b)=>a.tick-b.tick);
  const dedup=[];for(const e of tempos){if(dedup.length&&dedup[dedup.length-1].tick===e.tick)dedup[dedup.length-1]=e;else dedup.push(e)}
  tempoSegments=[{tick:0,sec:0,us:500000}];let lastTick=0,lastSec=0,us=500000;
  for(const e of dedup){lastSec+=(e.tick-lastTick)*us/division/1e6;lastTick=e.tick;us=e.us;if(e.tick===0)tempoSegments[0]={tick:0,sec:0,us};else tempoSegments.push({tick:e.tick,sec:lastSec,us})}
  const tickToSec=tick=>{let seg=tempoSegments[0];for(let i=1;i<tempoSegments.length&&tempoSegments[i].tick<=tick;i++)seg=tempoSegments[i];return seg.sec+(tick-seg.tick)*seg.us/division/1e6};
  notes=raw.map(n=>({...n,time:tickToSec(n.tick)})).sort((a,b)=>a.time-b.time);
  if(!notes.length)throw Error("drum notes not found");
  duration=notes[notes.length-1].time+1;
  previewStart=Math.max(0,(notes.find(n=>n.type!=="kick")?.time||notes[0].time)-3);
}

function secondsToBeat(sec){let seg=tempoSegments[0];for(let i=1;i<tempoSegments.length&&tempoSegments[i].sec<=sec;i++)seg=tempoSegments[i];return (seg.tick+(sec-seg.sec)*1e6/seg.us*division)/division}

// Preview intentionally uses one canvas pixel per logical CSS pixel. This avoids any
// transform/DPR ambiguity caused by the app's forced 90-degree mobile stage.
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
  const w=canvas.width,h=canvas.height;if(w<2||h<2)return;
  const t=current(),beatNow=secondsToBeat(t),judgeX=w*.11,kickH=Math.max(16,h*.12),mainH=h-kickH,laneH=mainH/3;
  ctx.clearRect(0,0,w,h);ctx.fillStyle="#081019";ctx.fillRect(0,0,w,h);
  const labels=["CYMBAL","HI-HAT / RIDE / OTHER","SNARE / TOMS"],laneColors=["#ffd45a","#52dfcf","#8898ff"];
  for(let i=0;i<3;i++){
    ctx.fillStyle=i%2===0?"#0d1520":"#0a121c";ctx.fillRect(0,laneH*i,w,laneH);
    if(i){ctx.strokeStyle="#2c3948";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(0,laneH*i+.5);ctx.lineTo(w,laneH*i+.5);ctx.stroke()}
    const y=laneH*(i+.5);ctx.strokeStyle=laneColors[i]+"bb";ctx.lineWidth=Math.max(2,laneH*.04);ctx.beginPath();ctx.arc(judgeX,y,Math.max(12,laneH*.2),0,Math.PI*2);ctx.stroke();
    ctx.fillStyle="#8b97a6";ctx.font=`700 ${Math.max(9,laneH*.13)}px system-ui,sans-serif`;ctx.textAlign="left";ctx.textBaseline="top";ctx.fillText(labels[i],7,laneH*i+6);
  }
  ctx.fillStyle="#090e15";ctx.fillRect(0,mainH,w,kickH);ctx.strokeStyle="#313a46";ctx.beginPath();ctx.moveTo(0,mainH+.5);ctx.lineTo(w,mainH+.5);ctx.stroke();ctx.fillStyle="#687483";ctx.font=`700 ${Math.max(8,kickH*.43)}px system-ui,sans-serif`;ctx.textAlign="left";ctx.textBaseline="middle";ctx.fillText("KICK",7,mainH+kickH/2);
  ctx.fillStyle="#eef6ff10";ctx.fillRect(judgeX-Math.max(5,w*.007),0,Math.max(10,w*.014),h);ctx.strokeStyle="#f3f8ff";ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(judgeX,0);ctx.lineTo(judgeX,h);ctx.stroke();

  for(const n of notes){
    const x=judgeX+(n.tick/division-beatNow)*PIXELS_PER_QUARTER;if(x<judgeX-48||x>w+48)continue;
    const group=GROUP[n.type],lane=group==="cymbal"?0:group==="hh"?1:group==="drums"?2:3,y=lane<3?laneH*(lane+.5):mainH+kickH/2,alpha=.48+.52*n.velocity/127;
    ctx.globalAlpha=alpha;ctx.strokeStyle=ctx.fillStyle=n.type==="snare"?"#38a9ff":n.type.includes("Tom")?"#ad82ff":group==="cymbal"?"#ffd45a":group==="hh"?"#52dfcf":"#a7b0bc";ctx.textAlign="center";ctx.textBaseline="middle";
    if(n.type==="snare"||n.type.includes("Tom")){const r=Math.max(12,laneH*.2);ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();ctx.globalAlpha=Math.min(1,alpha+.15);ctx.strokeStyle="#ffffffaa";ctx.lineWidth=1.5;ctx.stroke()}
    else if(n.type==="hhClosed"||n.type==="hhPedal"){ctx.font=`900 ${Math.max(28,laneH*.5)}px system-ui,sans-serif`;ctx.fillText("│",x,y)}
    else if(n.type==="hhOpen"){ctx.font=`900 ${Math.max(28,laneH*.5)}px system-ui,sans-serif`;ctx.fillText("||",x,y)}
    else if(n.type==="ride"){ctx.font=`900 ${Math.max(25,laneH*.43)}px system-ui,sans-serif`;ctx.fillText("△",x,y)}
    else if(n.type==="crash"){ctx.font=`900 ${Math.max(30,laneH*.52)}px system-ui,sans-serif`;ctx.fillText("×",x,y)}
    else if(n.type==="kick"){ctx.globalAlpha=.32+.28*n.velocity/127;ctx.fillStyle="#a7b0bc";ctx.fillRect(x-2,mainH+2,4,kickH-4)}
    else{ctx.font=`900 ${Math.max(25,laneH*.43)}px system-ui,sans-serif`;ctx.fillText("◇",x,y)}
  }
  ctx.globalAlpha=1;ctx.textAlign="start";ctx.textBaseline="alphabetic";
}

function flashPart(part){if(part==="kick"){const e=document.querySelector("#kickFx");if(e){e.classList.remove("hit");void e.offsetWidth;e.classList.add("hit")}return}const el=document.querySelector(`#hitLayer [data-part="${part}"]:not(.inactive)`);if(!el)return;el.classList.remove("struck");void el.offsetWidth;el.classList.add("struck")}
function updateHits(t){while(hitCursor<notes.length&&notes[hitCursor].time<=t){const n=notes[hitCursor++];if(n.time>=t-.08)flashPart(PART[n.type])}}
function setKit(){const used=new Set(notes.map(n=>PART[n.type]));document.querySelectorAll("#hitLayer [data-part]").forEach(el=>el.classList.toggle("inactive",!used.has(el.dataset.part)))}
function restart(){if(!ready)return;paused=false;pausePanel.classList.add("hidden");pauseBtn.textContent="Ⅱ";timeOffset=previewStart;startPerf=performance.now();hitCursor=notes.findIndex(n=>n.time>=previewStart);if(hitCursor<0)hitCursor=0;cancelAnimationFrame(raf);loop()}
function togglePause(forceResume=false){if(!ready)return;if(!paused&&!forceResume){pausedAt=current();paused=true;pausePanel.classList.remove("hidden");pauseBtn.textContent="▶";cancelAnimationFrame(raf)}else if(paused){timeOffset=pausedAt;startPerf=performance.now();paused=false;pausePanel.classList.add("hidden");pauseBtn.textContent="Ⅱ";loop()}}
function loop(){if(paused||!ready)return;const t=current();updateHits(t);draw();if(t>duration+1){restart();return}raf=requestAnimationFrame(loop)}

async function init(){
  try{
    subtitle.textContent="MIDI loading…";
    const r=await fetch(MIDI_PATH,{cache:"no-store"});if(!r.ok)throw Error(`MIDI HTTP ${r.status}`);
    parseMidi(await r.arrayBuffer());
    subtitle.textContent=`BUMP OF CHICKEN · ${notes.length.toLocaleString()} notes`;
    setKit();await waitForLayout();
    if(canvas.width<100||canvas.height<40)throw Error(`canvas size ${canvas.width}×${canvas.height}`);
    ready=true;restart();
  }catch(e){console.error(e);subtitle.textContent=`PREVIEW ERROR: ${e.message||e}`;syncCanvas();ctx.fillStyle="#f3f7fb";ctx.font="16px system-ui";ctx.fillText(String(e.message||e),20,30)}
}

pauseBtn.addEventListener("click",()=>togglePause());resumeBtn.addEventListener("click",()=>togglePause(true));quitBtn.addEventListener("click",restart);
document.querySelectorAll("#hitLayer [data-part]").forEach(b=>b.addEventListener("pointerdown",e=>{e.preventDefault();flashPart(b.dataset.part)}));
new ResizeObserver(()=>{if(syncCanvas()&&ready)draw()}).observe(chartWrap);
addEventListener("resize",()=>requestAnimationFrame(()=>{if(syncCanvas()&&ready)draw()}),{passive:true});
init();
