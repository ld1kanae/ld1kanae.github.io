"use strict";

(()=>{
  const header=document.querySelector("#game header"),busy=document.querySelector("#scorePlaybackBusy");
  if(!header||!busy)return;

  const label=document.createElement("span");
  label.id="scoreHeaderLoading";
  label.textContent="読み込み中…";
  header.appendChild(label);

  function sync(){
    const active=document.body.dataset.scorePlayback==="1",
          loading=document.body.dataset.scoreLoading==="1",
          switching=busy.textContent.trim()==="LOADING SONG";
    label.classList.toggle("show",active&&loading&&switching);
  }

  new MutationObserver(sync).observe(document.body,{attributes:true,attributeFilter:["data-score-playback","data-score-loading"]});
  new MutationObserver(sync).observe(busy,{childList:true,characterData:true,subtree:true});
  sync();
})();
