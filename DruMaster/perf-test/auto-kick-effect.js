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

  globalThis.DruMasterKickEffect={flash:flashKick};

  function isLegacyAutomaticKickCall(){
    if(!Array.isArray(globalThis.notes)&&typeof notes==="undefined")return false;
    if(typeof nextKick!=="number"||typeof current!=="function")return false;
    const list=typeof notes!=="undefined"?notes:globalThis.notes,n=list?.[nextKick-1];
    return !!n&&n.type==="kick"&&Math.abs(Number(n.time)-Number(current()))<=.06;
  }

  function syncKickGoalHits(){
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

  const ticker=globalThis.DruMasterPerfTicker;
  if(ticker?.register)ticker.register("kick-goal-sync",syncKickGoalHits);
  else{
    const fallback=()=>{syncKickGoalHits();requestAnimationFrame(fallback)};
    requestAnimationFrame(fallback);
  }

  playDrum=function(note,type,v=.75){
    const automaticKick=type==="kick"&&isLegacyAutomaticKickCall(),out=basePlayDrum(note,type,v);
    if(type==="kick"&&!automaticKick)queueMicrotask(flashKick);
    return out;
  };
})();
