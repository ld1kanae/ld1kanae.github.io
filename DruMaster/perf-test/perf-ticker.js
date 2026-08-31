"use strict";

(()=>{
  if(globalThis.DruMasterPerfTicker)return;

  const tasks=new Map();
  const params=new URLSearchParams(location.search);
  const perfEnabled=params.get("perf")==="1";
  const stats={frames:0,taskCalls:0,taskErrors:0,maxTaskBatchMs:0,startedAt:performance.now()};
  const hzBuckets=new Float64Array(5);
  let hzBucketCount=0,hzBucketIndex=0,windowStartedAt=performance.now(),windowFrames=0,lastHz=0,nextId=1,raf=0;

  function resetRateWindow(ts=performance.now()){
    hzBuckets.fill(0);hzBucketCount=0;hzBucketIndex=0;
    windowStartedAt=ts;windowFrames=0;lastHz=0;
  }

  function recordFrameRate(ts){
    windowFrames++;
    const elapsed=ts-windowStartedAt;
    if(elapsed<1000)return;
    lastHz=windowFrames*1000/Math.max(1,elapsed);
    hzBuckets[hzBucketIndex]=lastHz;
    hzBucketIndex=(hzBucketIndex+1)%hzBuckets.length;
    hzBucketCount=Math.min(hzBuckets.length,hzBucketCount+1);
    windowStartedAt=ts;windowFrames=0;
  }

  function averageHz(){
    if(!hzBucketCount)return lastHz;
    let total=0;
    for(let i=0;i<hzBucketCount;i++)total+=hzBuckets[i];
    return total/hzBucketCount;
  }

  function frame(ts){
    stats.frames++;
    recordFrameRate(ts);
    const started=perfEnabled?performance.now():0;
    for(const rec of tasks.values()){
      try{rec.fn(ts);stats.taskCalls++;rec.calls++}
      catch(error){
        stats.taskErrors++;rec.errors++;
        if(perfEnabled)console.error(`[DruMasterPerfTicker:${rec.name}]`,error);
      }
    }
    if(perfEnabled){
      const duration=performance.now()-started;
      if(duration>stats.maxTaskBatchMs)stats.maxTaskBatchMs=duration;
    }
    raf=requestAnimationFrame(frame);
  }

  globalThis.DruMasterPerfTicker={
    version:"20260901-pass7",
    stats,
    register(name,fn){
      if(typeof fn!=="function")return ()=>{};
      const id=nextId++;
      tasks.set(id,{name:String(name||`task-${id}`),fn,calls:0,errors:0});
      return ()=>tasks.delete(id);
    },
    resetMetrics(ts=performance.now()){
      stats.frames=0;stats.taskCalls=0;stats.taskErrors=0;stats.maxTaskBatchMs=0;stats.startedAt=ts;
      for(const rec of tasks.values()){rec.calls=0;rec.errors=0}
      resetRateWindow(ts);
    },
    snapshot(){
      const elapsed=Math.max(.001,(performance.now()-stats.startedAt)/1000);
      return {
        ...stats,
        taskCount:tasks.size,
        frameRate:+(stats.frames/elapsed).toFixed(1),
        frameRate1s:+lastHz.toFixed(1),
        frameRate5s:+averageHz().toFixed(1),
        maxTaskBatchMs:+stats.maxTaskBatchMs.toFixed(2),
        tasks:[...tasks.values()].map(x=>({name:x.name,calls:x.calls,errors:x.errors}))
      };
    }
  };

  raf=requestAnimationFrame(frame);
})();
