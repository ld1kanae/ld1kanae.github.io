"use strict";
(()=>{
  const desktop=!!matchMedia?.("(hover:hover) and (pointer:fine)")?.matches;\n  const mobile=!!matchMedia?.("(hover:none) and (pointer:coarse) and (max-width:900px)")?.matches;\n  if(!desktop&&!mobile)return;

  const SELECTOR="#start,#pause,#scorePlaybackControls button,#pausePanel button,.result-actions button,.mic-cal-actions button";

  /* Production settings based on the user's approved original editor payload.
     Only later explicitly approved changes are applied: faceSheen 120% and
     every hover animation advanced by 150ms. Negative delays intentionally
     begin the animation as if 150ms had already elapsed at hover start. */
  const SETTINGS={
    spectralAngle:"337.5deg",
    autoReplay:true,
    intervalSec:5,
    oppositePairOffset:50,
    elements:{
      rimRun1:{enabled:true,opacity:.3,speedPercent:150,fadeInMs:1300,fadeOutMs:2500,delayMs:0,base:1000,start:0,travel:-100,kind:"rim"},
      rimRun2:{enabled:true,opacity:.3,speedPercent:150,fadeInMs:1300,fadeOutMs:2500,delayMs:0,base:1000,start:-50,travel:-100,kind:"rim"},
      edge1:{enabled:false,opacity:1,speedPercent:100,fadeInMs:150,fadeOutMs:200,delayMs:-150,base:850,start:0,travel:-55,kind:"edge"},
      edge2:{enabled:false,opacity:1,speedPercent:100,fadeInMs:150,fadeOutMs:200,delayMs:-150,base:850,start:-50,travel:-55,kind:"edge"},
      faceSheen:{enabled:true,opacity:.7,speedPercent:120,fadeInMs:1000,fadeOutMs:1000,delayMs:-150,base:720,kind:"faceSheen"},
      faceFlash:{enabled:true,opacity:.25,speedPercent:100,fadeInMs:1000,fadeOutMs:400,delayMs:-150,base:660,kind:"flash"},
      faceLine:{enabled:false,opacity:1,speedPercent:20,fadeInMs:200,fadeOutMs:300,delayMs:-150,base:520,kind:"faceLine"},
      rimPulse:{enabled:false,opacity:1,speedPercent:100,fadeInMs:100,fadeOutMs:350,delayMs:-150,base:520,kind:"pulse"}
    }
  };

  const activeAnimations=new WeakMap();
  const replayTimers=new WeakMap();

  function stack(pos){
    const s=document.createElement("span");
    s.className=`glass-inner-stack ${pos}`;
    for(const cls of ["tail","shoulder","core"]){
      const i=document.createElement("i");
      i.className=cls;
      s.appendChild(i);
    }
    return s;
  }

  function makeFace(className){
    const i=document.createElement("i");
    i.className=className;
    i.setAttribute("aria-hidden","true");
    return i;
  }

  function makeRim(){
    const ns="http://www.w3.org/2000/svg";
    const svg=document.createElementNS(ns,"svg");
    svg.classList.add("glass-hover-rim-svg");
    svg.setAttribute("preserveAspectRatio","none");
    svg.setAttribute("aria-hidden","true");
    for(const cls of ["glass-hover-rim-run rim-run-1","glass-hover-rim-run rim-run-2"]){
      const r=document.createElementNS(ns,"rect");
      r.setAttribute("pathLength","100");
      r.setAttribute("class",cls);
      svg.appendChild(r);
    }
    return svg;
  }

  function buttonFor(host){
    return host.matches?.("button")?host:host.querySelector(":scope > button");
  }

  function syncRim(host){
    const button=buttonFor(host);
    const svg=host.querySelector(":scope > .glass-hover-rim-svg");
    if(!button||!svg)return;
    const box=button.getBoundingClientRect();
    if(box.width<2||box.height<2)return;
    const inset=1.25;
    const style=getComputedStyle(button);
    const cssRadius=parseFloat(style.borderTopLeftRadius)||0;
    const rx=Math.max(0,Math.min(cssRadius,(box.height-inset*2)/2));
    svg.setAttribute("viewBox",`0 0 ${box.width} ${box.height}`);
    for(const r of svg.querySelectorAll("rect")){
      r.setAttribute("x",String(inset));
      r.setAttribute("y",String(inset));
      r.setAttribute("width",String(Math.max(0,box.width-inset*2)));
      r.setAttribute("height",String(Math.max(0,box.height-inset*2)));
      r.setAttribute("rx",String(rx));
    }
  }

  /* This is the timing function used by the original editor when the supplied
     settings were captured. Large fade values are proportionally fitted into
     90% of the element's speed-derived duration. */
  function timing(s){
    const duration=Math.max(80,s.base*(100/Math.max(1,s.speedPercent)));
    let fi=Math.max(0,s.fadeInMs),fo=Math.max(0,s.fadeOutMs);
    const maxFade=duration*.9;
    if(fi+fo>maxFade){
      const k=maxFade/(fi+fo||1);
      fi*=k;
      fo*=k;
    }
    return {duration,inOff:fi/duration,outOff:1-fo/duration};
  }

  function strokeSpec(s){
    const t=timing(s),start=s.start,end=s.start+s.travel,max=s.opacity;
    const at=p=>start+(end-start)*p;
    return {duration:t.duration,frames:[
      {opacity:0,strokeDashoffset:start,offset:0},
      {opacity:max,strokeDashoffset:at(t.inOff),offset:t.inOff},
      {opacity:max,strokeDashoffset:at(t.outOff),offset:t.outOff},
      {opacity:0,strokeDashoffset:end,offset:1}
    ]};
  }

  function moveSpec(s,from,to){
    const t=timing(s),max=s.opacity;
    const at=p=>from+(to-from)*p;
    return {duration:t.duration,frames:[
      {opacity:0,left:`${from}%`,offset:0},
      {opacity:max,left:`${at(t.inOff)}%`,offset:t.inOff},
      {opacity:max,left:`${at(t.outOff)}%`,offset:t.outOff},
      {opacity:0,left:`${to}%`,offset:1}
    ]};
  }

  function fadeSpec(s){
    const t=timing(s),max=s.opacity;
    return {duration:t.duration,frames:[
      {opacity:0,offset:0},
      {opacity:max,offset:t.inOff},
      {opacity:max,offset:t.outOff},
      {opacity:0,offset:1}
    ]};
  }

  function play(host){
    const button=buttonFor(host);
    if(!button||button.disabled)return;
    syncRim(host);

    const old=activeAnimations.get(host)||[];
    for(const a of old){try{a.cancel()}catch{}}
    const running=[];

    const run=(el,s,spec)=>{
      if(!el||!s.enabled)return;
      const a=el.animate(spec.frames,{duration:spec.duration,delay:s.delayMs,easing:"linear",fill:"both"});
      running.push(a);
    };

    const e=SETTINGS.elements;
    run(host.querySelector(".rim-run-1"),e.rimRun1,strokeSpec(e.rimRun1));
    run(host.querySelector(".rim-run-2"),e.rimRun2,strokeSpec(e.rimRun2));
    run(button.querySelector(".glass-hover-face-sheen"),e.faceSheen,moveSpec(e.faceSheen,-58,122));
    run(button.querySelector(".glass-hover-face-flash"),e.faceFlash,fadeSpec(e.faceFlash));

    activeAnimations.set(host,running);
  }

  function stopReplay(host){
    const timer=replayTimers.get(host);
    if(timer)clearInterval(timer);
    replayTimers.delete(host);
  }

  function bindHover(host,button){
    const beginHover=()=>{
      play(host);
      stopReplay(host);
      if(SETTINGS.autoReplay){
        const timer=setInterval(()=>{
          if(button.matches(":hover"))play(host);
          else stopReplay(host);
        },SETTINGS.intervalSec*1000);
        replayTimers.set(host,timer);
      }
    };
    button.addEventListener("mouseenter",beginHover);
    button.addEventListener("mouseleave",()=>stopReplay(host));
  }

  const tapTimers=new WeakMap();
  function bindTap(host,button){
    button.addEventListener("pointerdown",()=>{
      if(button.disabled)return;
      play(host);
      host.classList.add("glass-tap-active");
      const old=tapTimers.get(host);
      if(old)clearTimeout(old);
      tapTimers.set(host,setTimeout(()=>{
        host.classList.remove("glass-tap-active");
        tapTimers.delete(host);
      },720));
    },{passive:true});
  }

  function observeSize(host,button){
    if("ResizeObserver" in window){
      const ro=new ResizeObserver(()=>syncRim(host));
      ro.observe(button);
    }
  }

  function enhance(button){
    if(!button||button.dataset.glassHoverFinal==="1")return;
    button.dataset.glassHoverFinal="1";

    button.prepend(stack("bottom"));
    button.prepend(stack("top"));
    button.prepend(makeFace("glass-hover-face-flash"));
    button.prepend(makeFace("glass-hover-face-sheen"));

    /* The pause button stays a direct flex child of the game header. Wrapping
       it changes the header's layout box and previously displaced both the
       pointer hit area and the animated rim. Keep every pause layer inside the
       real button so visual and interactive coordinates are identical. */
    if(button.id==="pause"){
      button.classList.add("glass-hover-inline");
      button.style.setProperty("--spectral-angle",SETTINGS.spectralAngle);
      button.appendChild(makeRim());
      syncRim(button);
      desktop?bindHover(button,button):bindTap(button,button);
      observeSize(button,button);
      return;
    }

    const wrap=document.createElement("span");
    wrap.className="glass-hover-wrap";
    wrap.style.setProperty("--spectral-angle",SETTINGS.spectralAngle);
    if(button.id==="start")wrap.classList.add("start-wrap");

    const glow=document.createElement("i");
    glow.className="glass-hover-drop";
    const rim=makeRim();

    const parent=button.parentNode;
    parent.insertBefore(wrap,button);
    wrap.appendChild(glow);
    wrap.appendChild(button);
    wrap.appendChild(rim);
    syncRim(wrap);
    desktop?bindHover(wrap,button):bindTap(wrap,button);
    observeSize(wrap,button);
  }

  function scan(root=document){
    if(root.matches?.(SELECTOR))enhance(root);
    root.querySelectorAll?.(SELECTOR).forEach(enhance);
  }

  scan();
  new MutationObserver(records=>{
    for(const record of records){
      for(const node of record.addedNodes){
        if(node.nodeType===1)scan(node);
      }
    }
  }).observe(document.documentElement,{childList:true,subtree:true});
})();
