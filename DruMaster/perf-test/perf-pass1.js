"use strict";

(()=>{
  const isTouch=(navigator.maxTouchPoints||0)>0||
    !!globalThis.matchMedia?.("(any-pointer:coarse)")?.matches||
    !!globalThis.matchMedia?.("(pointer:coarse)")?.matches;

  document.documentElement.dataset.dmPerfTest="pass4";

  const stats={
    renderRequests:0,
    actualRenders:0,
    suppressedRenders:0,
    suppressedKickSchedulerCalls:0,
    frameGapOver20:0,
    frameGapOver33:0,
    frameGapOver50:0,
    maxRenderGapMs:0,
    peakActiveVoices:0,
    longTasks:0,
    longTaskTotalMs:0,
    maxLongTaskMs:0,
    startedAt:performance.now()
  };

  if(isTouch&&typeof draw==="function"){
    const rawDraw=draw,FRAME_MS=1000/60;
    let nextRender=0,lastResult,lastActual=0;
    draw=function(...args){
      stats.renderRequests++;
      const now=performance.now();
      if(nextRender&&now+.75<nextRender){
        stats.suppressedRenders++;
        return lastResult;
      }
      if(!nextRender||now-nextRender>100)nextRender=now+FRAME_MS;
      else nextRender+=FRAME_MS;

      if(lastActual){
        const gap=now-lastActual;
        if(gap<500){
          if(gap>20)stats.frameGapOver20++;
          if(gap>33.34)stats.frameGapOver33++;
          if(gap>50)stats.frameGapOver50++;
          if(gap>stats.maxRenderGapMs)stats.maxRenderGapMs=gap;
        }
      }
      lastActual=now;
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
    style.dataset.dmPerfPass="4";
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

  const perfEnabled=new URLSearchParams(location.search).get("perf")==="1";
  if(perfEnabled&&typeof PerformanceObserver==="function"){
    try{
      const observer=new PerformanceObserver(list=>{
        for(const entry of list.getEntries()){
          const duration=Number(entry.duration)||0;
          stats.longTasks++;
          stats.longTaskTotalMs+=duration;
          stats.maxLongTaskMs=Math.max(stats.maxLongTaskMs,duration);
        }
      });
      observer.observe({entryTypes:["longtask"]});
    }catch{}
  }

  globalThis.DruMasterPerfTest={
    version:"20260901-pass4",
    stats,
    snapshot(){
      const elapsed=Math.max(.001,(performance.now()-stats.startedAt)/1000);
      const graph=globalThis.DruMasterPerfChartPass2?.stats||null;
      const core=globalThis.DruMasterPerfChartCorePass3||null;
      const audio=globalThis.DruMasterAudioControl?.getStats?.()||null;
      if(audio?.activeVoices>stats.peakActiveVoices)stats.peakActiveVoices=audio.activeVoices;
      const memory=performance?.memory;
      return {
        ...stats,
        maxRenderGapMs:+stats.maxRenderGapMs.toFixed(2),
        longTaskTotalMs:+stats.longTaskTotalMs.toFixed(1),
        maxLongTaskMs:+stats.maxLongTaskMs.toFixed(1),
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
        staticBackgroundBuilds:core?.stats?.staticBuilds??null,
        staticBackgroundBlits:core?.stats?.staticBlits??null,
        canvasDpr:globalThis.DruMasterPerfCanvasPass4?.dpr??(canvas?.clientWidth?canvas.width/canvas.clientWidth:null),
        jsHeapUsedMB:memory?.usedJSHeapSize?+(memory.usedJSHeapSize/1048576).toFixed(1):null,
        jsHeapTotalMB:memory?.totalJSHeapSize?+(memory.totalJSHeapSize/1048576).toFixed(1):null,
        audio
      };
    }
  };

  if(perfEnabled){
    setInterval(()=>console.table(globalThis.DruMasterPerfTest.snapshot()),5000);
  }
})();
