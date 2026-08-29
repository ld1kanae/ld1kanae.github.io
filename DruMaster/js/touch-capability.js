"use strict";

(()=>{
  const nativeMatchMedia=window.matchMedia.bind(window);
  const legacyMobileQuery="(hover:none) and (pointer:coarse) and (max-width:900px)";
  const compact=s=>String(s||"").replace(/\s+/g,"").toLowerCase();
  const legacyCompact=compact(legacyMobileQuery);
  const protectedSelector=[
    "#start",
    "#pause",
    "#scorePlaybackControls button",
    "#pausePanel button",
    ".result-actions button",
    ".mic-cal-actions button",
    ".setup .mobile-custom-select-trigger"
  ].join(",");

  function isTouchCapable(){
    return (navigator.maxTouchPoints||0)>0 ||
      nativeMatchMedia("(any-pointer:coarse)").matches ||
      nativeMatchMedia("(pointer:coarse)").matches;
  }

  function touchHitArea(){
    const value=parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--dm-touch-hit-area"));
    return Number.isFinite(value)&&value>0?value:44;
  }

  /* Performance mode used to equate 'mobile' with <=900 CSS px. In landscape
     that disables touch input on perfectly valid phones/tablets. Preserve the
     old query everywhere else, but make its JS .matches true on real touch
     hardware regardless of viewport width. CSS media queries are untouched. */
  window.matchMedia=function(query){
    const list=nativeMatchMedia(query);
    if(compact(query)!==legacyCompact || !isTouchCapable())return list;
    return new Proxy(list,{
      get(target,prop){
        if(prop==="matches")return true;
        const value=Reflect.get(target,prop,target);
        return typeof value==="function"?value.bind(target):value;
      }
    });
  };

  globalThis.DruMasterTouchCapable=isTouchCapable;

  function isUsableControl(el){
    if(!el || el.disabled)return false;
    const cs=getComputedStyle(el);
    if(cs.display==="none" || cs.visibility==="hidden" || cs.pointerEvents==="none")return false;
    const r=el.getBoundingClientRect();
    return r.width>0 && r.height>0;
  }

  /* Visual controls may intentionally stay smaller than a finger target.
     Hit testing is expanded in pointer space instead of changing their boxes,
     so the 26px mobile transport artwork remains visually unchanged. */
  function expandedControlAt(x,y){
    let best=null,bestDistance=Infinity;
    const minimum=touchHitArea();
    document.querySelectorAll(protectedSelector).forEach(el=>{
      if(!isUsableControl(el))return;
      const r=el.getBoundingClientRect();
      const w=Math.max(minimum,r.width);
      const h=Math.max(minimum,r.height);
      const cx=r.left+r.width/2,cy=r.top+r.height/2;
      const left=cx-w/2,right=cx+w/2,top=cy-h/2,bottom=cy+h/2;
      if(x<left||x>right||y<top||y>bottom)return;
      const d=(x-cx)*(x-cx)+(y-cy)*(y-cy);
      if(d<bestDistance){bestDistance=d;best=el}
    });
    return best;
  }

  function normalizedEventTimeStamp(e){
    const now=performance.now();
    let stamp=Number(e?.timeStamp);
    if(!Number.isFinite(stamp))return now;
    if(stamp>1e12&&Number.isFinite(performance.timeOrigin))stamp-=performance.timeOrigin;
    if(stamp<0||Math.abs(stamp-now)>60000)return now;
    return stamp;
  }

  /* Judge against the time at which the browser received the touch, not the
     later time at which a busy main thread finally dispatches this listener. */
  function eventSongTime(e){
    if(typeof current!=="function")return NaN;
    const queuedMs=Math.max(0,Math.min(160,performance.now()-normalizedEventTimeStamp(e)));
    const playbackRate=typeof rate!=="undefined"&&Number.isFinite(Number(rate))?Number(rate):1;
    return Math.max(0,current()-queuedMs/1000*playbackRate);
  }

  function canJudge(){
    return typeof running!=="undefined"&&running&&
      !(typeof paused!=="undefined"&&paused)&&
      !(typeof autoplay!=="undefined"&&autoplay)&&
      !document.body.classList.contains("acoustic-calibrating");
  }

  function gradeMatched(note,delta){
    let mult,label;
    if(delta<=.035){mult=1;label="PERFECT";counts.perfect++}
    else if(delta<=.105){mult=.75;label="GREAT";counts.great++}
    else{mult=.4;label="GOOD";counts.good++}
    score+=weight(note.type)*note.velocity/127*1000*mult;
    const scoreNode=document.querySelector("#score");
    if(scoreNode)scoreNode.textContent=String(Math.round(score)).padStart(6,"0");
    const judgement=globalThis.DruMasterJudgement;
    if(judgement?.emitForNote)judgement.emitForNote(note,label,{flash:false});
    else if(typeof showJudge==="function")showJudge(label);
  }

  function nearestAt(t,predicate){
    const maxDelta=.160,search=globalThis.DruMasterNoteSearch;
    if(search?.nearest)return search.nearest(notes,t,maxDelta,predicate);
    let best=null,bestDelta=maxDelta+.000001;
    for(const n of notes){
      if(n.time<t-maxDelta)continue;
      if(n.time>t+maxDelta)break;
      if(!predicate(n))continue;
      const delta=Math.abs(n.time-t);
      if(delta<bestDelta){best=n;bestDelta=delta}
    }
    return best?{note:best,delta:bestDelta}:null;
  }

  function consumeTouchAt(t){
    if(!canJudge()||!Number.isFinite(t)||typeof notes==="undefined"||!Array.isArray(notes))return false;
    const match=nearestAt(t,n=>!n.hit&&n.type!=="kick"&&n.type!=="hhPedal");
    if(!match||match.delta>.160)return false;
    const {note,delta}=match;
    note.hit=true;
    if(typeof playDrum==="function")playDrum(note.note,note.type,note.velocity/127);
    if(typeof flashPart==="function"&&typeof PART!=="undefined")flashPart(PART[note.type]);
    gradeMatched(note,delta);
    return true;
  }

  function consumePartAt(part,visualEl,t){
    if(!canJudge()||!Number.isFinite(t)||typeof notes==="undefined"||!Array.isArray(notes)||typeof PART==="undefined")return false;
    const match=nearestAt(t,n=>!n.hit&&n.type!=="kick"&&n.type!=="hhPedal"&&PART[n.type]===part),
          matched=!!match&&match.delta<=.160,
          best=matched?match.note:null,
          vel=best?best.velocity/127:.72,
          type=best?best.type:DEFAULT_TYPE[part],
          note=best?best.note:DEFAULT_NOTE[type];
    if(typeof playDrum==="function")playDrum(note,type,vel);
    if(typeof flashPart==="function")flashPart(part,visualEl);
    if(!best)return true;
    best.hit=true;
    gradeMatched(best,match.delta);
    return true;
  }

  let touchStart=null;
  document.addEventListener("pointerdown",e=>{
    if(!isTouchCapable() || e.pointerType==="mouse" || !e.isPrimary)return;
    touchStart={id:e.pointerId,x:e.clientX,y:e.clientY};
  },true);
  document.addEventListener("pointercancel",e=>{
    if(touchStart?.id===e.pointerId)touchStart=null;
  },true);
  document.addEventListener("pointerup",e=>{
    if(!isTouchCapable() || e.pointerType==="mouse" || !e.isPrimary)return;
    const start=touchStart;
    touchStart=null;
    if(!start || start.id!==e.pointerId)return;
    if(Math.hypot(e.clientX-start.x,e.clientY-start.y)>10)return;
    if(e.target.closest("button,input,select,a,[role=button]"))return;
    const control=expandedControlAt(e.clientX,e.clientY);
    if(!control)return;
    e.preventDefault();
    e.stopPropagation();
    control.click();
  },true);

  function installTouchInput(){
    const game=document.querySelector("#game"),mode=document.querySelector("#performanceModeSelect");
    if(!game||!mode)return;
    game.style.touchAction="none";

    document.addEventListener("pointerdown",e=>{
      if(!isTouchCapable() || e.pointerType==="mouse")return;
      if(!game.contains(e.target))return;
      if(e.target.closest("#pause,#pausePanel button,.mic-debug-controls,button:not(.hit),select,input"))return;
      /* Do not convert a near-miss on a compact UI control into a drum hit. */
      if(expandedControlAt(e.clientX,e.clientY))return;
      const api=globalThis.DruMasterPerformanceMode;
      if(!api)return;
      const t=eventSongTime(e);

      if(mode.value==="touch"&&api.getRunMode?.()==="touch"){
        consumeTouchAt(t);
      }else if(mode.value==="normal"&&api.getRunMode?.()==="normal"){
        const hit=e.target.closest("#hitLayer .hit:not(.inactive)");
        if(!hit)return;
        consumePartAt(hit.dataset.part,hit,t);
      }else return;

      /* Legacy target/game listeners use current() at dispatch time. Stop the
         pointer here so a delayed mobile event cannot be judged a second time. */
      e.preventDefault();
      e.stopImmediatePropagation();
    },true);
  }

  if(document.readyState==="loading")addEventListener("DOMContentLoaded",()=>setTimeout(installTouchInput,0),{once:true});
  else setTimeout(installTouchInput,0);
})();
