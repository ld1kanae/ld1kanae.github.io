"use strict";

(()=>{
  const api=globalThis.DruMusterChart;
  if(!api||typeof api.draw!=="function"||typeof api.noteVisual!=="function")return;

  const PPQ=Number(api.PIXELS_PER_QUARTER)||80;
  const DESKTOP_NOTE_WIDTH_SCALE=1.5;
  const visualCache=new Map();
  const topologyCache=new WeakMap();
  const originalNoteVisual=api.noteVisual.bind(api);
  const stats={
    noteVisualRequests:0,
    noteVisualMisses:0,
    simultaneousOffsetCalls:0,
    topologyBuilds:0,
    offsetLookups:0,
    activeSlotChecks:0,
    staticBuilds:0,
    staticBlits:0
  };
  let staticCanvas=null,staticCtx=null,staticKey="";

  function cachedNoteVisual(type,group,scale=1){
    stats.noteVisualRequests++;
    const normalizedScale=Number(scale)||1;
    const key=`${String(type)}\u0000${String(group)}\u0000${normalizedScale}`;
    let visual=visualCache.get(key);
    if(visual)return visual;
    visual=originalNoteVisual(type,group,normalizedScale);
    visualCache.set(key,visual);
    stats.noteVisualMisses++;
    return visual;
  }

  function laneForGroup(group){return group==="cymbal"?0:group==="hh"?1:group==="drums"?2:3}

  function sameHiddenTypes(entry,hiddenTypes){
    const count=hiddenTypes?.size||0;
    if(entry.hiddenTypes.length!==count)return false;
    if(!count)return true;
    for(const type of entry.hiddenTypes)if(!hiddenTypes.has(type))return false;
    return true;
  }

  function buildOffsetTopology(notes,groupMap,noteWidthScale,hiddenTypes){
    const hiddenList=hiddenTypes?[...hiddenTypes]:[];
    const buckets=new Map();
    const noteMeta=new WeakMap();

    for(let i=0;i<notes.length;i++){
      const note=notes[i];
      if(hiddenTypes?.has(note.type))continue;
      const group=groupMap[note.type],lane=laneForGroup(group),bucketKey=`${note.tick}|${lane}`;
      const midiNote=Number(note.note),slotKey=Number.isFinite(midiNote)?`midi:${midiNote}`:`type:${note.type}`;
      let bucket=buckets.get(bucketKey);
      if(!bucket){
        bucket={slots:[],slotMap:new Map()};
        buckets.set(bucketKey,bucket);
      }
      let slot=bucket.slotMap.get(slotKey);
      if(!slot){
        slot={
          width:cachedNoteVisual(note.type,group,noteWidthScale).totalWidth,
          entries:[],
          midiNote,
          type:note.type,
          activeEpoch:0,
          active:false
        };
        bucket.slotMap.set(slotKey,slot);
        bucket.slots.push(slot);
      }
      slot.entries.push({note,index:i});
    }

    for(const bucket of buckets.values()){
      bucket.slots.sort((a,b)=>{
        const aMidi=Number.isFinite(a.midiNote)?a.midiNote:Infinity;
        const bMidi=Number.isFinite(b.midiNote)?b.midiNote:Infinity;
        return aMidi-bMidi||String(a.type).localeCompare(String(b.type));
      });
      for(let slotIndex=0;slotIndex<bucket.slots.length;slotIndex++){
        const slot=bucket.slots[slotIndex];
        for(const entry of slot.entries)noteMeta.set(entry.note,{bucket,slotIndex});
      }
      bucket.slotMap=null;
    }

    const topology={
      groupMap,
      scale:Number(noteWidthScale)||1,
      hiddenTypes:hiddenList,
      noteMeta,
      epoch:0,
      start:0,
      end:0,
      skipHit:true,
      view:null
    };

    function slotIsActive(slot){
      stats.activeSlotChecks++;
      if(slot.activeEpoch===topology.epoch)return slot.active;
      let active=false;
      for(const entry of slot.entries){
        if(entry.index<topology.start||entry.index>=topology.end)continue;
        if(topology.skipHit&&entry.note.hit)continue;
        active=true;
        break;
      }
      slot.active=active;
      slot.activeEpoch=topology.epoch;
      return active;
    }

    topology.view={
      get(note){
        stats.offsetLookups++;
        const meta=topology.noteMeta.get(note);
        if(!meta)return undefined;
        let cursor=0;
        for(let i=0;i<meta.slotIndex;i++){
          const slot=meta.bucket.slots[i];
          if(slotIsActive(slot))cursor+=slot.width;
        }
        return cursor||undefined;
      }
    };

    stats.topologyBuilds++;
    return topology;
  }

  function getOffsetTopology(notes,groupMap,noteWidthScale,hiddenTypes){
    let list=topologyCache.get(notes);
    if(!list){list=[];topologyCache.set(notes,list)}
    const scale=Number(noteWidthScale)||1;
    for(const entry of list){
      if(entry.groupMap===groupMap&&entry.scale===scale&&sameHiddenTypes(entry,hiddenTypes))return entry;
    }
    const topology=buildOffsetTopology(notes,groupMap,scale,hiddenTypes);
    list.push(topology);
    return topology;
  }

  function simultaneousNoteOffsets(notes,start,end,skipHit,groupMap,noteWidthScale,hiddenTypes=null){
    stats.simultaneousOffsetCalls++;
    const topology=getOffsetTopology(notes,groupMap,noteWidthScale,hiddenTypes);
    topology.start=start;
    topology.end=end;
    topology.skipHit=!!skipHit;
    topology.epoch++;
    return topology.view;
  }

  function visibleRange(notes,minTick,maxTick){
    const search=globalThis.DruMasterNoteSearch;
    if(search?.visibleTickRange)return search.visibleTickRange(notes,minTick,maxTick);
    return {start:0,end:notes.length};
  }

  function ensureStaticBackground(canvas,w,h,mainH,kickH,laneH,labelFont){
    const dpr=Math.max(1,canvas.clientWidth?canvas.width/canvas.clientWidth:1);
    const bw=Math.max(1,Math.round(w*dpr)),bh=Math.max(1,Math.round(h*dpr));
    const key=`${bw}x${bh}|${w}x${h}|${dpr.toFixed(4)}|${mainH.toFixed(3)}|${laneH.toFixed(3)}|${labelFont.toFixed(3)}`;
    if(staticCanvas&&staticKey===key)return;

    staticCanvas=document.createElement("canvas");
    staticCanvas.width=bw;
    staticCanvas.height=bh;
    staticCtx=staticCanvas.getContext("2d");
    staticCtx.setTransform(dpr,0,0,dpr,0,0);

    const labels=["CYMBAL","HI-HAT / RIDE / OTHER","SNARE / TOMS"];
    staticCtx.fillStyle="#030507";
    staticCtx.fillRect(0,0,w,h);
    for(let i=0;i<3;i++){
      if(i>0){
        staticCtx.strokeStyle="#53677d";
        staticCtx.lineWidth=1.2;
        staticCtx.beginPath();
        staticCtx.moveTo(0,laneH*i+.5);
        staticCtx.lineTo(w,laneH*i+.5);
        staticCtx.stroke();
      }
      staticCtx.fillStyle="#8b97a6";
      staticCtx.font=`700 ${labelFont}px system-ui,sans-serif`;
      staticCtx.textAlign="left";
      staticCtx.textBaseline="top";
      staticCtx.fillText(labels[i],7,laneH*i+6);
    }
    staticCtx.strokeStyle="#5b6d82";
    staticCtx.lineWidth=1.2;
    staticCtx.beginPath();
    staticCtx.moveTo(0,mainH+.5);
    staticCtx.lineTo(w,mainH+.5);
    staticCtx.stroke();
    staticCtx.fillStyle="#687483";
    staticCtx.font=`700 ${labelFont}px system-ui,sans-serif`;
    staticCtx.textAlign="left";
    staticCtx.textBaseline="middle";
    staticCtx.fillText("KICK · AUTO",7,mainH+kickH/2);

    staticKey=key;
    stats.staticBuilds++;
  }

  function optimizedDraw({ctx,canvas,notes,currentSec,timing,groupMap,skipHit=true,hiddenTypes=null}){
    const w=canvas.clientWidth,h=canvas.clientHeight;
    const beatNow=api.secondsToBeat(currentSec,timing),division=timing.division||480;
    const judgeX=api.judgementX(w),judgeZoneW=api.judgementZoneWidth(w),kickH=Math.max(16,h*.12),mainH=h-kickH,laneH=mainH/3;
    const labelFont=Math.max(9,laneH*.13);
    const noteWidthScale=api.isMobileLayout()?1:DESKTOP_NOTE_WIDTH_SCALE;

    ensureStaticBackground(canvas,w,h,mainH,kickH,laneH,labelFont);
    ctx.clearRect(0,0,w,h);
    ctx.drawImage(staticCanvas,0,0,staticCanvas.width,staticCanvas.height,0,0,w,h);
    stats.staticBlits++;

    api.drawMeasureLines(ctx,w,h,judgeX,beatNow,timing,PPQ);
    ctx.fillStyle="#eef6ff10";ctx.fillRect(judgeX-judgeZoneW/2,0,judgeZoneW,h);
    ctx.strokeStyle="#f3f8ff";ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(judgeX,0);ctx.lineTo(judgeX,h);ctx.stroke();

    const minBeat=beatNow-48/PPQ,maxBeat=beatNow+(w+48-judgeX)/PPQ;
    const {start,end}=visibleRange(notes,minBeat*division,maxBeat*division);
    const noteOffsets=simultaneousNoteOffsets(notes,start,end,skipHit,groupMap,noteWidthScale,hiddenTypes);
    for(let i=start;i<end;i++){
      const n=notes[i];
      if(skipHit&&n.hit||hiddenTypes?.has(n.type))continue;
      const x=judgeX+(n.tick/division-beatNow)*PPQ+(noteOffsets.get(n)||0);
      const group=groupMap[n.type],lane=laneForGroup(group),alpha=.48+.52*n.velocity/127,visual=cachedNoteVisual(n.type,group,noteWidthScale);
      ctx.globalAlpha=n.type==="hhPedal"?.24+.18*n.velocity/127:n.type==="kick"?.32+.28*n.velocity/127:alpha;
      ctx.fillStyle=visual.color;
      if(lane<3){
        const barTop=lane*laneH,barH=laneH;
        if(visual.kind==="double"){
          const left=x-visual.totalWidth/2;
          ctx.fillRect(left,barTop,visual.barWidth,barH);
          ctx.fillRect(left+visual.barWidth+visual.gap,barTop,visual.barWidth,barH);
        }else ctx.fillRect(x-visual.totalWidth/2,barTop,visual.barWidth,barH);
      }else ctx.fillRect(x-visual.totalWidth/2,mainH,visual.barWidth,kickH);
    }
    ctx.globalAlpha=1;ctx.textAlign="start";ctx.textBaseline="alphabetic";
  }

  api.noteVisual=cachedNoteVisual;
  api.simultaneousNoteOffsets=simultaneousNoteOffsets;
  api.draw=optimizedDraw;

  globalThis.DruMasterPerfChartCorePass3={
    version:"20260901-pass6",
    stats,
    get cacheSize(){return visualCache.size},
    invalidateStatic(){staticKey="";staticCanvas=null;staticCtx=null}
  };
})();
