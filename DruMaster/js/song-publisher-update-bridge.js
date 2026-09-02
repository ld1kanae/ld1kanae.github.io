"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;
  let observer=null,initialResetDone=false;

  if(!document.querySelector('script[data-dm-draft-catalog]')){
    const s=document.createElement("script");
    s.src="js/song-publisher-draft-catalog.js?v=20260902-midiupload2";
    s.dataset.dmDraftCatalog="1";
    document.head.appendChild(s);
  }

  if(!document.querySelector('script[data-dm-update-commit]')){
    const s=document.createElement("script");
    s.src="js/song-publisher-update-commit-v2.js?v=20260902-commitfix1";
    s.dataset.dmUpdateCommit="1";
    document.head.appendChild(s);
  }

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

  async function deliverUpdate(d){
    const started=Date.now();
    while(typeof globalThis.DruMasterUpdateCommit!=="function"&&Date.now()-started<10000){
      await new Promise(resolve=>setTimeout(resolve,50));
    }
    if(typeof globalThis.DruMasterUpdateCommit==="function"){
      await globalThis.DruMasterUpdateCommit(d);
      return;
    }
    const rd=iframeDoc(),log=rd?.getElementById("log"),stage=rd?.getElementById("stage"),bar=rd?.getElementById("bar"),pct=rd?.getElementById("percent");
    if(stage)stage.textContent="GitHub更新エラー";
    if(bar)bar.style.width="0%";
    if(pct)pct.textContent="0%";
    if(log){log.textContent="GitHub更新処理を読み込めませんでした。ページを再読み込みしてください。";log.className="bad"}
  }

  frame.addEventListener("load",()=>setTimeout(installObserver,0));
  setTimeout(installObserver,400);

  addEventListener("message",e=>{
    if(e.source!==window||e.origin!==location.origin)return;
    const d=e.data;if(!d||d.type!=="dm-song-editor-ready"||d.mode!=="update"||!d.id||!d.sessionId)return;
    void deliverUpdate(d);
    dispatchEvent(new MessageEvent("message",{data:d,origin:location.origin,source:frame.contentWindow}));
  });
})();
