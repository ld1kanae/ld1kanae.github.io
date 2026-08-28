"use strict";

(()=>{
  const $=id=>document.getElementById(id);

  function install(){
    const audio=$("audioOffset"),read=$("audioRead"),undo=$("historyUndo"),redo=$("historyRedo");
    const panel=audio?.closest(".panel");
    if(!audio||!read||!undo||!redo||!panel)return false;
    if(panel.classList.contains("dm-audio-offset-panel"))return true;

    panel.classList.add("dm-audio-offset-panel");

    const style=document.createElement("style");
    style.id="dmAudioOffsetPanelStyle";
    style.textContent=`
      .dm-audio-offset-panel{padding:14px!important}
      .dm-audio-offset-panel>.label{margin-bottom:1px!important}
      .dm-audio-current{display:flex;align-items:center;justify-content:center;height:34px;margin:0 0 5px}
      .dm-audio-current #audioRead{font-size:19px!important;line-height:1!important;letter-spacing:.025em;color:#d9f1ff!important;text-align:center;text-shadow:0 0 8px rgba(94,192,255,.18)}
      .dm-audio-controls{display:grid;grid-template-columns:minmax(126px,.86fr) minmax(0,1.55fr);gap:10px;align-items:center}
      .dm-audio-input-row{display:flex!important;flex-wrap:nowrap!important;gap:8px!important;align-items:center!important;min-width:0}
      .dm-audio-input-row #audioOffset{width:92px!important;min-width:0!important;height:34px!important}
      .dm-audio-input-row .dm-audio-unit{font-size:11px;color:#dce9f4;white-space:nowrap}
      .dm-audio-history-row{display:grid!important;grid-template-columns:1fr 1fr!important;gap:7px!important;align-items:center!important;margin:0!important;min-width:0}
      .dm-audio-history-row button{width:100%!important;min-width:0!important;padding:0 8px!important;white-space:nowrap!important;font-size:11px!important}
      .dm-audio-history-row #historyStatus{display:none!important}
      .dm-audio-nudges{display:grid!important;grid-template-columns:repeat(5,minmax(0,1fr))!important;gap:7px!important;align-items:center!important;margin-top:8px!important}
      .dm-audio-nudges button{width:100%!important;min-width:0!important;padding:0 6px!important;font-weight:700!important}
      .dm-audio-offset-panel>.note{display:none!important}
      @media(max-width:850px){
        .dm-audio-controls{grid-template-columns:minmax(118px,.9fr) minmax(0,1.5fr)}
        .dm-audio-history-row button{font-size:10px!important;padding:0 5px!important}
      }
    `;
    document.head.appendChild(style);

    const inputRow=audio.closest(".row");
    const historyRow=undo.closest(".row");
    const nudgeRow=panel.querySelector("[data-audio]")?.closest(".row");
    const label=panel.querySelector(":scope > .label");
    if(!inputRow||!historyRow||!nudgeRow||!label)return true;

    const unit=[...inputRow.children].find(el=>el!==audio&&el!==read&&el.tagName==="SPAN");
    if(unit)unit.classList.add("dm-audio-unit");

    const current=document.createElement("div");
    current.className="dm-audio-current";
    current.appendChild(read);
    label.insertAdjacentElement("afterend",current);

    const controls=document.createElement("div");
    controls.className="dm-audio-controls";
    current.insertAdjacentElement("afterend",controls);

    inputRow.classList.add("dm-audio-input-row");
    inputRow.style.marginTop="";
    historyRow.classList.add("dm-audio-history-row");
    historyRow.style.marginTop="";
    controls.appendChild(inputRow);
    controls.appendChild(historyRow);

    nudgeRow.classList.add("dm-audio-nudges");
    nudgeRow.style.marginTop="";
    controls.insertAdjacentElement("afterend",nudgeRow);

    return true;
  }

  const timer=setInterval(()=>{if(install())clearInterval(timer)},50);
  setTimeout(()=>{clearInterval(timer);install()},5000);
})();
