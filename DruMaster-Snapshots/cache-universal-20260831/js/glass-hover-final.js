"use strict";
(()=>{
  const desktop=!!matchMedia?.("(hover:hover) and (pointer:fine)")?.matches;
  const mobile=!!matchMedia?.("(hover:none) and (pointer:coarse) and (max-width:900px)")?.matches;
  if(!desktop&&!mobile)return;

  if(mobile){
    const style=document.createElement("style");
    style.dataset.mobileGlassRimFix="1";
    style.textContent=`
      .glass-hover-wrap > .glass-hover-rim-svg{display:none!important}
      .glass-hover-wrap > button > .glass-hover-rim-svg,
      #pause.glass-hover-inline > .glass-hover-rim-svg{
        position:absolute!important;
        inset:0!important;
        left:0!important;
        top:0!important;
        width:100%!important;
        height:100%!important;
        min-width:0!important;
        min-height:0!important;
        max-width:none!important;
        max-height:none!important;
        margin:0!important;
        padding:0!important;
        transform:none!important;
        z-index:4!important;
        pointer-events:none!important;
        overflow:visible!important;
        display:block!important;
      }
    `;
    document.head.appendChild(style);
  }

  const SELECTOR="#start,#pause,#scorePlaybackControls button,#pausePanel button,.result-actions button,.mic-cal-actions button";

  const SETTINGS={
    spectralAngle:"337.5deg",
    autoReplay:true,
    intervalSec:5,
    elements:{
      rimRun1:{enabled:true,opacity:.3,speedPercent:150,fadeInMs:1300,fadeOutMs:2500,delayMs:0,base:1000,start:0,travel:-100},
      rimRun2:{enabled:true,opacity:.3,speedPercent:150,fadeInMs:1300,fadeOutMs:2500,delayMs:0,base:1000,start:-50,travel:-100},
      faceSheen:{enabled:true,opacity:.7,speedPercent:120,fadeInMs:1000,fadeOutMs:1000,delayMs:-150,base:720},
      faceFlash:{enabled:true,opacity:.25,speedPercent:100,fadeInMs:1000,fadeOutMs:400,delayMs:-150,base:660}
    }
  };

  const activeAnimations=new WeakMap();
  const replayTimers=new WeakMap();
  const tapTimers=new WeakMap();

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
    return host?.matches?.("button")?host:host?.querySelector?.(":scope > button");
  }

  function rimFor(host,button){
    return mobile
      ? button?.querySelector?.(":scope > .glass-hover-rim-svg")
      : host?.querySelector?.(":scope > .glass-hover-rim-svg");
  }

  function syncRim(host){
    const button=buttonFor(host);
    const svg=rimFor(host,button);
    if(!button||!svg)return;

    const width=button.offsetWidth||parseFloat(getComputedStyle(button).width)||0;
    const height=button.offsetHeight||parseFloat(getComputedStyle(button).height)||0;
    if(width<2||height<2)return;

    const inset=1.25;
    const style=getComputedStyle(button);
    const cssRadius=parseFloat(style.borderTopLeftRadius)||0;
    const rx=Math.max(0,Math.min(cssRadius,(height-inset*2)/2));
    svg.setAttribute("viewBox",`0 0 ${width} ${height}`);
    for(const r of svg.querySelectorAll("rect")){
      r.setAttribute("x",String(inset));
      r.setAttribute("y",String(inset));
      r.setAttribute("width",String(Math.max(0,width-inset*2)));
      r.setAttribute("height",String(Math.max(0,height-inset*2)));
      r.setAttribute("rx",String(rx));
      r.setAttribute("ry",String(rx));
    }
  }

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
    repair(button,false);
    syncRim(host);

    for(const a of activeAnimations.get(host)||[]){try{a.cancel()}catch{}}
    const running=[];
    const run=(el,s,spec)=>{
      if(!el||!s.enabled)return;
      const a=el.animate(spec.frames,{duration:spec.duration,delay:s.delayMs,easing:"linear",fill:"both"});
      running.push(a);
    };
    const e=SETTINGS.elements;
    const rim=rimFor(host,button);
    run(rim?.querySelector(".rim-run-1"),e.rimRun1,strokeSpec(e.rimRun1));
    run(rim?.querySelector(".rim-run-2"),e.rimRun2,strokeSpec(e.rimRun2));
    run(button.querySelector(":scope > .glass-hover-face-sheen"),e.faceSheen,moveSpec(e.faceSheen,-58,122));
    run(button.querySelector(":scope > .glass-hover-face-flash"),e.faceFlash,fadeSpec(e.faceFlash));
    activeAnimations.set(host,running);
  }

  function stopReplay(host){
    const timer=replayTimers.get(host);
    if(timer)clearInterval(timer);
    replayTimers.delete(host);
  }

  function bindHover(host,button){
    if(button.dataset.glassHoverBound==="1")return;
    button.dataset.glassHoverBound="1";
    button.addEventListener("mouseenter",()=>{
      play(host);
      stopReplay(host);
      if(SETTINGS.autoReplay){
        replayTimers.set(host,setInterval(()=>{
          if(button.matches(":hover"))play(host);
          else stopReplay(host);
        },SETTINGS.intervalSec*1000));
      }
    });
    button.addEventListener("mouseleave",()=>stopReplay(host));
  }

  function bindTap(host,button){
    if(button.dataset.glassTapBound==="1")return;
    button.dataset.glassTapBound="1";
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
    if(button.dataset.glassResizeBound==="1")return;
    button.dataset.glassResizeBound="1";
    if("ResizeObserver" in window)new ResizeObserver(()=>syncRim(host)).observe(button);
  }

  function ensureButtonLayers(button){
    let changed=false;
    if(!button.querySelector(":scope > .glass-inner-stack.bottom")){button.prepend(stack("bottom"));changed=true}
    if(!button.querySelector(":scope > .glass-inner-stack.top")){button.prepend(stack("top"));changed=true}
    if(!button.querySelector(":scope > .glass-hover-face-flash")){button.prepend(makeFace("glass-hover-face-flash"));changed=true}
    if(!button.querySelector(":scope > .glass-hover-face-sheen")){button.prepend(makeFace("glass-hover-face-sheen"));changed=true}
    return changed;
  }

  function ensurePauseIcon(button){
    if(button.id!=="pause"||button.querySelector(":scope > .pause-white-icon"))return;
    const state=button.getAttribute("aria-label")==="再生を再開"?"play":"pause";
    if(globalThis.DruMasterPauseIcon?.render)globalThis.DruMasterPauseIcon.render(state);
    else{
      const icon=document.createElement("span");
      icon.className="pause-white-icon";
      icon.setAttribute("aria-hidden","true");
      button.appendChild(icon);
      button.dataset.transportIcon=state;
    }
  }

  function ensureWrap(button){
    let wrap=button.parentElement?.classList?.contains("glass-hover-wrap")?button.parentElement:null;
    if(!wrap){
      wrap=document.createElement("span");
      wrap.className="glass-hover-wrap";
      const parent=button.parentNode;
      if(!parent)return null;
      parent.insertBefore(wrap,button);
      wrap.appendChild(button);
    }
    if(button.id==="start")wrap.classList.add("start-wrap");
    wrap.style.setProperty("--spectral-angle",SETTINGS.spectralAngle);
    if(!wrap.querySelector(":scope > .glass-hover-drop")){
      const glow=document.createElement("i");
      glow.className="glass-hover-drop";
      wrap.insertBefore(glow,button);
    }

    if(mobile){
      const oldOuter=wrap.querySelector(":scope > .glass-hover-rim-svg");
      if(oldOuter)oldOuter.remove();
      if(!button.querySelector(":scope > .glass-hover-rim-svg"))button.appendChild(makeRim());
    }else if(!wrap.querySelector(":scope > .glass-hover-rim-svg")){
      wrap.appendChild(makeRim());
    }
    return wrap;
  }

  function repair(button,bind=true){
    if(!button||!button.matches?.(SELECTOR))return;
    ensureButtonLayers(button);
    ensurePauseIcon(button);
    button.dataset.glassHoverFinal="1";

    let host;
    if(button.id==="pause"){
      button.classList.add("glass-hover-inline");
      button.style.setProperty("--spectral-angle",SETTINGS.spectralAngle);
      if(!button.querySelector(":scope > .glass-hover-rim-svg"))button.appendChild(makeRim());
      host=button;
    }else{
      host=ensureWrap(button);
      if(!host)return;
    }

    syncRim(host);
    if(bind){
      desktop?bindHover(host,button):bindTap(host,button);
      observeSize(host,button);
    }
  }

  function scan(root=document){
    if(root.matches?.(SELECTOR))repair(root);
    root.querySelectorAll?.(SELECTOR).forEach(button=>repair(button));
  }

  scan();

  let repairQueued=false;
  const pending=new Set();
  const queueRepair=button=>{
    if(!button||!button.matches?.(SELECTOR))return;
    pending.add(button);
    if(repairQueued)return;
    repairQueued=true;
    queueMicrotask(()=>{
      repairQueued=false;
      for(const b of pending)if(b.isConnected)repair(b);
      pending.clear();
    });
  };

  new MutationObserver(records=>{
    for(const record of records){
      const target=record.target?.nodeType===1?record.target:null;
      const targetButton=target?.matches?.(SELECTOR)?target:target?.closest?.(SELECTOR);
      if(targetButton)queueRepair(targetButton);
      for(const node of record.addedNodes){
        if(node.nodeType!==1)continue;
        if(node.matches?.(SELECTOR))queueRepair(node);
        node.querySelectorAll?.(SELECTOR).forEach(queueRepair);
      }
    }
  }).observe(document.documentElement,{childList:true,subtree:true});
})();