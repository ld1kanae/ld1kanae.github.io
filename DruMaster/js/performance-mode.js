"use strict";

(()=>{
  const mobileQuery=matchMedia("(hover:none) and (pointer:coarse) and (max-width:900px)"),
        setup=document.querySelector("#setup"),
        options=document.querySelector(".options"),
        startButton=document.querySelector("#start"),
        hiddenToggle=document.querySelector("#hiddenToggle"),
        autoToggle=document.querySelector("#autoToggle"),
        loadState=document.querySelector("#loadState"),
        game=document.querySelector("#game");
  if(!setup||!options||!startButton||!game)return;

  const PERFECT_WINDOW=.035,GREAT_WINDOW=.105,GOOD_WINDOW=.160;
  const MIC_REFRACTORY_MS=62;
  const MIC_TIMING_OFFSET_SEC=0; // Keep explicit for later device calibration.

  const modeRow=document.createElement("label");
  modeRow.className="option performance-mode-option";
  modeRow.innerHTML='<span>演奏モード</span><select id="performanceModeSelect" aria-label="演奏モード"><option value="normal">通常</option><option value="touch">どこでもタッチ</option><option value="pad">パッド練習</option></select>';
  options.appendChild(modeRow);
  const modeSelect=modeRow.querySelector("select");

  let runMode="normal",micStream=null,micSource=null,micFilter=null,micAnalyser=null,
      micData=null,micRaf=0,micNoiseFloor=.006,micPrevRms=0,micLastHit=-Infinity;

  function selectedMode(){return mobileQuery.matches?(modeSelect?.value||"normal"):"normal"}
  function isPerformanceMode(mode=runMode){return mode==="touch"||mode==="pad"}

  function setToggleLocked(toggle,locked){
    if(!toggle)return;
    if(locked&&toggle.checked){
      toggle.checked=false;
      toggle.dispatchEvent(new Event("change",{bubbles:true}));
    }
    toggle.disabled=locked;
    toggle.closest("label")?.classList.toggle("mode-locked",locked);
  }
  function syncModeUi(){
    const performance=isPerformanceMode(selectedMode());
    setToggleLocked(hiddenToggle,performance);
    setToggleLocked(autoToggle,performance);
    document.body.dataset.performanceSelection=selectedMode();
  }
  modeSelect?.addEventListener("change",syncModeUi);
  syncModeUi();

  function nearestPlayable(t){
    if(typeof notes==="undefined")return null;
    let best=null,bestDelta=GOOD_WINDOW+.000001;
    for(const n of notes){
      if(n.hit||n.type==="kick")continue;
      const d=Math.abs(n.time-t);
      if(d<bestDelta){best=n;bestDelta=d}
      if(n.time>t+GOOD_WINDOW)break;
    }
    return best?{note:best,delta:bestDelta}:null;
  }

  function gradeHit(note,delta){
    let mult,label;
    if(delta<=PERFECT_WINDOW){mult=1;label="PERFECT";counts.perfect++}
    else if(delta<=GREAT_WINDOW){mult=.75;label="GREAT";counts.great++}
    else{mult=.4;label="GOOD";counts.good++}
    score+=weight(note.type)*note.velocity/127*1000*mult;
    const scoreNode=document.querySelector("#score");
    if(scoreNode)scoreNode.textContent=String(Math.round(score/maxScore*1000000)).padStart(6,"0");
    return label;
  }

  function consumeNearest(source="touch"){
    if(!mobileQuery.matches||!isPerformanceMode()||typeof running==="undefined"||!running||paused||autoplay)return false;
    const inputTime=current()-(source==="mic"?MIC_TIMING_OFFSET_SEC:0),match=nearestPlayable(inputTime);
    if(!match||match.delta>GOOD_WINDOW)return false;

    const {note,delta}=match;
    note.hit=true;
    playDrum(note.note,note.type,note.velocity/127);
    if(typeof flashPart==="function"&&typeof PART!=="undefined")flashPart(PART[note.type]);
    const label=gradeHit(note,delta);
    const judgement=globalThis.DruMasterJudgement;
    if(judgement?.emitForNote)judgement.emitForNote(note,label,{flash:false});
    else if(typeof showJudge==="function")showJudge(label);
    return true;
  }

  /* Touch mode only captures the pointer when a chart note can actually be
     consumed. With no note inside the normal GOOD window, let the event keep
     propagating so the calibrated drum hit target underneath behaves exactly
     like normal play and can still be used as a free drum pad. */
  game.addEventListener("pointerdown",e=>{
    if(runMode!=="touch"||!mobileQuery.matches||!running||paused)return;
    if(e.target.closest("#pause,#pausePanel button"))return;
    const consumed=consumeNearest("touch");
    if(!consumed)return;
    e.preventDefault();
    e.stopImmediatePropagation();
  },true);

  async function ensureMic(){
    if(micStream&&micAnalyser)return;
    if(!navigator.mediaDevices?.getUserMedia)throw Error("このブラウザではマイク入力を利用できません");
    if(typeof ac==="undefined"||!ac)throw Error("オーディオ機能の準備ができていません");

    micStream=await navigator.mediaDevices.getUserMedia({
      audio:{echoCancellation:true,noiseSuppression:false,autoGainControl:false,channelCount:1},
      video:false
    });
    micSource=ac.createMediaStreamSource(micStream);
    micFilter=ac.createBiquadFilter();
    micFilter.type="highpass";
    micFilter.frequency.value=700;
    micFilter.Q.value=.7;
    micAnalyser=ac.createAnalyser();
    micAnalyser.fftSize=512;
    micAnalyser.smoothingTimeConstant=0;
    micData=new Float32Array(micAnalyser.fftSize);
    micSource.connect(micFilter).connect(micAnalyser);
    micNoiseFloor=.006;micPrevRms=0;micLastHit=-Infinity;
  }

  function stopMicLoop(){
    if(micRaf)cancelAnimationFrame(micRaf);
    micRaf=0;
  }
  function releaseMic(){
    stopMicLoop();
    try{micSource?.disconnect()}catch{}
    try{micFilter?.disconnect()}catch{}
    for(const track of micStream?.getTracks?.()||[])track.stop();
    micStream=null;micSource=null;micFilter=null;micAnalyser=null;micData=null;
  }

  function micFrame(){
    micRaf=0;
    if(runMode!=="pad"||!micAnalyser||typeof running==="undefined"||!running)return;
    if(!paused){
      micAnalyser.getFloatTimeDomainData(micData);
      let sum=0,peak=0;
      for(const x of micData){const a=Math.abs(x);sum+=x*x;if(a>peak)peak=a}
      const rms=Math.sqrt(sum/micData.length),rise=rms-micPrevRms,
            threshold=Math.max(.018,micNoiseFloor*2.8),
            riseGate=Math.max(.006,micNoiseFloor*.7),
            peakGate=Math.max(.065,micNoiseFloor*6),
            crest=peak/Math.max(.0001,rms),now=performance.now();
      const onset=rms>threshold&&rise>riseGate&&peak>peakGate&&crest>2.05&&now-micLastHit>=MIC_REFRACTORY_MS;
      if(onset){
        micLastHit=now;
        consumeNearest("mic");
      }else if(rms<threshold*1.35){
        micNoiseFloor=micNoiseFloor*.985+rms*.015;
      }
      micPrevRms=rms;
    }
    micRaf=requestAnimationFrame(micFrame);
  }
  function startMicLoop(){
    stopMicLoop();
    micLastHit=-Infinity;micPrevRms=0;
    micRaf=requestAnimationFrame(micFrame);
  }

  const baseStart=startButton.onclick;
  startButton.onclick=async function(e){
    runMode=selectedMode();
    document.body.dataset.performanceRun=runMode;
    if(runMode==="pad"){
      const before=loadState?.textContent||"";
      startButton.disabled=true;
      if(loadState)loadState.textContent="マイクの使用を許可してください…";
      try{
        await ensureMic();
      }catch(err){
        console.error(err);
        if(loadState)loadState.textContent=err?.name==="NotAllowedError"?"パッド練習にはマイクの許可が必要です":(err?.message||"マイクを開始できません");
        startButton.disabled=false;
        return;
      }
      startButton.disabled=false;
      if(loadState)loadState.textContent=before;
    }
    const out=baseStart?await baseStart.call(this,e):undefined;
    if(runMode==="pad"&&typeof running!=="undefined"&&running)startMicLoop();
    return out;
  };

  globalThis.DruMasterPerformanceMode={
    getSelectedMode:selectedMode,
    getRunMode:()=>runMode,
    isPerformanceRun:()=>isPerformanceMode(runMode),
    isPadRun:()=>runMode==="pad",
    consumeNearest,
    stopMic:releaseMic,
    micTimingOffsetSec:()=>MIC_TIMING_OFFSET_SEC
  };

  addEventListener("pagehide",releaseMic,{once:true});
})();
