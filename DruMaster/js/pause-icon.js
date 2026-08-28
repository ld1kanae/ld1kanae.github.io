"use strict";

(()=>{
  const button=document.querySelector("#pause");
  const panel=document.querySelector("#pausePanel");
  if(!button||!panel)return;

  function makeIcon(){
    const ns="http://www.w3.org/2000/svg";
    const svg=document.createElementNS(ns,"svg");
    svg.setAttribute("class","pause-white-icon");
    svg.setAttribute("viewBox","0 0 18 18");
    svg.setAttribute("aria-hidden","true");
    svg.setAttribute("focusable","false");
    svg.setAttribute("fill","#fff");

    const pauseGroup=document.createElementNS(ns,"g");
    pauseGroup.setAttribute("class","pause-shape");
    pauseGroup.setAttribute("fill","#fff");
    for(const x of [2,12]){
      const rect=document.createElementNS(ns,"rect");
      rect.setAttribute("x",String(x));
      rect.setAttribute("y","1");
      rect.setAttribute("width","4");
      rect.setAttribute("height","16");
      rect.setAttribute("rx","1.5");
      rect.setAttribute("fill","#fff");
      pauseGroup.appendChild(rect);
    }
    svg.appendChild(pauseGroup);

    const play=document.createElementNS(ns,"path");
    play.setAttribute("class","play-shape");
    play.setAttribute("d","M4 1.5v15L16 9z");
    play.setAttribute("fill","#fff");
    svg.appendChild(play);
    return svg;
  }

  function ensureSvg(){
    let icon=button.querySelector(":scope > .pause-white-icon");
    if(icon?.namespaceURI!=="http://www.w3.org/2000/svg"){
      const fresh=makeIcon();
      if(icon)icon.replaceWith(fresh);else button.appendChild(fresh);
      icon=fresh;
    }
    return icon;
  }

  function render(state){
    for(const node of [...button.childNodes]){
      if(node.nodeType===Node.TEXT_NODE)node.remove();
    }
    button.querySelectorAll(":scope > .transport-icon,:scope > .pause-transport-icon,:scope > .pause-css-icon").forEach(node=>node.remove());
    ensureSvg();
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
