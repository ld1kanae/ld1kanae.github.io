"use strict";
(()=>{
  const demo=document.querySelector("#demo");
  const controlsRoot=document.querySelector("#elementControls");
  const replay=document.querySelector("#replay");
  const autoReplay=document.querySelector("#autoReplay");
  const interval=document.querySelector("#interval");
  const intervalOut=document.querySelector("#intervalOut");
  const angle=document.querySelector("#spectralAngle");
  const angleOut=document.querySelector("#angleOut");
  const copy=document.querySelector("#copySettings");
  const copyStatus=document.querySelector("#copyStatus");
  if(!demo||!controlsRoot)return;

  const defs=[
    {id:"rimRun1",name:"輪郭を走る1",desc:"輪郭上を走る細い光。開始位置0/100",selector:".fx-rim-run-1",kind:"rim",base:1000,start:0,travel:-100,opacity:1,speed:100,fadeIn:160,fadeOut:240,delay:0,on:true},
    {id:"rimRun2",name:"輪郭を走る2",desc:"1の正反対。開始位置50/100",selector:".fx-rim-run-2",kind:"rim",base:1000,start:-50,travel:-100,opacity:1,speed:100,fadeIn:160,fadeOut:240,delay:0,on:true},
    {id:"edge1",name:"短い縁光1",desc:"短いエッジグリント。開始位置0/100",selector:".fx-edge-glint-1",kind:"edge",base:850,start:0,travel:-55,opacity:1,speed:100,fadeIn:150,fadeOut:180,delay:0,on:false},
    {id:"edge2",name:"短い縁光2",desc:"1の正反対。開始位置50/100",selector:".fx-edge-glint-2",kind:"edge",base:850,start:-50,travel:-55,opacity:1,speed:100,fadeIn:150,fadeOut:180,delay:0,on:false},
    {id:"faceSheen",name:"細い斜めの光帯",desc:"面を斜めに横切る広めの反射",selector:".fx-face-sheen",kind:"faceSheen",base:720,opacity:.9,speed:20,fadeIn:260,fadeOut:420,delay:0,on:true},
    {id:"faceFlash",name:"面全体フラッシュ",desc:"面全体を乳白色に持ち上げる",selector:".fx-face-flash",kind:"flash",base:660,opacity:.72,speed:100,fadeIn:120,fadeOut:380,delay:0,on:false},
    {id:"faceLine",name:"細い面反射",desc:"より細く鋭い斜めの光線",selector:".fx-face-line",kind:"faceLine",base:520,opacity:1,speed:20,fadeIn:180,fadeOut:300,delay:0,on:false},
    {id:"rimPulse",name:"輪郭全体フラッシュ",desc:"輪郭全体を一瞬だけ白く発光",selector:".fx-rim-pulse",kind:"pulse",base:520,opacity:1,speed:100,fadeIn:100,fadeOut:360,delay:0,on:false}
  ];

  const state={};
  const running=[];

  function field(def,key,label,min,max,step,unit=""){
    const id=`${def.id}-${key}`;
    return `<label class="field"><span>${label}</span><output data-out="${id}"></output><input id="${id}" data-id="${def.id}" data-key="${key}" type="range" min="${min}" max="${max}" step="${step}" value="${def[key]}"></label>`;
  }

  function build(){
    controlsRoot.innerHTML=defs.map(def=>`<article class="element-card" data-card="${def.id}">
      <label class="element-title"><input id="${def.id}-on" data-id="${def.id}" data-key="on" type="checkbox" ${def.on?"checked":""}><span><strong>${def.name}</strong><small>${def.desc}</small></span></label>
      ${field(def,"opacity","最大透明度",0,1,.01)}
      ${field(def,"speed","速度",10,200,5,"%")}
      ${field(def,"fadeIn","Fade In",0,2000,50,"ms")}
      ${field(def,"fadeOut","Fade Out",0,2500,50,"ms")}
      ${field(def,"delay","開始Delay",0,2500,50,"ms")}
    </article>`).join("");

    for(const def of defs){
      state[def.id]={...def};
      for(const key of ["opacity","speed","fadeIn","fadeOut","delay"]){
        const input=document.querySelector(`#${def.id}-${key}`);
        const out=document.querySelector(`[data-out="${def.id}-${key}"]`);
        const unit=key==="speed"?"%":(key==="opacity"?"":"ms");
        const sync=()=>{state[def.id][key]=Number(input.value);out.textContent=`${input.value}${unit}`};
        input.addEventListener("input",sync);sync();
      }
      const on=document.querySelector(`#${def.id}-on`);
      on.addEventListener("change",()=>{state[def.id].on=on.checked});
    }
  }

  function timing(s){
    const duration=Math.max(80,s.base*(100/Math.max(1,s.speed)));
    let fi=Math.max(0,s.fadeIn),fo=Math.max(0,s.fadeOut);
    const maxFade=duration*.9;
    if(fi+fo>maxFade){const k=maxFade/(fi+fo||1);fi*=k;fo*=k}
    return {duration,fi,fo,inOff:fi/duration,outOff:1-fo/duration};
  }

  function fadeMoveFrames(s,from,to){
    const t=timing(s),max=s.opacity;
    const at=p=>from+(to-from)*p;
    return {timing:t,frames:[
      {opacity:0,left:`${from}%`,offset:0},
      {opacity:max,left:`${at(t.inOff)}%`,offset:t.inOff},
      {opacity:max,left:`${at(t.outOff)}%`,offset:t.outOff},
      {opacity:0,left:`${to}%`,offset:1}
    ]};
  }

  function fadeStrokeFrames(s){
    const t=timing(s),max=s.opacity;
    const start=s.start,end=s.start+s.travel;
    const at=p=>start+(end-start)*p;
    return {timing:t,frames:[
      {opacity:0,strokeDashoffset:start,offset:0},
      {opacity:max,strokeDashoffset:at(t.inOff),offset:t.inOff},
      {opacity:max,strokeDashoffset:at(t.outOff),offset:t.outOff},
      {opacity:0,strokeDashoffset:end,offset:1}
    ]};
  }

  function fadeOnlyFrames(s){
    const t=timing(s),max=s.opacity;
    return {timing:t,frames:[
      {opacity:0,offset:0},
      {opacity:max,offset:t.inOff},
      {opacity:max,offset:t.outOff},
      {opacity:0,offset:1}
    ]};
  }

  function animateOne(s){
    if(!s.on)return;
    const el=demo.querySelector(s.selector);if(!el)return;
    let spec;
    if(s.kind==="rim"||s.kind==="edge")spec=fadeStrokeFrames(s);
    else if(s.kind==="faceSheen")spec=fadeMoveFrames(s,-58,122);
    else if(s.kind==="faceLine")spec=fadeMoveFrames(s,-32,116);
    else spec=fadeOnlyFrames(s);
    const anim=el.animate(spec.frames,{duration:spec.timing.duration,delay:s.delay,easing:"linear",fill:"both"});
    running.push(anim);
  }

  function play(){
    while(running.length){try{running.pop().cancel()}catch{}}
    for(const def of defs)animateOne(state[def.id]);
  }

  let timer=0;
  function restartAuto(){
    clearInterval(timer);timer=0;
    if(autoReplay.checked)timer=setInterval(play,Number(interval.value)*1000);
  }

  angle.addEventListener("input",()=>{demo.style.setProperty("--spectral-angle",`${angle.value}deg`);angleOut.textContent=`${angle.value}°`});
  interval.addEventListener("input",()=>{intervalOut.textContent=`${Number(interval.value).toFixed(1)}s`;restartAuto()});
  autoReplay.addEventListener("change",restartAuto);
  replay.addEventListener("click",play);

  function payload(){
    const data={spectralAngle:`${angle.value}deg`,autoReplay:autoReplay.checked,intervalSec:Number(interval.value),oppositePairOffset:"50/100",elements:{}};
    for(const def of defs){const s=state[def.id];data.elements[def.id]={enabled:s.on,opacity:s.opacity,speedPercent:s.speed,fadeInMs:s.fadeIn,fadeOutMs:s.fadeOut,delayMs:s.delay}}
    return `DruMaster hover animation settings\n${JSON.stringify(data,null,2)}`;
  }
  copy.addEventListener("click",async()=>{
    const text=payload();
    try{await navigator.clipboard.writeText(text);copyStatus.textContent="コピーしました"}
    catch{const ta=document.createElement("textarea");ta.value=text;document.body.appendChild(ta);ta.select();document.execCommand("copy");ta.remove();copyStatus.textContent="コピーしました"}
    setTimeout(()=>copyStatus.textContent="",1800);
  });

  build();
  angle.dispatchEvent(new Event("input"));
  interval.dispatchEvent(new Event("input"));
  setTimeout(play,400);
})();