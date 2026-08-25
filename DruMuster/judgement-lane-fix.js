"use strict";

(()=>{
  const wrap=document.querySelector("#chartWrap");
  if(!wrap)return;

  const laneTop=[14.6667,44,73.3333];
  const fxByLane=[];

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
    return fxByLane[lane];
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

  function emit(label,lane){
    const grade=String(label||"").toLowerCase();
    if(lane<0||lane>2||grade==="miss"||grade==="auto")return;
    const {fx,text}=ensureFx(lane);
    text.textContent=String(label).toUpperCase();
    fx.dataset.grade=grade;
    fx.classList.remove("play");
    void fx.offsetWidth;
    fx.classList.add("play");
  }

  // Production: remember which playable drum part triggered input,
  // then place PERFECT/GREAT/GOOD on that chart lane.
  if(typeof input==="function"&&typeof showJudge==="function"){
    let activeLane=-1;
    const originalInput=input;
    input=function(part,visualEl){
      activeLane=laneForPart(part);
      return originalInput(part,visualEl);
    };
    showJudge=function(label){emit(label,activeLane)};
  }

  // Preview: AUTO can hit several lanes at one instant, so emit one
  // PERFECT independently on every lane that received a note.
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
})();
