"use strict";

(()=>{
  const autoToggle=document.querySelector("#autoToggle"),chartWrap=document.querySelector("#chartWrap");
  if(!autoToggle||!chartWrap)return;

  let cursor=0,lastNotes=null,lastStartedAt=NaN,lastTime=0;
  let scrubbing=false,waitingCommit=false,scrubStartedAt=NaN;

  const scoreActive=()=>document.body.dataset.scorePlayback==="1";
  const autoEnabled=()=>scoreActive()&&autoToggle.checked;

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
    /* This module owns the flag only while score playback is active.
       Normal gameplay sets autoplay in startGame(); overwriting it here every
       frame used to cancel Auto immediately after START. */
    if(!scoreActive())return;
    try{if(typeof autoplay!=="undefined")autoplay=!!autoToggle.checked}catch{}
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

  function flashKitPart(note){
    if(!note)return;
    if(note.type==="kick"){
      try{globalThis.DruMasterKickEffect?.flash?.()}catch{}
      return;
    }
    if(typeof PART==="undefined")return;
    const part=PART[note.type];if(!part)return;
    const el=document.querySelector(`#hitLayer [data-part="${part}"]:not(.inactive)`);
    if(!el)return;
    el.classList.remove("struck");
    void el.offsetWidth;
    el.classList.add("struck");
  }

  function flashScoreNote(note){
    /* Goal-line glow is note-specific and includes the bass-drum lane. */
    try{globalThis.DruMasterJudgement?.flashNote?.(note)}catch{}
    /* Drum/cymbal body hit flash is visual-only and never calls playDrum(). */
    flashKitPart(note);
  }

  function scoreFrame(){
    syncAutoplayFlag();
    if(!scoreActive()){
      lastNotes=null;
      requestAnimationFrame(scoreFrame);
      return;
    }

    const list=notesSafe(),start=startedAtSafe(),t=currentTimeSafe();
    if(!list){requestAnimationFrame(scoreFrame);return}

    if(waitingCommit&&start!==scrubStartedAt){
      scrubbing=false;waitingCommit=false;resetCursor();
    }
    if(scrubbing){requestAnimationFrame(scoreFrame);return}

    let canPlay=false;
    try{canPlay=typeof running!=="undefined"&&running&&typeof paused!=="undefined"&&!paused}catch{}
    if(!canPlay){requestAnimationFrame(scoreFrame);return}

    if(list!==lastNotes||start!==lastStartedAt||t<lastTime-.05)resetCursor();

    while(cursor<list.length&&list[cursor].time<=t+.012){
      const n=list[cursor++];
      if(n.time<t-.05)continue;

      /* In score playback every chart note produces both visual effects,
         regardless of the Auto toggle. */
      flashScoreNote(n);

      /* Auto controls audio for every chart note, including kick.
         Guide Drums remains an optional backing stem chosen by the user. */
      if(autoEnabled()){
        try{playDrum(n.note,n.type,n.velocity/127)}catch{}
      }
    }
    lastNotes=list;lastStartedAt=start;lastTime=t;
    requestAnimationFrame(scoreFrame);
  }
  requestAnimationFrame(scoreFrame);

  globalThis.DruMasterScoreAuto={
    isEnabled:autoEnabled,
    reset:resetCursor
  };
})();
