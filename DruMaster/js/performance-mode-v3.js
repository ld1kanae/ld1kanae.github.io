"use strict";

(()=>{
  const mobileQuery=matchMedia("(hover:none) and (pointer:coarse) and (max-width:900px)"),
        setup=document.querySelector("#setup"),options=document.querySelector(".options"),startButton=document.querySelector("#start"),
        hiddenToggle=document.querySelector("#hiddenToggle"),autoToggle=document.querySelector("#autoToggle"),loadState=document.querySelector("#loadState"),
        game=document.querySelector("#game"),app=document.querySelector("#app");
  if(!setup||!options||!startButton||!game||!app)return;

  const PERFECT_WINDOW=.035,GREAT_WINDOW=.105,GOOD_WINDOW=.160;
  const MIC_REFRACTORY_MS=72,MIC_RETRIGGER_GUARD_MS=90,MIC_RELEASE_FRAMES=3,MIC_SELF_AUDIO_GUARD_MS=110;
  const MIC_TIMING_OFFSET_SEC=0,OUTPUT_HISTORY_FRAMES=4,BLEED_SUBTRACT_RATIO=.90,BLEED_GUARD_RATIO=.10;

  const modeRow=document.createElement("label");
  modeRow.className="option performance-mode-option";
  modeRow.innerHTML='<span>演奏モード</span><select id="performanceModeSelect" aria-label="演奏モード"><option value="normal">通常</option><option value="touch">どこでもタッチ</option><option value="pad">パッド練習</option></select>';
  options.appendChild(modeRow);
  const modeSelect=modeRow.querySelector("select");

  let runMode="normal",micStream=null,micSource=null,micFilter=null,micAnalyser=null,micData=null,micRaf=0,
      micNoiseFloor=.0009,micPrevRms=0,micPrevPeak=0,micLastHit=-Infinity,micArmed=true,micQuietFrames=0,micSelfGuardUntil=0,
      outputAnalyser=null,outputData=null,outputSilent=null,outputHistory=[],micCalibration=null,
      calibrationScreen=null,calibrationToken=0,calState=null,calResolve=null,calBusy=false;

  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  function selectedMode(){return mobileQuery.matches?(modeSelect?.value||"normal"):"normal"}
  function isPerformanceMode(mode=runMode){return mode==="touch"||mode==="pad"}
  function setToggleLocked(toggle,locked){if(!toggle)return;if(locked&&toggle.checked){toggle.checked=false;toggle.dispatchEvent(new Event("change",{bubbles:true}))}toggle.disabled=locked;toggle.closest("label")?.classList.toggle("mode-locked",locked)}
  function syncModeUi(){const p=isPerformanceMode(selectedMode());setToggleLocked(hiddenToggle,p);setToggleLocked(autoToggle,p);document.body.dataset.performanceSelection=selectedMode()}
  modeSelect?.addEventListener("change",syncModeUi);syncModeUi();

  function nearestPlayable(t){
    if(typeof notes==="undefined")return null;
    const search=globalThis.DruMasterNoteSearch;
    if(search?.nearest)return search.nearest(notes,t,GOOD_WINDOW,n=>!n.hit&&n.type!=="kick");
    let best=null,bestDelta=GOOD_WINDOW+.000001;
    for(const n of notes){if(n.time<t-GOOD_WINDOW)continue;if(n.time>t+GOOD_WINDOW)break;if(n.hit||n.type==="kick")continue;const d=Math.abs(n.time-t);if(d<bestDelta){best=n;bestDelta=d}}
    return best?{note:best,delta:bestDelta}:null;
  }
  function gradeHit(note,delta){
    let mult,label;if(delta<=PERFECT_WINDOW){mult=1;label="PERFECT";counts.perfect++}else if(delta<=GREAT_WINDOW){mult=.75;label="GREAT";counts.great++}else{mult=.4;label="GOOD";counts.good++}
    score+=weight(note.type)*note.velocity/127*1000*mult;const node=document.querySelector("#score");if(node)node.textContent=String(Math.round(score)).padStart(6,"0");return label;
  }
  function emitGrade(note,label){const j=globalThis.DruMasterJudgement;if(j?.emitForNote)j.emitForNote(note,label,{flash:false});else if(typeof showJudge==="function")showJudge(label)}
  function consumeNearest(source="touch"){
    if(!mobileQuery.matches||!isPerformanceMode()||typeof running==="undefined"||!running||paused||autoplay)return false;
    const match=nearestPlayable(current()-(source==="mic"?MIC_TIMING_OFFSET_SEC:0));if(!match||match.delta>GOOD_WINDOW)return false;
    const {note,delta}=match;note.hit=true;playDrum(note.note,note.type,note.velocity/127);if(typeof flashPart==="function"&&typeof PART!=="undefined")flashPart(PART[note.type]);const label=gradeHit(note,delta);emitGrade(note,label);return true;
  }
  function showPadSnareFeedback(){
    micSelfGuardUntil=performance.now()+MIC_SELF_AUDIO_GUARD_MS;
    if(typeof playDrum==="function"&&typeof DEFAULT_NOTE!=="undefined")playDrum(DEFAULT_NOTE.snare,"snare",.90);
    const snare=document.querySelector('#hitLayer [data-part="snare"]:not(.inactive)')||document.querySelector('#hitLayer [data-part="snare"]');
    if(snare&&typeof flashPart==="function")flashPart("snare",snare);globalThis.DruMasterMobileTapEffect?.showElement?.(snare);
  }
  function consumePadMicHit(){
    if(!mobileQuery.matches||runMode!=="pad"||typeof running==="undefined"||!running||paused||autoplay)return false;
    showPadSnareFeedback();const match=nearestPlayable(current()-MIC_TIMING_OFFSET_SEC);if(!match||match.delta>GOOD_WINDOW)return false;
    const {note,delta}=match;note.hit=true;const label=gradeHit(note,delta);emitGrade(note,label);return true;
  }
  game.addEventListener("pointerdown",e=>{if(runMode!=="touch"||!mobileQuery.matches||!running||paused)return;if(e.target.closest("#pause,#pausePanel button"))return;const ok=consumeNearest("touch");if(ok){e.preventDefault();e.stopImmediatePropagation()}},true);

  async function ensureMic(){
    if(micStream&&micAnalyser)return;
    if(!navigator.mediaDevices?.getUserMedia)throw Error("このブラウザではマイク入力を利用できません");
    if(typeof ac==="undefined"||!ac)throw Error("オーディオ機能の準備ができていません");
    micStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false,channelCount:1},video:false});
    micSource=ac.createMediaStreamSource(micStream);micFilter=ac.createBiquadFilter();micFilter.type="highpass";micFilter.frequency.value=250;micFilter.Q.value=.55;
    micAnalyser=ac.createAnalyser();micAnalyser.fftSize=256;micAnalyser.smoothingTimeConstant=0;micData=new Float32Array(micAnalyser.fftSize);micSource.connect(micFilter).connect(micAnalyser);
    micNoiseFloor=.0009;micPrevRms=0;micPrevPeak=0;micLastHit=-Infinity;micArmed=true;micQuietFrames=0;micSelfGuardUntil=0;ensureOutputProbe();
  }
  function ensureOutputProbe(){
    if(outputAnalyser)return;if(typeof masterBus==="undefined"||!masterBus||typeof ac==="undefined"||!ac)return;
    outputAnalyser=ac.createAnalyser();outputAnalyser.fftSize=256;outputAnalyser.smoothingTimeConstant=.10;outputData=new Float32Array(outputAnalyser.fftSize);
    outputSilent=ac.createGain();outputSilent.gain.value=0;masterBus.connect(outputAnalyser);outputAnalyser.connect(outputSilent).connect(ac.destination);
  }
  function nodeLevel(analyser,data){if(!analyser||!data)return {rms:0,peak:0};analyser.getFloatTimeDomainData(data);let sum=0,peak=0;for(const x of data){const a=Math.abs(x);sum+=x*x;if(a>peak)peak=a}return {rms:Math.sqrt(sum/data.length),peak}}
  const readMicLevel=()=>nodeLevel(micAnalyser,micData),readOutputLevel=()=>nodeLevel(outputAnalyser,outputData);
  function resetOutputHistory(){outputHistory=[]}
  function recentOutputEnvelope(out){outputHistory.push(out);if(outputHistory.length>OUTPUT_HISTORY_FRAMES)outputHistory.shift();return {rms:Math.max(...outputHistory.map(x=>x.rms),0),peak:Math.max(...outputHistory.map(x=>x.peak),0)}}
  function compensatedMic(raw,out,cal=micCalibration){
    if(!cal?.bleedRmsCoef&&!cal?.bleedPeakCoef)return {rms:raw.rms,peak:raw.peak,predictedRms:0,predictedPeak:0};
    const env=recentOutputEnvelope(out),predictedRms=env.rms*(cal.bleedRmsCoef||0)*BLEED_SUBTRACT_RATIO,predictedPeak=env.peak*(cal.bleedPeakCoef||0)*BLEED_SUBTRACT_RATIO;
    return {rms:Math.sqrt(Math.max(0,raw.rms*raw.rms-predictedRms*predictedRms)),peak:Math.max(0,raw.peak-predictedPeak),predictedRms,predictedPeak};
  }
  function stopMicLoop(){if(micRaf)cancelAnimationFrame(micRaf);micRaf=0}
  function stopCalibrationBed(){if(calState?.stopBed){try{calState.stopBed()}catch{}calState.stopBed=null}}
  function releaseMic(){
    calibrationToken++;stopMicLoop();stopCalibrationBed();try{micSource?.disconnect()}catch{}try{micFilter?.disconnect()}catch{}for(const track of micStream?.getTracks?.()||[])track.stop();
    micStream=null;micSource=null;micFilter=null;micAnalyser=null;micData=null;micArmed=true;micQuietFrames=0;micSelfGuardUntil=0;resetOutputHistory();
  }

  function percentile(values,p=.5){if(!values.length)return 0;const a=[...values].sort((x,y)=>x-y),i=Math.min(a.length-1,Math.max(0,Math.floor((a.length-1)*p)));return a[i]}
  function meterPercent(peak){const db=20*Math.log10(Math.max(1e-6,peak));return clamp((db+60)/60*100,0,100)}
  const waitFrame=()=>new Promise(r=>requestAnimationFrame(r)),waitMs=ms=>new Promise(r=>setTimeout(r,ms));

  function ensureCalibrationScreen(){
    if(calibrationScreen)return calibrationScreen;const section=document.createElement("section");section.id="micCalibration";section.className="screen mic-calibration hidden";
    section.innerHTML=`<div class="mic-calibration-card"><p class="mic-cal-eyebrow">PAD PRACTICE</p><h2>マイク感度調整</h2><p id="micCalInstruction" class="mic-cal-instruction">準備しています…</p><div class="mic-cal-meter"><i id="micCalMeterFill"></i><b id="micCalThresholdMarker"></b></div><div class="mic-cal-steps"><div data-cal-step="noise"><span>1</span><b>周囲の音</b><em>待機</em></div><div data-cal-step="speaker"><span>2</span><b>端末音</b><em>待機</em></div><div data-cal-step="strong"><span>3</span><b>強</b><em>待機</em></div><div data-cal-step="medium"><span>4</span><b>中</b><em>待機</em></div><div data-cal-step="weak"><span>5</span><b>弱</b><em>待機</em></div></div><p id="micCalCandidate" class="mic-cal-candidate"></p><p id="micCalDetail" class="mic-cal-detail">段階ごとに操作して測定します。検出しただけでは次へ進みません。</p><div class="mic-cal-actions manual-cal-actions"><button id="micCalAction" type="button">周囲の音を測定</button><button id="micCalAccept" type="button" class="hidden">この値を採用</button><button id="micCalStart" type="button" class="hidden" disabled>演奏開始</button><button id="micCalRetry" type="button">最初からやり直す</button></div></div>`;
    app.appendChild(section);calibrationScreen=section;return section;
  }
  const ui=sel=>calibrationScreen?.querySelector(sel);
  function setCalStep(name,state,text){const row=ui(`[data-cal-step="${name}"]`);if(!row)return;row.dataset.state=state;const em=row.querySelector("em");if(em)em.textContent=text}
  function updateCalibrationMeter(peak){const f=ui("#micCalMeterFill");if(f)f.style.width=`${meterPercent(peak)}%`}
  function setInstruction(text){const n=ui("#micCalInstruction");if(n)n.textContent=text}function setDetail(text){const n=ui("#micCalDetail");if(n)n.textContent=text}function setCandidate(text=""){const n=ui("#micCalCandidate");if(n)n.textContent=text}
  function setAction(text,disabled=false){const b=ui("#micCalAction");if(b){b.textContent=text;b.disabled=disabled;b.classList.remove("hidden")}}function showAccept(show){ui("#micCalAccept")?.classList.toggle("hidden",!show)}function showStart(show){const b=ui("#micCalStart");if(b){b.classList.toggle("hidden",!show);b.disabled=!show}}

  async function measureNoise(token,durationMs=1000){
    const rms=[],peak=[],until=performance.now()+durationMs;while(token===calibrationToken&&performance.now()<until){const m=readMicLevel();rms.push(m.rms);peak.push(m.peak);updateCalibrationMeter(m.peak);await waitFrame()}
    if(token!==calibrationToken)throw Error("calibration-cancelled");return {rms:Math.max(.00005,percentile(rms,.65)),peak:Math.max(.0002,percentile(peak,.80))};
  }
  function songConfig(){return globalThis.DruMasterSongs?.current||{}}function trackGain(name,fallback){const v=songConfig().mix?.[name];return Number.isFinite(v)?v:fallback}
  async function loadCalibrationStems(){if(typeof loadStem!=="function")return;await loadStem("base","オフボーカル");if(document.querySelector("#vocalToggle")?.checked)await loadStem("vocals","ボーカル");if(document.querySelector("#guideToggle")?.checked)await loadStem("drums","ガイドドラム")}
  function startCalibrationBed(){
    if(calState?.stopBed||typeof ac==="undefined"||!ac||typeof buffers==="undefined"||!buffers.base)return;
    const rateNow=Number(document.querySelector("#tempo")?.value||100)/100,voices=[],when=ac.currentTime+.04,specs=[["base",.95],["vocals",.95],["drums",.70]];
    for(const [name,fallback] of specs){const buf=buffers[name];if(!buf)continue;const s=ac.createBufferSource(),g=ac.createGain(),windowSec=Math.min(5,Math.max(1,buf.duration-.1)),startAt=Math.min(18,Math.max(0,buf.duration-windowSec-.05));s.buffer=buf;s.playbackRate.value=rateNow;s.loop=true;s.loopStart=startAt;s.loopEnd=Math.min(buf.duration,startAt+windowSec);g.gain.value=trackGain(name,fallback);s.connect(g).connect(masterBus);s.start(when,startAt);voices.push({s,g})}
    calState.stopBed=()=>{for(const v of voices){try{v.s.stop()}catch{}try{v.s.disconnect()}catch{}try{v.g.disconnect()}catch{}}};
  }
  async function measureSpeakerRelation(noise,token,durationMs=1900){
    const ratiosR=[],ratiosP=[],outR=[],outP=[],micR=[],micP=[],until=performance.now()+durationMs;resetOutputHistory();
    while(token===calibrationToken&&performance.now()<until){const m=readMicLevel(),env=recentOutputEnvelope(readOutputLevel());updateCalibrationMeter(m.peak);micR.push(m.rms);micP.push(m.peak);outR.push(env.rms);outP.push(env.peak);if(env.rms>.0025)ratiosR.push(clamp(Math.max(0,m.rms-noise.rms)/env.rms,0,8));if(env.peak>.008)ratiosP.push(clamp(Math.max(0,m.peak-noise.peak)/env.peak,0,8));await waitFrame()}
    if(token!==calibrationToken)throw Error("calibration-cancelled");if(ratiosR.length<5||ratiosP.length<5)throw Error("端末音の測定量が不足しました");
    return {micRms:percentile(micR,.70),micPeak:percentile(micP,.85),outputRms:percentile(outR,.65),outputPeak:percentile(outP,.80),bleedRmsCoef:percentile(ratiosR,.60),bleedPeakCoef:percentile(ratiosP,.60)};
  }
  async function captureOneHit(noise,token,timeoutMs=3600){
    const until=performance.now()+timeoutMs;let prevR=0,prevP=0,capture=null;
    while(token===calibrationToken&&performance.now()<until){const raw=readMicLevel(),now=performance.now();updateCalibrationMeter(raw.peak);if(capture){capture.rms=Math.max(capture.rms,raw.rms);capture.peak=Math.max(capture.peak,raw.peak);capture.rawPeak=Math.max(capture.rawPeak,raw.peak);if(now>=capture.until)return capture}else{const rise=raw.rms-prevR,peakRise=raw.peak-prevP,rmsGate=Math.max(.00028,noise.rms*1.55),peakGate=Math.max(.0011,noise.peak*1.50),riseGate=Math.max(.00010,noise.rms*.20),peakRiseGate=Math.max(.00028,noise.peak*.15);if((raw.rms>rmsGate||raw.peak>peakGate)&&(rise>riseGate||peakRise>peakRiseGate))capture={rms:raw.rms,peak:raw.peak,rawPeak:raw.peak,until:now+105}}prevR=raw.rms;prevP=raw.peak;await waitFrame()}
    if(token!==calibrationToken)throw Error("calibration-cancelled");return null;
  }
  function buildCalibration(){
    const {noise,speaker,strong,medium,weak}=calState,thresholdRms=Math.max(weak.rms*.85,noise.rms*1.65),thresholdPeak=Math.max(weak.peak*.85,noise.peak*1.55),riseGate=Math.max(.00008,(weak.rms-noise.rms)*.12,noise.rms*.12),peakRiseGate=Math.max(.00020,(weak.peak-noise.peak)*.10,noise.peak*.10),weakClear=weak.rms>noise.rms*1.35||weak.peak>noise.peak*1.35,ordered=strong.peak>medium.peak*1.04&&medium.peak>weak.peak*1.04;
    return {noise,speaker,strong,medium,weak,bleedRmsCoef:speaker.bleedRmsCoef,bleedPeakCoef:speaker.bleedPeakCoef,thresholdRms,thresholdPeak,riseGate,peakRiseGate,weakClear,ordered};
  }

  const nextHitStage=s=>s==="strong"?"medium":s==="medium"?"weak":null,hitLabel=s=>s==="strong"?"強く":s==="medium"?"普通の強さで":"弱く",hitButton=s=>s==="strong"?"強を測定":s==="medium"?"中を測定":"弱を測定";
  function prepareStage(stage){calState.stage=stage;calState.candidate=null;showAccept(false);setCandidate("");if(stage==="noise"){setInstruction("周囲の音を測定します。パッドはまだ叩かないでください");setAction("周囲の音を測定")}else if(stage==="speaker"){setInstruction("端末からテスト伴奏を流し、出力音量とマイクへの回り込みの関係を測定します");setAction("端末音を測定")}else{setInstruction(`伴奏は停止しています。「${hitButton(stage).replace("を測定","")}」を押してから、パッドを${hitLabel(stage)}1回叩いてください`);setAction(hitButton(stage))}}
  function resetCalibrationUi(){for(const name of ["noise","speaker","strong","medium","weak"])setCalStep(name,"idle","待機");const marker=ui("#micCalThresholdMarker");if(marker){marker.classList.remove("show");marker.style.left="0%"}showStart(false);showAccept(false);setCandidate("");setDetail("端末音の回り込み測定と、パッド自体の感度測定を分けて行います。");prepareStage("noise")}
  function resetCalibration(){calibrationToken++;stopCalibrationBed();calBusy=false;micCalibration=null;calState={stage:"noise",noise:null,speaker:null,strong:null,medium:null,weak:null,candidate:null,stopBed:null};resetOutputHistory();resetCalibrationUi()}

  async function runCalibrationAction(){
    if(calBusy||!calState)return;const stage=calState.stage,token=calibrationToken;calBusy=true;setAction(stage==="noise"||stage==="speaker"?"測定中…":"検出待ち…",true);showAccept(false);setCandidate("");
    try{
      if(stage==="noise"){
        setCalStep("noise","active","測定中");setInstruction("約1秒、そのまま静かにしてください");calState.noise=await measureNoise(token);if(token!==calibrationToken)return;setCalStep("noise","done","完了");setDetail("周囲音を記録しました。次に端末音の回り込み特性を測定します。");prepareStage("speaker");
      }else if(stage==="speaker"){
        setCalStep("speaker","active","準備中");setInstruction("テスト伴奏を準備しています。パッドは叩かないでください");await loadCalibrationStems();if(token!==calibrationToken)return;startCalibrationBed();await waitMs(250);setCalStep("speaker","active","測定中");setInstruction("テスト伴奏の出力とマイクへの回り込みを測定しています。パッドは叩かないでください");calState.speaker=await measureSpeakerRelation(calState.noise,token);if(token!==calibrationToken)return;stopCalibrationBed();resetOutputHistory();await waitMs(220);setCalStep("speaker","done","完了");setDetail("回り込み係数を記録しました。伴奏は停止しました。ここから強・中・弱のパッド音だけを測定します。");prepareStage("strong");
      }else{
        stopCalibrationBed();setCalStep(stage,"active","検出待ち");setInstruction(`伴奏は停止しています。今からパッドを${hitLabel(stage)}1回だけ叩いてください`);const hit=await captureOneHit(calState.noise,token);if(token!==calibrationToken)return;
        if(!hit){setCalStep(stage,"active","未検出");setDetail("打音を検出できませんでした。同じ段階をもう一度測定してください。");setAction(hitButton(stage));return}
        calState.candidate=hit;setCalStep(stage,"active","候補あり");setCandidate(`候補レベル  ${Math.round(meterPercent(hit.rawPeak))}%`);setInstruction("検出しました。この打音を使うなら「この値を採用」を押してください");setDetail("検出しただけでは次へ進みません。違う音なら「測り直す」を押してください。");setAction("測り直す");showAccept(true);
      }
    }catch(e){if(String(e?.message)!=="calibration-cancelled"){console.error(e);stopCalibrationBed();setDetail(e?.message||"測定に失敗しました");setAction(stage==="noise"?"周囲の音を測定":stage==="speaker"?"端末音を測定":hitButton(stage))}}
    finally{calBusy=false;const b=ui("#micCalAction");if(b)b.disabled=false}
  }
  function acceptCandidate(){
    if(calBusy||!calState?.candidate)return;const stage=calState.stage;if(!["strong","medium","weak"].includes(stage))return;calState[stage]=calState.candidate;calState.candidate=null;setCalStep(stage,"done","採用");showAccept(false);setCandidate("");const next=nextHitStage(stage);
    if(next){setDetail(`${stage==="strong"?"強":"中"}の値を採用しました。伴奏は停止したままです。`);prepareStage(next);return}
    micCalibration=buildCalibration();micNoiseFloor=micCalibration.noise.rms;resetOutputHistory();const marker=ui("#micCalThresholdMarker");if(marker){marker.style.left=`${meterPercent(micCalibration.thresholdPeak)}%`;marker.classList.add("show")}
    setInstruction("調整完了");setDetail(micCalibration.weakClear?"弱いパッド音の少し下を基準にしました。演奏中は実際の端末出力の起伏から回り込み量を毎フレーム推定し、マイク入力から差し引きます。":"弱いパッド音と周囲音が近い状態です。必要なら最初からやり直してください。");ui("#micCalAction")?.classList.add("hidden");showStart(true);
  }
  function showCalibration(){const screen=ensureCalibrationScreen();setup.classList.add("hidden");screen.classList.remove("hidden");resetCalibration();return new Promise(resolve=>{calResolve=resolve;ui("#micCalAction").onclick=()=>void runCalibrationAction();ui("#micCalAccept").onclick=acceptCandidate;ui("#micCalRetry").onclick=resetCalibration;ui("#micCalStart").onclick=()=>{if(!micCalibration)return;calibrationToken++;stopCalibrationBed();screen.classList.add("hidden");calResolve?.(true);calResolve=null}})}

  function micFrame(){
    micRaf=0;if(runMode!=="pad"||!micAnalyser||typeof running==="undefined"||!running)return;
    if(!paused){
      const raw=readMicLevel(),c=compensatedMic(raw,readOutputLevel()),rms=c.rms,peak=c.peak,rise=rms-micPrevRms,peakRise=peak-micPrevPeak,
            threshold=(micCalibration?Math.max(micCalibration.thresholdRms,micNoiseFloor*1.08):Math.max(.00195,micNoiseFloor*1.18))+c.predictedRms*BLEED_GUARD_RATIO,
            riseGate=micCalibration?micCalibration.riseGate:Math.max(.00045,micNoiseFloor*.06),
            peakGate=(micCalibration?Math.max(micCalibration.thresholdPeak,micNoiseFloor*1.35):Math.max(.0066,micNoiseFloor*1.55))+c.predictedPeak*BLEED_GUARD_RATIO,
            peakRiseGate=micCalibration?micCalibration.peakRiseGate:Math.max(.0012,micNoiseFloor*.18),
            releaseRms=micCalibration?Math.max(micCalibration.noise.rms*1.30,threshold*.52):Math.max(micNoiseFloor*1.12,threshold*.52),
            releasePeak=micCalibration?Math.max(micCalibration.noise.peak*1.30,peakGate*.52):Math.max(micNoiseFloor*1.60,peakGate*.52),now=performance.now(),loudEnough=rms>threshold||peak>peakGate,transient=rise>riseGate||peakRise>peakRiseGate,
            normalOnset=micArmed&&now>=micSelfGuardUntil&&loudEnough&&transient&&now-micLastHit>=MIC_REFRACTORY_MS,strongRetrigger=!micArmed&&now>=micSelfGuardUntil&&now-micLastHit>=MIC_RETRIGGER_GUARD_MS&&loudEnough&&(rise>riseGate*2.8||peakRise>peakRiseGate*2.8);
      if(normalOnset||strongRetrigger){micLastHit=now;micArmed=false;micQuietFrames=0;consumePadMicHit()}else if(!micArmed){if(rms<releaseRms&&peak<releasePeak){if(++micQuietFrames>=MIC_RELEASE_FRAMES){micArmed=true;micQuietFrames=0}}else micQuietFrames=0}
      if(!loudEnough&&rms<threshold*1.35)micNoiseFloor=Math.max(.00005,Math.min(.02,micNoiseFloor*.997+rms*.003));micPrevRms=rms;micPrevPeak=peak;
    }
    micRaf=requestAnimationFrame(micFrame);
  }
  function startMicLoop(){stopMicLoop();micLastHit=-Infinity;micPrevRms=0;micPrevPeak=0;micArmed=true;micQuietFrames=0;micSelfGuardUntil=0;resetOutputHistory();micRaf=requestAnimationFrame(micFrame)}

  const baseStart=startButton.onclick;
  startButton.onclick=async function(e){
    runMode=selectedMode();document.body.dataset.performanceRun=runMode;
    if(runMode==="pad"){
      const before=loadState?.textContent||"";startButton.disabled=true;if(loadState)loadState.textContent="マイクの使用を許可してください…";
      try{await ensureMic();try{await ac.resume()}catch{}if(loadState)loadState.textContent=before;await showCalibration()}catch(err){console.error(err);if(loadState)loadState.textContent=err?.name==="NotAllowedError"?"パッド練習にはマイクの許可が必要です":(err?.message||"マイクを開始できません");setup.classList.remove("hidden");startButton.disabled=false;return}startButton.disabled=false;
    }
    const out=baseStart?await baseStart.call(this,e):undefined;if(runMode==="pad"&&typeof running!=="undefined"&&running)startMicLoop();else if(runMode==="pad"&&typeof running!=="undefined"&&!running)setup.classList.remove("hidden");return out;
  };

  globalThis.DruMasterPerformanceMode={getSelectedMode:selectedMode,getRunMode:()=>runMode,isPerformanceRun:()=>isPerformanceMode(runMode),isPadRun:()=>runMode==="pad",consumeNearest,consumePadMicHit,stopMic:releaseMic,getMicCalibration:()=>micCalibration,micTimingOffsetSec:()=>MIC_TIMING_OFFSET_SEC};
  addEventListener("pagehide",releaseMic,{once:true});
})();