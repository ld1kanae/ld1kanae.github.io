"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;
  let observer=null,initialResetDone=false;

  function iframeDoc(){try{return frame.contentDocument}catch{return null}}
  function syncLame(){
    try{
      const lib=frame.contentWindow?.lamejs;
      if(lib?.Mp3Encoder)globalThis.lamejs=lib;
    }catch{}
  }
  function fixInitialNewMode(){
    if(initialResetDone)return;
    const d=iframeDoc();if(!d)return;
    const panel=d.getElementById("dmPublisherMode"),select=d.getElementById("dmExistingSong"),newButton=panel?.querySelector('[data-mode="new"]');
    if(!panel||!select||!select.options.length||!newButton)return;
    if(newButton.classList.contains("active")&&d.body.classList.contains("dm-publisher-new")){
      initialResetDone=true;
      newButton.click();
    }
  }
  function installObserver(){
    observer?.disconnect();observer=null;initialResetDone=false;
    const d=iframeDoc();if(!d?.documentElement)return;
    syncLame();fixInitialNewMode();
    observer=new MutationObserver(()=>{syncLame();fixInitialNewMode()});
    observer.observe(d.documentElement,{childList:true,subtree:true});
    setTimeout(()=>{observer?.disconnect();observer=null},12000);
  }

  frame.addEventListener("load",()=>setTimeout(installObserver,0));
  setTimeout(installObserver,400);

  addEventListener("message",e=>{
    if(e.source!==window||e.origin!==location.origin)return;
    const d=e.data;if(!d||d.type!=="dm-song-editor-ready"||!d.id||!d.sessionId)return;
    dispatchEvent(new MessageEvent("message",{data:d,origin:location.origin,source:frame.contentWindow}));
  });
})();
