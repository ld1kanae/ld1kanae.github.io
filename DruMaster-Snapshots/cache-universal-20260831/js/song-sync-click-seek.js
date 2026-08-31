"use strict";

(()=>{
  const canvas=document.getElementById("canvas"),pause=document.getElementById("stop");
  if(pause)pause.textContent="Ⅱ 一時停止";

  const hint=document.querySelector(".timeline-head small");
  if(hint)hint.textContent="クリック＝シーク / 上段ドラッグ＝音源オフセット";
  if(!canvas)return;

  let press=null;
  const MOVE_THRESHOLD=5;

  canvas.addEventListener("pointerdown",e=>{
    if(!e.isTrusted||e.button!==0)return;
    const r=canvas.getBoundingClientRect();
    press={
      pointerId:e.pointerId,
      x:e.clientX,
      y:e.clientY,
      upper:(e.clientY-r.top)<r.height*.53,
      moved:false
    };
  });

  canvas.addEventListener("pointermove",e=>{
    if(!press||e.pointerId!==press.pointerId)return;
    if(Math.hypot(e.clientX-press.x,e.clientY-press.y)>MOVE_THRESHOLD)press.moved=true;
  });

  canvas.addEventListener("pointerup",e=>{
    if(!press||e.pointerId!==press.pointerId)return;
    const p=press;press=null;
    if(!p.upper||p.moved)return;

    /* The base editor already has the canonical seek implementation in the
       lower half. Re-dispatch the same X coordinate into that branch so the
       playhead, time readout and playback cursor stay perfectly in sync. */
    const r=canvas.getBoundingClientRect();
    canvas.dispatchEvent(new PointerEvent("pointerdown",{
      bubbles:true,
      cancelable:true,
      pointerId:e.pointerId,
      pointerType:e.pointerType||"mouse",
      isPrimary:true,
      button:0,
      buttons:1,
      clientX:e.clientX,
      clientY:r.top+r.height*.75
    }));
  });

  canvas.addEventListener("pointercancel",()=>{press=null});
})();
