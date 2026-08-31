"use strict";

(()=>{
  const api=globalThis.DruMusterChart;
  if(!api||typeof api.draw!=="function"||typeof api.noteVisual!=="function")return;

  const PPQ=Number(api.PIXELS_PER_QUARTER)||80;
  const DESKTOP_NOTE_WIDTH_SCALE=1.5;
  const visualCache=new Map();
  const originalNoteVisual=api.noteVisual.bind(api);
  const stats={noteVisualRequests:0,noteVisualMisses:0,simultaneousOffsetCalls:0};

  function cachedNoteVisual(type,group,scale=1){
    stats.noteVisualRequests++;
    const key=`${String(type)}\u0000${String(group)}\u0000${Number(scale)||1}`;
    let visual=visualCache.get(key);
    if(visual)return visual;
    visual=originalNoteVisual(type,group,scale);
    visualCache.set(key,visual);
    stats.noteVisualMisses++;
    return visual;
  }

  function laneForGroup(group){return group==="cymbal"?0:group==="hh"?1:group==="drums"?2:3}

  function simultaneousNoteOffsets(notes,start,end,skipHit,groupMap,noteWidthScale,hiddenTypes=null){
    stats.simultaneousOffsetCalls++;
    const buckets=new Map(),offsets=new WeakMap(),gap=0;
    for(let i=start;i<end;i++){
      const note=notes[i];
      if(skipHit&&note.hit||hiddenTypes?.has(note.type))continue;
      const group=groupMap[note.type],lane=laneForGroup(group),key=`${note.tick}|${lane}`;
      const midiNote=Number(note.note),slotKey=Number.isFinite(midiNote)?`midi:${midiNote}`:`type:${note.type}`;
      let bucket=buckets.get(key);
      if(!bucket){bucket=new Map();buckets.set(key,bucket)}
      let slot=bucket.get(slotKey);
      if(!slot){
        slot={width:cachedNoteVisual(note.type,group,noteWidthScale).totalWidth,notes:[],midiNote,type:note.type};
        bucket.set(slotKey,slot);
      }
      slot.notes.push(note);
    }
    for(const bucket of buckets.values()){
      if(bucket.size<2)continue;
      const slots=[...bucket.values()].sort((a,b)=>{
        const aMidi=Number.isFinite(a.midiNote)?a.midiNote:Infinity;
        const bMidi=Number.isFinite(b.midiNote)?b.midiNote:Infinity;
        return aMidi-bMidi||String(a.type).localeCompare(String(b.type));
      });
      let cursor=0;
      for(const slot of slots){
        for(const note of slot.notes)offsets.set(note,cursor);
        cursor+=slot.width+gap;
      }
    }
    return offsets;
  }

  function visibleRange(notes,minTick,maxTick){
    const search=globalThis.DruMasterNoteSearch;
    if(search?.visibleTickRange)return search.visibleTickRange(notes,minTick,maxTick);
    return {start:0,end:notes.length};
  }

  function optimizedDraw({ctx,canvas,notes,currentSec,timing,groupMap,skipHit=true,hiddenTypes=null}){
    const w=canvas.clientWidth,h=canvas.clientHeight;
    const beatNow=api.secondsToBeat(currentSec,timing),division=timing.division||480;
    const judgeX=api.judgementX(w),judgeZoneW=api.judgementZoneWidth(w),kickH=Math.max(16,h*.12),mainH=h-kickH,laneH=mainH/3;
    const labelFont=Math.max(9,laneH*.13),labels=["CYMBAL","HI-HAT / RIDE / OTHER","SNARE / TOMS"];
    const noteWidthScale=api.isMobileLayout()?1:DESKTOP_NOTE_WIDTH_SCALE;

    ctx.clearRect(0,0,w,h);ctx.fillStyle="#030507";ctx.fillRect(0,0,w,h);
    for(let i=0;i<3;i++){
      ctx.fillStyle="#030507";ctx.fillRect(0,laneH*i,w,laneH);
      if(i>0){ctx.strokeStyle="#53677d";ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(0,laneH*i+.5);ctx.lineTo(w,laneH*i+.5);ctx.stroke()}
      ctx.fillStyle="#8b97a6";ctx.font=`700 ${labelFont}px system-ui,sans-serif`;ctx.textAlign="left";ctx.textBaseline="top";ctx.fillText(labels[i],7,laneH*i+6);
    }
    ctx.fillStyle="#030507";ctx.fillRect(0,mainH,w,kickH);
    ctx.strokeStyle="#5b6d82";ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(0,mainH+.5);ctx.lineTo(w,mainH+.5);ctx.stroke();
    ctx.fillStyle="#687483";ctx.font=`700 ${labelFont}px system-ui,sans-serif`;ctx.textAlign="left";ctx.textBaseline="middle";ctx.fillText("KICK · AUTO",7,mainH+kickH/2);
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
    version:"20260901-pass3",
    stats,
    get cacheSize(){return visualCache.size}
  };
})();
