"use strict";

(()=>{
  if(typeof playDrum!=="function")return;
  const basePlayDrum=playDrum;
  let kickAnimation=null,kickGoalCursor=0,kickGoalRunStart=NaN;

  function flashKick(){
    const fx=document.querySelector("#kickFx");
    if(!fx)return;
    fx.classList.remove("hit","auto-hit");
    kickAnimation?.cancel();
    kickAnimation=fx.animate([
      {opacity:.8,transform:"translate(-50%,-50%) scale(.4)"},
      {opacity:0,transform:"translate(-50%,-50%) scale(1.5)"}
    ],{duration:240,easing:"ease-out"});
  }

  /* Expose the visual independently from audio. Score playback uses this to
     show the bass-drum hit without synthesizing a second kick sound. */
  globalThis.DruMasterKickEffect={flash:flashKick};

  function isLegacyAutomaticKickCall(){
    if(!Array.isArray(globalThis.notes)&&typeof notes==="undefined")return false;
    if(typeof nextKick!=="number"||typeof current!=="function")return false;
    const list=typeof notes!=="undefined"?notes:globalThis.notes,n=list?.[nextKick-1];
    return !!n&&n.type==="kick"&&Math.abs(Number(n.time)-Number(current()))<=.06;
  }

  /* Kick audio can be scheduled ahead of the visible goal line. Retire the
     chart note only when the latency-corrected chart clock actually reaches
     the goal, and fire the kick flash in that same frame. */
  function syncKickGoalHits(){
    requestAnimationFrame(syncKickGoalHits);
    if(document.body.dataset.scorePlayback==="1")return;
    if(typeof running==="undefined"||!running||typeof paused!=="undefined"&&paused||typeof notes==="undefined"||!Array.isArray(notes)||!notes.length)return;
    const runStart=Number(typeof startedAt!=="undefined"?startedAt:NaN);
    if(runStart!==kickGoalRunStart){kickGoalRunStart=runStart;kickGoalCursor=0}
    const chartClock=globalThis.DruMasterChartClock?.current,
          t=typeof chartClock==="function"?Number(chartClock()):typeof current==="function"?Number(current()):NaN;
    if(!Number.isFinite(t))return;
    while(kickGoalCursor<notes.length&&Number(notes[kickGoalCursor].time)<=t+.0005){
      const n=notes[kickGoalCursor++];
      if(n.type!=="kick"||n.hit)continue;
      n.hit=true;
      flashKick();
    }
  }
  requestAnimationFrame(syncKickGoalHits);

  /* Manual kick input still flashes immediately. Automatic chart kicks are
     flashed by syncKickGoalHits so the note disappearance and glow coincide. */
  playDrum=function(note,type,v=.75){
    const automaticKick=type==="kick"&&isLegacyAutomaticKickCall(),out=basePlayDrum(note,type,v);
    if(type==="kick"&&!automaticKick)queueMicrotask(flashKick);
    return out;
  };
})();
