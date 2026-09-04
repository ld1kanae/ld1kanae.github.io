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

  /* Like nearest(), but each candidate owns only the interval between the
     midpoints to its adjacent notes in the same judgement family. This keeps
     dense rolls/flams from stealing the following note after the previous one
     has already been hit, while preserving the existing +/- judgement windows. */
  function nearestOwned(list,time,maxDelta,eligiblePredicate,neighborPredicate=eligiblePredicate){
    const match=nearest(list,time,maxDelta,eligiblePredicate);
    if(!match)return null;
    const i=match.index,n=match.note;
    let prev=null,next=null;
    for(let j=i-1;j>=0;j--){
      const candidate=list[j];
      if(!neighborPredicate||neighborPredicate(candidate,j)){prev=candidate;break}
    }
    for(let j=i+1;j<list.length;j++){
      const candidate=list[j];
      if(!neighborPredicate||neighborPredicate(candidate,j)){next=candidate;break}
    }
    const left=prev?(prev.time+n.time)/2:-Infinity;
    const right=next?(n.time+next.time)/2:Infinity;
    /* Exact midpoint belongs to the earlier note, matching nearest() tie order. */
    if(time<=left||time>right)return null;
    return {...match,left,right};
  }

  function visibleTickRange(list,minTick,maxTick){
    if(!Array.isArray(list)||!list.length)return {start:0,end:0};
    const start=lowerBoundTick(list,minTick),end=lowerBoundTick(list,maxTick+1e-7);
    return {start,end};
  }

  return {lowerBoundTime,lowerBoundTick,nearest,nearestOwned,visibleTickRange};
})();
