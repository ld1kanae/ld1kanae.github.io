"use strict";

(()=>{
  const $=id=>document.getElementById(id),canvas=$("canvas"),play=$("play"),pause=$("stop"),time=$("time"),duration=$("duration"),zoom=$("zoom"),scroll=$("scroll"),scrollOut=$("scrollOut");
  if(!canvas||!play||!pause||!time||!duration)return;

  if(!$("timingSeek")){
    const row=pause.closest(".row");
    const wrap=document.createElement("div");
    wrap.id="timingSeekWrap";
    wrap.innerHTML='<input id="timingSeek" type="range" min="0" max="1" step="0.01" value="0" disabled aria-label="再生位置"><span id="timingSeekTime">0:00 / 0:00</span>';
    row?.insertAdjacentElement("afterend",wrap);
    const style=document.createElement("style");
    style.id="dmTimingSeekStyle";
    style.textContent=`
      #timingSeekWrap{display:flex;align-items:center;gap:8px;width:100%;margin-top:9px;padding:3px 10px;border-radius:999px;background:#06101ac2;border:1px solid #64788b55}
      #timingSeek{flex:1;min-width:0;margin:0}
      #timingSeekTime{min-width:72px;text-align:right;color:#b9c7d7;font:800 9px/1 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:nowrap}
    `;
    document.head.appendChild(style);
  }

  const seek=$("timingSeek"),seekTime=$("timingSeekTime");
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const fmt=s=>{s=Math.max(0,Math.floor(Number(s)||0));return `${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`};
  const parseClock=text=>{const m=String(text||"").match(/(\d+):(\d+)\.(\d+)/);return m?Number(m[1])*60+Number(m[2])+Number(`0.${m[3]}`):0};
  const getDuration=()=>{const v=parseFloat(duration.textContent||"");return Number.isFinite(v)&&v>0?v:0};
  const getViewStart=()=>{const v=parseFloat(scrollOut?.textContent||"");return Number.isFinite(v)?v:0};
  const getPx=()=>Math.max(1,Number(zoom?.value)||260);
  let playing=false,seeking=false,resume=false;

  function dispatchSeek(sec){
    const d=getDuration();if(!d)return;
    const target=clamp(Number(sec)||0,0,d),r=canvas.getBoundingClientRect(),px=getPx(),span=r.width/px,maxView=Math.max(0,d-span);
    let view=getViewStart();
    if(target<view||target>view+span){
      view=clamp(target-span*.25,0,maxView);
      if(scroll){scroll.value=maxView?String(Math.round(view/maxView*1000)):"0";scroll.dispatchEvent(new Event("input",{bubbles:true}))}
    }
    view=getViewStart();
    const x=clamp((target-view)*px,0,r.width);
    canvas.dispatchEvent(new PointerEvent("pointerdown",{bubbles:true,cancelable:true,pointerId:99127,pointerType:"mouse",isPrimary:true,button:0,buttons:1,clientX:r.left+x,clientY:r.top+r.height*.76}));
  }

  play.addEventListener("click",()=>{playing=true});
  pause.addEventListener("click",()=>{playing=false});
  seek.addEventListener("pointerdown",()=>{seeking=true;resume=playing});
  seek.addEventListener("input",()=>dispatchSeek(seek.value));
  const finish=()=>{if(!seeking)return;seeking=false;if(resume){resume=false;play.click();playing=true}};
  seek.addEventListener("change",finish);
  seek.addEventListener("pointerup",finish);
  seek.addEventListener("pointercancel",()=>{seeking=false;resume=false});

  function sync(){
    const d=getDuration(),t=parseClock(time.textContent);
    if(d>0){seek.disabled=false;seek.max=String(d);if(!seeking)seek.value=String(clamp(t,0,d));seekTime.textContent=`${fmt(t)} / ${fmt(d)}`}
    requestAnimationFrame(sync);
  }
  requestAnimationFrame(sync);
})();
