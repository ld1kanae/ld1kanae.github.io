"use strict";

(()=>{
  const isTouch=(navigator.maxTouchPoints||0)>0||
    !!globalThis.matchMedia?.("(any-pointer:coarse)")?.matches||
    !!globalThis.matchMedia?.("(pointer:coarse)")?.matches;

  document.documentElement.dataset.dmPerfTest="pass6";

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
    style.dataset.dmPerfPass="6";
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

  if(perfEnabled&&globalThis.DruMasterPerfTicker?.register){
    let lastAudioSample=0;
    globalThis.DruMasterPerfTicker.register("perf-metrics",ts=>{
      if(ts-lastAudioSample<250)return;
      lastAudioSample=ts;
      const audio=globalThis.DruMasterAudioControl?.getStats?.();
      if(audio?.activeVoices>stats.peakActiveVoices)stats.peakActiveVoices=audio.activeVoices;
    });
  }

  globalThis.DruMasterPerfTest={
    version:"20260901-pass6",
    stats,
    snapshot(){
      const elapsed=Math.max(.001,(performance.now()-stats.startedAt)/1000);
      const graph=globalThis.DruMasterPerfChartPass2?.stats||null;
      const core=globalThis.DruMasterPerfChartCorePass3||null;
      const audio=globalThis.DruMasterAudioControl?.getStats?.()||null;
      if(audio?.activeVoices>stats.peakActiveVoices)stats.peakActiveVoices=audio.activeVoices;
      const memory=performance?.memory;
      const ticker=globalThis.DruMasterPerfTicker?.snapshot?.()||null;
      let songSec=null;
      try{if(typeof current==="function"&&typeof running!=="undefined"&&running)songSec=current()}catch{}
      return {
        ...stats,
        maxRenderGapMs:+stats.maxRenderGapMs.toFixed(2),
        longTaskTotalMs:+stats.longTaskTotalMs.toFixed(1),
        maxLongTaskMs:+stats.maxLongTaskMs.toFixed(1),
        elapsedSec:+elapsed.toFixed(2),
        songSec:Number.isFinite(songSec)?+songSec.toFixed(1):null,
        renderRequestRate:+(stats.renderRequests/elapsed).toFixed(1),
        renderRate:+(stats.actualRenders/elapsed).toFixed(1),
        suppressedRenderRate:+(stats.suppressedRenders/elapsed).toFixed(1),
        tickerFrameRate:ticker?.frameRate??null,
        tickerTaskCount:ticker?.taskCount??null,
        tickerTaskErrors:ticker?.taskErrors??null,
        tickerMaxBatchMs:ticker?.maxTaskBatchMs??null,
        hhGraphFrames:graph?.frames??null,
        hhGraphSamples:graph?.samples??null,
        hhGraphSamplesPerFrame:graph?.frames?+(graph.samples/graph.frames).toFixed(1):null,
        noteVisualCacheSize:core?.cacheSize??null,
        noteVisualRequests:core?.stats?.noteVisualRequests??null,
        noteVisualMisses:core?.stats?.noteVisualMisses??null,
        simultaneousOffsetCalls:core?.stats?.simultaneousOffsetCalls??null,
        topologyBuilds:core?.stats?.topologyBuilds??null,
        offsetLookups:core?.stats?.offsetLookups??null,
        activeSlotChecks:core?.stats?.activeSlotChecks??null,
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
    const overlay=document.createElement("div");
    overlay.id="dmPerfOverlay";
    Object.assign(overlay.style,{
      position:"absolute",right:"4px",bottom:"4px",zIndex:"99999",pointerEvents:"none",
      padding:"4px 6px",borderRadius:"4px",background:"rgba(0,0,0,.72)",color:"#dff7ff",
      font:"700 9px/1.35 ui-monospace,SFMono-Regular,Consolas,monospace",whiteSpace:"pre",textAlign:"left"
    });
    const host=document.querySelector("#game")||document.body;
    host.appendChild(overlay);
    const refresh=()=>{
      const s=globalThis.DruMasterPerfTest.snapshot();
      const voices=s.audio?.activeVoices??"-";
      overlay.textContent=[
        `PASS6  song ${s.songSec??"-"}s`,
        `render ${s.renderRate}/s  >50 ${s.frameGapOver50}  max ${s.maxRenderGapMs}ms`,
        `ticker ${s.tickerFrameRate??"-"}/s  tasks ${s.tickerTaskCount??"-"}  max ${s.tickerMaxBatchMs??"-"}ms`,
        `voices ${voices}  peak ${s.peakActiveVoices}`,
        `long ${s.longTasks}  max ${s.maxLongTaskMs}ms`,
        `heap ${s.jsHeapUsedMB??"-"}/${s.jsHeapTotalMB??"-"} MB`,
        `topology ${s.topologyBuilds??"-"}  offset calls ${s.simultaneousOffsetCalls??"-"}`
      ].join("\n");
    };
    refresh();
    setInterval(()=>{refresh();console.table(globalThis.DruMasterPerfTest.snapshot())},1000);
  }
})();
