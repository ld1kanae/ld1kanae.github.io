"use strict";

(()=>{
  const button=document.querySelector("#pause");
  const panel=document.querySelector("#pausePanel");
  if(!button||!panel)return;

  const SVG_NS="http://www.w3.org/2000/svg";

  function whiteShape(tag,attrs){
    const node=document.createElementNS(SVG_NS,tag);
    for(const [name,value] of Object.entries(attrs))node.setAttribute(name,value);
    node.setAttribute("fill","#fff");
    node.style.setProperty("fill","#fff","important");
    return node;
  }

  function makeIcon(){
    const svg=document.createElementNS(SVG_NS,"svg");
    svg.setAttribute("class","pause-white-icon");
    svg.setAttribute("viewBox","0 0 18 18");
    svg.setAttribute("aria-hidden","true");
    svg.setAttribute("focusable","false");
    svg.setAttribute("fill","#fff");
    svg.style.setProperty("fill","#fff","important");

    const pause=document.createElementNS(SVG_NS,"g");
    pause.setAttribute("class","pause-shape");
    pause.append(
      whiteShape("rect",{x:"2",y:"1",width:"4",height:"16",rx:"2"}),
      whiteShape("rect",{x:"12",y:"1",width:"4",height:"16",rx:"2"})
    );

    const play=whiteShape("path",{class:"play-shape",d:"M4 1.5v15l12-7.5z"});
    svg.append(pause,play);
    return svg;
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
  s.src="js/glass-hover-final.js?v=20260828-mobiletap2";
  document.body.appendChild(s);
})();
