"use strict";

(()=>{
  const button=document.querySelector("#pause");
  const panel=document.querySelector("#pausePanel");
  if(!button||!panel)return;

  function render(state){
    /* Remove every legacy transport source without touching hover layers. */
    for(const node of [...button.childNodes]){
      if(node.nodeType===Node.TEXT_NODE)node.remove();
    }
    button.querySelectorAll(":scope > .pause-transport-icon").forEach(node=>node.remove());
    let icon=button.querySelector(":scope > .pause-css-icon");
    if(!icon){
      icon=document.createElement("span");
      icon.className="pause-css-icon";
      icon.setAttribute("aria-hidden","true");
      icon.append(document.createElement("i"),document.createElement("i"));
      button.appendChild(icon);
    }
    button.dataset.transportIcon=state;
  }

  globalThis.DruMasterPauseIcon={render};

  render("pause");
  button.setAttribute("aria-label","一時停止");

  /* Keep pause state changes free of font glyphs and inline SVG. */
  togglePause=async function(forceResume=false){
    if(!running)return;
    if(!paused&&!forceResume){
      paused=true;
      cancelAnimationFrame(raf);
      await ac.suspend();
      panel.classList.remove("hidden");
      render("play");
      button.setAttribute("aria-label","再生を再開");
    }else{
      await ac.resume();
      paused=false;
      panel.classList.add("hidden");
      render("pause");
      button.setAttribute("aria-label","一時停止");
      loop();
    }
  };

  /* Load the finalized PC-only hover enhancer after the transport SVG setup. */
  const s=document.createElement("script");
  s.src="js/glass-hover-final.js?v=20260828-mobiletap1";
  document.body.appendChild(s);
})();
