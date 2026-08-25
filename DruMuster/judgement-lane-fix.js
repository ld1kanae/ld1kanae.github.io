"use strict";

(()=>{
  const wrap=document.querySelector("#chartWrap"),canvas=document.querySelector("#chart");
  if(!wrap||!canvas)return;

  const laneTop=[14.6667,44,73.3333];
  const fxByLane=[];
  const glowByLane=[];

  function chartGeometry(){
    const w=canvas.clientWidth,h=canvas.clientHeight,
          judgeX=w*.11,
          kickH=Math.max(16,h*.12),
          mainH=h-kickH,
          laneH=mainH/3;
    return {judgeX,laneH};
  }

  function placeFx(lane,node){
    const {laneH}=chartGeometry();
    node.style.top=`${laneH*(lane+.5)}px`;
  }
  function placeGlow(lane,node){
    const {judgeX,laneH}=chartGeometry();
    node.style.left=`${judgeX}px`;
    node.style.top=`${laneH*(lane+.5)}px`;
    node.style.height=`${laneH}px`;
  }
  function syncGeometry(){
    for(let lane=0;lane<3;lane++){
      if(fxByLane[lane])placeFx(lane,fxByLane[lane].fx);
      if(glowByLane[lane])placeGlow(lane,glowByLane[lane]);
    }
  }

  function ensureFx(lane){
    if(fxByLane[lane])return fxByLane[lane];
    const fx=document.createElement("div");
    fx.className="lane-judge-fx";
    fx.style.setProperty("--lane-top",laneTop[lane]+"%");
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
    placeGlow(lane,glow);
    return glow;
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

  function flashLane(lane){
    if(lane<0||lane>2)return;
    const glow=ensureGlow(lane);
    placeGlow(lane,glow);
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

  // Any visible drum strike flashes the exact judgement-line segment for that lane.
  if(typeof flashPart==="function"){
    const originalFlashPart=flashPart;
    flashPart=function(part,el){
      flashLane(laneForPart(part));
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
