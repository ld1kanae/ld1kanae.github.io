"use strict";

(()=>{
  const button=document.querySelector("#pause");
  const panel=document.querySelector("#pausePanel");
  if(!button||!panel)return;

  function makeIcon(){
    const icon=document.createElement("span");
    icon.className="pause-white-icon";
    icon.setAttribute("aria-hidden","true");
    return icon;
  }

  function render(state){
    for(const node of [...button.childNodes]){
      if(node.nodeType===Node.TEXT_NODE)node.remove();
    }
    button.querySelectorAll(":scope > .transport-icon,:scope > .pause-transport-icon,:scope > .pause-css-icon").forEach(node=>node.remove());
    if(!button.querySelector(":scope > .pause-white-icon"))button.appendChild(makeIcon());
    button.dataset.transportIcon=state;
  }

  globalThis.DruMasterPauseIcon={render};

  render("pause");
  button.setAttribute("aria-label","一時停止");

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

  const s=document.createElement("script");
  s.src="js/glass-hover-final.js?v=20260828-hoverfullrestore1";
  document.body.appendChild(s);
})();
