"use strict";

(()=>{
  const PERFECT_WINDOW=.035;

  /* Keep artwork and hit targets in one transform space. */
  const kit=document.querySelector("#kit");
  if(kit&&!kit.querySelector(":scope > .kit-stage")){
    const stage=document.createElement("div");
    stage.className="kit-stage";
    while(kit.firstChild)stage.appendChild(kit.firstChild);
    kit.appendChild(stage);
  }

  /* Two keys per playable timbre for two-hand PC drumming.
     Crash uses the physical left/right cymbal buttons; other timbres share one pad. */
  const KEY_BINDINGS={
    KeyQ:{part:"crash",side:"left",label:"Q"},
    KeyP:{part:"crash",side:"right",label:"P"},
    KeyW:{part:"highTom",label:"W"},
    KeyO:{part:"highTom",label:"O"},
    KeyE:{part:"midTom",label:"E"},
    KeyI:{part:"midTom",label:"I"},
    KeyR:{part:"special",label:"R"},
    KeyU:{part:"special",label:"U"},
    KeyA:{part:"hh",label:"A"},
    KeyS:{part:"hh",label:"S"},
    KeyD:{part:"snare",label:"D"},
    KeyF:{part:"snare",label:"F"},
    KeyJ:{part:"floorTom",label:"J"},
    KeyK:{part:"floorTom",label:"K"},
    KeyL:{part:"ride",label:"L"},
    Semicolon:{part:"ride",label:";"}
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
    setBadge(document.querySelector("#hitLayer .crash.left"),["Q"]);
    setBadge(document.querySelector("#hitLayer .crash.right"),["P"]);
    setBadge(document.querySelector('#hitLayer [data-part="highTom"]'),["W","O"]);
    setBadge(document.querySelector('#hitLayer [data-part="midTom"]'),["E","I"]);
    setBadge(document.querySelector('#hitLayer [data-part="special"]'),["R","U"]);
    setBadge(document.querySelector('#hitLayer [data-part="hh"]'),["A","S"]);
    setBadge(document.querySelector('#hitLayer [data-part="snare"]'),["D","F"]);
    setBadge(document.querySelector('#hitLayer [data-part="floorTom"]'),["J","K"]);
    setBadge(document.querySelector('#hitLayer [data-part="ride"]'),["L",";"]);
  }
  installBadges();

  /* Production judgement override. GREAT/GOOD windows remain unchanged. */
  if(typeof input==="function"&&typeof notes!=="undefined"&&typeof PART!=="undefined"){
    input=function(part,visualEl){
      if(!running||paused||autoplay)return;
      const t=current();
      let best=null,delta=Infinity;
      for(const n of notes){
        if(n.hit||PART[n.type]!==part||n.type==="kick")continue;
        const d=Math.abs(n.time-t);
        if(d<delta){best=n;delta=d}
        if(n.time>t+.16)break;
      }
      const matched=best&&delta<=.16,
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
      $("#score").textContent=String(Math.round(score/maxScore*1000000)).padStart(6,"0");
      showJudge(label);
    };
  }

  const heldCodes=new Set();

  /* Capture phase deliberately supersedes app.js's old one-key map. */
  addEventListener("keydown",e=>{
    if(e.code==="Space"){
      if(e.repeat)return;
      const tag=e.target?.tagName;
      if(tag==="INPUT"||tag==="TEXTAREA"||tag==="SELECT")return;
      if(typeof togglePause!=="function")return;
      e.preventDefault();
      e.stopImmediatePropagation();
      togglePause();
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
