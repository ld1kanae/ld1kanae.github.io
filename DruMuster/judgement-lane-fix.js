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
          kickH=Math.max(16,h*.12),
          mainH=h-kickH,
          laneH=mainH/3;
    return {w,h,judgeX,laneH};
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

  function nearestNoteForPart(part,t,maxDelta=.16,includeHit=false){
    if(typeof notes==="undefined"||typeof PART==="undefined")return null;
    let best=null,bestDelta=maxDelta+.000001;
    for(const n of notes){
      if((!includeHit&&n.hit)||n.type==="kick"||PART[n.type]!==part)continue;
      const d=Math.abs(n.time-t);
      if(d<bestDelta){best=n;bestDelta=d}
      if(n.time>t+maxDelta)break;
    }
    return best;
  }

  function noteVisual(note){
    const group=typeof GROUP!=="undefined"?GROUP[note.type]:null;
    if(DruMusterChart.noteVisual)return DruMusterChart.noteVisual(note.type,group);
    const isOpen=note.type==="hhOpen";
    return {
      kind:isOpen?"double":"single",
      barWidth:isOpen?3:4,
      gap:isOpen?1:0,
      totalWidth:isOpen?7:4,
      color:note.type==="snare"?"#38a9ff":String(note.type||"").includes("Tom")?"#ad82ff":group==="cymbal"?"#ffd45a":group==="hh"?"#52dfcf":"#a7b0bc"
    };
  }

  function placeFx(lane,node){
    const {laneH}=chartGeometry();
    node.style.top=`${laneH*(lane+.5)}px`;
  }

  function placeGlow(lane,node,note){
    const {judgeX,laneH}=chartGeometry(),visual=noteVisual(note);
    // Hit feedback is centered on the goal line and uses the exact same bar/double-bar
    // dimensions and timbre color as the chart note itself. No judgement-zone rectangle.
    node.style.left=`${judgeX-visual.totalWidth/2}px`;
    node.style.top=`${lane*laneH}px`;
    node.style.width=`${visual.totalWidth}px`;
    node.style.height=`${laneH}px`;
    node.style.setProperty("--note-total-w",`${visual.totalWidth}px`);
    node.style.setProperty("--note-bar-w",`${visual.barWidth}px`);
    node.style.setProperty("--note-gap",`${visual.gap}px`);
    node.style.setProperty("--note-color",visual.color);
    node.dataset.shape=visual.kind;
    node.dataset.type=note.type;
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

  function flashNote(note){
    if(!note||note.type==="kick")return;
    const lane=laneForType(note.type);
    if(lane<0)return;
    const glow=ensureGlow(lane);
    placeGlow(lane,glow,note);
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

  // Autoplay reaches flashPart after marking its note hit, so include just-hit notes
  // and choose the closest one in a narrow timing window.
  if(typeof flashPart==="function"){
    const originalFlashPart=flashPart;
    flashPart=function(part,el){
      if(!suppressAutoGlow&&part!=="kick"&&typeof current==="function"){
        const note=nearestNoteForPart(part,current(),.05,true);
        if(note)flashNote(note);
      }
      return originalFlashPart(part,el);
    };
  }

  // Production manual input: resolve the exact candidate before input marks it hit.
  // The note-shaped flash always occurs at the goal line rather than as a rectangular zone.
  if(typeof input==="function"&&typeof showJudge==="function"){
    let activeLane=-1;
    const originalInput=input;
    input=function(part,visualEl){
      const t=typeof current==="function"?current():0,
            note=nearestNoteForPart(part,t,.16);
      activeLane=note?laneForType(note.type):laneForPart(part);
      if(note)flashNote(note);
      suppressAutoGlow=true;
      try{return originalInput(part,visualEl)}
      finally{suppressAutoGlow=false}
    };
    showJudge=function(label){emit(label,activeLane)};
  }

  // Preview AUTO has the exact note object, so its goal-line flash always uses that note's shape.
  if(typeof showPreviewJudge==="function"&&typeof updateHits==="function"){
    showPreviewJudge=function(label="PERFECT",lane=1){emit(label,lane)};
    updateHits=function(t){
      const hitLanes=new Set();
      while(hitCursor<notes.length&&notes[hitCursor].time<=t){
        const n=notes[hitCursor++];
        if(n.time>=t-.08){
          if(n.type!=="kick")flashNote(n);
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
