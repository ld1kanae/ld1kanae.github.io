"use strict";

(()=>{
  const autoToggle=document.querySelector("#autoToggle"),chartWrap=document.querySelector("#chartWrap");
  if(!autoToggle||!chartWrap)return;

  let cursor=0,lastNotes=null,lastStartedAt=NaN,lastTime=0;
  let scrubbing=false,waitingCommit=false,scrubStartedAt=NaN;

  const scoreActive=()=>document.body.dataset.scorePlayback==="1";
  const autoEnabled=()=>scoreActive()&&autoToggle.checked;

  /* Score playback already has a dedicated Guide Drums stem. The legacy score
     loop also auto-fired kick samples regardless of the Auto toggle, which made
     the bass drum sound doubled whenever Guide Drums was enabled. Suppress only
     those game-generated kick samples while score playback is active. */
  const basePlayDrum=typeof playDrum==="function"?playDrum:null;
  if(basePlayDrum){
    playDrum=function(note,type,v){
      if(scoreActive()&&type==="kick")return;
      return basePlayDrum(note,type,v);
    };
  }

  const lowerBound=(list,sec)=>{
    let lo=0,hi=list.length;
    while(lo<hi){const mid=(lo+hi)>>1;if(list[mid].time<sec)lo=mid+1;else hi=mid}
    return lo;
  };

  function currentTimeSafe(){
    try{return typeof current==="function"?current():0}catch{return 0}
  }
  function startedAtSafe(){
    try{return typeof startedAt!=="undefined"?startedAt:NaN}catch{return NaN}
  }
  function notesSafe(){
    try{return typeof notes!=="undefined"&&Array.isArray(notes)?notes:null}catch{return null}
  }
  function resetCursor(){
    const list=notesSafe(),t=currentTimeSafe();
    if(!list)return;
    cursor=lowerBound(list,Math.max(0,t-.05));
    lastNotes=list;lastStartedAt=startedAtSafe();lastTime=t;
  }
  function syncAutoplayFlag(){
    try{if(typeof autoplay!=="undefined")autoplay=autoEnabled()}catch{}
  }

  function beginScrub(){
    if(!scoreActive())return;
    scrubbing=true;waitingCommit=false;scrubStartedAt=startedAtSafe();
  }
  function waitForCommit(){
    if(!scrubbing)return;
    waitingCommit=true;
  }
  chartWrap.addEventListener("pointerdown",beginScrub,true);
  chartWrap.addEventListener("pointerup",waitForCommit,true);
  chartWrap.addEventListener("pointercancel",waitForCommit,true);

  const baseInput=typeof input==="function"?input:null;
  if(baseInput){
    input=function(part,visualEl){
      if(autoEnabled())return;
      return baseInput(part,visualEl);
    };
  }

  const observer=new MutationObserver(()=>{
    syncAutoplayFlag();
    if(scoreActive())resetCursor();
    else{scrubbing=false;waitingCommit=false;lastNotes=null}
  });
  observer.observe(document.body,{attributes:true,attributeFilter:["data-score-playback"]});

  function autoFrame(){
    syncAutoplayFlag();
    if(!autoEnabled()){
      lastNotes=null;
      requestAnimationFrame(autoFrame);
      return;
    }

    const list=notesSafe(),start=startedAtSafe(),t=currentTimeSafe();
    if(!list){requestAnimationFrame(autoFrame);return}

    if(waitingCommit&&start!==scrubStartedAt){
      scrubbing=false;waitingCommit=false;resetCursor();
    }
    if(scrubbing){requestAnimationFrame(autoFrame);return}

    let canPlay=false;
    try{canPlay=typeof running!=="undefined"&&running&&typeof paused!=="undefined"&&!paused}catch{}
    if(!canPlay){requestAnimationFrame(autoFrame);return}

    if(list!==lastNotes||start!==lastStartedAt||t<lastTime-.05)resetCursor();

    while(cursor<list.length&&list[cursor].time<=t+.012){
      const n=list[cursor++];
      if(n.type==="kick"||n.time<t-.05)continue;
      try{playDrum(n.note,n.type,n.velocity/127)}catch{}
      try{if(typeof flashPart==="function"&&typeof PART!=="undefined")flashPart(PART[n.type])}catch{}
    }
    lastNotes=list;lastStartedAt=start;lastTime=t;
    requestAnimationFrame(autoFrame);
  }
  requestAnimationFrame(autoFrame);

  globalThis.DruMasterScoreAuto={
    isEnabled:autoEnabled,
    reset:resetCursor
  };
})();
