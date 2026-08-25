"use strict";

(()=>{
  const hiddenToggle=document.querySelector("#hiddenToggle"),
        volume=document.querySelector("#masterVolume"),
        volumeValue=document.querySelector("#masterVolumeValue"),
        startButton=document.querySelector("#start"),
        mobileQuery=matchMedia("(hover:none) and (pointer:coarse) and (max-width:900px)");

  const state={active:false};
  globalThis.DruMasterMode={
    isHidden:()=>state.active,
    isMobile:()=>mobileQuery.matches
  };

  function syncHiddenLabel(){
    if(!hiddenToggle)return;
    const label=hiddenToggle.closest("label"),value=label?.querySelector("b");
    if(value)value.textContent=hiddenToggle.checked?"ON":"OFF";
  }
  hiddenToggle?.addEventListener("change",syncHiddenLabel);
  syncHiddenLabel();

  function applyVolume(){
    if(!volume)return;
    const value=Math.max(0,Math.min(100,+volume.value||0));
    if(volumeValue)volumeValue.textContent=`${value}%`;
    if(typeof masterBus!=="undefined"&&masterBus?.gain){
      const target=value/100;
      if(typeof ac!=="undefined"&&ac){
        masterBus.gain.cancelScheduledValues(ac.currentTime);
        masterBus.gain.setTargetAtTime(target,ac.currentTime,.012);
      }else{
        masterBus.gain.value=target;
      }
    }
  }
  volume?.addEventListener("input",applyVolume);
  applyVolume();

  /* game-speed-fix.js has already installed the shared chart draw function.
     Hidden Mode suppresses Canvas rendering altogether rather than merely hiding it. */
  if(typeof draw==="function"){
    const normalDraw=draw;
    draw=function(){
      if(state.active)return;
      return normalDraw();
    };
  }

  if(startButton&&typeof startGame==="function"){
    const normalStart=startGame;
    startButton.onclick=async()=>{
      state.active=!!(mobileQuery.matches&&hiddenToggle?.checked);
      document.body.classList.toggle("hidden-mode",state.active);
      applyVolume();
      return normalStart();
    };
  }
})();
