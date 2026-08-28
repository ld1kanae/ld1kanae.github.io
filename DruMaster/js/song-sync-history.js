"use strict";

(()=>{
  const HISTORY_LIMIT=5;
  const $=id=>document.getElementById(id);
  let undoStack=[],redoStack=[],currentState=null,restoring=false,dragStartState=null,ready=false;

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
    audio.title="msを直接入力できます（0.1ms単位）";

    const panel=audio.closest(".panel"),note=panel?.querySelector(".note");
    if(note&&!note.dataset.directInputNote){
      note.textContent=`数値欄は直接入力できます。${note.textContent}`;
      note.dataset.directInputNote="1";
    }

    const row=document.createElement("div");
    row.className="row dm-history-row";
    row.style.marginTop="8px";
    row.innerHTML='<button id="historyUndo" type="button" disabled>↶ 元に戻す</button><button id="historyRedo" type="button" disabled>↷ やり直す</button><span id="historyStatus" class="note" style="margin:0">戻る 0/5 · やり直し 0</span>';
    if(note)panel.insertBefore(row,note);else panel?.appendChild(row);

    $("historyUndo").addEventListener("click",undo);
    $("historyRedo").addEventListener("click",redo);
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
