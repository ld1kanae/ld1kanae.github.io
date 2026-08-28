"use strict";

(()=>{
  const HISTORY_LIMIT=5;
  const $=id=>document.getElementById(id);
  let undoStack=[],redoStack=[],currentState=null,restoring=false,dragStartState=null,ready=false;
  let audioWheelStartState=null,audioWheelCommitTimer=0;

  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const same=(a,b)=>!!a&&!!b&&Math.abs(a.audioMs-b.audioMs)<.0001&&a.midiMeasure===b.midiMeasure;
  const readMidiMeasure=()=>{
    const text=$("midiRead")?.textContent||"0";
    const m=text.match(/[+-]?\d+/);
    return m?Number(m[0]):0;
  };
  const readState=()=>({
    audioMs:Number($("audioOffset")?.value||0),
    midiMeasure:readMidiMeasure()
  });

  function updateButtons(){
    const undo=$("historyUndo"),redo=$("historyRedo"),status=$("historyStatus");
    if(undo)undo.disabled=!undoStack.length;
    if(redo)redo.disabled=!redoStack.length;
    if(status)status.textContent=`戻る ${undoStack.length}/${HISTORY_LIMIT} · やり直し ${redoStack.length}`;
  }

  function commit(next=readState()){
    if(restoring||!currentState)return;
    if(same(next,currentState))return;
    undoStack.push({...currentState});
    if(undoStack.length>HISTORY_LIMIT)undoStack.shift();
    currentState={...next};
    redoStack=[];
    updateButtons();
  }

  function applyState(state){
    if(!state)return;
    restoring=true;
    try{
      const audio=$("audioOffset");
      if(audio){
        audio.value=Number(state.audioMs).toFixed(1);
        audio.dispatchEvent(new Event("change",{bubbles:true}));
      }
      let now=readMidiMeasure(),guard=0;
      while(now!==state.midiMeasure&&guard++<130){
        if(now<state.midiMeasure)$("midiNext")?.click();
        else $("midiPrev")?.click();
        now=readMidiMeasure();
      }
      currentState={audioMs:Number(audio?.value||state.audioMs),midiMeasure:readMidiMeasure()};
    }finally{
      restoring=false;
      updateButtons();
    }
  }

  function undo(){
    if(!undoStack.length||!currentState)return;
    const previous=undoStack.pop();
    redoStack.push({...currentState});
    if(redoStack.length>HISTORY_LIMIT)redoStack.shift();
    applyState(previous);
  }

  function redo(){
    if(!redoStack.length||!currentState)return;
    const next=redoStack.pop();
    undoStack.push({...currentState});
    if(undoStack.length>HISTORY_LIMIT)undoStack.shift();
    applyState(next);
  }

  function installUi(){
    const audio=$("audioOffset");
    if(!audio||$("historyUndo"))return;
    audio.inputMode="decimal";
    audio.setAttribute("aria-label","Audio offset milliseconds");
    audio.title="0.1ms単位で直接入力できます。クリックしてフォーカス後、ホイールで±0.1ms調整できます。＋＝音源を前へ、−＝音源を後ろへ。";

    const panel=audio.closest(".panel"),note=panel?.querySelector(".note");
    if(note)note.style.display="none";

    const row=document.createElement("div");
    row.className="row dm-history-row";
    row.style.marginTop="8px";
    row.innerHTML='<button id="historyUndo" type="button" disabled>↶ 元に戻す</button><button id="historyRedo" type="button" disabled>↷ やり直す</button><span id="historyStatus" class="note" style="margin:0">戻る 0/5 · やり直し 0</span>';
    if(note)panel.insertBefore(row,note);else panel?.appendChild(row);

    $("historyUndo").title="元に戻す · Ctrl＋Z";
    $("historyRedo").title="やり直す · Ctrl＋Y / Ctrl＋Shift＋Z";
    $("historyUndo").addEventListener("click",undo);
    $("historyRedo").addEventListener("click",redo);

    document.querySelectorAll("[data-audio]").forEach(el=>el.title="音源オフセットを微調整します。＋＝前へ、−＝後ろへ。");
    if($("audioReset"))$("audioReset").title="音源オフセットを0msへ戻します。";
    if($("midiPrev"))$("midiPrev").title="MIDI全体を1小節前へ移動します。";
    if($("midiNext"))$("midiNext").title="MIDI全体を1小節後ろへ移動します。";
    if($("midiReset"))$("midiReset").title="MIDIの小節オフセットを0へ戻します。";
    if($("canvas"))$("canvas").title="上段ドラッグ：音源オフセット / 下段クリック：シーク / ホイール：前後移動 / Ctrl＋ホイール：拡大・縮小";
    if($("zoom"))$("zoom").title="波形タイムラインの拡大率。波形上ではCtrl＋ホイールでも変更できます。";
    if($("scroll"))$("scroll").title="波形タイムラインの表示位置。波形上ではホイールでも前後移動できます。";

    const help=document.querySelector(".timeline-head small");
    if(help)help.style.display="none";
  }

  function timelineMetrics(){
    const canvas=$("canvas"),zoom=$("zoom"),scrollOut=$("scrollOut"),durationNode=$("duration");
    if(!canvas||!zoom)return null;
    const rect=canvas.getBoundingClientRect(),px=Math.max(1,Number(zoom.value)||260),duration=Math.max(0,parseFloat(durationNode?.textContent)||0),start=Math.max(0,parseFloat(scrollOut?.textContent)||0),visible=rect.width/px,maxStart=Math.max(0,duration-visible);
    return {canvas,zoom,rect,px,duration,start,visible,maxStart};
  }

  function setTimelineStart(start,pxOverride=null){
    const m=timelineMetrics(),scroll=$("scroll");
    if(!m||!scroll)return;
    const px=pxOverride||m.px,visible=m.rect.width/px,maxStart=Math.max(0,m.duration-visible),next=clamp(start,0,maxStart);
    scroll.value=maxStart?String(next/maxStart*1000):"0";
    scroll.dispatchEvent(new Event("input",{bubbles:true}));
  }

  function installWheelNavigation(canvas){
    canvas.addEventListener("wheel",e=>{
      const m=timelineMetrics();
      if(!m||m.duration<=0)return;
      e.preventDefault();
      e.stopPropagation();

      const raw=Math.abs(e.deltaY)>=Math.abs(e.deltaX)?e.deltaY:e.deltaX;
      const unit=e.deltaMode===1?16:e.deltaMode===2?m.rect.width:1;
      const wheelPixels=raw*unit;

      if(e.ctrlKey||e.metaKey){
        const oldPx=m.px,minPx=Number(m.zoom.min)||80,maxPx=Number(m.zoom.max)||3000;
        const factor=Math.exp(-wheelPixels*.0018),newPx=clamp(oldPx*factor,minPx,maxPx);
        if(Math.abs(newPx-oldPx)<.01)return;

        const pointerRatio=clamp((e.clientX-m.rect.left)/Math.max(1,m.rect.width),0,1);
        const anchorTime=m.start+pointerRatio*m.visible;
        m.zoom.value=String(newPx);
        m.zoom.dispatchEvent(new Event("input",{bubbles:true}));
        const newVisible=m.rect.width/newPx;
        setTimelineStart(anchorTime-pointerRatio*newVisible,newPx);
        return;
      }

      const deltaSec=wheelPixels/m.px;
      setTimelineStart(m.start+deltaSec);
    },{passive:false});
  }

  function flushAudioWheelHistory(){
    clearTimeout(audioWheelCommitTimer);
    audioWheelCommitTimer=0;
    if(!audioWheelStartState)return;
    const final=readState();
    if(!same(final,audioWheelStartState)){
      currentState={...audioWheelStartState};
      commit(final);
    }
    audioWheelStartState=null;
  }

  function installAudioWheel(audio){
    audio.addEventListener("wheel",e=>{
      if(document.activeElement!==audio||restoring)return;
      e.preventDefault();
      e.stopPropagation();

      if(!audioWheelStartState)audioWheelStartState={...currentState};
      const direction=e.deltaY<0?1:-1;
      const next=clamp((Number(audio.value)||0)+direction*.1,-500,500);
      if(Math.abs(next-(Number(audio.value)||0))<.0001)return;

      audio.value=next.toFixed(1);
      restoring=true;
      try{audio.dispatchEvent(new Event("change",{bubbles:true}))}
      finally{restoring=false}

      clearTimeout(audioWheelCommitTimer);
      audioWheelCommitTimer=setTimeout(flushAudioWheelHistory,180);
    },{passive:false});
    audio.addEventListener("blur",flushAudioWheelHistory);
  }

  function installTracking(){
    if(ready)return;
    ready=true;
    installUi();
    currentState=readState();
    updateButtons();

    const audio=$("audioOffset");
    audio?.addEventListener("change",()=>commit());
    audio?.addEventListener("keydown",e=>{
      if(e.key==="Enter"){
        e.preventDefault();
        audio.blur();
      }
    });
    if(audio)installAudioWheel(audio);

    document.querySelectorAll("[data-audio],#audioReset,#midiPrev,#midiNext,#midiReset").forEach(el=>{
      el.addEventListener("click",()=>{
        if(!restoring)queueMicrotask(()=>commit());
      });
    });

    const canvas=$("canvas");
    canvas?.addEventListener("pointerdown",e=>{
      if(restoring)return;
      const r=canvas.getBoundingClientRect();
      if(e.clientY-r.top<r.height*.53)dragStartState=readState();
      else dragStartState=null;
    });
    const finishDrag=()=>{
      if(!dragStartState||restoring)return;
      const final=readState();
      if(!same(final,dragStartState)){
        currentState={...dragStartState};
        commit(final);
      }
      dragStartState=null;
    };
    canvas?.addEventListener("pointerup",finishDrag);
    canvas?.addEventListener("pointercancel",finishDrag);
    if(canvas)installWheelNavigation(canvas);

    addEventListener("keydown",e=>{
      if(!(e.ctrlKey||e.metaKey)||e.altKey)return;
      if(e.target?.id==="token")return;
      const key=e.key.toLowerCase();
      if(key==="z"){
        e.preventDefault();
        if(e.shiftKey)redo();else undo();
      }else if(key==="y"){
        e.preventDefault();
        redo();
      }
    });
  }

  const timer=setInterval(()=>{
    const status=$("status")?.textContent||"";
    if($("audioOffset")&&$("midiRead")&&(status.includes("調整可能")||!$("source")?.disabled)){
      clearInterval(timer);
      installTracking();
    }
  },80);
  setTimeout(()=>{if(!ready&&$("audioOffset")){clearInterval(timer);installTracking()}},5000);
})();
