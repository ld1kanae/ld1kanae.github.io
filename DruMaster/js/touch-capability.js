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

  function eventSongTime(e){
    if(typeof current!=="function")return NaN;
    const queuedMs=Math.max(0,Math.min(160,performance.now()-normalizedEventTimeStamp(e)));
    const playbackRate=typeof rate!=="undefined"&&Number.isFinite(Number(rate))?Number(rate):1;
    return Math.max(0,current()-queuedMs/1000*playbackRate);
  }

  function nearestTouchNote(t,includeHit=false){
    if(!Number.isFinite(t)||typeof notes==="undefined"||!Array.isArray(notes))return null;
    const maxDelta=.160,search=globalThis.DruMasterNoteSearch,
          predicate=n=>(includeHit||!n.hit)&&n.type!=="kick"&&n.type!=="hhPedal";
    if(search?.nearest)return search.nearest(notes,t,maxDelta,predicate)||null;
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
    if(typeof running==="undefined"||!running||typeof paused!=="undefined"&&paused||typeof autoplay!=="undefined"&&autoplay)return false;
    if(document.body.classList.contains("acoustic-calibrating"))return false;
    const match=nearestTouchNote(t,false);
    if(!match||match.delta>.160)return false;

    const {note,delta}=match;
    note.hit=true;
    if(typeof playDrum==="function")playDrum(note.note,note.type,note.velocity/127);
    if(typeof flashPart==="function"&&typeof PART!=="undefined")flashPart(PART[note.type]);

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
    return true;
  }

  function playFreePad(target){
    if(!target||typeof DEFAULT_TYPE==="undefined"||typeof DEFAULT_NOTE==="undefined")return false;
    const part=target.dataset.part,type=DEFAULT_TYPE[part],note=DEFAULT_NOTE[type];
    if(!type||!Number.isFinite(Number(note)))return false;
    if(typeof playDrum==="function")playDrum(note,type,.72);
    if(typeof flashPart==="function")flashPart(part,target);
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
      if(mode.value!=="touch")return;
      if(e.target.closest("#pause,#pausePanel button,.mic-debug-controls,button:not(.hit),select,input"))return;
      if(expandedControlAt(e.clientX,e.clientY))return;

      const active=typeof running!=="undefined"&&running&&
        !(typeof paused!=="undefined"&&paused)&&
        !(typeof autoplay!=="undefined"&&autoplay)&&
        !document.body.classList.contains("acoustic-calibrating");
      if(!active)return;

      const t=eventSongTime(e),nearby=nearestTouchNote(t,true);

      /* Anywhere-touch owns the whole pointer while a playable chart note is
         inside the GOOD window. This is intentionally based on note presence,
         not only on whether an unhit note can still be consumed. It prevents a
         drum hit target underneath the finger from sounding an extra sample. */
      if(nearby&&nearby.delta<=.160){
        e.preventDefault();
        e.stopImmediatePropagation();
        consumeTouchAt(t);
        return;
      }

      /* Outside every note window, keep the drum set usable as a free pad. */
      const target=e.target.closest("#hitLayer .hit:not(.inactive)");
      if(target&&playFreePad(target)){
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    },true);
  }

  if(document.readyState==="loading")addEventListener("DOMContentLoaded",()=>setTimeout(installTouchInput,0),{once:true});
  else setTimeout(installTouchInput,0);
})();
