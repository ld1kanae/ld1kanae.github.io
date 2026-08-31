"use strict";

(()=>{
  const MAX_CAPTURE_SEC=8;
  const MIN_EARLY_SEC=1;
  let captureActive=false,captureStartedAt=0,captureResolve=null,captureReject=null;
  let sourceNode=null,processorNode=null,muteNode=null,chunks=[],sampleCount=0,maxTimer=0,enableTimer=0;

  function actionButton(){return document.querySelector("#micCalibration #micCalAction")}
  function instruction(){return document.querySelector("#micCalibration #micCalInstruction")}
  function detail(){return document.querySelector("#micCalibration #micCalDetail")}
  function noiseState(){return document.querySelector("#micCalibration #fpNoiseState")}
  function clearTimers(){clearTimeout(maxTimer);clearTimeout(enableTimer);maxTimer=enableTimer=0}

  function cleanupCapture(){
    clearTimers();
    try{processorNode&&(processorNode.onaudioprocess=null)}catch{}
    try{sourceNode?.disconnect()}catch{}
    try{processorNode?.disconnect()}catch{}
    try{muteNode?.disconnect()}catch{}
    sourceNode=processorNode=muteNode=null;
  }
  function setCapturingUi(){
    const b=actionButton();
    if(noiseState())noiseState().textContent="収録中";
    if(instruction())instruction().textContent="環境ノイズを自動収録しています。パッドはまだ叩かないでください";
    if(detail())detail().textContent="1秒以上収録すると次へ進めます。最大8秒で自動的に収録を終了します。";
    if(b){b.disabled=true;b.textContent="収録中…"}
  }
  function enableEarlyFinish(){
    if(!captureActive)return;
    const b=actionButton();if(b){b.disabled=false;b.textContent="次に進む"}
    if(detail())detail().textContent="必要な環境音は取得できています。今進んでも、最大8秒までそのまま収録しても構いません。";
  }
  function finishCapture(){
    if(!captureActive)return;
    const elapsed=(performance.now()-captureStartedAt)/1000;
    if(elapsed<MIN_EARLY_SEC||sampleCount<256)return;
    captureActive=false;
    const sr=(typeof ac!=="undefined"&&ac?.sampleRate)||48000,total=sampleCount,pcm=new Float32Array(total);let at=0;
    for(const chunk of chunks){pcm.set(chunk,at);at+=chunk.length}
    chunks=[];sampleCount=0;const resolve=captureResolve;captureResolve=captureReject=null;cleanupCapture();
    const b=actionButton();if(b){b.disabled=true;b.textContent="解析中…"}
    resolve?.({type:"capture",mic:pcm.buffer,ref:new Float32Array(total).buffer,sampleRate:sr,samples:total});
  }
  function failCapture(message){
    if(!captureActive)return;captureActive=false;const reject=captureReject;captureResolve=captureReject=null;chunks=[];sampleCount=0;cleanupCapture();reject?.(Error(message));
  }

  /* performance-mode-v4 currently calls this name in the environment-noise
     branch. It records the raw microphone PCM directly, independent of AEC. */
  globalThis.beginAECCapture=function(){
    return new Promise((resolve,reject)=>{
      try{
        const stream=globalThis.DruMasterPerformanceMode?.getRawMicStream?.();
        if(!stream)throw Error("環境ノイズ収録用のマイク入力を取得できません");
        if(typeof ac==="undefined"||!ac)throw Error("オーディオ機能の準備ができていません");
        if(typeof ac.createScriptProcessor!=="function")throw Error("このブラウザでは環境ノイズPCM収録を利用できません");
        captureResolve=resolve;captureReject=reject;captureActive=true;captureStartedAt=performance.now();chunks=[];sampleCount=0;setCapturingUi();
        sourceNode=ac.createMediaStreamSource(stream);processorNode=ac.createScriptProcessor(1024,1,1);muteNode=ac.createGain();muteNode.gain.value=0;
        processorNode.onaudioprocess=e=>{
          if(!captureActive)return;const input=e.inputBuffer.getChannelData(0),copy=new Float32Array(input.length);copy.set(input);chunks.push(copy);sampleCount+=copy.length;
          const max=Math.round(ac.sampleRate*MAX_CAPTURE_SEC);if(sampleCount>=max)finishCapture();
        };
        sourceNode.connect(processorNode);processorNode.connect(muteNode).connect(ac.destination);
        enableTimer=setTimeout(enableEarlyFinish,MIN_EARLY_SEC*1000);
        maxTimer=setTimeout(finishCapture,MAX_CAPTURE_SEC*1000+80);
      }catch(e){captureActive=false;cleanupCapture();reject(e)}
    });
  };

  /* While environment capture is active, the existing action button becomes
     an explicit early-completion button. */
  document.addEventListener("click",e=>{
    const b=e.target?.closest?.("#micCalibration #micCalAction");
    if(!b||!captureActive||b.textContent!=="次に進む")return;
    e.preventDefault();e.stopImmediatePropagation();finishCapture();
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
    if(captureActive)failCapture("calibration-cancelled");
    const screen=document.querySelector("#micCalibration");if(screen)screen.dataset.noiseAutoStarted="0";
    setTimeout(autoStartNoise,80);
  },true);

  setTimeout(autoStartNoise,0);
})();
