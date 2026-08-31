"use strict";

(()=>{
  const wrap=document.querySelector("#chartWrap"),canvas=document.querySelector("#chart"),gameHeader=document.querySelector("#game header");
  if(!wrap||!canvas)return;

  const fxByLane=[];
  const glowByLane=[];
  const CYMBAL_PARTS=new Set(["crash","crash2","ride","splash"]);
  const MOBILE_JUDGE_FONT=9;
  const MOBILE_GOAL_GAP=12;
  const MOBILE_OPTICAL_X=2;
  const MOBILE_OPTICAL_Y=-3;
  const DESKTOP_OPTICAL_X=-4;
  const stats={geometryBuilds:0,measureTextCalls:0,fxPlacements:0,glowStyleWrites:0,glowStyleSkips:0};
  let suppressAutoGlow=false,hiddenFx=null,geometry=null,geometryVersion=0;

  function isMobile(){
    return DruMusterChart.isMobileLayout?DruMusterChart.isMobileLayout():!!matchMedia?.("(hover:none) and (pointer:coarse) and (max-width:900px)")?.matches;
  }
  function isHiddenMode(){return !!(isMobile()&&globalThis.DruMasterMode?.isHidden?.())}

  function rebuildGeometry(){
    const w=canvas.clientWidth,h=canvas.clientHeight,
          judgeX=DruMusterChart.judgementX?DruMusterChart.judgementX(w):w*.11,
          kickH=Math.max(16,h*.12),
          mainH=h-kickH,
          laneH=mainH/3,
          labelFont=Math.max(9,laneH*.13),
          mobile=isMobile();
    let judgeWidth=0;
    if(mobile&&w>0&&h>0){
      ctx.save();
      ctx.font=`900 ${MOBILE_JUDGE_FONT}px system-ui,sans-serif`;
      const letterSpacing=MOBILE_JUDGE_FONT*.055;
      judgeWidth=ctx.measureText("PERFECT").width+letterSpacing*6;
      ctx.restore();
      stats.measureTextCalls++;
    }
    geometry={w,h,judgeX,laneH,labelFont,mainH,kickH,mobile,judgeWidth,version:++geometryVersion};
    stats.geometryBuilds++;
    return geometry;
  }
  function chartGeometry(){
    if(!geometry||geometry.w<=0||geometry.h<=0)return rebuildGeometry();
    return geometry;
  }

  function laneForPart(part){
    if(part==="kick")return 3;
    if(part==="crash"||part==="crash2"||part==="splash")return 0;
    if(part==="hh"||part==="ride"||part==="special")return 1;
    if(part==="snare"||part==="highTom"||part==="midTom"||part==="floorTom")return 2;
    return -1;
  }
  function laneForType(type){
    if(type==="kick")return 3;
    const group=typeof GROUP!=="undefined"?GROUP[type]:null;
    return group==="cymbal"?0:group==="hh"?1:group==="drums"?2:-1;
  }

  function matchesPart(part,n){
    const notePart=PART[n.type];
    return CYMBAL_PARTS.has(part)?CYMBAL_PARTS.has(notePart):notePart===part;
  }

  function nearestNoteForPart(part,t,maxDelta=.16,includeHit=false){
    if(typeof notes==="undefined"||typeof PART==="undefined")return null;
    const search=globalThis.DruMasterNoteSearch;
    if(search?.nearest){
      return search.nearest(notes,t,maxDelta,n=>(includeHit||!n.hit)&&n.type!=="kick"&&matchesPart(part,n))?.note||null;
    }
    let best=null,bestDelta=maxDelta+.000001;
    for(const n of notes){
      if(n.time<t-maxDelta)continue;
      if(n.time>t+maxDelta)break;
      if((!includeHit&&n.hit)||n.type==="kick"||!matchesPart(part,n))continue;
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
    const g=chartGeometry();
    if(g.mobile){
      const left=Math.max(7,g.judgeX-g.judgeWidth-MOBILE_GOAL_GAP)+MOBILE_OPTICAL_X;
      node.style.left=`${left}px`;
      node.style.top=`${g.laneH*(lane+.5)+MOBILE_OPTICAL_Y}px`;
      node.style.transform="translate(0,-50%)";
    }else{
      node.style.left="9%";
      node.style.top=`${g.laneH*(lane+.5)}px`;
      node.style.transform=`translate(calc(-50% + ${DESKTOP_OPTICAL_X}px),-50%)`;
    }
    stats.fxPlacements++;
  }

  function placeGlow(lane,slot,note){
    const g=chartGeometry(),visual=noteVisual(note),isKick=lane===3||note.type==="kick";
    const signature=`${g.version}|${lane}|${note.type}|${visual.kind}|${visual.totalWidth}|${visual.barWidth}|${visual.gap}|${visual.color}`;
    slot.lastNote=note;
    if(slot.signature===signature){stats.glowStyleSkips++;return}
    slot.signature=signature;
    const node=slot.node;
    node.style.left=`${g.judgeX-visual.totalWidth/2}px`;
    node.style.top=`${isKick?g.mainH+2:lane*g.laneH}px`;
    node.style.width=`${visual.totalWidth}px`;
    node.style.height=`${isKick?Math.max(4,g.kickH-4):g.laneH}px`;
    node.style.setProperty("--note-total-w",`${visual.totalWidth}px`);
    node.style.setProperty("--note-bar-w",`${visual.barWidth}px`);
    node.style.setProperty("--note-gap",`${visual.gap}px`);
    node.style.setProperty("--note-color",visual.color);
    node.dataset.shape=visual.kind;
    node.dataset.type=note.type;
    stats.glowStyleWrites++;
  }

  function syncGeometry(){
    geometry=null;
    rebuildGeometry();
    for(let lane=0;lane<3;lane++)if(fxByLane[lane])placeFx(lane,fxByLane[lane].fx);
    for(let lane=0;lane<glowByLane.length;lane++){
      const slot=glowByLane[lane];
      if(slot?.lastNote)placeGlow(lane,slot,slot.lastNote);
    }
  }

  function buildFx(className,parent){
    const fx=document.createElement("div");
    fx.className=className;
    const text=document.createElement("span");
    text.className="lane-judge-text";
    fx.appendChild(text);
    parent.appendChild(fx);
    return {fx,text,lastLabel:"",lastGrade:""};
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
    const node=document.createElement("div");
    node.className="lane-hit-glow";
    node.dataset.lane=String(lane);
    wrap.appendChild(node);
    const slot={node,signature:"",lastNote:null};
    glowByLane[lane]=slot;
    return slot;
  }

  function flashNote(note){
    if(!note||isHiddenMode())return;
    const lane=laneForType(note.type);
    if(lane<0)return;
    const slot=ensureGlow(lane),glow=slot.node;
    placeGlow(lane,slot,note);
    if(!globalThis.DruMasterPerfAnimationPool){
      for(const a of glow.getAnimations())a.cancel();
    }
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
    const text=String(label).toUpperCase();
    if(pair.lastLabel!==text){pair.text.textContent=text;pair.lastLabel=text}
    if(pair.lastGrade!==grade){pair.fx.dataset.grade=grade;pair.lastGrade=grade}
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
    playFx(ensureFx(lane),label,grade);
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
      const scorePlayback=document.body.dataset.scorePlayback==="1";
      if(!scorePlayback&&typeof notes!=="undefined"&&typeof current==="function"&&typeof running!=="undefined"&&running&&!paused){
        const t=current();
        if(lastT<0||t<lastT-.08)resetKickCursor(t);
        while(kickCursor<notes.length&&notes[kickCursor].time<=t){
          const n=notes[kickCursor++];
          if(n.type==="kick"&&n.time>=Math.max(0,lastT)-.025){n.hit=true;flashNote(n)}
        }
        lastT=t;
      }else{
        lastT=-1;kickCursor=0;
      }
    };
    const ticker=globalThis.DruMasterPerfTicker;
    if(ticker?.register)ticker.register("judgement-kick-watch",watchKick);
    else{
      const fallback=()=>{watchKick();requestAnimationFrame(fallback)};
      requestAnimationFrame(fallback);
    }
  }

  globalThis.DruMasterJudgement={
    flashNote,
    emitForNote(note,label,options={}){
      if(!note)return;
      if(options.flash!==false)flashNote(note);
      emit(label,laneForType(note.type));
    }
  };
  globalThis.DruMasterJudgementPerf={version:"20260901-pass9",stats};

  new ResizeObserver(()=>requestAnimationFrame(syncGeometry)).observe(wrap);
  addEventListener("resize",()=>requestAnimationFrame(syncGeometry),{passive:true});
})();
