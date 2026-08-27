"use strict";
(()=>{
  const demo=document.querySelector("#demo"), replay=document.querySelector("#replay"), autoReplay=document.querySelector("#autoReplay"), interval=document.querySelector("#interval"), intervalOut=document.querySelector("#intervalOut"), angle=document.querySelector("#spectralAngle"), angleOut=document.querySelector("#angleOut"), copy=document.querySelector("#copySettings"), copyStatus=document.querySelector("#copyStatus");
  if(!demo)return;

  const defs={
    rimRun1:{selector:".fx-rim-run-1",kind:"rim",base:1000,start:0},
    rimRun2:{selector:".fx-rim-run-2",kind:"rim",base:1000,start:-50},
    edge1:{selector:".fx-edge-glint-1",kind:"edge",base:850,start:0,travel:-55},
    edge2:{selector:".fx-edge-glint-2",kind:"edge",base:850,start:-50,travel:-55},
    faceSheen:{selector:".fx-face-sheen",kind:"faceSheen",base:720},
    faceFlash:{selector:".fx-face-flash",kind:"flash",base:660},
    faceLine:{selector:".fx-face-line",kind:"faceLine",base:520},
    rimPulse:{selector:".fx-rim-pulse",kind:"pulse",base:520}
  };
  const running=[];
  let timer=0;

  function n(id){return Number(document.querySelector(`#${id}`)?.value||0)}
  function checked(id){return !!document.querySelector(`#${id}`)?.checked}
  function syncOutput(id,unit=""){const el=document.querySelector(`#${id}`),out=document.querySelector(`#${id}-out`);if(el&&out)out.textContent=`${el.value}${unit}`}
  const fieldUnits={opacity:"",speed:"%",fadeIn:"ms",fadeOut:"ms",delay:"ms",endAt:"ms",width:"%"};
  for(const id of Object.keys(defs)){
    for(const key of ["opacity","speed","fadeIn","fadeOut","delay","endAt","width"]){
      const el=document.querySelector(`#${id}-${key}`);if(!el)continue;
      const sync=()=>{syncOutput(`${id}-${key}`,fieldUnits[key]);if(id==="faceFlash"&&key==="width")demo.querySelector(".fx-face-flash").style.width=`${el.value}%`};
      el.addEventListener("input",sync);sync();
    }
  }

  function state(id){
    const d=defs[id];
    return {...d,on:checked(`${id}-enabled`),opacity:n(`${id}-opacity`),speed:n(`${id}-speed`),fadeIn:n(`${id}-fadeIn`),fadeOut:n(`${id}-fadeOut`),delay:n(`${id}-delay`),endAt:document.querySelector(`#${id}-endAt`)?n(`${id}-endAt`):null,width:document.querySelector(`#${id}-width`)?n(`${id}-width`):null};
  }

  function standardTiming(s){
    const travelDuration=Math.max(80,s.base*(100/Math.max(1,s.speed)));
    const duration=Math.max(travelDuration,s.fadeIn+s.fadeOut,80);
    const fi=Math.min(s.fadeIn,duration), fo=Math.min(s.fadeOut,Math.max(0,duration-fi));
    return {duration,inOff:fi/duration,outOff:1-fo/duration};
  }
  function rimTiming(s){
    const duration=Math.max(80,s.endAt-s.delay);
    let fi=Math.min(s.fadeIn,duration),fo=Math.min(s.fadeOut,Math.max(0,duration-fi));
    return {duration,inOff:fi/duration,outOff:1-fo/duration};
  }
  function strokeFrames(s,isRim){
    const t=isRim?rimTiming(s):standardTiming(s);
    const start=s.start;
    let end;
    if(isRim){const lap=s.base*(100/Math.max(1,s.speed));end=start-100*(t.duration/lap)}
    else end=start+s.travel;
    const at=p=>start+(end-start)*p;
    return {t,frames:[{opacity:0,strokeDashoffset:start,offset:0},{opacity:s.opacity,strokeDashoffset:at(t.inOff),offset:t.inOff},{opacity:s.opacity,strokeDashoffset:at(t.outOff),offset:t.outOff},{opacity:0,strokeDashoffset:end,offset:1}]};
  }
  function moveFrames(s,from,to){
    const t=standardTiming(s),at=p=>from+(to-from)*p;
    return {t,frames:[{opacity:0,left:`${from}%`,offset:0},{opacity:s.opacity,left:`${at(t.inOff)}%`,offset:t.inOff},{opacity:s.opacity,left:`${at(t.outOff)}%`,offset:t.outOff},{opacity:0,left:`${to}%`,offset:1}]};
  }
  function fadeFrames(s){
    const t=standardTiming(s);
    return {t,frames:[{opacity:0,offset:0},{opacity:s.opacity,offset:t.inOff},{opacity:s.opacity,offset:t.outOff},{opacity:0,offset:1}]};
  }
  function animate(id){
    const s=state(id);if(!s.on)return;
    const el=demo.querySelector(s.selector);if(!el)return;
    if(s.kind==="flash"&&s.width!=null)el.style.width=`${s.width}%`;
    let spec;
    if(s.kind==="rim")spec=strokeFrames(s,true);
    else if(s.kind==="edge")spec=strokeFrames(s,false);
    else if(s.kind==="faceSheen")spec=moveFrames(s,-58,122);
    else if(s.kind==="faceLine")spec=moveFrames(s,-32,116);
    else spec=fadeFrames(s);
    running.push(el.animate(spec.frames,{duration:spec.t.duration,delay:s.delay,easing:"linear",fill:"both"}));
  }
  function play(){while(running.length){try{running.pop().cancel()}catch{}}Object.keys(defs).forEach(animate)}
  function restart(){clearInterval(timer);timer=0;if(autoReplay.checked)timer=setInterval(play,Number(interval.value)*1000)}

  angle.addEventListener("input",()=>{demo.style.setProperty("--spectral-angle",`${angle.value}deg`);angleOut.textContent=`${angle.value}°`});
  interval.addEventListener("input",()=>{intervalOut.textContent=`${Number(interval.value).toFixed(1)}s`;restart()});
  autoReplay.addEventListener("change",restart);replay.addEventListener("click",play);

  function payload(){
    const data={spectralAngle:`${angle.value}deg`,autoReplay:autoReplay.checked,intervalSec:Number(interval.value),oppositePairOffset:"50/100",elements:{}};
    for(const id of Object.keys(defs)){
      const s=state(id),item={enabled:s.on,opacity:s.opacity,speedPercent:s.speed,fadeInMs:s.fadeIn,fadeOutMs:s.fadeOut,delayMs:s.delay};
      if(s.endAt!=null)item.endAtMs=s.endAt;if(s.width!=null)item.widthPercent=s.width;data.elements[id]=item;
    }
    return `DruMaster hover animation settings\n${JSON.stringify(data,null,2)}`;
  }
  copy.addEventListener("click",async()=>{const text=payload();try{await navigator.clipboard.writeText(text);copyStatus.textContent="コピーしました"}catch{const ta=document.createElement("textarea");ta.value=text;document.body.appendChild(ta);ta.select();document.execCommand("copy");ta.remove();copyStatus.textContent="コピーしました"}setTimeout(()=>copyStatus.textContent="",1800)});

  angle.dispatchEvent(new Event("input"));interval.dispatchEvent(new Event("input"));setTimeout(play,350);
})();