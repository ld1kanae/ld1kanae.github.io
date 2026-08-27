"use strict";

(()=>{
  const MAX_CAPTURE_SEC=8;
  const MIN_EARLY_SEC=1;
  let observedAecNode=null;
  let captureActive=false;
  let captureStartedAt=0;
  let finishTimer=0;
  let enableTimer=0;

  /* performance-mode-v4 currently calls beginAECCapture() in its environment
     sampling path. Provide that bridge here and keep the actual AEC node visible
     to the bounded-capture controller without exposing it to normal gameplay. */
  const NativeAudioWorkletNode=globalThis.AudioWorkletNode;
  if(NativeAudioWorkletNode&&!globalThis.__DruMasterObservedAudioWorkletNode){
    class ObservedAudioWorkletNode extends NativeAudioWorkletNode{
      constructor(context,name,options){
        super(context,name,options);
        if(name==="drumaster-acoustic-canceller")observedAecNode=this;
      }
    }
    globalThis.AudioWorkletNode=ObservedAudioWorkletNode;
    globalThis.__DruMasterObservedAudioWorkletNode=true;
  }

  /* Ensure the updated processor (which accepts endCapture) is fetched even if
     an older worklet URL is still cached by the mobile browser. */
  function patchWorkletLoader(){
    try{
      if(typeof ac==="undefined"||!ac?.audioWorklet||ac.audioWorklet.__dmNoisePatched)return false;
      const nativeAdd=ac.audioWorklet.addModule.bind(ac.audioWorklet);
      ac.audioWorklet.addModule=(url,options)=>{
        const u=String(url||"");
        return nativeAdd(u.includes("acoustic-cancel-processor.js")?"js/acoustic-cancel-processor.js?v=20260827-noiseauto1":url,options);
      };
      ac.audioWorklet.__dmNoisePatched=true;
      return true;
    }catch{return false}
  }
  if(!patchWorkletLoader()){
    const loaderTimer=setInterval(()=>{if(patchWorkletLoader())clearInterval(loaderTimer)},50);
    setTimeout(()=>clearInterval(loaderTimer),10000);
  }

  function actionButton(){return document.querySelector("#micCalibration #micCalAction")}
  function instruction(){return document.querySelector("#micCalibration #micCalInstruction")}
  function detail(){return document.querySelector("#micCalibration #micCalDetail")}
  function noiseState(){return document.querySelector("#micCalibration #fpNoiseState")}

  function setCapturingUi(){
    const b=actionButton();
    if(noiseState())noiseState().textContent="収録中";
    if(instruction())instruction().textContent="環境ノイズを自動収録しています。パッドはまだ叩かないでください";
    if(detail())detail().textContent="1秒以上収録すると次へ進めます。最大8秒で自動的に収録を終了します。";
    if(b){b.disabled=true;b.textContent="収録中…"}
  }
  function enableEarlyFinish(){
    if(!captureActive)return;
    const b=actionButton();
    if(b){b.disabled=false;b.textContent="次に進む"}
    if(detail())detail().textContent="必要な環境音は取得できています。今進んでも、最大8秒までそのまま収録しても構いません。";
  }
  function requestFinish(){
    if(!captureActive||!observedAecNode)return;
    const elapsed=(performance.now()-captureStartedAt)/1000;
    if(elapsed<MIN_EARLY_SEC)return;
    const b=actionButton();if(b){b.disabled=true;b.textContent="解析中…"}
    try{observedAecNode.port.postMessage({type:"endCapture"})}catch{}
  }
  function clearCaptureTimers(){clearTimeout(finishTimer);clearTimeout(enableTimer);finishTimer=enableTimer=0}

  globalThis.beginAECCapture=function(_requestedSeconds){
    return new Promise((resolve,reject)=>{
      const node=observedAecNode;
      if(!node){reject(Error("環境ノイズ収録用のAudioWorkletを取得できません"));return}
      captureActive=true;captureStartedAt=performance.now();clearCaptureTimers();setCapturingUi();
      let settled=false;
      const done=e=>{
        if(e.data?.type!=="capture"||settled)return;
        settled=true;captureActive=false;clearCaptureTimers();node.port.removeEventListener("message",done);resolve(e.data);
      };
      node.port.addEventListener("message",done);try{node.port.start?.()}catch{}
      /* Always request at most eight seconds. The updated processor can also be
         ended early by the user; an older cached processor still self-completes
         within its own five-second cap. */
      node.port.postMessage({type:"beginCapture",seconds:MAX_CAPTURE_SEC});
      enableTimer=setTimeout(enableEarlyFinish,MIN_EARLY_SEC*1000);
      finishTimer=setTimeout(()=>{requestFinish();setTimeout(()=>{if(!settled){node.port.removeEventListener("message",done);captureActive=false;reject(Error("環境ノイズの収録を8秒で終了できませんでした"))}},900)},MAX_CAPTURE_SEC*1000);
    });
  };

  /* Capture-phase handler turns the existing action button into an early
     completion control while recording. */
  document.addEventListener("click",e=>{
    const b=e.target?.closest?.("#micCalibration #micCalAction");
    if(!b||!captureActive||b.textContent!=="次に進む")return;
    e.preventDefault();e.stopImmediatePropagation();requestFinish();
  },true);

  function normalizeNextButton(){
    const screen=document.querySelector("#micCalibration"),b=actionButton();
    if(!screen||screen.classList.contains("hidden")||!b)return;
    if(!captureActive&&b.textContent==="パッド音の登録を開始")b.textContent="次に進む";
  }
  function autoStartNoise(){
    const screen=document.querySelector("#micCalibration"),b=actionButton();
    if(!screen||screen.classList.contains("hidden")||!b||captureActive)return;
    if(!/環境ノイズを収録/.test(b.textContent)||b.disabled||screen.dataset.noiseAutoStarted==="1")return;
    screen.dataset.noiseAutoStarted="1";
    setTimeout(()=>{if(!screen.classList.contains("hidden")&&!captureActive&&/環境ノイズを収録/.test(b.textContent))b.click()},40);
  }
  const observer=new MutationObserver(()=>{normalizeNextButton();autoStartNoise()});
  observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:["class","disabled"]});

  document.addEventListener("click",e=>{
    if(!e.target?.closest?.("#micCalibration #micCalRetry"))return;
    const screen=document.querySelector("#micCalibration");if(screen)screen.dataset.noiseAutoStarted="0";
    setTimeout(autoStartNoise,60);
  },true);

  setTimeout(autoStartNoise,0);
})();
