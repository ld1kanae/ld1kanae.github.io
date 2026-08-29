"use strict";

(()=>{
  const wrap=document.querySelector("#chartWrap"),canvas=document.querySelector("#chart"),gameHeader=document.querySelector("#game header");
  if(!wrap||!canvas)return;

  const fxByLane=[];
  const glowByLane=[];
  const MOBILE_JUDGE_FONT=9;
  const MOBILE_GOAL_GAP=12;
  const MOBILE_OPTICAL_X=2;
  const MOBILE_OPTICAL_Y=-3;
  const DESKTOP_OPTICAL_X=-4;
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
    return {w,h,judgeX,laneH,labelFont,mainH,kickH};
  }

  function laneForPart(part){
    if(part==="kick")return 3;
    if(part==="crash"||part==="crash2")return 0;
    if(part==="hh"||part==="ride"||part==="special")return 1;
    if(part==="snare"||part==="highTom"||part==="midTom"||part==="floorTom")return 2;
    return -1;
  }
  function laneForType(type){
    if(type==="kick")return 3;
    const group=typeof GROUP!=="undefined"?GROUP[type]:null;
    return group==="cymbal"?0:group==="hh"?1:group==="drums"?2:-1;
  }

  function nearestNoteForPart(part,t,maxDelta=.16,includeHit=false){
    if(typeof notes==="undefined"||typeof PART==="undefined")return null;
    const search=globalThis.DruMasterNoteSearch;
    if(search?.nearest){
      return search.nearest(notes,t,maxDelta,n=>(includeHit||!n.hit)&&n.type!=="kick"&&PART[n.type]===part)?.note||null;
    }
    let best=null,bestDelta=maxDelta+.000001;
    for(const n of notes){
      if(n.time<t-maxDelta)continue;
      if(n.time>t+maxDelta)break;
      if((!includeHit&&n.hit)||n.type==="kick"||PART[n.type]!==part)continue;
      const d=Math.abs(n.time-t);
      if(d<bestDelta){best=n;bestDelta=d}
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
      color:note.type==="snare"?"#ff3d73":note.type==="highTom"?"#d76bff":note.type==="midTom"?"#8875ff":note.type==="floorTom"?"#329cff":note.type==="ride"?"#63d66f":group==="cymbal"?"#ffd45a":group==="hh"?"#52dfcf":"#aeb9c7"
    };
  }

  function placeFx(lane,node){
    const {judgeX,laneH}=chartGeometry();
    if(isMobile()){
      ctx.save();
      ctx.font=`900 ${MOBILE_JUDGE_FONT}px system-ui,sans-serif`;
      const letterSpacing=MOBILE_JUDGE_FONT*.055;
      const judgeWidth=ctx.measureText("PERFECT").width+letterSpacing*6;
      ctx.restore();

      const left=Math.max(7,judgeX-judgeWidth-MOBILE_GOAL_GAP)+MOBILE_OPTICAL_X;
      node.style.left=`${left}px`;
      node.style.top=`${laneH*(lane+.5)+MOBILE_OPTICAL_Y}px`;
      node.style.transform="translate(0,-50%)";
    }else{
      node.style.left="9%";
      node.style.top=`${laneH*(lane+.5)}px`;
      node.style.transform=`translate(calc(-50% + ${DESKTOP_OPTICAL_X}px),-50%)`;
    }
  }

  function placeGlow(lane,node,note){
    const {judgeX,laneH,mainH,kickH}=chartGeometry(),visual=noteVisual(note),isKick=lane===3||note.type==="kick";
    node.style.left=`${judgeX-visual.totalWidth/2}px`;
    node.style.top=`${isKick?mainH+2:lane*laneH}px`;
    node.style.width=`${visual.totalWidth}px`;
    node.style.height=`${isKick?Math.max(4,kickH-4):laneH}px`;
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
    if(!note||isHiddenMode())return;
    const lane=laneForType(note.type);
    if(lane<0)return;
    const glow=ensureGlow(lane);
    placeGlow(lane,glow,note);
    for(const a of glow.getAnimations())a.cancel();
    glow.animate([
      {opacity:0,filter:"brightness(1)",offset:0},
      {opacity:1,filter:"brightness(1.75)",offset:.12},
      {opacity:.78,filter:"brightness(1.3)",offset:.42},
      {opacity:0,filter:"brightness(1)",offset:1}
    ],{duration:200,easing:"ease-out"});
  }

  function restartPlayClass(fx){
    const active=fx.getAnimations({subtree:true});
    if(active.length){
      for(const a of active){try{a.currentTime=0;a.play()}catch{}}
      return;
    }
    fx.classList.remove("play");
    requestAnimationFrame(()=>fx.classList.add("play"));
  }

  function playFx(pair,label,grade){
    if(!pair)return;
    pair.text.textContent=String(label).toUpperCase();
    pair.fx.dataset.grade=grade;
    if(!pair.fx.classList.contains("play"))pair.fx.classList.add("play");
    else restartPlayClass(pair.fx);
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
          flashNote(n);
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
  }else{
    let kickCursor=0,lastT=-1;
    const resetKickCursor=t=>{
      const search=globalThis.DruMasterNoteSearch;
      kickCursor=search?.lowerBoundTime?search.lowerBoundTime(notes,t-.03):0;
      if(!search?.lowerBoundTime)while(kickCursor<notes.length&&notes[kickCursor].time<t-.03)kickCursor++;
    };
    const watchKick=()=>{
      /* Score playback owns all note-synchronised visuals itself, including
         kick, so the normal-play kick watcher must not duplicate that glow. */
      const scorePlayback=document.body.dataset.scorePlayback==="1";
      if(!scorePlayback&&typeof notes!=="undefined"&&typeof current==="function"&&typeof running!=="undefined"&&running&&!paused){
        const t=current();
        if(lastT<0||t<lastT-.08)resetKickCursor(t);
        while(kickCursor<notes.length&&notes[kickCursor].time<=t){
          const n=notes[kickCursor++];
          if(n.type==="kick"&&n.time>=Math.max(0,lastT)-.025)flashNote(n);
        }
        lastT=t;
      }else{
        lastT=-1;kickCursor=0;
      }
      requestAnimationFrame(watchKick);
    };
    requestAnimationFrame(watchKick);
  }

  /* Shared entry point for input modes that match a note without choosing a
     drum lane first (anywhere-touch / microphone pad practice). */
  globalThis.DruMasterJudgement={
    flashNote,
    emitForNote(note,label,options={}){
      if(!note)return;
      if(options.flash!==false)flashNote(note);
      emit(label,laneForType(note.type));
    }
  };

  new ResizeObserver(()=>requestAnimationFrame(syncGeometry)).observe(wrap);
  addEventListener("resize",()=>requestAnimationFrame(syncGeometry),{passive:true});
})();
