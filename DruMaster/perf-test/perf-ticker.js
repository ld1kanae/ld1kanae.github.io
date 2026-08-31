"use strict";

(()=>{
  if(globalThis.DruMasterPerfTicker)return;

  const tasks=new Map();
  const perfEnabled=new URLSearchParams(location.search).get("perf")==="1";
  const stats={frames:0,taskCalls:0,taskErrors:0,maxTaskBatchMs:0,startedAt:performance.now()};
  let nextId=1,raf=0;

  function frame(ts){
    stats.frames++;
    const measure=perfEnabled;
    const started=measure?performance.now():0;
    for(const rec of tasks.values()){
      try{rec.fn(ts);stats.taskCalls++;rec.calls++}
      catch(error){
        stats.taskErrors++;rec.errors++;
        if(perfEnabled)console.error(`[DruMasterPerfTicker:${rec.name}]`,error);
      }
    }
    if(measure){
      const duration=performance.now()-started;
      if(duration>stats.maxTaskBatchMs)stats.maxTaskBatchMs=duration;
    }
    raf=requestAnimationFrame(frame);
  }

  globalThis.DruMasterPerfTicker={
    version:"20260901-pass5",
    stats,
    register(name,fn){
      if(typeof fn!=="function")return ()=>{};
      const id=nextId++;
      tasks.set(id,{name:String(name||`task-${id}`),fn,calls:0,errors:0});
      return ()=>tasks.delete(id);
    },
    snapshot(){
      const elapsed=Math.max(.001,(performance.now()-stats.startedAt)/1000);
      return {
        ...stats,
        taskCount:tasks.size,
        frameRate:+(stats.frames/elapsed).toFixed(1),
        maxTaskBatchMs:+stats.maxTaskBatchMs.toFixed(2),
        tasks:[...tasks.values()].map(x=>({name:x.name,calls:x.calls,errors:x.errors}))
      };
    }
  };

  raf=requestAnimationFrame(frame);
})();
