"use strict";

(()=>{
  const mobileQuery=matchMedia("(hover:none) and (pointer:coarse) and (max-width:900px)"),
        debugMode=document.body.dataset.micDebug==="1"||new URLSearchParams(location.search).has("micdebug"),
        setup=document.querySelector("#setup"),options=document.querySelector(".options"),startButton=document.querySelector("#start"),
        hiddenToggle=document.querySelector("#hiddenToggle"),autoToggle=document.querySelector("#autoToggle"),loadState=document.querySelector("#loadState"),
        game=document.querySelector("#game"),app=document.querySelector("#app");
  if(!setup||!options||!startButton||!game||!app)return;

  const PERFECT_WINDOW=.035,GREAT_WINDOW=.105,GOOD_WINDOW=.160;
  const MIC_REFRACTORY_MS=72,MIC_RETRIGGER_GUARD_MS=92,MIC_RELEASE_FRAMES=3,MIC_SELF_AUDIO_GUARD_MS=105;
  const MIC_TIMING_OFFSET_SEC=0,NOISE_CAPTURE_MS=1500,AEC_CAPTURE_SEC=2.8,AEC_ADAPT_MS=1800,AEC_TEST_MS=900;
  const BANDS=[[180,350],[350,700],[700,1200],[1200,2000],[2000,3200],[3200,5000],[5000,8000],[8000,12000]];

  const modeRow=document.createElement("label");
  modeRow.className="option performance-mode-option";
  modeRow.innerHTML='<span>演奏モード</span><select id="performanceModeSelect" aria-label="演奏モード"><option value="normal">通常</option><option value="touch">どこでもタッチ</option><option value="pad">パッド練習</option></select>';
  options.appendChild(modeRow);
  const modeSelect=modeRow.querySelector("select");
  if(debugMode)modeSelect.value="pad";

  let runMode="normal",micStream=null,micSource=null,micFilter=null,rawAnalyser=null,rawTimeData=null,rawFreqData=null,
      aecNode=null,residualAnalyser=null,residualTimeData=null,residualFreqData=null,residualSilent=null,residualDestination=null,
      micRaf=0,micNoiseFloor=.0009,micPrevRms=0,micPrevPeak=0,micLastHit=-Infinity,micArmed=true,micQuietFrames=0,micSelfGuardUntil=0,
      micCalibration=null,calibrationScreen=null,calibrationToken=0,calState=null,calResolve=null,calBusy=false,
      aecCaptureResolve=null,aecMetrics={rawRms:0,refRms:0,residualRms:0,erleDb:0,delaySamples:0},workletLoaded=false;

  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const waitFrame=()=>new Promise(r=>requestAnimationFrame(r)),waitMs=ms=>new Promise(r=>setTimeout(r,ms));
  function selectedMode(){return debugMode?"pad":(mobileQuery.matches?(modeSelect?.value||"normal"):"normal")}
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
    if((!mobileQuery.matches&&!debugMode)||!isPerformanceMode()||typeof running==="undefined"||!running||paused||autoplay||document.body.classList.contains("acoustic-calibrating"))return false;
    const match=nearestPlayable(current()-(source==="mic"?MIC_TIMING_OFFSET_SEC:0));if(!match||match.delta>GOOD_WINDOW)return false;
    const {note,delta}=match;note.hit=true;playDrum(note.note,note.type,note.velocity/127);if(typeof flashPart==="function"&&typeof PART!=="undefined")flashPart(PART[note.type]);const label=gradeHit(note,delta);emitGrade(note,label);return true;
  }
  function showPadSnareFeedback(){
    micSelfGuardUntil=performance.now()+MIC_SELF_AUDIO_GUARD_MS;
    try{aecNode?.port.postMessage({type:"freeze",ms:180})}catch{}
    if(typeof playDrum==="function"&&typeof DEFAULT_NOTE!=="undefined")playDrum(DEFAULT_NOTE.snare,"snare",.90);
    const snare=document.querySelector('#hitLayer [data-part="snare"]:not(.inactive)')||document.querySelector('#hitLayer [data-part="snare"]');
    if(snare&&typeof flashPart==="function")flashPart("snare",snare);globalThis.DruMasterMobileTapEffect?.showElement?.(snare);
  }
  function consumePadMicHit(){
    if((!mobileQuery.matches&&!debugMode)||runMode!=="pad"||typeof running==="undefined"||!running||paused||autoplay||document.body.classList.contains("acoustic-calibrating"))return false;
    showPadSnareFeedback();const match=nearestPlayable(current()-MIC_TIMING_OFFSET_SEC);if(!match||match.delta>GOOD_WINDOW)return false;
    const {note,delta}=match;note.hit=true;const label=gradeHit(note,delta);emitGrade(note,label);return true;
  }
  game.addEventListener("pointerdown",e=>{if(runMode!=="touch"||(!mobileQuery.matches&&!debugMode)||!running||paused)return;if(e.target.closest("#pause,#pausePanel button,.mic-debug-controls"))return;const ok=consumeNearest("touch");if(ok){e.preventDefault();e.stopImmediatePropagation()}},true);

  function nodeLevel(analyser,data){if(!analyser||!data)return {rms:0,peak:0};analyser.getFloatTimeDomainData(data);let sum=0,peak=0;for(const x of data){const a=Math.abs(x);sum+=x*x;if(a>peak)peak=a}return {rms:Math.sqrt(sum/data.length),peak}}
  const readRawLevel=()=>nodeLevel(rawAnalyser,rawTimeData),readResidualLevel=()=>nodeLevel(residualAnalyser,residualTimeData);
  function bandPowers(analyser,data){
    if(!analyser||!data)return BANDS.map(()=>0);analyser.getFloatFrequencyData(data);const nyquist=ac.sampleRate/2,binHz=nyquist/data.length;
    return BANDS.map(([lo,hi])=>{let sum=0,n=0;const a=Math.max(0,Math.floor(lo/binHz)),b=Math.min(data.length-1,Math.ceil(hi/binHz));for(let i=a;i<=b;i++){const db=data[i];if(Number.isFinite(db)){sum+=Math.pow(10,db/10);n++}}return n?sum/n:0});
  }
  function percentile(values,p=.5){if(!values.length)return 0;const a=[...values].sort((x,y)=>x-y),i=Math.min(a.length-1,Math.max(0,Math.floor((a.length-1)*p)));return a[i]}
  function meterPercent(peak){const db=20*Math.log10(Math.max(1e-6,peak));return clamp((db+60)/60*100,0,100)}

  async function ensureMic(){
    if(micStream&&aecNode)return;
    if(!navigator.mediaDevices?.getUserMedia)throw Error("このブラウザではマイク入力を利用できません");
    if(typeof ac==="undefined"||!ac)throw Error("オーディオ機能の準備ができていません");
    micStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false,channelCount:1},video:false});
    if(!workletLoaded){if(!ac.audioWorklet)throw Error("このブラウザでは精密な音響相殺を利用できません");await ac.audioWorklet.addModule("js/acoustic-cancel-processor.js?v=20260827-aec1");workletLoaded=true}
    micSource=ac.createMediaStreamSource(micStream);
    micFilter=ac.createBiquadFilter();micFilter.type="highpass";micFilter.frequency.value=180;micFilter.Q.value=.55;
    rawAnalyser=ac.createAnalyser();rawAnalyser.fftSize=1024;rawAnalyser.smoothingTimeConstant=0;rawTimeData=new Float32Array(rawAnalyser.fftSize);rawFreqData=new Float32Array(rawAnalyser.frequencyBinCount);
    aecNode=new AudioWorkletNode(ac,"drumaster-acoustic-canceller",{numberOfInputs:2,numberOfOutputs:1,outputChannelCount:[1]});
    residualAnalyser=ac.createAnalyser();residualAnalyser.fftSize=1024;residualAnalyser.smoothingTimeConstant=0;residualTimeData=new Float32Array(residualAnalyser.fftSize);residualFreqData=new Float32Array(residualAnalyser.frequencyBinCount);
    residualSilent=ac.createGain();residualSilent.gain.value=0;residualDestination=ac.createMediaStreamDestination();
    micSource.connect(micFilter);micFilter.connect(rawAnalyser);micFilter.connect(aecNode,0,0);
    if(typeof safetyLimiter==="undefined"||!safetyLimiter)throw Error("伴奏参照信号を取得できません");
    safetyLimiter.connect(aecNode,0,1);
    aecNode.connect(residualAnalyser);residualAnalyser.connect(residualSilent).connect(ac.destination);aecNode.connect(residualDestination);
    aecNode.port.onmessage=e=>{
      const m=e.data||{};
      if(m.type==="metrics"){aecMetrics={...aecMetrics,...m};globalThis.dispatchEvent(new CustomEvent("drumaster-aec-metrics",{detail:aecMetrics}))}
      else if(m.type==="capture"&&aecCaptureResolve){const r=aecCaptureResolve;aecCaptureResolve=null;r(m)}
    };
    globalThis.DruMasterMicInputSettings=micStream.getAudioTracks?.()[0]?.getSettings?.()||{};
    micNoiseFloor=.0009;micPrevRms=0;micPrevPeak=0;micLastHit=-Infinity;micArmed=true;micQuietFrames=0;micSelfGuardUntil=0;
  }
  function stopMicLoop(){if(micRaf)cancelAnimationFrame(micRaf);micRaf=0}
  function releaseMic(){
    calibrationToken++;stopMicLoop();try{if(aecNode&&safetyLimiter)safetyLimiter.disconnect(aecNode)}catch{}try{micSource?.disconnect()}catch{}try{micFilter?.disconnect()}catch{}try{aecNode?.disconnect()}catch{}try{residualAnalyser?.disconnect()}catch{}try{residualSilent?.disconnect()}catch{}for(const track of micStream?.getTracks?.()||[])track.stop();
    micStream=null;micSource=null;micFilter=null;rawAnalyser=null;rawTimeData=null;rawFreqData=null;aecNode=null;residualAnalyser=null;residualTimeData=null;residualFreqData=null;residualSilent=null;residualDestination=null;micArmed=true;micQuietFrames=0;micSelfGuardUntil=0;
  }

  function ensureCalibrationScreen(){
    if(calibrationScreen)return calibrationScreen;const section=document.createElement("section");section.id="micCalibration";section.className="screen mic-calibration hidden";
    section.innerHTML=`<div class="mic-calibration-card"><p class="mic-cal-eyebrow">PAD PRACTICE</p><h2>マイク感度調整</h2><p id="micCalInstruction" class="mic-cal-instruction">準備しています…</p><div class="mic-cal-meter"><i id="micCalMeterFill"></i><b id="micCalThresholdMarker"></b></div><div class="mic-cal-steps"><div data-cal-step="noise"><span>1</span><b>環境ノイズ</b><em>待機</em></div><div data-cal-step="strong"><span>2</span><b>強</b><em>待機</em></div><div data-cal-step="medium"><span>3</span><b>中</b><em>待機</em></div><div data-cal-step="weak"><span>4</span><b>弱</b><em>待機</em></div></div><p id="micCalCandidate" class="mic-cal-candidate"></p><p id="micCalDetail" class="mic-cal-detail">環境ノイズを記録し、その後パッド音だけを測定します。伴奏はここでは鳴りません。</p><div class="mic-cal-actions manual-cal-actions"><button id="micCalAction" type="button">環境ノイズを収録</button><button id="micCalAccept" type="button" class="hidden">この値を採用</button><button id="micCalStart" type="button" class="hidden" disabled>演奏開始</button><button id="micCalRetry" type="button">最初からやり直す</button></div></div>`;
    app.appendChild(section);calibrationScreen=section;return section;
  }
  const ui=sel=>calibrationScreen?.querySelector(sel);
  function setCalStep(name,state,text){const row=ui(`[data-cal-step="${name}"]`);if(!row)return;row.dataset.state=state;const em=row.querySelector("em");if(em)em.textContent=text}
  function updateCalibrationMeter(peak){const f=ui("#micCalMeterFill");if(f)f.style.width=`${meterPercent(peak)}%`}
  function setInstruction(text){const n=ui("#micCalInstruction");if(n)n.textContent=text}function setDetail(text){const n=ui("#micCalDetail");if(n)n.textContent=text}function setCandidate(text=""){const n=ui("#micCalCandidate");if(n)n.textContent=text}
  function setAction(text,disabled=false){const b=ui("#micCalAction");if(b){b.textContent=text;b.disabled=disabled;b.classList.remove("hidden")}}function showAccept(show){ui("#micCalAccept")?.classList.toggle("hidden",!show)}function showStart(show){const b=ui("#micCalStart");if(b){b.classList.toggle("hidden",!show);b.disabled=!show}}

  async function measureNoiseProfile(token,durationMs=NOISE_CAPTURE_MS){
    const rms=[],peak=[],bandFrames=BANDS.map(()=>[]),until=performance.now()+durationMs;
    while(token===calibrationToken&&performance.now()<until){const m=readRawLevel(),bands=bandPowers(rawAnalyser,rawFreqData);rms.push(m.rms);peak.push(m.peak);bands.forEach((v,i)=>bandFrames[i].push(v));updateCalibrationMeter(m.peak);await waitFrame()}
    if(token!==calibrationToken)throw Error("calibration-cancelled");
    return {rms:Math.max(.00003,percentile(rms,.70)),peak:Math.max(.00015,percentile(peak,.85)),bands:bandFrames.map(a=>Math.max(1e-12,percentile(a,.72)))};
  }
  async function captureOneHit(noise,token,timeoutMs=3800){
    const until=performance.now()+timeoutMs;let prevR=0,prevP=0,capture=null;
    while(token===calibrationToken&&performance.now()<until){const raw=readRawLevel(),now=performance.now();updateCalibrationMeter(raw.peak);if(capture){capture.rms=Math.max(capture.rms,raw.rms);capture.peak=Math.max(capture.peak,raw.peak);if(now>=capture.until)return capture}else{const rise=raw.rms-prevR,peakRise=raw.peak-prevP,rmsGate=Math.max(.00025,noise.rms*1.55),peakGate=Math.max(.001,noise.peak*1.50),riseGate=Math.max(.00008,noise.rms*.18),peakRiseGate=Math.max(.00024,noise.peak*.14);if((raw.rms>rmsGate||raw.peak>peakGate)&&(rise>riseGate||peakRise>peakRiseGate))capture={rms:raw.rms,peak:raw.peak,until:now+115}}prevR=raw.rms;prevP=raw.peak;await waitFrame()}
    if(token!==calibrationToken)throw Error("calibration-cancelled");return null;
  }
  function buildCalibration(){
    const {noise,strong,medium,weak}=calState,thresholdRms=Math.max(weak.rms*.82,noise.rms*1.55),thresholdPeak=Math.max(weak.peak*.82,noise.peak*1.48),riseGate=Math.max(.00007,(weak.rms-noise.rms)*.10,noise.rms*.10),peakRiseGate=Math.max(.00018,(weak.peak-noise.peak)*.09,noise.peak*.09),weakClear=weak.rms>noise.rms*1.30||weak.peak>noise.peak*1.30,ordered=strong.peak>medium.peak*1.03&&medium.peak>weak.peak*1.03;
    return {noise,strong,medium,weak,thresholdRms,thresholdPeak,riseGate,peakRiseGate,weakClear,ordered,aec:null};
  }
  const nextHitStage=s=>s==="strong"?"medium":s==="medium"?"weak":null,hitLabel=s=>s==="strong"?"強く":s==="medium"?"普通の強さで":"弱く",hitButton=s=>s==="strong"?"強を測定":s==="medium"?"中を測定":"弱を測定";
  function prepareStage(stage){calState.stage=stage;calState.candidate=null;showAccept(false);setCandidate("");if(stage==="noise"){setInstruction("環境ノイズを記録します。パッドは叩かず、そのままにしてください");setAction("環境ノイズを収録")}else{setInstruction(`「${hitButton(stage).replace("を測定","")}」を押してから、パッドを${hitLabel(stage)}1回叩いてください`);setAction(hitButton(stage))}}
  function resetCalibrationUi(){for(const name of ["noise","strong","medium","weak"])setCalStep(name,"idle","待機");const marker=ui("#micCalThresholdMarker");if(marker){marker.classList.remove("show");marker.style.left="0%"}showStart(false);showAccept(false);setCandidate("");setDetail("環境ノイズは周波数帯ごとのプロファイルとして記録し、演奏中の残差信号から差し引きます。");prepareStage("noise")}
  function resetCalibration(){calibrationToken++;calBusy=false;micCalibration=null;calState={stage:"noise",noise:null,strong:null,medium:null,weak:null,candidate:null};resetCalibrationUi()}
  async function runCalibrationAction(){
    if(calBusy||!calState)return;const stage=calState.stage,token=calibrationToken;calBusy=true;setAction(stage==="noise"?"収録中…":"検出待ち…",true);showAccept(false);setCandidate("");
    try{
      if(stage==="noise"){
        setCalStep("noise","active","収録中");setInstruction("約1.5秒、そのまま静かにしてください");calState.noise=await measureNoiseProfile(token);if(token!==calibrationToken)return;setCalStep("noise","done","完了");setDetail("環境ノイズの周波数プロファイルを記録しました。次にパッド音を測定します。");prepareStage("strong");
      }else{
        setCalStep(stage,"active","検出待ち");setInstruction(`今からパッドを${hitLabel(stage)}1回だけ叩いてください`);const hit=await captureOneHit(calState.noise,token);if(token!==calibrationToken)return;
        if(!hit){setCalStep(stage,"active","未検出");setDetail("打音を検出できませんでした。同じ段階をもう一度測定してください。");setAction(hitButton(stage));return}
        calState.candidate=hit;setCalStep(stage,"active","候補あり");setCandidate(`候補レベル ${Math.round(meterPercent(hit.peak))}%`);setInstruction("検出しました。この打音を使うなら「この値を採用」を押してください");setDetail("検出しただけでは次へ進みません。違う音なら「測り直す」を押してください。");setAction("測り直す");showAccept(true);
      }
    }catch(e){if(String(e?.message)!=="calibration-cancelled"){console.error(e);setDetail(e?.message||"測定に失敗しました");setAction(stage==="noise"?"環境ノイズを収録":hitButton(stage))}}
    finally{calBusy=false;const b=ui("#micCalAction");if(b)b.disabled=false}
  }
  function acceptCandidate(){
    if(calBusy||!calState?.candidate)return;const stage=calState.stage;if(!["strong","medium","weak"].includes(stage))return;calState[stage]=calState.candidate;calState.candidate=null;setCalStep(stage,"done","採用");showAccept(false);setCandidate("");const next=nextHitStage(stage);
    if(next){setDetail(`${stage==="strong"?"強":"中"}の値を採用しました。`);prepareStage(next);return}
    micCalibration=buildCalibration();micNoiseFloor=micCalibration.noise.rms;const marker=ui("#micCalThresholdMarker");if(marker){marker.style.left=`${meterPercent(micCalibration.thresholdPeak)}%`;marker.classList.add("show")}
    try{aecNode?.port.postMessage({type:"setNoise",noiseRms:micCalibration.noise.rms,padProtect:Math.max(micCalibration.weak.peak*.70,micCalibration.noise.peak*3.2)})}catch{}
    setInstruction("感度調整完了");setDetail(micCalibration.weakClear?"「演奏開始」の後、伴奏だけを数秒再生して端末固有の回り込み遅延と相殺フィルタを自動調整します。":"弱いパッド音と環境ノイズが近い状態です。必要なら最初からやり直してください。");ui("#micCalAction")?.classList.add("hidden");showStart(true);
  }
  function showCalibration(){const screen=ensureCalibrationScreen();setup.classList.add("hidden");screen.classList.remove("hidden");resetCalibration();return new Promise(resolve=>{calResolve=resolve;ui("#micCalAction").onclick=()=>void runCalibrationAction();ui("#micCalAccept").onclick=acceptCandidate;ui("#micCalRetry").onclick=resetCalibration;ui("#micCalStart").onclick=()=>{if(!micCalibration)return;calibrationToken++;screen.classList.add("hidden");calResolve?.(true);calResolve=null}})}

  function songConfig(){return globalThis.DruMasterSongs?.current||{}}function trackGain(name,fallback){const v=songConfig().mix?.[name];return Number.isFinite(v)?v:fallback}
  async function loadCalibrationStems(){if(typeof loadStem!=="function")return;await loadStem("base","オフボーカル");if(document.querySelector("#vocalToggle")?.checked)await loadStem("vocals","ボーカル");if(document.querySelector("#guideToggle")?.checked)await loadStem("drums","ガイドドラム")}
  function startCalibrationBed(seconds=3,startOffset=18){
    if(typeof ac==="undefined"||!ac||typeof buffers==="undefined"||!buffers.base)throw Error("伴奏の準備ができていません");
    const rateNow=Number(document.querySelector("#tempo")?.value||100)/100,voices=[],when=ac.currentTime+.06,specs=[["base",.95],["vocals",.95],["drums",.70]];
    for(const [name,fallback] of specs){const buf=buffers[name];if(!buf)continue;const s=ac.createBufferSource(),g=ac.createGain(),offset=Math.min(startOffset,Math.max(0,buf.duration-seconds*rateNow-.1));s.buffer=buf;s.playbackRate.value=rateNow;g.gain.value=trackGain(name,fallback);s.connect(g).connect(masterBus);s.start(when,offset,Math.min(buf.duration-offset,seconds*rateNow+.2));voices.push({s,g})}
    return ()=>{for(const v of voices){try{v.s.stop()}catch{}try{v.s.disconnect()}catch{}try{v.g.disconnect()}catch{}}};
  }
  function beginAECapture(seconds){return new Promise(resolve=>{aecCaptureResolve=resolve;aecNode.port.postMessage({type:"beginCapture",seconds})})}
  function estimateDelay(micBuf,refBuf,sr){
    const mic=new Float32Array(micBuf),ref=new Float32Array(refBuf),n=Math.min(mic.length,ref.length),minLag=Math.round(sr*.004),maxLag=Math.min(Math.round(sr*.24),Math.floor(n*.35));
    const scoreAt=(lag,step)=>{let xy=0,xx=0,yy=0,count=0;const start=lag,end=Math.min(n,start+Math.round(sr*1.9));for(let i=start;i<end;i+=step){const x=ref[i-lag],y=mic[i];xy+=x*y;xx+=x*x;yy+=y*y;count++}return count>64?Math.abs(xy)/Math.sqrt(Math.max(1e-18,xx*yy)):0};
    let bestLag=Math.round(sr*.06),best=-1;for(let lag=minLag;lag<=maxLag;lag+=16){const s=scoreAt(lag,16);if(s>best){best=s;bestLag=lag}}
    const lo=Math.max(minLag,bestLag-48),hi=Math.min(maxLag,bestLag+48);for(let lag=lo;lag<=hi;lag++){const s=scoreAt(lag,4);if(s>best){best=s;bestLag=lag}}
    return {samples:bestLag,ms:bestLag/sr*1000,score:best};
  }
  function ensureAcousticOverlay(){
    let el=document.querySelector("#acousticCalibrationOverlay");if(el)return el;el=document.createElement("div");el.id="acousticCalibrationOverlay";el.innerHTML='<div><p>PAD PRACTICE</p><strong>音響調整中</strong><span id="acousticCalibrationText">まだパッドを叩かないでください</span><small id="acousticCalibrationMetric"></small></div>';game.appendChild(el);return el;
  }
  function setAcousticText(text,metric=""){const o=ensureAcousticOverlay();o.querySelector("#acousticCalibrationText").textContent=text;o.querySelector("#acousticCalibrationMetric").textContent=metric}
  function finite(v,f=0){return Number.isFinite(v)?v:f}function dbfs(v){return (20*Math.log10(Math.max(1e-7,finite(v,0)))).toFixed(1)}
  async function runAcousticPreflight(){
    if(!micCalibration||!aecNode)return;document.body.classList.add("acoustic-calibrating");setup.classList.add("hidden");game.classList.remove("hidden");const overlay=ensureAcousticOverlay();overlay.classList.add("show");
    try{
      await loadCalibrationStems();try{await ac.resume()}catch{}
      aecNode.port.postMessage({type:"adapt",enabled:false});aecNode.port.postMessage({type:"resetFilter"});
      setAcousticText("伴奏の回り込みタイミングを測定しています。まだ叩かないでください");
      const capturePromise=beginAECapture(AEC_CAPTURE_SEC),stopBed=startCalibrationBed(AEC_CAPTURE_SEC+.25,18),capture=await capturePromise;stopBed();await waitMs(90);
      const delay=estimateDelay(capture.mic,capture.ref,capture.sampleRate||ac.sampleRate);aecNode.port.postMessage({type:"setDelay",samples:delay.samples});aecNode.port.postMessage({type:"resetFilter"});
      setAcousticText("端末スピーカー→マイクの相殺フィルタを学習しています",`遅延 ${delay.ms.toFixed(1)} ms · 相関 ${(delay.score*100).toFixed(0)}%`);
      aecNode.port.postMessage({type:"adapt",enabled:true});const stopAdapt=startCalibrationBed((AEC_ADAPT_MS+250)/1000,26);await waitMs(AEC_ADAPT_MS);stopAdapt();await waitMs(100);
      setAcousticText("相殺結果を内部テストしています",`残差 ${dbfs(aecMetrics.residualRms)} dBFS · ERLE ${finite(aecMetrics.erleDb,0).toFixed(1)} dB`);
      const stopTest=startCalibrationBed((AEC_TEST_MS+180)/1000,34);await waitMs(AEC_TEST_MS);stopTest();await waitMs(100);
      micCalibration.aec={delaySamples:delay.samples,delayMs:delay.ms,correlation:delay.score,erleDb:aecMetrics.erleDb,residualRms:aecMetrics.residualRms};
      setAcousticText("調整完了。演奏を開始します",`遅延 ${delay.ms.toFixed(1)} ms · 残差 ${dbfs(aecMetrics.residualRms)} dBFS`);await waitMs(420);
    }finally{overlay.classList.remove("show");document.body.classList.remove("acoustic-calibrating");game.classList.add("hidden")}
  }
  function spectralExcess(){
    if(!micCalibration?.noise?.bands||!residualAnalyser)return {ratio:0,hot:false};const p=bandPowers(residualAnalyser,residualFreqData),n=micCalibration.noise.bands;let excess=0,noise=0;for(let i=0;i<p.length;i++){noise+=n[i];excess+=Math.max(0,p[i]-n[i]*1.25)}const ratio=excess/Math.max(1e-12,noise);return {ratio,hot:ratio>.55};
  }
  function micFrame(){
    micRaf=0;if(runMode!=="pad"||!residualAnalyser||typeof running==="undefined"||!running)return;
    if(!paused&&!document.body.classList.contains("acoustic-calibrating")){
      const c=readResidualLevel(),rms=c.rms,peak=c.peak,rise=rms-micPrevRms,peakRise=peak-micPrevPeak,spec=spectralExcess(),
            threshold=micCalibration?Math.max(micCalibration.thresholdRms*.76,micNoiseFloor*1.06):Math.max(.0016,micNoiseFloor*1.15),
            peakGate=micCalibration?Math.max(micCalibration.thresholdPeak*.76,micCalibration.noise.peak*1.28):Math.max(.0055,micNoiseFloor*1.5),
            riseGate=micCalibration?micCalibration.riseGate*.68:Math.max(.00035,micNoiseFloor*.05),peakRiseGate=micCalibration?micCalibration.peakRiseGate*.68:Math.max(.001,micNoiseFloor*.15),
            releaseRms=Math.max(micNoiseFloor*1.15,threshold*.50),releasePeak=Math.max((micCalibration?.noise?.peak||micNoiseFloor)*1.30,peakGate*.50),now=performance.now(),loudEnough=rms>threshold||peak>peakGate,
            transient=rise>riseGate||peakRise>peakRiseGate,strongSpectral=spec.hot||peak>peakGate*1.30,
            normalOnset=micArmed&&now>=micSelfGuardUntil&&loudEnough&&transient&&strongSpectral&&now-micLastHit>=MIC_REFRACTORY_MS,
            strongRetrigger=!micArmed&&now>=micSelfGuardUntil&&now-micLastHit>=MIC_RETRIGGER_GUARD_MS&&loudEnough&&(rise>riseGate*2.5||peakRise>peakRiseGate*2.5)&&strongSpectral;
      if(normalOnset||strongRetrigger){micLastHit=now;micArmed=false;micQuietFrames=0;try{aecNode.port.postMessage({type:"freeze",ms:190})}catch{}consumePadMicHit()}else if(!micArmed){if(rms<releaseRms&&peak<releasePeak){if(++micQuietFrames>=MIC_RELEASE_FRAMES){micArmed=true;micQuietFrames=0}}else micQuietFrames=0}
      if(!loudEnough&&rms<threshold*1.30)micNoiseFloor=Math.max(.00003,Math.min(.02,micNoiseFloor*.998+rms*.002));micPrevRms=rms;micPrevPeak=peak;
    }
    micRaf=requestAnimationFrame(micFrame);
  }
  function startMicLoop(){stopMicLoop();micLastHit=-Infinity;micPrevRms=0;micPrevPeak=0;micArmed=true;micQuietFrames=0;micSelfGuardUntil=0;micRaf=requestAnimationFrame(micFrame)}

  const baseStart=startButton.onclick;
  startButton.onclick=async function(e){
    runMode=selectedMode();document.body.dataset.performanceRun=runMode;
    if(runMode==="pad"){
      const before=loadState?.textContent||"";startButton.disabled=true;if(loadState)loadState.textContent="マイクの使用を許可してください…";
      try{await ensureMic();try{await ac.resume()}catch{}if(loadState)loadState.textContent=before;await showCalibration();await runAcousticPreflight()}catch(err){console.error(err);if(loadState)loadState.textContent=err?.name==="NotAllowedError"?"パッド練習にはマイクの許可が必要です":(err?.message||"マイクを開始できません");game.classList.add("hidden");calibrationScreen?.classList.add("hidden");setup.classList.remove("hidden");startButton.disabled=false;return}startButton.disabled=false;
    }
    const out=baseStart?await baseStart.call(this,e):undefined;if(runMode==="pad"&&typeof running!=="undefined"&&running)startMicLoop();else if(runMode==="pad"&&typeof running!=="undefined"&&!running)setup.classList.remove("hidden");return out;
  };

  globalThis.DruMasterPerformanceMode={
    getSelectedMode:selectedMode,getRunMode:()=>runMode,isPerformanceRun:()=>isPerformanceMode(runMode),isPadRun:()=>runMode==="pad",consumeNearest,consumePadMicHit,
    stopMic:releaseMic,getMicCalibration:()=>micCalibration,getAECMetrics:()=>({...aecMetrics}),getResidualStream:()=>residualDestination?.stream||null,getRawMicStream:()=>micStream,micTimingOffsetSec:()=>MIC_TIMING_OFFSET_SEC
  };
  addEventListener("pagehide",releaseMic,{once:true});
})();
