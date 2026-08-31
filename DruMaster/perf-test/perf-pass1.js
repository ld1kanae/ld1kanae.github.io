"use strict";

(()=>{
  const isTouch=(navigator.maxTouchPoints||0)>0||
    !!globalThis.matchMedia?.("(any-pointer:coarse)")?.matches||
    !!globalThis.matchMedia?.("(pointer:coarse)")?.matches;

  document.documentElement.dataset.dmPerfTest="pass1";

  const stats={
    renderRequests:0,
    actualRenders:0,
    suppressedRenders:0,
    suppressedKickSchedulerCalls:0,
    startedAt:performance.now()
  };

  /* Performance pass 1 / high-safety change:
     keep gameplay/audio/event clocks at native rAF cadence, but do not repaint
     the heavy chart faster than 60 fps on 90/120 Hz touch displays. */
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

  /* game-chart.js already registered the original scheduleKickAudio function
     with setInterval(...,25). Its rAF wrapper calls the global binding again.
     Replacing only the later binding with a no-op leaves the 25 ms lookahead
     scheduler intact while removing the duplicate per-frame invocation. */
  if(typeof scheduleKickAudio==="function"){
    scheduleKickAudio=function(){stats.suppressedKickSchedulerCalls++};
  }

  /* No visual benefit at blur(0)/saturate(100%); make the mobile compositing
     path explicit and cheap in the test environment only. */
  if(isTouch){
    const style=document.createElement("style");
    style.dataset.dmPerfPass="1";
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
    version:"20260901-pass1",
    stats,
    snapshot(){
      const elapsed=Math.max(.001,(performance.now()-stats.startedAt)/1000);
      return {
        ...stats,
        elapsedSec:+elapsed.toFixed(2),
        renderRequestRate:+(stats.renderRequests/elapsed).toFixed(1),
        renderRate:+(stats.actualRenders/elapsed).toFixed(1),
        suppressedRenderRate:+(stats.suppressedRenders/elapsed).toFixed(1),
        audio:globalThis.DruMasterAudioControl?.getStats?.()||null
      };
    }
  };

  if(new URLSearchParams(location.search).get("perf")==="1"){
    setInterval(()=>console.table(globalThis.DruMasterPerfTest.snapshot()),5000);
  }
})();
