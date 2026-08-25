"use strict";

(()=>{
  const PERFECT_WINDOW=.035; // ±35 ms; previously ±55 ms.

  /* Production judgement override. Keep GREAT/GOOD windows unchanged; only
     PERFECT is tightened. This script loads before judgement-lane-fix.js so
     lane-local PERFECT/GREAT/GOOD placement still wraps this input function. */
  if(typeof input==="function"&&typeof notes!=="undefined"&&typeof PART!=="undefined"){
    input=function(part,visualEl){
      if(!running||paused||autoplay)return;
      const t=current();
      let best=null,delta=Infinity;
      for(const n of notes){
        if(n.hit||PART[n.type]!==part||n.type==="kick")continue;
        const d=Math.abs(n.time-t);
        if(d<delta){best=n;delta=d}
        if(n.time>t+.16)break;
      }
      const matched=best&&delta<=.16,
            vel=matched?best.velocity/127:.72,
            type=matched?best.type:DEFAULT_TYPE[part],
            note=matched?best.note:DEFAULT_NOTE[type];
      playDrum(note,type,vel);
      flashPart(part,visualEl);
      if(!matched)return;

      best.hit=true;
      let mult,label;
      if(delta<=PERFECT_WINDOW){
        mult=1;label="PERFECT";counts.perfect++;
      }else if(delta<=.105){
        mult=.75;label="GREAT";counts.great++;
      }else{
        mult=.4;label="GOOD";counts.good++;
      }
      score+=weight(best.type)*best.velocity/127*1000*mult;
      $("#score").textContent=String(Math.round(score/maxScore*1000000)).padStart(6,"0");
      showJudge(label);
    };
  }

  /* Space toggles pause/resume in both production and preview. The existing
     drum-key handler ignores Space, so this does not interfere with Q/W/etc. */
  addEventListener("keydown",e=>{
    if(e.code!=="Space"||e.repeat)return;
    const tag=e.target?.tagName;
    if(tag==="INPUT"||tag==="TEXTAREA"||tag==="SELECT")return;
    if(typeof togglePause!=="function")return;
    e.preventDefault();
    togglePause();
  });
})();
