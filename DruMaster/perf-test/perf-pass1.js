"use strict";

(()=>{
  const isTouch=(navigator.maxTouchPoints||0)>0||
    !!globalThis.matchMedia?.("(any-pointer:coarse)")?.matches||
    !!globalThis.matchMedia?.("(pointer:coarse)")?.matches;

  document.documentElement.dataset.dmPerfTest="pass3";

  const stats={
    renderRequests:0,
    actualRenders:0,
    suppressedRenders:0,
    suppressedKickSchedulerCalls:0,
    startedAt:performance.now()
  };

  if(isTouch&&typeof draw==="function"){
    const rawDraw=draw,FRAME_MS=1000/60;
    let nextRender=0,lastResult;
    draw=function(...args){
      stats.renderRequests++;
      const now=performance.now();
      if(nextRender&&now+.75<nextRender){
        stats.suppressedRenders++;
        return lastResult;
      }
      if(!nextRender||now-nextRender>100)nextRender=now+FRAME_MS;
      else nextRender+=FRAME_MS;
      stats.actualRenders++;
      lastResult=rawDraw.apply(this,args);
      return lastResult;
    };
  }

  if(typeof scheduleKickAudio==="function"){
    scheduleKickAudio=function(){stats.suppressedKickSchedulerCalls++};
  }

  if(isTouch){
    const style=document.createElement("style");
    style.dataset.dmPerfPass="3";
    style.textContent=`
      @media (hover:none) and (pointer:coarse) and (max-width:900px){
        .game #chartWrap{
          -webkit-backdrop-filter:none!important;
          backdrop-filter:none!important;
        }
        #hhOpenGaugeHandle{will-change:transform!important}
      }
    `;
    document.head.appendChild(style);
  }

  globalThis.DruMasterPerfTest={
    version:"20260901-pass3",
    stats,
    snapshot(){
      const elapsed=Math.max(.001,(performance.now()-stats.startedAt)/1000);
      const graph=globalThis.DruMasterPerfChartPass2?.stats||null;
      const core=globalThis.DruMasterPerfChartCorePass3||null;
      return {
        ...stats,
        elapsedSec:+elapsed.toFixed(2),
        renderRequestRate:+(stats.renderRequests/elapsed).toFixed(1),
        renderRate:+(stats.actualRenders/elapsed).toFixed(1),
        suppressedRenderRate:+(stats.suppressedRenders/elapsed).toFixed(1),
        hhGraphFrames:graph?.frames??null,
        hhGraphSamples:graph?.samples??null,
        hhGraphSamplesPerFrame:graph?.frames?+(graph.samples/graph.frames).toFixed(1):null,
        noteVisualCacheSize:core?.cacheSize??null,
        noteVisualRequests:core?.stats?.noteVisualRequests??null,
        noteVisualMisses:core?.stats?.noteVisualMisses??null,
        simultaneousOffsetCalls:core?.stats?.simultaneousOffsetCalls??null,
        audio:globalThis.DruMasterAudioControl?.getStats?.()||null
      };
    }
  };

  if(new URLSearchParams(location.search).get("perf")==="1"){
    setInterval(()=>console.table(globalThis.DruMasterPerfTest.snapshot()),5000);
  }
})();
