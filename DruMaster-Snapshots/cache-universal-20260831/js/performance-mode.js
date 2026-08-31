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
  const MIC_REFRACTORY_MS=72,MIC_RETRIGGER_GUARD_MS=90,MIC_RELEASE_FRAMES=3,MIC_SELF_AUDIO_GUARD_MS=95;
  const MIC_TIMING_OFFSET_SEC=0;

  const modeRow=document.createElement("label");
  modeRow.className="option performance-mode-option";
  modeRow.innerHTML='<span>演奏モード</span><select id="performanceModeSelect" aria-label="演奏モード"><option value="normal">通常</option><option value="touch">どこでもタッチ</option><option value="pad">パッド練習</option></select>';
  options.appendChild(modeRow);
  const modeSelect=modeRow.querySelector("select");

  let runMode="normal",micStream=null,micSource=null,micFilter=null,micAnalyser=null,
      micData=null,micRaf=0,micNoiseFloor=.0009,micPrevRms=0,micPrevPeak=0,micLastHit=-Infinity,
      micArmed=true,micQuietFrames=0,micSelfGuardUntil=0,micCalibration=null,calibrationToken=0,calibrationScreen=null;

  function selectedMode(){return mobileQuery.matches?(modeSelect?.value||"normal"):"normal"}
  function isPerformanceMode(mode=runMode){return mode==="touch"||mode==="pad"}

  function setToggleLocked(toggle,locked){
    if(!toggle)return;
    if(locked&&toggle.checked){toggle.checked=false;toggle.dispatchEvent(new Event("change",{bubbles:true}))}
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
      const d=Math.abs(n.time-t);if(d<bestDelta){best=n;bestDelta=d}
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
    const label=gradeHit(note,delta);emitGrade(note,label);return true;
  }

  function showPadSnareFeedback(){
    /* Do not let the snare emitted by the phone immediately become another
       microphone onset. The normal release latch remains active after this guard. */
    micSelfGuardUntil=performance.now()+MIC_SELF_AUDIO_GUARD_MS;
    if(typeof playDrum==="function"&&typeof DEFAULT_NOTE!=="undefined")playDrum(DEFAULT_NOTE.snare,"snare",.90);
    const snare=document.querySelector('#hitLayer [data-part="snare"]:not(.inactive)')||document.querySelector('#hitLayer [data-part="snare"]');
    if(snare&&typeof flashPart==="function")flashPart("snare",snare);
    globalThis.DruMasterMobileTapEffect?.showElement?.(snare);
  }
  function consumePadMicHit(){
    if(!mobileQuery.matches||runMode!=="pad"||typeof running==="undefined"||!running||paused||autoplay)return false;
    showPadSnareFeedback();
    const match=nearestPlayable(current()-MIC_TIMING_OFFSET_SEC);
    if(!match||match.delta>GOOD_WINDOW)return false;
    const {note,delta}=match;note.hit=true;const label=gradeHit(note,delta);emitGrade(note,label);return true;
  }

  game.addEventListener("pointerdown",e=>{
    if(runMode!=="touch"||!mobileQuery.matches||!running||paused)return;
    if(e.target.closest("#pause,#pausePanel button"))return;
    const consumed=consumeNearest("touch");if(!consumed)return;e.preventDefault();e.stopImmediatePropagation();
  },true);

  async function ensureMic(){
    if(micStream&&micAnalyser)return;
    if(!navigator.mediaDevices?.getUserMedia)throw Error("このブラウザではマイク入力を利用できません");
    if(typeof ac==="undefined"||!ac)throw Error("オーディオ機能の準備ができていません");
    micStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false,channelCount:1},video:false});
    micSource=ac.createMediaStreamSource(micStream);
    micFilter=ac.createBiquadFilter();micFilter.type="highpass";micFilter.frequency.value=250;micFilter.Q.value=.55;
    micAnalyser=ac.createAnalyser();micAnalyser.fftSize=256;micAnalyser.smoothingTimeConstant=0;
    micData=new Float32Array(micAnalyser.fftSize);micSource.connect(micFilter).connect(micAnalyser);
    micNoiseFloor=.0009;micPrevRms=0;micPrevPeak=0;micLastHit=-Infinity;micArmed=true;micQuietFrames=0;micSelfGuardUntil=0;
  }
  function readMicLevel(){
    if(!micAnalyser||!micData)return {rms:0,peak:0};
    micAnalyser.getFloatTimeDomainData(micData);let sum=0,peak=0;
    for(const x of micData){const a=Math.abs(x);sum+=x*x;if(a>peak)peak=a}
    return {rms:Math.sqrt(sum/micData.length),peak};
  }
  function stopMicLoop(){if(micRaf)cancelAnimationFrame(micRaf);micRaf=0}
  function releaseMic(){
    calibrationToken++;stopMicLoop();
    try{micSource?.disconnect()}catch{}try{micFilter?.disconnect()}catch{}
    for(const track of micStream?.getTracks?.()||[])track.stop();
    micStream=null;micSource=null;micFilter=null;micAnalyser=null;micData=null;micArmed=true;micQuietFrames=0;micSelfGuardUntil=0;
  }

  function percentile(values,p=.5){if(!values.length)return 0;const sorted=[...values].sort((a,b)=>a-b),i=Math.min(sorted.length-1,Math.max(0,Math.floor((sorted.length-1)*p)));return sorted[i]}
  function meterPercent(peak){const db=20*Math.log10(Math.max(1e-6,peak));return Math.max(0,Math.min(100,(db+60)/60*100))}
  function waitFrame(){return new Promise(resolve=>requestAnimationFrame(resolve))}
  function waitMs(ms){return new Promise(resolve=>setTimeout(resolve,ms))}

  function ensureCalibrationScreen(){
    if(calibrationScreen)return calibrationScreen;
    const section=document.createElement("section");section.id="micCalibration";section.className="screen mic-calibration hidden";
    section.innerHTML=`
      <div class="mic-calibration-card">
        <p class="mic-cal-eyebrow">PAD PRACTICE</p>
        <h2>マイク感度調整</h2>
        <p id="micCalInstruction" class="mic-cal-instruction">準備しています…</p>
        <div class="mic-cal-meter" aria-label="マイク入力レベル"><i id="micCalMeterFill"></i><b id="micCalThresholdMarker"></b></div>
        <div class="mic-cal-steps">
          <div data-cal-step="noise"><span>1</span><b>周囲の音</b><em>待機</em></div>
          <div data-cal-step="speaker"><span>2</span><b>端末音</b><em>待機</em></div>
          <div data-cal-step="strong"><span>3</span><b>強</b><em>待機</em></div>
          <div data-cal-step="medium"><span>4</span><b>中</b><em>待機</em></div>
          <div data-cal-step="weak"><span>5</span><b>弱</b><em>待機</em></div>
        </div>
        <p id="micCalDetail" class="mic-cal-detail">周囲の音と端末スピーカーの回り込みを測定したあと、伴奏を流したまま強・中・弱の順に叩いてください。</p>
        <div class="mic-cal-actions"><button id="micCalStart" type="button" disabled>演奏開始</button><button id="micCalRetry" type="button">やり直す</button></div>
      </div>`;
    app.appendChild(section);calibrationScreen=section;return section;
  }
  function setCalStep(name,state,text){const row=calibrationScreen?.querySelector(`[data-cal-step="${name}"]`);if(!row)return;row.dataset.state=state;const em=row.querySelector("em");if(em)em.textContent=text}
  function resetCalibrationUi(){
    const screen=ensureCalibrationScreen(),instruction=screen.querySelector("#micCalInstruction"),detail=screen.querySelector("#micCalDetail"),start=screen.querySelector("#micCalStart"),marker=screen.querySelector("#micCalThresholdMarker");
    for(const name of ["noise","speaker","strong","medium","weak"])setCalStep(name,"idle","待機");
    if(instruction)instruction.textContent="周囲の音を測定します。まだ叩かないでください";
    if(detail)detail.textContent="周囲の音と端末スピーカーの回り込みを測定したあと、伴奏を流したまま強・中・弱の順に叩いてください。";
    if(start)start.disabled=true;if(marker){marker.style.left="0%";marker.classList.remove("show")}
  }
  function updateCalibrationMeter(peak){const fill=calibrationScreen?.querySelector("#micCalMeterFill");if(fill)fill.style.width=`${meterPercent(peak)}%`}

  async function measureNoise(token,durationMs=900){
    setCalStep("noise","active","測定中");const instruction=calibrationScreen.querySelector("#micCalInstruction");if(instruction)instruction.textContent="そのまま静かにしてください";
    const rmsValues=[],peakValues=[],until=performance.now()+durationMs;
    while(token===calibrationToken&&performance.now()<until){const level=readMicLevel();rmsValues.push(level.rms);peakValues.push(level.peak);updateCalibrationMeter(level.peak);await waitFrame()}
    if(token!==calibrationToken)throw Error("calibration-cancelled");
    const noise={rms:Math.max(.00005,percentile(rmsValues,.6)),peak:Math.max(.0002,percentile(peakValues,.75))};setCalStep("noise","done","完了");return noise;
  }

  function songConfig(){return globalThis.DruMasterSongs?.current||{}}
  function trackGain(name,fallback){const v=songConfig().mix?.[name];return Number.isFinite(v)?v:fallback}
  async function loadCalibrationStems(){
    if(typeof loadStem!=="function")return;
    await loadStem("base","オフボーカル");
    if(document.querySelector("#vocalToggle")?.checked)await loadStem("vocals","ボーカル");
    if(document.querySelector("#guideToggle")?.checked)await loadStem("drums","ガイドドラム");
  }
  function startCalibrationBed(){
    if(typeof ac==="undefined"||!ac||typeof buffers==="undefined"||!buffers.base)return ()=>{};
    const rateNow=Number(document.querySelector("#tempo")?.value||100)/100,voices=[],when=ac.currentTime+.04;
    const specs=[["base",.95],["vocals",.95],["drums",.70]];
    for(const [name,fallback] of specs){
      const buf=buffers[name];if(!buf)continue;
      const source=ac.createBufferSource(),gain=ac.createGain(),windowSec=Math.min(4,Math.max(.8,buf.duration-.1)),startAt=Math.min(18,Math.max(0,buf.duration-windowSec-.05));
      source.buffer=buf;source.playbackRate.value=rateNow;source.loop=true;source.loopStart=startAt;source.loopEnd=Math.min(buf.duration,startAt+windowSec);
      gain.gain.value=trackGain(name,fallback);source.connect(gain).connect(masterBus);source.start(when,startAt);voices.push({source,gain});
    }
    return ()=>{for(const v of voices){try{v.source.stop()}catch{}try{v.source.disconnect()}catch{}try{v.gain.disconnect()}catch{}}};
  }
  async function measureSpeakerBleed(noise,token,durationMs=1150){
    setCalStep("speaker","active","測定中");const instruction=calibrationScreen.querySelector("#micCalInstruction");if(instruction)instruction.textContent="テスト伴奏を再生しています。まだ叩かないでください";
    const rmsValues=[],peakValues=[],until=performance.now()+durationMs;
    while(token===calibrationToken&&performance.now()<until){const level=readMicLevel();rmsValues.push(level.rms);peakValues.push(level.peak);updateCalibrationMeter(level.peak);await waitFrame()}
    if(token!==calibrationToken)throw Error("calibration-cancelled");
    const speaker={rms:Math.max(noise.rms,percentile(rmsValues,.65)),peak:Math.max(noise.peak,percentile(peakValues,.85))};setCalStep("speaker","done","完了");return speaker;
  }

  async function captureCalibrationHit(name,label,baseline,token){
    setCalStep(name,"active","叩いてください");const instruction=calibrationScreen.querySelector("#micCalInstruction");if(instruction)instruction.textContent=`伴奏が流れている状態で${label}に1回叩いてください`;
    let prevRms=0,prevPeak=0,capture=null,armedAt=performance.now()+260;
    while(token===calibrationToken){
      const now=performance.now(),level=readMicLevel();updateCalibrationMeter(level.peak);
      if(capture){
        capture.rms=Math.max(capture.rms,level.rms);capture.peak=Math.max(capture.peak,level.peak);
        if(now>=capture.until){setCalStep(name,"done","完了");return {rms:capture.rms,peak:capture.peak}}
      }else if(now>=armedAt){
        const rise=level.rms-prevRms,peakRise=level.peak-prevPeak,
              rmsGate=Math.max(.00025,baseline.rms*1.55),peakGate=Math.max(.0010,baseline.peak*1.32),
              riseGate=Math.max(.00008,baseline.rms*.20),peakRiseGate=Math.max(.00020,baseline.peak*.11),
              loudEnough=level.rms>rmsGate||level.peak>peakGate,transient=rise>riseGate||peakRise>peakRiseGate;
        if(loudEnough&&transient)capture={rms:level.rms,peak:level.peak,until:now+95};
      }
      prevRms=level.rms;prevPeak=level.peak;await waitFrame();
    }
    throw Error("calibration-cancelled");
  }

  function buildCalibration(noise,speaker,strong,medium,weak){
    /* Subtract most, not all, of the measured speaker bleed. Leaving a small
       residual avoids over-cancellation when the song becomes quieter than the test loop. */
    const speakerOnlyRms=Math.max(0,speaker.rms-noise.rms),speakerOnlyPeak=Math.max(0,speaker.peak-noise.peak),
          speakerCompRms=speakerOnlyRms*.84,speakerCompPeak=speakerOnlyPeak*.84,
          correct=x=>({rms:Math.max(.00001,x.rms-speakerCompRms),peak:Math.max(.00005,x.peak-speakerCompPeak)}),
          strongC=correct(strong),mediumC=correct(medium),weakC=correct(weak),
          rmsTarget=Math.max(weakC.rms*.85,noise.rms*1.7),peakTarget=Math.max(weakC.peak*.85,noise.peak*1.55),
          thresholdRms=Math.min(weakC.rms*.94,rmsTarget),thresholdPeak=Math.min(weakC.peak*.94,peakTarget),
          riseGate=Math.max(.00008,(weakC.rms-noise.rms)*.12,noise.rms*.12),
          peakRiseGate=Math.max(.00020,(weakC.peak-noise.peak)*.10,noise.peak*.10),
          weakClear=weakC.rms>noise.rms*1.35||weakC.peak>noise.peak*1.35,
          ordered=strongC.peak>mediumC.peak*1.04&&mediumC.peak>weakC.peak*1.04;
    return {noise,speaker,strong,medium,weak,strongC,mediumC,weakC,speakerCompRms,speakerCompPeak,thresholdRms,thresholdPeak,riseGate,peakRiseGate,weakClear,ordered};
  }

  async function runCalibration(){
    const screen=ensureCalibrationScreen(),token=++calibrationToken;let stopBed=null;micCalibration=null;resetCalibrationUi();
    try{
      try{await ac.resume()}catch{}
      const noise=await measureNoise(token);
      const instruction=screen.querySelector("#micCalInstruction");if(instruction)instruction.textContent="テスト伴奏を準備しています…";
      await loadCalibrationStems();if(token!==calibrationToken)throw Error("calibration-cancelled");
      stopBed=startCalibrationBed();await waitMs(180);
      const speaker=await measureSpeakerBleed(noise,token),baseline={rms:Math.max(noise.rms,speaker.rms),peak:Math.max(noise.peak,speaker.peak)},
            strong=await captureCalibrationHit("strong","強め",baseline,token),
            medium=await captureCalibrationHit("medium","普通の強さ",baseline,token),
            weak=await captureCalibrationHit("weak","弱め",baseline,token);
      if(token!==calibrationToken)return;
      micCalibration=buildCalibration(noise,speaker,strong,medium,weak);micNoiseFloor=noise.rms;
      const detail=screen.querySelector("#micCalDetail"),start=screen.querySelector("#micCalStart"),marker=screen.querySelector("#micCalThresholdMarker");
      if(instruction)instruction.textContent="調整完了";
      if(detail){
        if(!micCalibration.weakClear)detail.textContent="弱い打音と周囲の音が近い状態です。端末音の回り込みは差し引いていますが、誤反応する場合は「やり直す」で再調整してください。";
        else if(!micCalibration.ordered)detail.textContent="調整できました。端末スピーカーの回り込みを差し引き、弱い打音の少し下を判定基準にしています。";
        else detail.textContent="端末スピーカーの回り込みを測定・補正し、弱い打音の少し下を判定基準に設定しました。";
      }
      if(marker){marker.style.left=`${meterPercent(micCalibration.thresholdPeak+micCalibration.speakerCompPeak)}%`;marker.classList.add("show")}
      if(start)start.disabled=false;
    }catch(e){
      if(String(e?.message)!=="calibration-cancelled"){console.error(e);const instruction=screen.querySelector("#micCalInstruction");if(instruction)instruction.textContent="調整に失敗しました。やり直してください"}
    }finally{try{stopBed?.()}catch{}}
  }

  function showCalibration(){
    const screen=ensureCalibrationScreen();setup.classList.add("hidden");screen.classList.remove("hidden");
    return new Promise(resolve=>{
      const start=screen.querySelector("#micCalStart"),retry=screen.querySelector("#micCalRetry");
      start.onclick=()=>{if(!micCalibration)return;calibrationToken++;screen.classList.add("hidden");resolve(true)};
      retry.onclick=()=>{void runCalibration()};void runCalibration();
    });
  }

  function micFrame(){
    micRaf=0;if(runMode!=="pad"||!micAnalyser||typeof running==="undefined"||!running)return;
    if(!paused){
      const raw=readMicLevel(),compRms=micCalibration?.speakerCompRms||0,compPeak=micCalibration?.speakerCompPeak||0,
            rms=Math.max(0,raw.rms-compRms),peak=Math.max(0,raw.peak-compPeak),
            rise=rms-micPrevRms,peakRise=peak-micPrevPeak,
            threshold=micCalibration?Math.max(micCalibration.thresholdRms,micNoiseFloor*1.08):Math.max(.00195,micNoiseFloor*1.18),
            riseGate=micCalibration?micCalibration.riseGate:Math.max(.00045,micNoiseFloor*.06),
            peakGate=micCalibration?Math.max(micCalibration.thresholdPeak,micNoiseFloor*1.35):Math.max(.0066,micNoiseFloor*1.55),
            peakRiseGate=micCalibration?micCalibration.peakRiseGate:Math.max(.0012,micNoiseFloor*.18),
            releaseRms=micCalibration?Math.max(micCalibration.noise.rms*1.30,threshold*.52):Math.max(micNoiseFloor*1.12,threshold*.52),
            releasePeak=micCalibration?Math.max(micCalibration.noise.peak*1.30,peakGate*.52):Math.max(micNoiseFloor*1.60,peakGate*.52),
            now=performance.now(),outsideSelfGuard=now>=micSelfGuardUntil;
      const loudEnough=rms>threshold||peak>peakGate,transient=rise>riseGate||peakRise>peakRiseGate,
            normalOnset=outsideSelfGuard&&micArmed&&loudEnough&&transient&&now-micLastHit>=MIC_REFRACTORY_MS,
            strongRetrigger=outsideSelfGuard&&!micArmed&&now-micLastHit>=MIC_RETRIGGER_GUARD_MS&&loudEnough&&(rise>riseGate*2.8||peakRise>peakRiseGate*2.8);
      if(normalOnset||strongRetrigger){micLastHit=now;micArmed=false;micQuietFrames=0;consumePadMicHit()}
      else if(!micArmed){if(rms<releaseRms&&peak<releasePeak){if(++micQuietFrames>=MIC_RELEASE_FRAMES){micArmed=true;micQuietFrames=0}}else micQuietFrames=0}
      if(!loudEnough&&rms<threshold*1.35)micNoiseFloor=Math.max(.00005,Math.min(.02,micNoiseFloor*.997+rms*.003));
      micPrevRms=rms;micPrevPeak=peak;
    }
    micRaf=requestAnimationFrame(micFrame);
  }
  function startMicLoop(){stopMicLoop();micLastHit=-Infinity;micPrevRms=0;micPrevPeak=0;micArmed=true;micQuietFrames=0;micSelfGuardUntil=0;micRaf=requestAnimationFrame(micFrame)}

  const baseStart=startButton.onclick;
  startButton.onclick=async function(e){
    runMode=selectedMode();document.body.dataset.performanceRun=runMode;
    if(runMode==="pad"){
      const before=loadState?.textContent||"";startButton.disabled=true;if(loadState)loadState.textContent="マイクの使用を許可してください…";
      try{await ensureMic()}catch(err){console.error(err);if(loadState)loadState.textContent=err?.name==="NotAllowedError"?"パッド練習にはマイクの許可が必要です":(err?.message||"マイクを開始できません");startButton.disabled=false;return}
      if(loadState)loadState.textContent=before;await showCalibration();startButton.disabled=false;
    }
    const out=baseStart?await baseStart.call(this,e):undefined;
    if(runMode==="pad"&&typeof running!=="undefined"&&running)startMicLoop();else if(runMode==="pad"&&typeof running!=="undefined"&&!running)setup.classList.remove("hidden");
    return out;
  };

  globalThis.DruMasterPerformanceMode={getSelectedMode:selectedMode,getRunMode:()=>runMode,isPerformanceRun:()=>isPerformanceMode(runMode),isPadRun:()=>runMode==="pad",consumeNearest,consumePadMicHit,stopMic:releaseMic,getMicCalibration:()=>micCalibration,micTimingOffsetSec:()=>MIC_TIMING_OFFSET_SEC};
  addEventListener("pagehide",releaseMic,{once:true});
})();
