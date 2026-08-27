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

  /* Defaults reproduce the settings supplied by the user in chat. New fields:
     - rimRun endAt: absolute finish time from replay trigger
     - faceFlash width: horizontal luminous region width */
  const defs=[
    {id:"rimRun1",name:"輪郭を走る1",desc:"輪郭上を走る細い光。開始位置0/100",selector:".fx-rim-run-1",kind:"rim",base:1000,start:0,opacity:.3,speed:150,fadeIn:1300,fadeOut:2500,delay:150,endAt:4000,on:true},
    {id:"rimRun2",name:"輪郭を走る2",desc:"1の正反対。開始位置50/100",selector:".fx-rim-run-2",kind:"rim",base:1000,start:-50,opacity:.3,speed:150,fadeIn:1300,fadeOut:2500,delay:150,endAt:4000,on:true},
    {id:"edge1",name:"短い縁光1",desc:"短いエッジグリント。開始位置0/100",selector:".fx-edge-glint-1",kind:"edge",base:850,start:0,travel:-55,opacity:1,speed:100,fadeIn:150,fadeOut:200,delay:0,on:false},
    {id:"edge2",name:"短い縁光2",desc:"1の正反対。開始位置50/100",selector:".fx-edge-glint-2",kind:"edge",base:850,start:-50,travel:-55,opacity:1,speed:100,fadeIn:150,fadeOut:200,delay:0,on:false},
    {id:"faceSheen",name:"細い斜めの光帯",desc:"面を斜めに横切る広めの反射",selector:".fx-face-sheen",kind:"faceSheen",base:720,opacity:.7,speed:100,fadeIn:1000,fadeOut:1000,delay:0,on:true},
    {id:"faceFlash",name:"面全体フラッシュ",desc:"面全体を乳白色に持ち上げる",selector:".fx-face-flash",kind:"flash",base:660,opacity:.25,speed:100,fadeIn:1000,fadeOut:400,delay:0,width:100,on:true},
    {id:"faceLine",name:"細い面反射",desc:"より細く鋭い斜めの光線",selector:".fx-face-line",kind:"faceLine",base:520,opacity:1,speed:20,fadeIn:200,fadeOut:300,delay:0,on:false},
    {id:"rimPulse",name:"輪郭全体フラッシュ",desc:"輪郭全体を一瞬だけ白く発光",selector:".fx-rim-pulse",kind:"pulse",base:520,opacity:1,speed:100,fadeIn:100,fadeOut:350,delay:0,on:false}
  ];

  const state={};
  const running=[];

  function field(def,key,label,min,max,step){
    const id=`${def.id}-${key}`;
    return `<label class="field"><span>${label}</span><output data-out="${id}"></output><input id="${id}" data-id="${def.id}" data-key="${key}" type="range" min="${min}" max="${max}" step="${step}" value="${def[key]}"></label>`;
  }

  function fieldSpec(def,key){
    if(key==="opacity")return field(def,key,"最大透明度",0,1,.01);
    if(key==="speed")return field(def,key,"速度",10,300,5);
    if(key==="fadeIn")return field(def,key,"Fade In",0,4000,50);
    if(key==="fadeOut")return field(def,key,"Fade Out",0,5000,50);
    if(key==="delay")return field(def,key,"開始Delay",0,5000,50);
    if(key==="endAt")return field(def,key,"終了タイミング",500,10000,100);
    if(key==="width")return field(def,key,"フラッシュ幅",50,300,5);
    return "";
  }

  function unitFor(key){
    if(key==="speed"||key==="width")return "%";
    if(key==="opacity")return "";
    return "ms";
  }

  function build(){
    controlsRoot.innerHTML=defs.map(def=>{
      const keys=["opacity","speed","fadeIn","fadeOut","delay"];
      if(def.kind==="rim")keys.push("endAt");
      if(def.kind==="flash")keys.push("width");
      const extra=keys.length>5?" has-extra":"";
      return `<article class="element-card${extra}" data-card="${def.id}">
        <label class="element-title"><input id="${def.id}-on" data-id="${def.id}" data-key="on" type="checkbox" ${def.on?"checked":""}><span><strong>${def.name}</strong><small>${def.desc}</small></span></label>
        ${keys.map(key=>fieldSpec(def,key)).join("")}
      </article>`;
    }).join("");

    for(const def of defs){
      state[def.id]={...def};
      const keys=["opacity","speed","fadeIn","fadeOut","delay"];
      if(def.kind==="rim")keys.push("endAt");
      if(def.kind==="flash")keys.push("width");
      for(const key of keys){
        const input=document.querySelector(`#${def.id}-${key}`);
        const out=document.querySelector(`[data-out="${def.id}-${key}"]`);
        const sync=()=>{
          state[def.id][key]=Number(input.value);
          out.textContent=`${input.value}${unitFor(key)}`;
          if(def.kind==="flash"&&key==="width"){
            demo.querySelector(def.selector)?.style.setProperty("--flash-width",`${input.value}%`);
          }
        };
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

  function rimTiming(s){
    const duration=Math.max(80,s.endAt-s.delay);
    let fi=Math.max(0,s.fadeIn),fo=Math.max(0,s.fadeOut);
    if(fi+fo>duration){const k=duration/(fi+fo||1);fi*=k;fo*=k}
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

  function rimRunFrames(s){
    const t=rimTiming(s),max=s.opacity;
    const lapDuration=s.base*(100/Math.max(1,s.speed));
    const distance=100*(t.duration/lapDuration);
    const start=s.start,end=start-distance;
    const at=p=>start+(end-start)*p;
    return {timing:t,frames:[
      {opacity:0,strokeDashoffset:start,offset:0},
      {opacity:max,strokeDashoffset:at(t.inOff),offset:t.inOff},
      {opacity:max,strokeDashoffset:at(t.outOff),offset:t.outOff},
      {opacity:0,strokeDashoffset:end,offset:1}
    ]};
  }

  function fadeOnlyFrames(s){
    const baseDuration=Math.max(80,s.base*(100/Math.max(1,s.speed)));
    const duration=Math.max(baseDuration,s.fadeIn+s.fadeOut);
    const fi=Math.min(s.fadeIn,duration),fo=Math.min(s.fadeOut,duration-fi);
    const max=s.opacity;
    return {timing:{duration,inOff:fi/duration,outOff:1-fo/duration},frames:[
      {opacity:0,offset:0},
      {opacity:max,offset:fi/duration},
      {opacity:max,offset:1-fo/duration},
      {opacity:0,offset:1}
    ]};
  }

  function animateOne(s){
    if(!s.on)return;
    const el=demo.querySelector(s.selector);if(!el)return;
    if(s.kind==="flash")el.style.setProperty("--flash-width",`${s.width}%`);
    let spec;
    if(s.kind==="rim")spec=rimRunFrames(s);
    else if(s.kind==="edge")spec=fadeStrokeFrames(s);
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
    for(const def of defs){
      const s=state[def.id];
      const item={enabled:s.on,opacity:s.opacity,speedPercent:s.speed,fadeInMs:s.fadeIn,fadeOutMs:s.fadeOut,delayMs:s.delay};
      if(def.kind==="rim")item.endAtMs=s.endAt;
      if(def.kind==="flash")item.widthPercent=s.width;
      data.elements[def.id]=item;
    }
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