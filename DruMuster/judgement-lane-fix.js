"use strict";

(()=>{
  const wrap=document.querySelector("#chartWrap"),canvas=document.querySelector("#chart");
  if(!wrap||!canvas)return;

  const fxByLane=[];
  const glowByLane=[];
  let suppressAutoGlow=false;

  function chartGeometry(){
    const w=canvas.clientWidth,h=canvas.clientHeight,
          judgeX=w*.11,
          glowW=DruMusterChart.judgementZoneWidth?DruMusterChart.judgementZoneWidth(w):Math.max(10,w*.014),
          kickH=Math.max(16,h*.12),
          mainH=h-kickH,
          laneH=mainH/3;
    return {w,h,judgeX,glowW,laneH};
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
      if(n.hit||n.type==="kick"||PART[n.type]!==part)continue;
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
    const {laneH,glowW}=chartGeometry();
    // Identical width to the chart's judgement zone. Explicit pixel edges avoid
    // the asymmetric drift visible in the previous screenshot.
    node.style.left=`${x-glowW/2}px`;
    node.style.top=`${lane*laneH}px`;
    node.style.width=`${glowW}px`;
    node.style.height=`${laneH}px`;
  }

  function syncGeometry(){
    for(let lane=0;lane<3;lane++)if(fxByLane[lane])placeFx(lane,fxByLane[lane].fx);
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

  function flashNote(note,t){
    if(!note||note.type==="kick")return;
    const lane=laneForType(note.type),x=noteXAt(note,t);
    if(lane<0||!Number.isFinite(x))return;
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

  // Surface flash still works for autoplay and pointer taps. When no exact note
  // is supplied, use the nearest still-unhit chart note at the current time.
  if(typeof flashPart==="function"){
    const originalFlashPart=flashPart;
    flashPart=function(part,el){
      if(!suppressAutoGlow&&part!=="kick"&&typeof current==="function"){
        const t=current(),note=nearestNoteForPart(part,t,.16);
        if(note)flashNote(note,t);
      }
      return originalFlashPart(part,el);
    };
  }

  // Production manual input: resolve the exact candidate before input marks it hit,
  // then flash at that note's current X rather than at the goal line.
  if(typeof input==="function"&&typeof showJudge==="function"){
    let activeLane=-1;
    const originalInput=input;
    input=function(part,visualEl){
      const t=typeof current==="function"?current():0,
            note=nearestNoteForPart(part,t,.16);
      activeLane=note?laneForType(note.type):laneForPart(part);
      if(note)flashNote(note,t);
      suppressAutoGlow=true;
      try{return originalInput(part,visualEl)}
      finally{suppressAutoGlow=false}
    };
    showJudge=function(label){emit(label,activeLane)};
  }

  // Preview AUTO knows the exact note object, so never infer from neighbors.
  if(typeof showPreviewJudge==="function"&&typeof updateHits==="function"){
    showPreviewJudge=function(label="PERFECT",lane=1){emit(label,lane)};
    updateHits=function(t){
      const hitLanes=new Set();
      while(hitCursor<notes.length&&notes[hitCursor].time<=t){
        const n=notes[hitCursor++];
        if(n.time>=t-.08){
          if(n.type!=="kick")flashNote(n,t);
          suppressAutoGlow=true;
          try{flashPart(PART[n.type])}finally{suppressAutoGlow=false}
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
