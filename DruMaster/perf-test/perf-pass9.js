"use strict";

(()=>{
  const isTouch=(navigator.maxTouchPoints||0)>0||
    !!globalThis.matchMedia?.("(any-pointer:coarse)")?.matches||
    !!globalThis.matchMedia?.("(pointer:coarse)")?.matches;
  const params=new URLSearchParams(location.search);
  const perfEnabled=params.get("perf")==="1";
  const fpsEnabled=perfEnabled||params.get("fps")==="1";

  document.documentElement.dataset.dmPerfTest="pass9";

  const stats={
    renderRequests:0,actualRenders:0,suppressedRenders:0,suppressedKickSchedulerCalls:0,
    frameGapOver20:0,frameGapOver33:0,frameGapOver50:0,maxRenderGapMs:0,
    peakActiveVoices:0,longTasks:0,longTaskTotalMs:0,maxLongTaskMs:0,
    tapEvents:0,inputCalls:0,inputTotalMs:0,inputMaxMs:0,
    playDrumCalls:0,playDrumTotalMs:0,playDrumMaxMs:0,
    startedAt:performance.now(),sessionActive:false
  };

  const fpsBuckets=new Float64Array(5),requestBuckets=new Float64Array(5);
  let fpsBucketCount=0,fpsBucketIndex=0,fpsWindowStartedAt=performance.now(),fpsWindowRenders=0,fpsWindowRequests=0;
  let chartFps1s=0,chartFps5s=0,drawRequestFps1s=0,drawRequestFps5s=0;
  let nextRender=0,lastResult,lastActual=0;

  function resetFpsWindow(now=performance.now()){
    fpsBuckets.fill(0);requestBuckets.fill(0);fpsBucketCount=0;fpsBucketIndex=0;
    fpsWindowStartedAt=now;fpsWindowRenders=0;fpsWindowRequests=0;
    chartFps1s=0;chartFps5s=0;drawRequestFps1s=0;drawRequestFps5s=0;
  }
  function updateFpsWindow(now=performance.now()){
    const elapsed=now-fpsWindowStartedAt;
    if(elapsed<1000)return;
    chartFps1s=fpsWindowRenders*1000/Math.max(1,elapsed);
    drawRequestFps1s=fpsWindowRequests*1000/Math.max(1,elapsed);
    fpsBuckets[fpsBucketIndex]=chartFps1s;
    requestBuckets[fpsBucketIndex]=drawRequestFps1s;
    fpsBucketIndex=(fpsBucketIndex+1)%fpsBuckets.length;
    fpsBucketCount=Math.min(fpsBuckets.length,fpsBucketCount+1);
    let totalFps=0,totalRequests=0;
    for(let i=0;i<fpsBucketCount;i++){totalFps+=fpsBuckets[i];totalRequests+=requestBuckets[i]}
    chartFps5s=totalFps/Math.max(1,fpsBucketCount);
    drawRequestFps5s=totalRequests/Math.max(1,fpsBucketCount);
    fpsWindowStartedAt=now;fpsWindowRenders=0;fpsWindowRequests=0;
  }
  function resetSession(now=performance.now()){
    stats.renderRequests=0;stats.actualRenders=0;stats.suppressedRenders=0;
    stats.frameGapOver20=0;stats.frameGapOver33=0;stats.frameGapOver50=0;stats.maxRenderGapMs=0;
    stats.peakActiveVoices=0;stats.longTasks=0;stats.longTaskTotalMs=0;stats.maxLongTaskMs=0;
    stats.tapEvents=0;stats.inputCalls=0;stats.inputTotalMs=0;stats.inputMaxMs=0;
    stats.playDrumCalls=0;stats.playDrumTotalMs=0;stats.playDrumMaxMs=0;
    stats.startedAt=now;stats.sessionActive=true;
    lastActual=0;nextRender=0;
    resetFpsWindow(now);
    globalThis.DruMasterPerfTicker?.resetMetrics?.(now);
  }

  if(isTouch&&typeof draw==="function"){
    const rawDraw=draw,FRAME_MS=1000/60;
    draw=function(...args){
      stats.renderRequests++;fpsWindowRequests++;
      const now=performance.now();
      updateFpsWindow(now);
      if(nextRender&&now+.75<nextRender){stats.suppressedRenders++;return lastResult}
      if(!nextRender||now-nextRender>100)nextRender=now+FRAME_MS;else nextRender+=FRAME_MS;
      if(lastActual){
        const gap=now-lastActual;
        if(gap<500){
          if(gap>20)stats.frameGapOver20++;
          if(gap>33.34)stats.frameGapOver33++;
          if(gap>50)stats.frameGapOver50++;
          if(gap>stats.maxRenderGapMs)stats.maxRenderGapMs=gap;
        }
      }
      lastActual=now;stats.actualRenders++;fpsWindowRenders++;
      lastResult=rawDraw.apply(this,args);return lastResult;
    };
  }

  if(typeof scheduleKickAudio==="function")scheduleKickAudio=function(){stats.suppressedKickSchedulerCalls++};

  if(isTouch){
    const style=document.createElement("style");
    style.dataset.dmPerfPass="9";
    style.textContent=`@media (hover:none) and (pointer:coarse) and (max-width:900px){.game #chartWrap{-webkit-backdrop-filter:none!important;backdrop-filter:none!important}#hhOpenGaugeHandle{will-change:transform!important}}`;
    document.head.appendChild(style);
  }

  if(perfEnabled){
    addEventListener("pointerdown",e=>{
      const target=e.target;
      if(target instanceof Element&&target.closest("#game")&&stats.sessionActive)stats.tapEvents++;
    },true);
    if(typeof playDrum==="function"){
      const rawPlayDrum=playDrum;
      playDrum=function(...args){
        const started=performance.now();
        try{return rawPlayDrum.apply(this,args)}finally{
          const d=performance.now()-started;stats.playDrumCalls++;stats.playDrumTotalMs+=d;if(d>stats.playDrumMaxMs)stats.playDrumMaxMs=d;
        }
      };
    }
    if(typeof input==="function"){
      const rawInput=input;
      input=function(...args){
        const started=performance.now();
        try{return rawInput.apply(this,args)}finally{
          const d=performance.now()-started;stats.inputCalls++;stats.inputTotalMs+=d;if(d>stats.inputMaxMs)stats.inputMaxMs=d;
        }
      };
    }
  }

  if(perfEnabled&&typeof PerformanceObserver==="function"){
    try{
      const observer=new PerformanceObserver(list=>{
        if(!stats.sessionActive)return;
        for(const entry of list.getEntries()){
          if(entry.startTime<stats.startedAt)continue;
          const duration=Number(entry.duration)||0;
          stats.longTasks++;stats.longTaskTotalMs+=duration;stats.maxLongTaskMs=Math.max(stats.maxLongTaskMs,duration);
        }
      });
      observer.observe({entryTypes:["longtask"]});
    }catch{}
  }

  const ticker=globalThis.DruMasterPerfTicker;
  if(ticker?.register){
    let wasRunning=false,lastAudioSample=0;
    ticker.register("perf-session",ts=>{
      let isRunning=false;
      try{isRunning=typeof running!=="undefined"&&!!running}catch{}
      if(isRunning&&!wasRunning)resetSession(ts);
      wasRunning=isRunning;updateFpsWindow(ts);
      if(perfEnabled&&isRunning&&ts-lastAudioSample>=250){
        lastAudioSample=ts;
        const audio=globalThis.DruMasterAudioControl?.getStats?.();
        const active=audio?.activeVoices||0;if(active>stats.peakActiveVoices)stats.peakActiveVoices=active;
      }
    });
  }

  globalThis.DruMasterPerfTest={
    version:"20260901-pass9",stats,resetSession,
    snapshot(){
      const elapsed=Math.max(.001,(performance.now()-stats.startedAt)/1000);
      const graph=globalThis.DruMasterPerfChartPass2?.stats||null;
      const core=globalThis.DruMasterPerfChartCorePass3||null;
      const judgement=globalThis.DruMasterJudgementPerf?.stats||null;
      const audio=globalThis.DruMasterAudioControl?.getStats?.()||null;
      const active=audio?.activeVoices||0;if(active>stats.peakActiveVoices)stats.peakActiveVoices=active;
      const memory=performance?.memory,tickerSnapshot=ticker?.snapshot?.()||null,animations=globalThis.DruMasterPerfAnimationPool?.stats||null;
      let songSec=null;try{if(typeof current==="function"&&typeof running!=="undefined"&&running)songSec=current()}catch{}
      return {
        ...stats,
        inputAvgMs:stats.inputCalls?+(stats.inputTotalMs/stats.inputCalls).toFixed(3):0,inputMaxMs:+stats.inputMaxMs.toFixed(3),
        playDrumAvgMs:stats.playDrumCalls?+(stats.playDrumTotalMs/stats.playDrumCalls).toFixed(3):0,playDrumMaxMs:+stats.playDrumMaxMs.toFixed(3),
        maxRenderGapMs:+stats.maxRenderGapMs.toFixed(2),longTaskTotalMs:+stats.longTaskTotalMs.toFixed(1),maxLongTaskMs:+stats.maxLongTaskMs.toFixed(1),
        elapsedSec:+elapsed.toFixed(2),songSec:Number.isFinite(songSec)?+songSec.toFixed(1):null,
        chartFps1s:+chartFps1s.toFixed(1),chartFps5s:+chartFps5s.toFixed(1),drawRequestFps1s:+drawRequestFps1s.toFixed(1),drawRequestFps5s:+drawRequestFps5s.toFixed(1),
        displayHz1s:tickerSnapshot?.frameRate1s??null,displayHz5s:tickerSnapshot?.frameRate5s??null,renderRate:+(stats.actualRenders/elapsed).toFixed(1),
        tickerTaskCount:tickerSnapshot?.taskCount??null,tickerTaskErrors:tickerSnapshot?.taskErrors??null,tickerMaxBatchMs:tickerSnapshot?.maxTaskBatchMs??null,
        animationCreated:animations?.created??null,animationReused:animations?.reused??null,animationRecreated:animations?.recreated??null,
        judgementGeometryBuilds:judgement?.geometryBuilds??null,judgementMeasureTextCalls:judgement?.measureTextCalls??null,
        judgementFxPlacements:judgement?.fxPlacements??null,judgementGlowStyleWrites:judgement?.glowStyleWrites??null,judgementGlowStyleSkips:judgement?.glowStyleSkips??null,
        hhGraphFrames:graph?.frames??null,hhGraphSamples:graph?.samples??null,hhGraphSamplesPerFrame:graph?.frames?+(graph.samples/graph.frames).toFixed(1):null,
        noteVisualCacheSize:core?.cacheSize??null,noteVisualRequests:core?.stats?.noteVisualRequests??null,noteVisualMisses:core?.stats?.noteVisualMisses??null,
        simultaneousOffsetCalls:core?.stats?.simultaneousOffsetCalls??null,topologyBuilds:core?.stats?.topologyBuilds??null,offsetLookups:core?.stats?.offsetLookups??null,
        activeSlotChecks:core?.stats?.activeSlotChecks??null,staticBackgroundBuilds:core?.stats?.staticBuilds??null,staticBackgroundBlits:core?.stats?.staticBlits??null,
        canvasDpr:globalThis.DruMasterPerfCanvasPass4?.dpr??(canvas?.clientWidth?canvas.width/canvas.clientWidth:null),
        jsHeapUsedMB:memory?.usedJSHeapSize?+(memory.usedJSHeapSize/1048576).toFixed(1):null,jsHeapTotalMB:memory?.totalJSHeapSize?+(memory.totalJSHeapSize/1048576).toFixed(1):null,
        audio
      };
    }
  };

  if(fpsEnabled){
    const overlay=document.createElement("div");overlay.id="dmPerfOverlay";
    Object.assign(overlay.style,{position:"absolute",right:"4px",bottom:"4px",zIndex:"99999",pointerEvents:"none",padding:"4px 6px",borderRadius:"4px",background:"rgba(0,0,0,.72)",color:"#dff7ff",font:"700 9px/1.35 ui-monospace,SFMono-Regular,Consolas,monospace",whiteSpace:"pre",textAlign:"left"});
    (document.querySelector("#game")||document.body).appendChild(overlay);
    const refresh=()=>{
      const s=globalThis.DruMasterPerfTest.snapshot();
      if(!perfEnabled){
        overlay.textContent=[`FPS PASS9  song ${s.songSec??"-"}s`,`display ${s.displayHz1s??"-"} Hz  (5s ${s.displayHz5s??"-"})`,`chart   ${s.chartFps1s} fps (5s ${s.chartFps5s})`,`request ${s.drawRequestFps1s}/s`,`>50ms ${s.frameGapOver50}  max ${s.maxRenderGapMs}ms`].join("\n");
        return;
      }
      const a=s.audio||{};
      overlay.textContent=[
        `PASS9  song ${s.songSec??"-"}s  taps ${s.tapEvents}`,
        `display ${s.displayHz1s??"-"}Hz  chart ${s.chartFps1s}fps (5s ${s.chartFps5s})`,
        `request ${s.drawRequestFps1s}/s  >50 ${s.frameGapOver50}  max ${s.maxRenderGapMs}ms`,
        `input avg/max ${s.inputAvgMs}/${s.inputMaxMs}ms`,
        `audio avg/max ${s.playDrumAvgMs}/${s.playDrumMaxMs}ms`,
        `voices ${a.activeVoices??"-"} peak ${a.peakActiveVoices??s.peakActiveVoices}  gainPool ${a.pooledGainNodes??"-"}`,
        `sources ${a.totalSourcesCreated??"-"} ended ${a.totalVoicesEnded??"-"}`,
        `judge geom ${s.judgementGeometryBuilds??"-"} measure ${s.judgementMeasureTextCalls??"-"}`,
        `judge style ${s.judgementGlowStyleWrites??"-"} skip ${s.judgementGlowStyleSkips??"-"}`,
        `long ${s.longTasks} max ${s.maxLongTaskMs}ms  heap ${s.jsHeapUsedMB??"-"}/${s.jsHeapTotalMB??"-"}MB`,
        `anim new ${s.animationCreated??"-"} reuse ${s.animationReused??"-"}`
      ].join("\n");
    };
    let lastRefresh=0;
    if(ticker?.register)ticker.register("perf-overlay",ts=>{if(ts-lastRefresh<500)return;lastRefresh=ts;refresh();if(perfEnabled)console.table(globalThis.DruMasterPerfTest.snapshot())});
    else setInterval(refresh,500);
    refresh();
  }
})();
