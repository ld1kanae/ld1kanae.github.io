"use strict";

(()=>{
  const wrap=document.querySelector("#chartWrap"),canvas=document.querySelector("#chart"),gameHeader=document.querySelector("#game header");
  if(!wrap||!canvas)return;

  const fxByLane=[];
  const glowByLane=[];
  const LANE_LABELS=["CYMBAL","HI-HAT / RIDE / OTHER","SNARE / TOMS"];
  let suppressAutoGlow=false,hiddenFx=null;

  function isMobile(){
    return DruMusterChart.isMobileLayout?DruMusterChart.isMobileLayout():!!matchMedia?.("(hover:none) and (pointer:coarse) and (max-width:900px)")?.matches;
  }
  function isHiddenMode(){return !!(isMobile()&&globalThis.DruMasterMode?.isHidden?.())}

  function chartGeometry(){
    const w=canvas.clientWidth,h=canvas.clientHeight,
          judgeX=DruMusterChart.judgementX?DruMusterChart.judgementX(w):w*.11,
          kickH=Math.max(16,h*.12),
          mainH=h-kickH,
          laneH=mainH/3,
          labelFont=Math.max(9,laneH*.13);
    return {w,h,judgeX,laneH,labelFont};
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
    const {w,laneH,labelFont}=chartGeometry();
    if(isMobile()){
      ctx.save();
      ctx.font=`700 ${labelFont}px system-ui,sans-serif`;
      const labelWidth=ctx.measureText(LANE_LABELS[lane]||"").width;
      ctx.restore();
      node.style.left=`${Math.min(w-18,7+labelWidth+14)}px`;
      node.style.top=`${lane*laneH+6+labelFont*.5}px`;
      node.style.transform="translate(0,-50%)";
    }else{
      node.style.left="9%";
      node.style.top=`${laneH*(lane+.5)}px`;
      node.style.transform="translate(-50%,-50%)";
    }
  }

  function placeGlow(lane,node,note){
    const {judgeX,laneH}=chartGeometry(),visual=noteVisual(note);
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

  function buildFx(className,parent){
    const fx=document.createElement("div");
    fx.className=className;
    const text=document.createElement("span");
    text.className="lane-judge-text";
    fx.appendChild(text);
    parent.appendChild(fx);
    return {fx,text};
  }
  function ensureFx(lane){
    if(fxByLane[lane])return fxByLane[lane];
    const pair=buildFx("lane-judge-fx",wrap);
    pair.fx.dataset.lane=String(lane);
    fxByLane[lane]=pair;
    placeFx(lane,pair.fx);
    return pair;
  }
  function ensureHiddenFx(){
    if(hiddenFx)return hiddenFx;
    if(!gameHeader)return null;
    hiddenFx=buildFx("lane-judge-fx hidden-header-judge",gameHeader);
    return hiddenFx;
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
    if(!note||note.type==="kick"||isHiddenMode())return;
    const lane=laneForType(note.type);
    if(lane<0)return;
    const glow=ensureGlow(lane);
    placeGlow(lane,glow,note);
    glow.classList.remove("flash");
    void glow.offsetWidth;
    glow.classList.add("flash");
  }

  function playFx(pair,label,grade){
    if(!pair)return;
    pair.text.textContent=String(label).toUpperCase();
    pair.fx.dataset.grade=grade;
    pair.fx.classList.remove("play");
    void pair.fx.offsetWidth;
    pair.fx.classList.add("play");
  }

  function emit(label,lane){
    const grade=String(label||"").toLowerCase();
    if(grade==="miss"||grade==="auto")return;
    if(isHiddenMode()){
      playFx(ensureHiddenFx(),label,grade);
      return;
    }
    if(lane<0||lane>2)return;
    const pair=ensureFx(lane);
    placeFx(lane,pair.fx);
    playFx(pair,label,grade);
  }

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
