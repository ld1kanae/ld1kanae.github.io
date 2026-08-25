"use strict";

(()=>{
  const wrap=document.querySelector("#chartWrap"),canvas=document.querySelector("#chart");
  if(!wrap||!canvas)return;

  const fxByLane=[];
  const glowByLane=[];
  const GLOW_WIDTH=14;

  function chartGeometry(){
    const w=canvas.clientWidth,h=canvas.clientHeight,
          judgeX=w*.11,
          kickH=Math.max(16,h*.12),
          mainH=h-kickH,
          laneH=mainH/3;
    return {w,h,judgeX,laneH};
  }

  function activeTiming(){
    if(typeof beatTiming!=="undefined"&&beatTiming?.division)return beatTiming;
    if(typeof timing!=="undefined"&&timing?.division)return timing;
    return null;
  }

  function noteXAt(note,t){
    const tm=activeTiming();
    if(!tm||!note||typeof note.tick!=="number")return NaN;
    const {judgeX}=chartGeometry(),
          beatNow=DruMusterChart.secondsToBeat(t,tm),
          division=tm.division||480;
    return judgeX+(note.tick/division-beatNow)*DruMusterChart.PIXELS_PER_QUARTER;
  }

  function laneForPart(part){
    if(part==="crash")return 0;
    if(part==="hh"||part==="ride"||part==="special")return 1;
    if(part==="snare"||part==="highTom"||part==="midTom"||part==="floorTom")return 2;
    return -1;
  }
  function laneForType(type){
    const group=typeof GROUP!=="undefined"?GROUP[type]:null;
    return group==="cymbal"?0:group==="hh"?1:group==="drums"?2:-1;
  }

  function nearestNoteForPart(part,t,maxDelta=.16){
    if(typeof notes==="undefined"||typeof PART==="undefined")return null;
    let best=null,bestDelta=maxDelta+.000001;
    for(const n of notes){
      if(n.type==="kick"||PART[n.type]!==part)continue;
      const d=Math.abs(n.time-t);
      if(d<bestDelta){best=n;bestDelta=d}
      if(n.time>t+maxDelta)break;
    }
    return best;
  }

  function placeFx(lane,node){
    const {laneH}=chartGeometry();
    node.style.top=`${laneH*(lane+.5)}px`;
  }

  function placeGlow(lane,node,x){
    const {laneH}=chartGeometry();
    // Exact top/height and explicit half-width subtraction avoid transform rounding drift.
    node.style.left=`${x-GLOW_WIDTH/2}px`;
    node.style.top=`${lane*laneH}px`;
    node.style.width=`${GLOW_WIDTH}px`;
    node.style.height=`${laneH}px`;
  }

  function syncGeometry(){
    for(let lane=0;lane<3;lane++){
      if(fxByLane[lane])placeFx(lane,fxByLane[lane].fx);
    }
  }

  function ensureFx(lane){
    if(fxByLane[lane])return fxByLane[lane];
    const fx=document.createElement("div");
    fx.className="lane-judge-fx";
    const text=document.createElement("span");
    text.className="lane-judge-text";
    fx.appendChild(text);
    wrap.appendChild(fx);
    fxByLane[lane]={fx,text};
    placeFx(lane,fx);
    return fxByLane[lane];
  }

  function ensureGlow(lane){
    if(glowByLane[lane])return glowByLane[lane];
    const glow=document.createElement("div");
    glow.className="lane-hit-glow";
    glow.dataset.lane=String(lane);
    wrap.appendChild(glow);
    glowByLane[lane]=glow;
    return glow;
  }

  function flashLane(lane,x){
    if(lane<0||lane>2||!Number.isFinite(x))return;
    const glow=ensureGlow(lane);
    placeGlow(lane,glow,x);
    glow.classList.remove("flash");
    void glow.offsetWidth;
    glow.classList.add("flash");
  }

  function emit(label,lane){
    const grade=String(label||"").toLowerCase();
    if(lane<0||lane>2||grade==="miss"||grade==="auto")return;
    const {fx,text}=ensureFx(lane);
    placeFx(lane,fx);
    text.textContent=String(label).toUpperCase();
    fx.dataset.grade=grade;
    fx.classList.remove("play");
    void fx.offsetWidth;
    fx.classList.add("play");
  }

  // Drum-surface flash remains independent. The chart glow is emitted only when
  // a nearby chart note exists, and it is centered on that note's current X.
  if(typeof flashPart==="function"){
    const originalFlashPart=flashPart;
    flashPart=function(part,el){
      if(part!=="kick"&&typeof current==="function"){
        const t=current(),note=nearestNoteForPart(part,t,.16);
        if(note){
          const lane=laneForType(note.type),x=noteXAt(note,t);
          flashLane(lane,x);
        }
      }
      return originalFlashPart(part,el);
    };
  }

  // Production: place PERFECT/GREAT/GOOD on the lane that triggered input.
  if(typeof input==="function"&&typeof showJudge==="function"){
    let activeLane=-1;
    const originalInput=input;
    input=function(part,visualEl){
      activeLane=laneForPart(part);
      return originalInput(part,visualEl);
    };
    showJudge=function(label){emit(label,activeLane)};
  }

  // Preview AUTO can hit several lanes at once, so each receives its own feedback.
  if(typeof showPreviewJudge==="function"&&typeof updateHits==="function"){
    showPreviewJudge=function(label="PERFECT",lane=1){emit(label,lane)};
    updateHits=function(t){
      const hitLanes=new Set();
      while(hitCursor<notes.length&&notes[hitCursor].time<=t){
        const n=notes[hitCursor++];
        if(n.time>=t-.08){
          flashPart(PART[n.type]);
          if(n.type!=="kick"){
            const lane=laneForType(n.type);
            if(lane>=0)hitLanes.add(lane);
          }
        }
      }
      for(const lane of hitLanes)emit("PERFECT",lane);
    };
  }

  new ResizeObserver(()=>requestAnimationFrame(syncGeometry)).observe(wrap);
  addEventListener("resize",()=>requestAnimationFrame(syncGeometry),{passive:true});
})();
