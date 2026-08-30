"use strict";

(()=>{
  if(typeof flashPart!=="function")return;
  const fxByTarget=new WeakMap();

  const ORIGINS={
    "crash left":["61.1%","79.1%"],
    "crash right":["34.6%","78.6%"],
    hh:["69.9%","64.9%"],
    ride:["30.1%","55.9%"],
    high:["49.9%","52%"],
    mid:["52.1%","44.9%"],
    snare:["44.4%","43.5%"],
    floor:["55.9%","45.6%"],
    special:["50%","50%"]
  };

  function targetFor(part,el){
    return el||document.querySelector(`#hitLayer [data-part="${part}"]:not(.inactive)`);
  }

  function originFor(target){
    if(target.classList.contains("crash")){
      return target.classList.contains("right")?ORIGINS["crash right"]:ORIGINS["crash left"];
    }
    for(const name of["hh","ride","high","mid","snare","floor","special"]){
      if(target.classList.contains(name))return ORIGINS[name];
    }
    return["50%","50%"];
  }

  function ensureFx(target){
    let slot=fxByTarget.get(target);
    if(slot)return slot;
    const fx=document.createElement("span"),[left,top]=originFor(target);
    fx.setAttribute("aria-hidden","true");
    Object.assign(fx.style,{
      position:"absolute",left,top,width:"42%",aspectRatio:"1",
      borderRadius:"50%",transform:"translate(-50%,-50%) scale(.7)",opacity:"0",
      pointerEvents:"none",background:"radial-gradient(circle,#fff 0 10%,rgba(170,255,244,.98) 25%,rgba(82,223,207,.48) 47%,rgba(108,215,255,.18) 58%,transparent 70%)",
      boxShadow:"0 0 34px rgba(108,215,255,1),0 0 52px rgba(82,223,207,.72),0 0 72px rgba(82,223,207,.28)",zIndex:"1"
    });
    target.appendChild(fx);slot={fx,animation:null};fxByTarget.set(target,slot);return slot;
  }

  function animatePart(part,el){
    const target=targetFor(part,el);if(!target)return;
    const slot=ensureFx(target);slot.animation?.cancel();
    slot.animation=slot.fx.animate([
      {opacity:1,transform:"translate(-50%,-50%) scale(.4)"},
      {opacity:0,transform:"translate(-50%,-50%) scale(1.5)"}
    ],{duration:240,easing:"ease-out"});
  }

  function reportedOutputDelaySec(){
    if(typeof ac==="undefined"||!ac)return 0;
    const now=Number(ac.currentTime);if(!Number.isFinite(now))return 0;
    const base=Math.max(0,Number(ac.baseLatency)||0),out=Math.max(0,Number(ac.outputLatency)||0);
    let stampLag=0;
    try{
      const ts=typeof ac.getOutputTimestamp==="function"?ac.getOutputTimestamp():null,
            ct=Number(ts?.contextTime);
      if(Number.isFinite(ct)&&ct>=0&&ct<=now+.02)stampLag=Math.max(0,now-ct);
    }catch{}
    return Math.min(.6,Math.max(stampLag,base+out));
  }

  function oldChartDelaySec(){
    if(typeof ac==="undefined"||!ac)return 0;
    const now=Number(ac.currentTime),clock=globalThis.DruMasterChartClock;
    if(!Number.isFinite(now)||!clock?.audibleContextTime)return 0;
    try{
      const heard=Number(clock.audibleContextTime());
      return Number.isFinite(heard)?Math.max(0,Math.min(.6,now-heard)):0;
    }catch{return 0}
  }

  function extraChartDelaySec(){return Math.max(0,reportedOutputDelaySec()-oldChartDelaySec())}
  function visualCurrent(){
    const t=typeof current==="function"?current():0,
          speed=Math.max(.01,Number(typeof rate!=="undefined"?rate:1)||1);
    return t-reportedOutputDelaySec()*speed;
  }
  globalThis.DruMasterVisualSync={reportedOutputDelaySec,visualCurrent};

  /* game-chart.js already applies a first-pass latency correction. Add only
     the missing remainder here, so chart notes reach the goal at the same
     instant the scheduled MIDI/drum transient is actually audible. */
  if(typeof draw==="function"&&typeof current==="function"){
    const baseDraw=draw;
    draw=function(){
      const extra=extraChartDelaySec();
      if(extra<=.0005)return baseDraw();
      const realCurrent=globalThis.current,speed=Math.max(.01,Number(typeof rate!=="undefined"?rate:1)||1);
      if(typeof realCurrent!=="function")return baseDraw();
      globalThis.current=()=>realCurrent()-extra*speed;
      try{return baseDraw()}finally{globalThis.current=realCurrent}
    };
  }

  /* This becomes the low-level pad flash. judgement.js loads later and wraps
     it for note-specific goal glows. */
  flashPart=animatePart;

  /* After judgement.js has wrapped flashPart, defer AUTO playback visuals by
     the audio device's measured output latency. While calling the wrapper we
     temporarily expose the matching MIDI time so its nearest-note lookup still
     resolves the exact note instead of the following one. Manual input remains
     immediate and its scoring windows are unchanged. */
  function installAutoVisualDelay(){
    if(!globalThis.DruMasterJudgement||typeof globalThis.flashPart!=="function"){
      requestAnimationFrame(installAutoVisualDelay);return;
    }
    if(globalThis.flashPart.__dmAudibleSync)return;
    const wrapped=globalThis.flashPart;
    const delayed=function(part,el){
      const auto=typeof autoplay!=="undefined"&&autoplay&&typeof running!=="undefined"&&running&&!(typeof paused!=="undefined"&&paused);
      if(!auto)return wrapped(part,el);
      const delay=reportedOutputDelaySec();
      if(delay<=.0005)return wrapped(part,el);
      setTimeout(()=>{
        const realCurrent=globalThis.current,speed=Math.max(.01,Number(typeof rate!=="undefined"?rate:1)||1);
        if(typeof realCurrent!=="function"){wrapped(part,el);return}
        globalThis.current=()=>realCurrent()-delay*speed;
        try{wrapped(part,el)}finally{globalThis.current=realCurrent}
      },delay*1000);
    };
    delayed.__dmAudibleSync=true;
    globalThis.flashPart=delayed;
  }
  requestAnimationFrame(installAutoVisualDelay);
})();
