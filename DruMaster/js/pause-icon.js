"use strict";

(()=>{
  const button=document.querySelector("#pause");
  const panel=document.querySelector("#pausePanel");
  if(!button||!panel)return;

  const iconMarkup=state=>state==="play"
    ? '<svg class="pause-transport-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false" style="color:#eef3f7!important;fill:#eef3f7!important"><path d="M8 5.2c0-.9 1-1.45 1.78-.98l8.35 5.03a3.2 3.2 0 0 1 0 5.5l-8.35 5.03A1.15 1.15 0 0 1 8 18.8V5.2Z" fill="#eef3f7" style="fill:#eef3f7!important"/></svg>'
    : '<svg class="pause-transport-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false" style="color:#eef3f7!important;fill:none!important"><path d="M7.5 5v14M16.5 5v14" fill="none" stroke="#eef3f7" stroke-width="4" stroke-linecap="round" style="fill:none!important;stroke:#eef3f7!important"/></svg>';

  function render(state){
    button.querySelector(":scope > .pause-transport-icon")?.remove();
    button.insertAdjacentHTML("beforeend",iconMarkup(state));
    button.dataset.transportIcon=state;
  }

  globalThis.DruMasterPauseIcon={render};

  render("pause");
  button.setAttribute("aria-label","一時停止");

  /* Replace app.js's text-glyph implementation entirely. This override uses
     only inline SVG for both transport states; no font glyph is ever assigned
     to the button after this script loads. */
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
  s.src="js/glass-hover-final.js?v=20260828-pausestable1";
  document.body.appendChild(s);
})();
