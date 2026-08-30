"use strict";

(()=>{
  const PERFECT_WINDOW=.035;
  const CYMBAL_PARTS=new Set(["crash","crash2","ride","splash"]);
  const CYMBAL_SOUNDS={
    crash:{type:"crash",note:49},
    crash2:{type:"crash2",note:57},
    ride:{type:"ride",note:51},
    splash:{type:"splash",note:55}
  };

  /* MIDI 55 is the GM Splash Cymbal sample already present in drumsound.wav. */
  try{if(typeof DEFAULT_NOTE!=="undefined")DEFAULT_NOTE.splash=55}catch{}
  try{if(typeof DEFAULT_TYPE!=="undefined")DEFAULT_TYPE.splash="splash"}catch{}
  try{if(typeof DRUM_GAIN!=="undefined")DRUM_GAIN.splash=1.2}catch{}

  /* Scoring rules: drums/toms are emphasized; hi-hat now has the same 1.0
     base weight as cymbals/ride. Scores are accumulated as raw points rather
     than normalized to a fixed maximum. */
  if(typeof weight==="function"){
    weight=function(t){return ["snare","highTom","midTom","floorTom"].includes(t)?1.5:1};
  }

  /* Keep artwork and hit targets in one transform space. */
  const kit=document.querySelector("#kit");
  if(kit&&!kit.querySelector(":scope > .kit-stage")){
    const stage=document.createElement("div");
    stage.className="kit-stage";
    while(kit.firstChild)stage.appendChild(kit.firstChild);
    kit.appendChild(stage);
  }
  const stage=kit?.querySelector(":scope > .kit-stage"),kickFx=document.querySelector("#kickFx");
  if(stage&&!stage.querySelector(":scope > .kit-art-plane")){
    const plane=document.createElement("div");
    plane.className="kit-art-plane";
    const bass=stage.querySelector(":scope > .bass-drum-art");
    const art=stage.querySelector(":scope > .kit-art");
    stage.insertBefore(plane,bass||art||stage.firstChild);
    if(bass)plane.appendChild(bass);
    if(art)plane.appendChild(art);
  }
  const plane=stage?.querySelector(":scope > .kit-art-plane");
  if(plane&&!plane.querySelector(":scope > .splash-cymbal-art")){
    const splashArt=document.createElement("img");
    splashArt.className="splash-cymbal-art";
    splashArt.src="assets/splash-cymbal.svg?v=20260830-prod2";
    splashArt.alt="";
    const art=plane.querySelector(":scope > .kit-art");
    plane.insertBefore(splashArt,art||plane.firstChild);
  }
  if(stage&&kickFx&&kickFx.parentElement!==stage)stage.appendChild(kickFx);

  /* Splash gets its own physical hit target while chart judgement treats all
     crash/ride/splash targets as the same cymbal family. */
  const hitLayer=stage?.querySelector("#hitLayer");
  let splashHit=hitLayer?.querySelector('[data-part="splash"]')||null;
  if(hitLayer&&!splashHit){
    splashHit=document.createElement("button");
    splashHit.type="button";
    splashHit.className="hit splash";
    splashHit.dataset.part="splash";
    splashHit.setAttribute("aria-label","Splash cymbal");
    hitLayer.appendChild(splashHit);
  }
  if(typeof setKit==="function"){
    const originalSetKit=setKit;
    setKit=function(){
      const value=originalSetKit();
      splashHit?.classList.remove("inactive");
      return value;
    };
  }
  splashHit?.classList.remove("inactive");

  /* Registered before touch-capability.js, so tapping the visible splash keeps
     the splash timbre even in anywhere-touch mode. */
  document.addEventListener("pointerdown",e=>{
    const el=e.target.closest?.('#hitLayer .hit[data-part="splash"]:not(.inactive)');
    if(!el)return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if(typeof input==="function")input("splash",el);
  },true);

  /* Expanded PC bindings: nearby keys can strike the same drum/cymbal. */
  const KEY_BINDINGS={
    KeyA:{part:"hh",label:"A"},
    KeyS:{part:"hh",label:"S"},
    KeyZ:{part:"snare",label:"Z"},
    KeyX:{part:"snare",label:"X"},
    KeyC:{part:"snare",label:"C"},
    KeyW:{part:"crash",side:"left",label:"W"},
    KeyE:{part:"crash",side:"left",label:"E"},
    KeyR:{part:"crash",side:"left",label:"R"},
    KeyT:{part:"crash",side:"left",label:"T"},
    KeyD:{part:"highTom",label:"D"},
    KeyF:{part:"highTom",label:"F"},
    KeyG:{part:"midTom",label:"G"},
    KeyH:{part:"midTom",label:"H"},
    KeyB:{part:"floorTom",label:"B"},
    KeyN:{part:"floorTom",label:"N"},
    KeyM:{part:"floorTom",label:"M"},
    KeyY:{part:"crash2",side:"right",label:"Y"},
    KeyU:{part:"crash2",side:"right",label:"U"},
    KeyI:{part:"crash2",side:"right",label:"I"},
    KeyO:{part:"crash2",side:"right",label:"O"},
    KeyJ:{part:"ride",label:"J"},
    KeyK:{part:"ride",label:"K"}
  };

  function visualForBinding(binding){
    if(!binding)return null;
    if(binding.part==="crash"&&binding.side){
      return document.querySelector(`#hitLayer .crash.${binding.side}:not(.inactive)`);
    }
    return document.querySelector(`#hitLayer [data-part="${binding.part}"]:not(.inactive)`);
  }

  function setBadge(el,labels){
    if(!el)return;
    el.querySelectorAll(":scope > kbd,:scope > .key-badges").forEach(n=>n.remove());
    if(!labels.length)return;
    const box=document.createElement("div");
    box.className="key-badges";
    for(const label of labels){
      const k=document.createElement("kbd");
      k.textContent=label;
      box.appendChild(k);
    }
    el.appendChild(box);
  }

  function installBadges(){
    setBadge(document.querySelector('#hitLayer [data-part="hh"]'),["A","S"]);
    setBadge(document.querySelector('#hitLayer [data-part="snare"]'),["Z","X","C"]);
    setBadge(document.querySelector("#hitLayer .crash.left"),["W","E","R","T"]);
    setBadge(document.querySelector('#hitLayer [data-part="highTom"]'),["D","F"]);
    setBadge(document.querySelector('#hitLayer [data-part="midTom"]'),["G","H"]);
    setBadge(document.querySelector('#hitLayer [data-part="floorTom"]'),["B","N","M"]);
    setBadge(document.querySelector("#hitLayer .crash.right"),["Y","U","I","O"]);
    setBadge(document.querySelector('#hitLayer [data-part="ride"]'),["J","K"]);
  }
  installBadges();

  function noteMatchesPart(part,n){
    const notePart=PART[n.type];
    return CYMBAL_PARTS.has(part)?CYMBAL_PARTS.has(notePart):notePart===part;
  }

  function nearestPartNote(part,t,maxDelta=.16){
    const search=globalThis.DruMasterNoteSearch;
    if(search?.nearest){
      return search.nearest(notes,t,maxDelta,n=>!n.hit&&n.type!=="kick"&&noteMatchesPart(part,n));
    }
    let best=null,delta=maxDelta+1e-9;
    for(const n of notes){
      if(n.time<t-maxDelta)continue;
      if(n.time>t+maxDelta)break;
      if(n.hit||n.type==="kick"||!noteMatchesPart(part,n))continue;
      const d=Math.abs(n.time-t);if(d<delta){best=n;delta=d}
    }
    return best?{note:best,delta}:null;
  }

  /* Production judgement override. GREAT/GOOD windows remain unchanged. */
  if(typeof input==="function"&&typeof notes!=="undefined"&&typeof PART!=="undefined"){
    input=function(part,visualEl){
      if(!running||paused||autoplay)return;
      const t=current(),match=nearestPartNote(part,t,.16),best=match?.note||null,delta=match?.delta??Infinity;
      const matched=!!best,
            vel=matched?best.velocity/127:.72,
            chartType=matched?best.type:DEFAULT_TYPE[part],
            chartNote=matched?best.note:DEFAULT_NOTE[chartType],
            physical=CYMBAL_SOUNDS[part];
      if(physical)playDrum(physical.note,physical.type,vel);
      else playDrum(chartNote,chartType,vel);
      flashPart(part,visualEl);
      if(!matched)return;

      best.hit=true;
      let mult,label;
      if(delta<=PERFECT_WINDOW){
        mult=1;label="PERFECT";counts.perfect++;
      }else if(delta<=.105){
        mult=.75;label="GREAT";counts.great++;
      }else{
        mult=.4;label="GOOD";counts.good++;
      }
      score+=weight(best.type)*best.velocity/127*1000*mult;
      $("#score").textContent=String(Math.round(score)).padStart(6,"0");
      if(part==="splash"&&globalThis.DruMasterJudgement?.emitForNote){
        globalThis.DruMasterJudgement.emitForNote(best,label,{flash:false});
      }else{
        showJudge(label);
      }
    };
  }

  const heldCodes=new Set();
  const isDesktop=()=>!!globalThis.matchMedia?.("(hover:hover) and (pointer:fine)")?.matches;

  function playKeyboardKick(){
    let isRunning=false,isPaused=true;
    try{
      isRunning=typeof running!=="undefined"&&running;
      isPaused=typeof paused!=="undefined"&&paused;
    }catch{}
    if(!isRunning||isPaused||typeof playDrum!=="function")return false;
    try{
      const note=typeof DEFAULT_NOTE!=="undefined"&&DEFAULT_NOTE.kick||36;
      playDrum(note,"kick",.72);
      if(kickFx){
        kickFx.classList.remove("hit");
        void kickFx.offsetWidth;
        kickFx.classList.add("hit");
      }
      return true;
    }catch{return false}
  }

  /* Capture phase deliberately supersedes app.js's old one-key map.
     Escape is the PC pause/resume shortcut. Space starts from setup and
     becomes a manual bass-drum trigger while the performance is running. */
  addEventListener("keydown",e=>{
    if(e.code==="Space"){
      if(!isDesktop()||e.repeat)return;
      const setup=document.querySelector("#setup"),
            start=document.querySelector("#start"),
            setupVisible=!!setup&&!setup.classList.contains("hidden");
      if(setupVisible){
        if(!start||start.disabled)return;
        e.preventDefault();
        e.stopImmediatePropagation();
        start.click();
        return;
      }
      if(playKeyboardKick()){
        e.preventDefault();
        e.stopImmediatePropagation();
      }
      return;
    }

    if(e.code==="Escape"){
      if(!isDesktop()||e.repeat)return;
      let isRunning=false;
      try{isRunning=typeof running!=="undefined"&&running}catch{}
      if(!isRunning)return;
      e.preventDefault();
      e.stopImmediatePropagation();
      try{if(typeof togglePause==="function")void togglePause()}catch{}
      return;
    }

    const binding=KEY_BINDINGS[e.code];
    if(!binding)return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if(e.repeat||heldCodes.has(e.code))return;
    const el=visualForBinding(binding);
    if(!el)return;
    heldCodes.add(e.code);
    el.classList.add("pressed");
    if(typeof input==="function")input(binding.part,el);
  },true);

  addEventListener("keyup",e=>{
    const binding=KEY_BINDINGS[e.code];
    if(!binding)return;
    e.preventDefault();
    e.stopImmediatePropagation();
    heldCodes.delete(e.code);
    const el=visualForBinding(binding);
    if(!el)return;
    const stillHeld=[...heldCodes].some(code=>visualForBinding(KEY_BINDINGS[code])===el);
    if(!stillHeld)el.classList.remove("pressed");
  },true);
})();
