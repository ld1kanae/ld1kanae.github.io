"use strict";

(()=>{
  const mobileQuery=matchMedia("(hover:none) and (pointer:coarse) and (max-width:900px)"),
        setup=document.querySelector("#setup"),
        options=document.querySelector(".options"),
        startButton=document.querySelector("#start"),
        hiddenToggle=document.querySelector("#hiddenToggle"),
        autoToggle=document.querySelector("#autoToggle"),
        loadState=document.querySelector("#loadState"),
        game=document.querySelector("#game"),
        app=document.querySelector("#app");
  if(!setup||!options||!startButton||!game||!app)return;

  const PERFECT_WINDOW=.035,GREAT_WINDOW=.105,GOOD_WINDOW=.160;
  const MIC_REFRACTORY_MS=72;
  const MIC_TIMING_OFFSET_SEC=0; // Keep explicit for later device calibration.

  const modeRow=document.createElement("label");
  modeRow.className="option performance-mode-option";
  modeRow.innerHTML='<span>演奏モード</span><select id="performanceModeSelect" aria-label="演奏モード"><option value="normal">通常</option><option value="touch">どこでもタッチ</option><option value="pad">パッド練習</option></select>';
  options.appendChild(modeRow);
  const modeSelect=modeRow.querySelector("select");

  let runMode="normal",micStream=null,micSource=null,micFilter=null,micAnalyser=null,
      micData=null,micRaf=0,micNoiseFloor=.0009,micPrevRms=0,micPrevPeak=0,micLastHit=-Infinity,
      micCalibration=null,calibrationToken=0,calibrationScreen=null;

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
    const search=globalThis.DruMasterNoteSearch;
    if(search?.nearest)return search.nearest(notes,t,GOOD_WINDOW,n=>!n.hit&&n.type!=="kick");
    let best=null,bestDelta=GOOD_WINDOW+.000001;
    for(const n of notes){
      if(n.time<t-GOOD_WINDOW)continue;
      if(n.time>t+GOOD_WINDOW)break;
      if(n.hit||n.type==="kick")continue;
      const d=Math.abs(n.time-t);
      if(d<bestDelta){best=n;bestDelta=d}
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
    if(scoreNode)scoreNode.textContent=String(Math.round(score)).padStart(6,"0");
    return label;
  }

  function emitGrade(note,label){
    const judgement=globalThis.DruMasterJudgement;
    if(judgement?.emitForNote)judgement.emitForNote(note,label,{flash:false});
    else if(typeof showJudge==="function")showJudge(label);
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
    emitGrade(note,label);
    return true;
  }

  function showPadSnareFeedback(){
    if(typeof playDrum==="function"&&typeof DEFAULT_NOTE!=="undefined"){
      playDrum(DEFAULT_NOTE.snare,"snare",.90);
    }
    const snare=document.querySelector('#hitLayer [data-part="snare"]:not(.inactive)')||document.querySelector('#hitLayer [data-part="snare"]');
    if(snare&&typeof flashPart==="function")flashPart("snare",snare);
    globalThis.DruMasterMobileTapEffect?.showElement?.(snare);
  }

  function consumePadMicHit(){
    if(!mobileQuery.matches||runMode!=="pad"||typeof running==="undefined"||!running||paused||autoplay)return false;
    showPadSnareFeedback();

    const match=nearestPlayable(current()-MIC_TIMING_OFFSET_SEC);
    if(!match||match.delta>GOOD_WINDOW)return false;
    const {note,delta}=match;
    note.hit=true;
    const label=gradeHit(note,delta);
    emitGrade(note,label);
    return true;
  }

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
      audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false,channelCount:1},
      video:false
    });
    micSource=ac.createMediaStreamSource(micStream);
    micFilter=ac.createBiquadFilter();
    micFilter.type="highpass";
    micFilter.frequency.value=250;
    micFilter.Q.value=.55;
    micAnalyser=ac.createAnalyser();
    micAnalyser.fftSize=256;
    micAnalyser.smoothingTimeConstant=0;
    micData=new Float32Array(micAnalyser.fftSize);
    micSource.connect(micFilter).connect(micAnalyser);
    micNoiseFloor=.0009;micPrevRms=0;micPrevPeak=0;micLastHit=-Infinity;
  }

  function readMicLevel(){
    if(!micAnalyser||!micData)return {rms:0,peak:0};
    micAnalyser.getFloatTimeDomainData(micData);
    let sum=0,peak=0;
    for(const x of micData){const a=Math.abs(x);sum+=x*x;if(a>peak)peak=a}
    return {rms:Math.sqrt(sum/micData.length),peak};
  }

  function stopMicLoop(){
    if(micRaf)cancelAnimationFrame(micRaf);
    micRaf=0;
  }
  function releaseMic(){
    calibrationToken++;
    stopMicLoop();
    try{micSource?.disconnect()}catch{}
    try{micFilter?.disconnect()}catch{}
    for(const track of micStream?.getTracks?.()||[])track.stop();
    micStream=null;micSource=null;micFilter=null;micAnalyser=null;micData=null;
  }

  function percentile(values,p=.5){
    if(!values.length)return 0;
    const sorted=[...values].sort((a,b)=>a-b),i=Math.min(sorted.length-1,Math.max(0,Math.floor((sorted.length-1)*p)));
    return sorted[i];
  }
  function meterPercent(peak){
    const db=20*Math.log10(Math.max(1e-6,peak));
    return Math.max(0,Math.min(100,(db+60)/60*100));
  }

  function ensureCalibrationScreen(){
    if(calibrationScreen)return calibrationScreen;
    const section=document.createElement("section");
    section.id="micCalibration";
    section.className="screen mic-calibration hidden";
    section.innerHTML=`
      <div class="mic-calibration-card">
        <p class="mic-cal-eyebrow">PAD PRACTICE</p>
        <h2>マイク感度調整</h2>
        <p id="micCalInstruction" class="mic-cal-instruction">準備しています…</p>
        <div class="mic-cal-meter" aria-label="マイク入力レベル"><i id="micCalMeterFill"></i><b id="micCalThresholdMarker"></b></div>
        <div class="mic-cal-steps">
          <div data-cal-step="noise"><span>1</span><b>周囲の音</b><em>待機</em></div>
          <div data-cal-step="strong"><span>2</span><b>強</b><em>待機</em></div>
          <div data-cal-step="medium"><span>3</span><b>中</b><em>待機</em></div>
          <div data-cal-step="weak"><span>4</span><b>弱</b><em>待機</em></div>
        </div>
        <p id="micCalDetail" class="mic-cal-detail">最初に周囲の音を測定し、そのあと強・中・弱の順に1回ずつパッドを叩いてください。</p>
        <div class="mic-cal-actions">
          <button id="micCalStart" type="button" disabled>演奏開始</button>
          <button id="micCalRetry" type="button">やり直す</button>
        </div>
      </div>`;
    app.appendChild(section);
    calibrationScreen=section;
    return section;
  }

  function setCalStep(name,state,text){
    const row=calibrationScreen?.querySelector(`[data-cal-step="${name}"]`);
    if(!row)return;
    row.dataset.state=state;
    const em=row.querySelector("em");
    if(em)em.textContent=text;
  }
  function resetCalibrationUi(){
    const screen=ensureCalibrationScreen(),instruction=screen.querySelector("#micCalInstruction"),detail=screen.querySelector("#micCalDetail"),start=screen.querySelector("#micCalStart"),marker=screen.querySelector("#micCalThresholdMarker");
    for(const name of ["noise","strong","medium","weak"])setCalStep(name,"idle","待機");
    if(instruction)instruction.textContent="周囲の音を測定します。まだ叩かないでください";
    if(detail)detail.textContent="最初に周囲の音を測定し、そのあと強・中・弱の順に1回ずつパッドを叩いてください。";
    if(start)start.disabled=true;
    if(marker){marker.style.left="0%";marker.classList.remove("show")}
  }
  function updateCalibrationMeter(peak){
    const fill=calibrationScreen?.querySelector("#micCalMeterFill");
    if(fill)fill.style.width=`${meterPercent(peak)}%`;
  }

  function waitFrame(){return new Promise(resolve=>requestAnimationFrame(resolve))}
  async function measureNoise(token,durationMs=900){
    setCalStep("noise","active","測定中");
    const instruction=calibrationScreen.querySelector("#micCalInstruction");
    if(instruction)instruction.textContent="そのまま静かにしてください";
    const rmsValues=[],peakValues=[],until=performance.now()+durationMs;
    while(token===calibrationToken&&performance.now()<until){
      const level=readMicLevel();
      rmsValues.push(level.rms);peakValues.push(level.peak);updateCalibrationMeter(level.peak);
      await waitFrame();
    }
    if(token!==calibrationToken)throw Error("calibration-cancelled");
    const noise={rms:Math.max(.00005,percentile(rmsValues,.6)),peak:Math.max(.0002,percentile(peakValues,.75))};
    setCalStep("noise","done","完了");
    return noise;
  }

  async function captureCalibrationHit(name,label,noise,token){
    setCalStep(name,"active","叩いてください");
    const instruction=calibrationScreen.querySelector("#micCalInstruction");
    if(instruction)instruction.textContent=`${label}で1回叩いてください`;
    let prevRms=0,prevPeak=0,capture=null,armedAt=performance.now()+260;
    while(token===calibrationToken){
      const now=performance.now(),level=readMicLevel();
      updateCalibrationMeter(level.peak);
      if(capture){
        capture.rms=Math.max(capture.rms,level.rms);
        capture.peak=Math.max(capture.peak,level.peak);
        if(now>=capture.until){
          setCalStep(name,"done","完了");
          return {rms:capture.rms,peak:capture.peak};
        }
      }else if(now>=armedAt){
        const rise=level.rms-prevRms,peakRise=level.peak-prevPeak,
              rmsGate=Math.max(.00025,noise.rms*1.40),
              peakGate=Math.max(.0010,noise.peak*1.35),
              riseGate=Math.max(.00008,noise.rms*.18),
              peakRiseGate=Math.max(.00020,noise.peak*.12),
              loudEnough=level.rms>rmsGate||level.peak>peakGate,
              transient=rise>riseGate||peakRise>peakRiseGate;
        if(loudEnough&&transient)capture={rms:level.rms,peak:level.peak,until:now+95};
      }
      prevRms=level.rms;prevPeak=level.peak;
      await waitFrame();
    }
    throw Error("calibration-cancelled");
  }

  function buildCalibration(noise,strong,medium,weak){
    /* Base the run on a point just below the user's weakest deliberate hit.
       Room noise is also respected, but both gates are capped below the weak hit
       so the calibration can never make that exact weak strike unplayable. */
    const rmsTarget=Math.max(weak.rms*.85,noise.rms*2.5),
          peakTarget=Math.max(weak.peak*.85,noise.peak*2.0),
          thresholdRms=Math.min(weak.rms*.94,rmsTarget),
          thresholdPeak=Math.min(weak.peak*.94,peakTarget),
          riseGate=Math.max(.00008,(weak.rms-noise.rms)*.12,noise.rms*.12),
          peakRiseGate=Math.max(.00020,(weak.peak-noise.peak)*.10,noise.peak*.10),
          weakClear=weak.rms>noise.rms*1.35||weak.peak>noise.peak*1.35,
          ordered=strong.peak>medium.peak*1.04&&medium.peak>weak.peak*1.04;
    return {noise,strong,medium,weak,thresholdRms,thresholdPeak,riseGate,peakRiseGate,weakClear,ordered};
  }

  async function runCalibration(){
    const screen=ensureCalibrationScreen(),token=++calibrationToken;
    micCalibration=null;
    resetCalibrationUi();
    try{
      try{await ac.resume()}catch{}
      const noise=await measureNoise(token),
            strong=await captureCalibrationHit("strong","強め",noise,token),
            medium=await captureCalibrationHit("medium","普通の強さ",noise,token),
            weak=await captureCalibrationHit("weak","弱め",noise,token);
      if(token!==calibrationToken)return;
      micCalibration=buildCalibration(noise,strong,medium,weak);
      micNoiseFloor=noise.rms;
      const instruction=screen.querySelector("#micCalInstruction"),detail=screen.querySelector("#micCalDetail"),start=screen.querySelector("#micCalStart"),marker=screen.querySelector("#micCalThresholdMarker");
      if(instruction)instruction.textContent="調整完了";
      if(detail){
        if(!micCalibration.weakClear)detail.textContent="弱い打音と周囲の音がかなり近い状態です。誤反応する場合は「やり直す」で再調整してください。";
        else if(!micCalibration.ordered)detail.textContent="調整できました。強弱の差は小さめですが、弱い打音の少し下を検出基準に設定しています。";
        else detail.textContent="弱い打音の少し下を検出基準に設定しました。このまま演奏を開始できます。";
      }
      if(marker){marker.style.left=`${meterPercent(micCalibration.thresholdPeak)}%`;marker.classList.add("show")}
      if(start)start.disabled=false;
    }catch(e){
      if(String(e?.message)==="calibration-cancelled")return;
      console.error(e);
      const instruction=screen.querySelector("#micCalInstruction");
      if(instruction)instruction.textContent="調整に失敗しました。やり直してください";
    }
  }

  function showCalibration(){
    const screen=ensureCalibrationScreen();
    setup.classList.add("hidden");
    screen.classList.remove("hidden");
    return new Promise(resolve=>{
      const start=screen.querySelector("#micCalStart"),retry=screen.querySelector("#micCalRetry");
      start.onclick=()=>{
        if(!micCalibration)return;
        calibrationToken++;
        screen.classList.add("hidden");
        resolve(true);
      };
      retry.onclick=()=>{void runCalibration()};
      void runCalibration();
    });
  }

  function micFrame(){
    micRaf=0;
    if(runMode!=="pad"||!micAnalyser||typeof running==="undefined"||!running)return;
    if(!paused){
      const {rms,peak}=readMicLevel(),
            rise=rms-micPrevRms,
            peakRise=peak-micPrevPeak,
            threshold=micCalibration?Math.max(micCalibration.thresholdRms,micNoiseFloor*1.08):Math.max(.00195,micNoiseFloor*1.18),
            riseGate=micCalibration?micCalibration.riseGate:Math.max(.00045,micNoiseFloor*.06),
            peakGate=micCalibration?Math.max(micCalibration.thresholdPeak,micNoiseFloor*1.35):Math.max(.0066,micNoiseFloor*1.55),
            peakRiseGate=micCalibration?micCalibration.peakRiseGate:Math.max(.0012,micNoiseFloor*.18),
            now=performance.now();
      const loudEnough=rms>threshold||peak>peakGate,
            transient=rise>riseGate||peakRise>peakRiseGate,
            onset=loudEnough&&transient&&now-micLastHit>=MIC_REFRACTORY_MS;
      if(onset){
        micLastHit=now;
        consumePadMicHit();
      }else if(rms<threshold*1.35){
        micNoiseFloor=Math.max(.00005,Math.min(.02,micNoiseFloor*.997+rms*.003));
      }
      micPrevRms=rms;
      micPrevPeak=peak;
    }
    micRaf=requestAnimationFrame(micFrame);
  }
  function startMicLoop(){
    stopMicLoop();
    micLastHit=-Infinity;micPrevRms=0;micPrevPeak=0;
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
      if(loadState)loadState.textContent=before;
      await showCalibration();
      startButton.disabled=false;
    }
    const out=baseStart?await baseStart.call(this,e):undefined;
    if(runMode==="pad"&&typeof running!=="undefined"&&running)startMicLoop();
    else if(runMode==="pad"&&typeof running!=="undefined"&&!running)setup.classList.remove("hidden");
    return out;
  };

  globalThis.DruMasterPerformanceMode={
    getSelectedMode:selectedMode,
    getRunMode:()=>runMode,
    isPerformanceRun:()=>isPerformanceMode(runMode),
    isPadRun:()=>runMode==="pad",
    consumeNearest,
    consumePadMicHit,
    stopMic:releaseMic,
    getMicCalibration:()=>micCalibration,
    micTimingOffsetSec:()=>MIC_TIMING_OFFSET_SEC
  };

  addEventListener("pagehide",releaseMic,{once:true});
})();
