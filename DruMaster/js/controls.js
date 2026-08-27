"use strict";

(()=>{
  const PERFECT_WINDOW=.035;

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
  if(stage&&kickFx&&kickFx.parentElement!==stage)stage.appendChild(kickFx);

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
    KeyY:{part:"crash",side:"right",label:"Y"},
    KeyU:{part:"crash",side:"right",label:"U"},
    KeyI:{part:"crash",side:"right",label:"I"},
    KeyO:{part:"crash",side:"right",label:"O"},
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

  function nearestPartNote(part,t,maxDelta=.16){
    const search=globalThis.DruMasterNoteSearch;
    if(search?.nearest){
      return search.nearest(notes,t,maxDelta,n=>!n.hit&&n.type!=="kick"&&PART[n.type]===part);
    }
    let best=null,delta=maxDelta+1e-9;
    for(const n of notes){
      if(n.time<t-maxDelta)continue;
      if(n.time>t+maxDelta)break;
      if(n.hit||n.type==="kick"||PART[n.type]!==part)continue;
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
            type=matched?best.type:DEFAULT_TYPE[part],
            note=matched?best.note:DEFAULT_NOTE[type];
      playDrum(note,type,vel);
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
      showJudge(label);
    };
  }

  const heldCodes=new Set();
  const isDesktop=()=>!!globalThis.matchMedia?.("(hover:hover) and (pointer:fine)")?.matches;

  /* Capture phase deliberately supersedes app.js's old one-key map.
     Escape is the PC pause/resume shortcut; Space remains intentionally unused. */
  addEventListener("keydown",e=>{
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
