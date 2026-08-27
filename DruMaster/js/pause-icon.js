"use strict";

(()=>{
  const button=document.querySelector("#pause");
  const panel=document.querySelector("#pausePanel");
  if(!button||!panel)return;

  const iconMarkup=state=>state==="play"
    ? '<svg class="pause-transport-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M8 5.2c0-.9 1-1.45 1.78-.98l8.35 5.03a3.2 3.2 0 0 1 0 5.5l-8.35 5.03A1.15 1.15 0 0 1 8 18.8V5.2Z"/></svg>'
    : '<svg class="pause-transport-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="5" y="4" width="4" height="16" rx="1.3"/><rect x="15" y="4" width="4" height="16" rx="1.3"/></svg>';

  function render(state){
    button.innerHTML=iconMarkup(state);
    button.dataset.transportIcon=state;
  }

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
})();
