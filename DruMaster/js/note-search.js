"use strict";

/* Shared O(log n + k) note lookup helpers. Notes are sorted by time/tick, so
   gameplay should never scan the complete song for a local judgement/render. */
globalThis.DruMasterNoteSearch=(()=>{
  function lowerBoundTime(list,time){
    let lo=0,hi=list?.length||0;
    while(lo<hi){
      const mid=(lo+hi)>>>1;
      if(list[mid].time<time)lo=mid+1;else hi=mid;
    }
    return lo;
  }

  function lowerBoundTick(list,tick){
    let lo=0,hi=list?.length||0;
    while(lo<hi){
      const mid=(lo+hi)>>>1;
      if(list[mid].tick<tick)lo=mid+1;else hi=mid;
    }
    return lo;
  }

  function nearest(list,time,maxDelta,predicate){
    if(!Array.isArray(list)||!list.length)return null;
    const start=lowerBoundTime(list,time-maxDelta),limit=time+maxDelta;
    let best=null,bestDelta=maxDelta+1e-9,bestIndex=-1;
    for(let i=start;i<list.length;i++){
      const n=list[i];
      if(n.time>limit)break;
      if(predicate&&!predicate(n,i))continue;
      const delta=Math.abs(n.time-time);
      if(delta<bestDelta){best=n;bestDelta=delta;bestIndex=i}
    }
    return best?{note:best,delta:bestDelta,index:bestIndex}:null;
  }

  function visibleTickRange(list,minTick,maxTick){
    if(!Array.isArray(list)||!list.length)return {start:0,end:0};
    const start=lowerBoundTick(list,minTick),end=lowerBoundTick(list,maxTick+1e-7);
    return {start,end};
  }

  return {lowerBoundTime,lowerBoundTick,nearest,visibleTickRange};
})();
