"use strict";

(()=>{
  const search=globalThis.DruMasterNoteSearch;
  if(!search||typeof search.nearest!=="function")return;

  const originalNearest=search.nearest.bind(search);
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

  function latencyState(){
    const perf=globalThis.DruMasterPerformanceMode;
    const aec=perf?.getMicCalibration?.()?.aec;
    const measuredSec=Number(aec?.delayMs)/1000;
    const outputLatencySec=Number(globalThis.ac?.outputLatency);
    const reportedInputLatencySec=Number(globalThis.DruMasterMicInputSettings?.latency);
    const measured=Number.isFinite(measuredSec)&&measuredSec>0?measuredSec:0;
    const output=Number.isFinite(outputLatencySec)&&outputLatencySec>0?outputLatencySec:0;
    /* AEC delay contains the output-device leg as well as the acoustic/mic-input
       return path. Pad strikes do not traverse the output-device leg, so remove
       it when the browser exposes AudioContext.outputLatency. If unavailable,
       the measured round-trip value is retained rather than inventing a value. */
    const judgeOffsetSec=clamp(measured-output,0,.250);
    return {
      measuredEchoDelaySec:measured,
      outputLatencySec:output,
      reportedInputLatencySec:Number.isFinite(reportedInputLatencySec)&&reportedInputLatencySec>=0?reportedInputLatencySec:null,
      judgeOffsetSec,
      judgeOffsetMs:judgeOffsetSec*1000
    };
  }

  function isPadMicLookup(predicate){
    const perf=globalThis.DruMasterPerformanceMode;
    if(!perf?.isPadRun?.())return false;
    if(document.body.classList.contains("acoustic-calibrating"))return false;
    /* performance-mode's microphone lookup uses the generic playable-note
       predicate. Part-specific keyboard/touch lookup contains PART and must not
       receive microphone latency compensation. */
    const source=predicate?Function.prototype.toString.call(predicate):"";
    return !source.includes("PART[")&&!source.includes("PART [")&&!source.includes("part");
  }

  search.nearest=function(list,time,maxDelta,predicate){
    const state=latencyState();
    const corrected=isPadMicLookup(predicate)?time-state.judgeOffsetSec:time;
    return originalNearest(list,corrected,maxDelta,predicate);
  };

  globalThis.DruMasterMicJudgeLatency={
    get:latencyState,
    getJudgeOffsetSec:()=>latencyState().judgeOffsetSec,
    getJudgeOffsetMs:()=>latencyState().judgeOffsetMs
  };
})();
