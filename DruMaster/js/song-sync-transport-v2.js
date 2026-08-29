"use strict";

(()=>{
  const $=id=>document.getElementById(id),canvas=$("canvas"),play=$("play"),pause=$("stop");
  if(!canvas||!play||!pause)return;

  pause.textContent="Ⅱ 一時停止";
  const hint=document.querySelector(".timeline-head small");
  if(hint)hint.textContent="クリック＝シーク / 上段ドラッグ＝音源オフセット";

  const style=document.createElement("style");
  style.id="dmTimingTransportV2Style";
  style.textContent=`
    .dm-timing-seek{display:flex;align-items:center;gap:9px;width:100%;margin-top:9px;padding:5px 9px;border:1px solid rgba(100,120,139,.33);border-radius:999px;background:#06101ac2}
    .dm-timing-seek input{flex:1;min-width:0}
    .dm-timing-seek-time{min-width:82px;text-align:right;color:#b9c7d7;font:800 9px/1 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:nowrap}
  `;
  document.head.appendChild(style);

  const firstRow=pause.closest(".row");
  const seekWrap=document.createElement("div");
  seekWrap.className="dm-timing-seek";
  seekWrap.innerHTML='<input id="timingSeek" type="range" min="0" max="1" step="0.01" value="0" disabled aria-label="再生位置"><span id="timingSeekTime" class="dm-timing-seek-time">0:00 / 0:00</span>';
  firstRow?.insertAdjacentElement("afterend",seekWrap);
  const seek=$("timingSeek"),seekTime=$("timingSeekTime"),zoom=$("zoom"),scroll=$("scroll"),scrollOut=$("scrollOut"),durationNode=$("duration"),timeNode=$("time");

  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const format=s=>{s=Math.max(0,Math.floor(Number(s)||0));return `${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`};
  const parseClock=text=>{const m=String(text||"").match(/(\d+):(\d+)\.(\d+)/);return m?Number(m[1])*60+Number(m[2])+Number(`0.${m[3]}`):0};
  const getDuration=()=>{const v=parseFloat(durationNode?.textContent||"");return Number.isFinite(v)&&v>0?v:0};
  const getViewStart=()=>{const v=parseFloat(scrollOut?.textContent||"");return Number.isFinite(v)?v:0};
  const getPx=()=>Math.max(1,Number(zoom?.value)||260);
  let transportPlaying=false,resumeAfterSeek=false,seeking=false,press=null;

  function syncSeek(){
    const d=getDuration(),t=parseClock(timeNode?.textContent);
    if(d>0){seek.disabled=false;seek.max=String(d);if(!seeking)seek.value=String(clamp(t,0,d));seekTime.textContent=`${format(t)} / ${format(d)}`}
    requestAnimationFrame(syncSeek);
  }

  function dispatchCanvasSeek(sec){
    const d=getDuration();if(!d)return;
    const target=clamp(Number(sec)||0,0,d),r=canvas.getBoundingClientRect(),px=getPx(),span=r.width/px,maxView=Math.max(0,d-span);
    let view=getViewStart();
    if(target<view||target>view+span){view=clamp(target-span*.25,0,maxView);if(scroll){scroll.value=maxView?String(Math.round(view/maxView*1000)):"0";scroll.dispatchEvent(new Event("input",{bubbles:true}))}}
    view=getViewStart();
    const x=clamp((target-view)*px,0,r.width);
    canvas.dispatchEvent(new PointerEvent("pointerdown",{bubbles:true,cancelable:true,pointerId:99991,pointerType:"mouse",isPrimary:true,button:0,buttons:1,clientX:r.left+x,clientY:r.top+r.height*.76}));
    transportPlaying=false;
  }

  play.addEventListener("click",()=>{transportPlaying=true});
  pause.addEventListener("click",()=>{transportPlaying=false});

  seek.addEventListener("pointerdown",()=>{seeking=true;resumeAfterSeek=transportPlaying});
  seek.addEventListener("input",()=>dispatchCanvasSeek(seek.value));
  function finishSeek(){if(!seeking)return;seeking=false;const resume=resumeAfterSeek;resumeAfterSeek=false;if(resume){play.click();transportPlaying=true}}
  seek.addEventListener("change",finishSeek);
  seek.addEventListener("pointerup",finishSeek);
  seek.addEventListener("pointercancel",()=>{seeking=false;resumeAfterSeek=false});

  canvas.addEventListener("pointerdown",e=>{
    if(!e.isTrusted||e.button!==0)return;
    const r=canvas.getBoundingClientRect();
    press={pointerId:e.pointerId,x:e.clientX,y:e.clientY,upper:e.clientY-r.top<r.height*.53,moved:false};
    transportPlaying=false;
  },true);
  canvas.addEventListener("pointermove",e=>{if(press&&e.pointerId===press.pointerId&&Math.hypot(e.clientX-press.x,e.clientY-press.y)>5)press.moved=true},true);
  canvas.addEventListener("pointerup",e=>{
    if(!press||e.pointerId!==press.pointerId)return;
    const p=press;press=null;
    if(!p.upper||p.moved)return;
    const r=canvas.getBoundingClientRect(),x=e.clientX-r.left;
    canvas.dispatchEvent(new PointerEvent("pointerdown",{bubbles:true,cancelable:true,pointerId:99992,pointerType:e.pointerType||"mouse",isPrimary:true,button:0,buttons:1,clientX:e.clientX,clientY:r.top+r.height*.76}));
    const target=getViewStart()+x/getPx();
    if(getDuration())seek.value=String(clamp(target,0,getDuration()));
  },true);
  canvas.addEventListener("pointercancel",()=>{press=null},true);

  requestAnimationFrame(syncSeek);
})();
