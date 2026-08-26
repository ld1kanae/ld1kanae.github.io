"use strict";

// Production adapter for the shared chart engine. Preview uses the same engine/file.
let beatTiming={division:480,segments:[{tick:0,sec:0,us:500000}]};
const timingReady=fetch(ASSET.midi,{cache:"force-cache"})
  .then(r=>r.ok?r.arrayBuffer():Promise.reject())
  .then(ab=>{beatTiming=DruMusterChart.parseTempoTiming(ab)})
  .catch(()=>{});

globalThis.DruMasterChartTimingReady=timingReady;

draw=function(){
  DruMusterChart.draw({
    ctx,
    canvas,
    notes,
    currentSec:current(),
    timing:beatTiming,
    groupMap:GROUP,
    skipHit:true
  });
};
