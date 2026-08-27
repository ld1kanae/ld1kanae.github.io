"use strict";

(()=>{
  const mobileQuery=matchMedia("(hover:none) and (pointer:coarse) and (max-width:900px)"),
        debugMode=new URLSearchParams(location.search).has("micdebug"),
        setup=document.querySelector("#setup"),options=document.querySelector(".options"),startButton=document.querySelector("#start"),
        hiddenToggle=document.querySelector("#hiddenToggle"),autoToggle=document.querySelector("#autoToggle"),loadState=document.querySelector("#loadState"),
        game=document.querySelector("#game"),app=document.querySelector("#app");
  if(!setup||!options||!startButton||!game||!app)return;

  const PERFECT_WINDOW=.035,GREAT_WINDOW=.105,GOOD_WINDOW=.160;
  const NOISE_CAPTURE_MAX_SEC=8,NOISE_CAPTURE_MIN_SEC=1,PAD_SAMPLE_TARGET=8;
  const AEC_CAPTURE_SEC=2.8,AEC_ADAPT_MS=1800,AEC_TEST_MS=900;
  const BAND_EDGES=[180,260,380,550,800,1150,1650,2350,3350,4700,6500,9000,12000];

  const modeRow=document.createElement("label");
  modeRow.className="option performance-mode-option";
  modeRow.innerHTML='<span>演奏モード</span><select id="performanceModeSelect" aria-label="演奏モード"><option value="normal">通常</option><option value="touch">どこでもタッチ</option><option value="pad">パッド練習</option></select>';
  options.appendChild(modeRow);
  const modeSelect=modeRow.querySelector("select");
  if(debugMode)modeSelect.value="pad";

  let runMode="normal",micStream=null,micSource=null,micFilter=null,rawAnalyser=null,rawTimeData=null,
      aecNode=null,residualAnalyser=null,residualTimeData=null,residualSilent=null,residualDestination=null,
      micCalibration=null,calibrationScreen=null,calibrationToken=0,calResolve=null,calBusy=false,calStage="noise",
      aecCaptureResolve=null,aecMetrics={rawRms:0,refRms:0,residualRms:0,erleDb:0,delaySamples:0},workletLoaded=false,
      noiseCaptureActive=false,noiseCaptureReady=false,noiseFinishRequested=false,
      padModel=null,padClassifier={lastScore:0,threshold:.62,lastAccepted:false,samples:0,testHits:0,testCandidates:0};

  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const waitFrame=()=>new Promise(r=>requestAnimationFrame(r)),waitMs=ms=>new Promise(r=>setTimeout(r,ms));
  const percentile=(values,p=.5)=>{if(!values.length)return 0;const a=[...values].sort((x,y)=>x-y),i=Math.min(a.length-1,Math.max(0,Math.floor((a.length-1)*p)));return a[i]};
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
  function consumeNearest(){
    if((!mobileQuery.matches&&!debugMode)||!isPerformanceMode()||typeof running==="undefined"||!running||paused||autoplay||document.body.classList.contains("acoustic-calibrating"))return false;
    const match=nearestPlayable(current());if(!match||match.delta>GOOD_WINDOW)return false;
    const {note,delta}=match;note.hit=true;playDrum(note.note,note.type,note.velocity/127);if(typeof flashPart==="function"&&typeof PART!=="undefined")flashPart(PART[note.type]);const label=gradeHit(note,delta);emitGrade(note,label);return true;
  }
  function showPadSnareFeedback(){
    /* Mic-detected pad hits must never play a speaker snare here. Doing so feeds
       the synthetic snare back into the microphone and can self-trigger forever.
       Keep only visual feedback and AEC-coefficient freeze; there is no candidate
       dead-time, so rapid rolls remain detectable. */
    try{aecNode?.port.postMessage({type:"freeze",ms:190})}catch{}
    const snare=document.querySelector('#hitLayer [data-part="snare"]:not(.inactive)')||document.querySelector('#hitLayer [data-part="snare"]');
    if(snare&&typeof flashPart==="function")flashPart("snare",snare);globalThis.DruMasterMobileTapEffect?.showElement?.(snare);
  }
  function consumePadMicHit(){
    if((!mobileQuery.matches&&!debugMode)||runMode!=="pad"||typeof running==="undefined"||!running||paused||autoplay||document.body.classList.contains("acoustic-calibrating"))return false;
    showPadSnareFeedback();const match=nearestPlayable(current());if(!match||match.delta>GOOD_WINDOW)return false;
    const {note,delta}=match;note.hit=true;const label=gradeHit(note,delta);emitGrade(note,label);return true;
  }
  game.addEventListener("pointerdown",e=>{if(runMode!=="touch"||(!mobileQuery.matches&&!debugMode)||!running||paused)return;if(e.target.closest("#pause,#pausePanel button,.mic-debug-controls"))return;const ok=consumeNearest();if(ok){e.preventDefault();e.stopImmediatePropagation()}},true);

  function nodeLevel(analyser,data){if(!analyser||!data)return {rms:0,peak:0};analyser.getFloatTimeDomainData(data);let sum=0,peak=0;for(const x of data){const a=Math.abs(x);sum+=x*x;if(a>peak)peak=a}return {rms:Math.sqrt(sum/data.length),peak}}
  const readRawLevel=()=>nodeLevel(rawAnalyser,rawTimeData);
  function meterPercent(peak){const db=20*Math.log10(Math.max(1e-6,peak));return clamp((db+60)/60*100,0,100)}

  async function ensureMic(){
    if(micStream&&aecNode)return;
    if(!navigator.mediaDevices?.getUserMedia)throw Error("このブラウザではマイク入力を利用できません");
    if(typeof ac==="undefined"||!ac)throw Error("オーディオ機能の準備ができていません");
    micStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false,channelCount:1},video:false});
    if(!workletLoaded){if(!ac.audioWorklet)throw Error("このブラウザでは精密な音響相殺を利用できません");await ac.audioWorklet.addModule("js/acoustic-cancel-processor.js?v=20260827-rapid2");workletLoaded=true}
    micSource=ac.createMediaStreamSource(micStream);
    micFilter=ac.createBiquadFilter();micFilter.type="highpass";micFilter.frequency.value=180;micFilter.Q.value=.55;
    rawAnalyser=ac.createAnalyser();rawAnalyser.fftSize=1024;rawAnalyser.smoothingTimeConstant=0;rawTimeData=new Float32Array(rawAnalyser.fftSize);
    aecNode=new AudioWorkletNode(ac,"drumaster-acoustic-canceller",{numberOfInputs:2,numberOfOutputs:1,outputChannelCount:[1]});
    residualAnalyser=ac.createAnalyser();residualAnalyser.fftSize=1024;residualAnalyser.smoothingTimeConstant=0;residualTimeData=new Float32Array(residualAnalyser.fftSize);
    residualSilent=ac.createGain();residualSilent.gain.value=0;residualDestination=ac.createMediaStreamDestination();
    micSource.connect(micFilter);micFilter.connect(rawAnalyser);micFilter.connect(aecNode,0,0);
    if(typeof safetyLimiter==="undefined"||!safetyLimiter)throw Error("伴奏参照信号を取得できません");
    safetyLimiter.connect(aecNode,0,1);
    aecNode.connect(residualAnalyser);residualAnalyser.connect(residualSilent).connect(ac.destination);aecNode.connect(residualDestination);
    aecNode.port.onmessage=e=>{
      const m=e.data||{};
      if(m.type==="metrics"){aecMetrics={...aecMetrics,...m};globalThis.dispatchEvent(new CustomEvent("drumaster-aec-metrics",{detail:aecMetrics}))}
      else if(m.type==="capture"&&aecCaptureResolve){const r=aecCaptureResolve;aecCaptureResolve=null;r(m)}
      else if(m.type==="padCandidate")handlePadCandidate(m);
    };
    globalThis.DruMasterMicInputSettings=micStream.getAudioTracks?.()[0]?.getSettings?.()||{};
  }
  function releaseMic(){
    calibrationToken++;setCandidateMode("off");try{if(aecNode&&safetyLimiter)safetyLimiter.disconnect(aecNode)}catch{}try{micSource?.disconnect()}catch{}try{micFilter?.disconnect()}catch{}try{aecNode?.disconnect()}catch{}try{residualAnalyser?.disconnect()}catch{}try{residualSilent?.disconnect()}catch{}for(const track of micStream?.getTracks?.()||[])track.stop();
    micStream=null;micSource=null;micFilter=null;rawAnalyser=null;rawTimeData=null;aecNode=null;residualAnalyser=null;residualTimeData=null;residualSilent=null;residualDestination=null;
  }
  function setCandidateMode(mode){try{aecNode?.port.postMessage({type:"candidateMode",mode,noiseRms:micCalibration?.noise?.rms||.0005})}catch{}}

  /* ---------- PCM analysis / pad timbre fingerprint ---------- */
  function fftPower(frame){
    const n=512,re=new Float64Array(n),im=new Float64Array(n);for(let i=0;i<n;i++){const w=.5-.5*Math.cos(2*Math.PI*i/(n-1));re[i]=(frame[i]||0)*w}
    for(let i=1,j=0;i<n;i++){let bit=n>>1;for(;j&bit;bit>>=1)j^=bit;j^=bit;if(i<j){const tr=re[i];re[i]=re[j];re[j]=tr}}
    for(let len=2;len<=n;len<<=1){const ang=-2*Math.PI/len,wr0=Math.cos(ang),wi0=Math.sin(ang);for(let i=0;i<n;i+=len){let wr=1,wi=0;for(let j=0;j<len/2;j++){const a=i+j,b=a+len/2,tr=wr*re[b]-wi*im[b],ti=wr*im[b]+wi*re[b];re[b]=re[a]-tr;im[b]=im[a]-ti;re[a]+=tr;im[a]+=ti;const nr=wr*wr0-wi*wi0;wi=wr*wi0+wi*wr0;wr=nr}}}
    const out=new Float64Array(n/2);for(let i=0;i<out.length;i++)out[i]=re[i]*re[i]+im[i]*im[i];return out;
  }
  function bandPowerFromSpectrum(pow,sr){const hz=sr/512;return BAND_EDGES.slice(0,-1).map((lo,b)=>{const hi=BAND_EDGES[b+1],a=Math.max(1,Math.floor(lo/hz)),z=Math.min(pow.length-1,Math.ceil(hi/hz));let s=0,n=0;for(let i=a;i<=z;i++){s+=pow[i];n++}return n?s/n:0})}
  function aggregateBandPower(pcm,sr,start=0){
    const frames=[],hop=256,end=Math.min(pcm.length,start+Math.round(sr*.090));for(let at=start;at+512<=end;at+=hop)frames.push(bandPowerFromSpectrum(fftPower(pcm.subarray(at,at+512)),sr));
    if(!frames.length){const f=new Float32Array(512);f.set(pcm.subarray(start,Math.min(pcm.length,start+512)));frames.push(bandPowerFromSpectrum(fftPower(f),sr))}
    return BAND_EDGES.slice(0,-1).map((_,i)=>frames.reduce((s,f)=>s+f[i],0)/frames.length);
  }
  function rmsRange(pcm,a,b){a=Math.max(0,a|0);b=Math.min(pcm.length,b|0);let s=0,n=0;for(let i=a;i<b;i++){s+=pcm[i]*pcm[i];n++}return Math.sqrt(s/Math.max(1,n))}
  function noiseProfileFromPCM(pcm,sr){
    let sum=0,peak=0;for(const x of pcm){sum+=x*x;peak=Math.max(peak,Math.abs(x))}
    const bandFrames=[],hop=Math.round(sr*.08);for(let at=0;at+512<pcm.length;at+=hop)bandFrames.push(bandPowerFromSpectrum(fftPower(pcm.subarray(at,at+512)),sr));
    const bands=BAND_EDGES.slice(0,-1).map((_,i)=>Math.max(1e-12,percentile(bandFrames.map(f=>f[i]),.72)));
    return {rms:Math.max(.00002,Math.sqrt(sum/Math.max(1,pcm.length))),peak:Math.max(.0001,peak),bands};
  }
  function dct(v,count=6){const n=v.length,out=[];for(let k=0;k<count;k++){let s=0;for(let i=0;i<n;i++)s+=v[i]*Math.cos(Math.PI*k*(i+.5)/n);out.push(s/Math.sqrt(n))}return out}
  function cosine(a,b){let xy=0,xx=0,yy=0;for(let i=0;i<Math.min(a.length,b.length);i++){xy+=a[i]*b[i];xx+=a[i]*a[i];yy+=b[i]*b[i]}return xy/Math.sqrt(Math.max(1e-12,xx*yy))}
  function fingerprintFromPCM(pcm,sr,noise){
    let peak=0,peakAt=0;for(let i=0;i<pcm.length;i++){const a=Math.abs(pcm[i]);if(a>peak){peak=a;peakAt=i}}
    const onsetLevel=peak*.18;let onset=0;for(let i=0;i<=peakAt;i++){if(Math.abs(pcm[i])>=onsetLevel){onset=i;break}}
    const bands=aggregateBandPower(pcm,sr,Math.max(0,onset-Math.round(sr*.004))),clean=bands.map((p,i)=>Math.max(1e-13,p-(noise?.bands?.[i]||0)*1.10));
    const logs=clean.map(p=>Math.log10(p+1e-13)),mean=logs.reduce((s,x)=>s+x,0)/logs.length,shape=logs.map(x=>x-mean),mfcc=dct(logs,6);
    const centers=BAND_EDGES.slice(0,-1).map((lo,i)=>Math.sqrt(lo*BAND_EDGES[i+1])),total=clean.reduce((s,x)=>s+x,0),centroid=clean.reduce((s,x,i)=>s+x*centers[i],0)/Math.max(1e-13,total);
    let acc=0,rolloff=centers.at(-1);for(let i=0;i<clean.length;i++){acc+=clean[i];if(acc>=total*.85){rolloff=centers[i];break}}
    const early=rmsRange(pcm,onset,onset+Math.round(sr*.022)),late=rmsRange(pcm,onset+Math.round(sr*.045),onset+Math.round(sr*.088)),rms=rmsRange(pcm,onset,Math.min(pcm.length,onset+Math.round(sr*.09)));
    let zc=0,last=pcm[onset]||0,end=Math.min(pcm.length,onset+Math.round(sr*.08));for(let i=onset+1;i<end;i++){const x=pcm[i];if((x>=0)!=(last>=0))zc++;last=x}
    return {shape,mfcc,centroid,rolloff,attackMs:Math.max(0,(peakAt-onset)/sr*1000),decay:late/Math.max(1e-8,early),crest:peak/Math.max(1e-8,rms),zcr:zc/Math.max(1,end-onset),peak,rms};
  }
  function fingerprintSimilarity(a,b){
    const spec=.5+.5*clamp(cosine(a.shape,b.shape),-1,1),cep=.5+.5*clamp(cosine(a.mfcc.slice(1),b.mfcc.slice(1)),-1,1);
    const scalar=[Math.exp(-Math.abs(a.centroid-b.centroid)/1900),Math.exp(-Math.abs(a.rolloff-b.rolloff)/2600),Math.exp(-Math.abs(a.attackMs-b.attackMs)/22),Math.exp(-Math.abs(a.decay-b.decay)/.42),Math.exp(-Math.abs(a.crest-b.crest)/3.2),Math.exp(-Math.abs(a.zcr-b.zcr)/.09)].reduce((s,x)=>s+x,0)/6;
    return clamp(spec*.52+cep*.24+scalar*.24,0,1);
  }
  function modelScore(fp){if(!padModel?.samples?.length)return 0;const scores=padModel.samples.map(s=>fingerprintSimilarity(fp,s)).sort((a,b)=>b-a),n=Math.min(3,scores.length);return scores.slice(0,n).reduce((s,x)=>s+x,0)/n}
  function recomputeModelThreshold(){
    if(!padModel||padModel.samples.length<2){padModel.threshold=.62;return}
    const own=padModel.samples.map((s,i)=>Math.max(...padModel.samples.map((x,j)=>i===j?-Infinity:fingerprintSimilarity(s,x))));
    padModel.threshold=clamp(percentile(own,.18)-.065,.53,.80);padClassifier.threshold=padModel.threshold;padClassifier.samples=padModel.samples.length;
  }
  function addModelSample(fp,limit=24){if(!padModel)padModel={samples:[],threshold:.62};padModel.samples.push(fp);if(padModel.samples.length>limit)padModel.samples.splice(1,padModel.samples.length-limit);recomputeModelThreshold()}

  /* ---------- calibration UI ---------- */
  function ensureCalibrationScreen(){
    if(calibrationScreen)return calibrationScreen;const section=document.createElement("section");section.id="micCalibration";section.className="screen mic-calibration mic-fingerprint-cal hidden";
    section.innerHTML=`<div class="mic-calibration-card"><p class="mic-cal-eyebrow">PAD PRACTICE</p><h2>パッド音を登録</h2><p id="micCalInstruction" class="mic-cal-instruction">準備しています…</p><div class="mic-fingerprint-grid"><div class="mic-fingerprint-pane" data-fp-step="noise"><span>1</span><b>環境ノイズ</b><em id="fpNoiseState">待機</em><small id="fpNoiseProgress">自動収録 0.0 / ${NOISE_CAPTURE_MAX_SEC.toFixed(1)}秒</small></div><div class="mic-fingerprint-pane" data-fp-step="sample"><span>2</span><b>パッド音登録</b><em id="fpSampleState">0 / ${PAD_SAMPLE_TARGET}</em><small>強弱を混ぜて普通に叩いてください。打音の音色を短い波形として登録します</small></div><div class="mic-fingerprint-pane mic-fingerprint-test" data-fp-step="test"><span>3</span><b>叩いてみてください</b><em id="fpTestState">未テスト</em><small id="fpTestScore">登録後、「テストする」で認識を確認できます</small><i class="fp-hit-ring"></i></div></div><div class="mic-cal-meter"><i id="micCalMeterFill"></i></div><p id="micCalDetail" class="mic-cal-detail">環境音と打音が混ざることを前提に、環境ノイズ成分を差し引いて音色を比較します。</p><div class="mic-cal-actions"><button id="micCalAction" type="button">収録準備中…</button><button id="micCalTest" type="button" class="hidden">テストする</button><button id="micCalStart" type="button" class="hidden">演奏開始</button><button id="micCalRetry" type="button">最初からやり直す</button></div></div>`;
    app.appendChild(section);calibrationScreen=section;return section;
  }
  const ui=sel=>calibrationScreen?.querySelector(sel);
  function setInstruction(t){const n=ui("#micCalInstruction");if(n)n.textContent=t}function setDetail(t){const n=ui("#micCalDetail");if(n)n.textContent=t}
  function updateMeter(p){const n=ui("#micCalMeterFill");if(n)n.style.width=`${meterPercent(p)}%`}
  function setPane(stage,state){calibrationScreen?.querySelectorAll("[data-fp-step]").forEach(x=>x.dataset.state=x.dataset.fpStep===stage?state:"idle")}
  function setCandidateModeForStage(){setCandidateMode(calStage==="sample"||calStage==="test"?"raw":"off")}
  function beginAECapture(seconds){return new Promise((resolve,reject)=>{if(aecCaptureResolve){reject(Error("音声キャプチャが既に動作しています"));return}aecCaptureResolve=resolve;aecNode.port.postMessage({type:"beginCapture",seconds})})}
  function requestCaptureEnd(){try{aecNode?.port.postMessage({type:"endCapture"})}catch{}}
  function scheduleNoiseAutoStart(){
    setTimeout(()=>{
      if(!calibrationScreen||calibrationScreen.classList.contains("hidden")||calStage!=="noise")return;
      if(calBusy||aecCaptureResolve){scheduleNoiseAutoStart();return}
      void recordNoise();
    },90);
  }
  function resetCalibration(){
    calibrationToken++;
    if(noiseCaptureActive||aecCaptureResolve)requestCaptureEnd();
    calStage="noise";micCalibration=null;padModel={samples:[],threshold:.62};padClassifier={lastScore:0,threshold:.62,lastAccepted:false,samples:0,testHits:0,testCandidates:0};noiseCaptureActive=false;noiseCaptureReady=false;noiseFinishRequested=false;
    setCandidateMode("off");const s=ensureCalibrationScreen();s.querySelector("#fpNoiseState").textContent="待機";s.querySelector("#fpNoiseProgress").textContent=`自動収録 0.0 / ${NOISE_CAPTURE_MAX_SEC.toFixed(1)}秒`;s.querySelector("#fpSampleState").textContent=`0 / ${PAD_SAMPLE_TARGET}`;s.querySelector("#fpTestState").textContent="未テスト";s.querySelector("#fpTestScore").textContent="登録後、「テストする」で認識を確認できます";
    s.querySelector("#micCalTest").classList.add("hidden");s.querySelector("#micCalTest").disabled=false;s.querySelector("#micCalTest").textContent="テストする";s.querySelector("#micCalStart").classList.add("hidden");const action=s.querySelector("#micCalAction");action.classList.remove("hidden");action.disabled=true;action.textContent="収録準備中…";
    setPane("noise","active");setInstruction("環境ノイズを自動収録します。パッドはまだ叩かないでください");setDetail(`1秒後から「次に進む」を押せます。押さなくても最大${NOISE_CAPTURE_MAX_SEC}秒で自動的に終了します。`);updateMeter(0);scheduleNoiseAutoStart();
  }
  function finishNoiseEarly(){
    if(!noiseCaptureActive||!noiseCaptureReady||noiseFinishRequested)return;noiseFinishRequested=true;const b=ui("#micCalAction");if(b){b.disabled=true;b.textContent="解析中…"}requestCaptureEnd();
  }
  async function recordNoise(){
    if(calBusy||calStage!=="noise")return;calBusy=true;noiseCaptureActive=true;noiseCaptureReady=false;noiseFinishRequested=false;const token=calibrationToken,b=ui("#micCalAction"),state=ui("#fpNoiseState"),progress=ui("#fpNoiseProgress");if(b){b.disabled=true;b.textContent="収録中…"}if(state)state.textContent="収録中 0.0秒";setCandidateMode("off");setInstruction("環境ノイズを自動収録しています。パッドはまだ叩かないでください");
    try{
      let resolved=false;const capturePromise=beginAECapture(NOISE_CAPTURE_MAX_SEC).then(v=>{resolved=true;return v}),started=performance.now();
      while(token===calibrationToken&&!resolved){
        const elapsed=Math.min(NOISE_CAPTURE_MAX_SEC,(performance.now()-started)/1000),pct=Math.round(elapsed/NOISE_CAPTURE_MAX_SEC*100);updateMeter(readRawLevel().peak);if(state)state.textContent=`収録中 ${elapsed.toFixed(1)} / ${NOISE_CAPTURE_MAX_SEC.toFixed(1)}秒`;if(progress)progress.textContent=`進捗 ${pct}% · ${elapsed.toFixed(1)} / ${NOISE_CAPTURE_MAX_SEC.toFixed(1)}秒`;
        if(elapsed>=NOISE_CAPTURE_MIN_SEC&&!noiseCaptureReady&&!noiseFinishRequested){noiseCaptureReady=true;if(b){b.disabled=false;b.textContent="次に進む"}}
        await waitFrame();
      }
      const capture=await capturePromise;noiseCaptureActive=false;if(token!==calibrationToken)return;const pcm=new Float32Array(capture.mic);micCalibration={noise:noiseProfileFromPCM(pcm,capture.sampleRate||ac.sampleRate),aec:null};if(state)state.textContent="完了";if(progress)progress.textContent=`${(capture.samples/(capture.sampleRate||ac.sampleRate)).toFixed(1)}秒を解析済み`;
      calStage="sample";setPane("sample","active");if(b)b.classList.add("hidden");setInstruction(`そのままパッドを${PAD_SAMPLE_TARGET}回ほど叩いてください`);setDetail("パッド音登録は自動で開始しています。強弱を少し混ぜてください。環境ノイズを差し引いた音色特徴を登録します。");startSampling();
    }catch(e){if(token!==calibrationToken)return;console.error(e);setDetail(e?.message||"環境ノイズの収録に失敗しました");if(b){b.classList.remove("hidden");b.disabled=false;b.textContent="やり直す"}}
    finally{noiseCaptureActive=false;noiseCaptureReady=false;noiseFinishRequested=false;calBusy=false;if(calStage==="noise"&&token!==calibrationToken)scheduleNoiseAutoStart()}
  }
  function startSampling(){if(calStage!=="sample")return;ui("#micCalAction")?.classList.add("hidden");setCandidateMode("raw");setInstruction("パッドを続けて叩いてください");setDetail(`現在 0 / ${PAD_SAMPLE_TARGET}。音量閾値ではなく、打音の音色を登録しています。強弱を混ぜてください。`)}
  function enterReadyStage(){
    calStage="ready";setCandidateMode("off");ui("#micCalAction")?.classList.add("hidden");const test=ui("#micCalTest"),start=ui("#micCalStart");test?.classList.remove("hidden");start?.classList.remove("hidden");if(test){test.disabled=false;test.textContent="テストする"}ui("#fpTestState").textContent="未テスト";setInstruction("パッド音の登録が完了しました");setDetail("「テストする」で認識確認、そのまま「演奏開始」、または「最初からやり直す」を選べます。");
  }
  function enterTestStage(){
    if(!padModel?.samples?.length)return;calStage="test";setPane("test","active");setCandidateMode("raw");const test=ui("#micCalTest");if(test){test.classList.remove("hidden");test.disabled=true;test.textContent="テスト中"}ui("#micCalStart")?.classList.remove("hidden");ui("#fpTestState").textContent="待機中";setInstruction("右の「叩いてみてください」で認識を確認してください");setDetail("テスト中も解析を続けます。高信頼の打音は登録モデルへ取り込み、叩き方のばらつきへ適応します。");
  }
  function testPaneFeedback(score,accepted){
    const pane=ui('[data-fp-step="test"]'),state=ui("#fpTestState"),txt=ui("#fpTestScore");if(!pane||!state||!txt)return;state.textContent=accepted?"HIT":"解析中";txt.textContent=`PAD SIMILARITY ${(score*100).toFixed(0)}% · 基準 ${(padModel.threshold*100).toFixed(0)}%`;
    if(accepted){pane.classList.remove("hit");void pane.offsetWidth;pane.classList.add("hit")}
  }
  function finishCalibration(){const s=ensureCalibrationScreen();if(!micCalibration||!padModel?.samples?.length)return;calibrationToken++;setCandidateMode("off");s.classList.add("hidden");calResolve?.(true);calResolve=null}
  function showCalibration(){
    const s=ensureCalibrationScreen();setup.classList.add("hidden");s.classList.remove("hidden");resetCalibration();return new Promise(resolve=>{calResolve=resolve;ui("#micCalAction").onclick=()=>{if(calStage==="noise")finishNoiseEarly()};ui("#micCalTest").onclick=enterTestStage;ui("#micCalRetry").onclick=resetCalibration;ui("#micCalStart").onclick=finishCalibration})
  }

  function handlePadCandidate(m){
    if(!micCalibration?.noise||!m.pcm)return;
    if((calStage==="sample"||calStage==="test")&&m.mode!=="raw")return;
    if(calStage==="play"&&m.mode!=="residual")return;
    const fp=fingerprintFromPCM(new Float32Array(m.pcm),m.sampleRate||ac.sampleRate,micCalibration.noise);updateMeter(fp.peak);
    if(calStage==="sample"){
      const clear=fp.peak>micCalibration.noise.peak*1.08||fp.rms>micCalibration.noise.rms*1.15;if(!clear)return;
      addModelSample(fp,PAD_SAMPLE_TARGET);ui("#fpSampleState").textContent=`${padModel.samples.length} / ${PAD_SAMPLE_TARGET}`;setDetail(`登録 ${padModel.samples.length} / ${PAD_SAMPLE_TARGET}。環境音が混ざった状態から音色特徴を抽出しています。`);
      if(padModel.samples.length>=PAD_SAMPLE_TARGET){ui("#fpSampleState").textContent="登録完了";enterReadyStage()}return;
    }
    if(calStage==="test"){
      padClassifier.testCandidates++;let score=modelScore(fp),accepted=score>=padModel.threshold;const learningFloor=Math.max(.43,padModel.threshold-.18);
      if(accepted){padClassifier.testHits++;addModelSample(fp,24)}else if(score>=learningFloor&&fp.peak>micCalibration.noise.peak*1.12){addModelSample(fp,24);score=modelScore(fp);accepted=score>=padModel.threshold}
      if(!accepted&&score>=learningFloor*.92&&padClassifier.testCandidates%3===0)padModel.threshold=clamp(padModel.threshold-.008,.50,.80);
      padClassifier={...padClassifier,lastScore:score,threshold:padModel.threshold,lastAccepted:accepted,samples:padModel.samples.length,testHits:padClassifier.testHits,testCandidates:padClassifier.testCandidates};testPaneFeedback(score,accepted);return;
    }
    if(runMode==="pad"&&calStage==="play"&&typeof running!=="undefined"&&running&&!paused&&!document.body.classList.contains("acoustic-calibrating")){
      const score=modelScore(fp),accepted=score>=padModel.threshold;padClassifier={...padClassifier,lastScore:score,threshold:padModel.threshold,lastAccepted:accepted,samples:padModel.samples.length};
      if(accepted){try{aecNode.port.postMessage({type:"freeze",ms:190})}catch{}consumePadMicHit()}
    }
  }

  /* ---------- acoustic echo calibration ---------- */
  function songConfig(){return globalThis.DruMasterSongs?.current||{}}function trackGain(name,fallback){const v=songConfig().mix?.[name];return Number.isFinite(v)?v:fallback}
  async function loadCalibrationStems(){if(typeof loadStem!=="function")return;await loadStem("base","オフボーカル");if(document.querySelector("#vocalToggle")?.checked)await loadStem("vocals","ボーカル");if(document.querySelector("#guideToggle")?.checked)await loadStem("drums","ガイドドラム")}
  function startCalibrationBed(seconds=3,startOffset=18){
    if(typeof ac==="undefined"||!ac||typeof buffers==="undefined"||!buffers.base)throw Error("伴奏の準備ができていません");const rateNow=Number(document.querySelector("#tempo")?.value||100)/100,voices=[],when=ac.currentTime+.06,specs=[["base",.95],["vocals",.95],["drums",.70]];
    for(const [name,fallback] of specs){const buf=buffers[name];if(!buf)continue;const s=ac.createBufferSource(),g=ac.createGain(),offset=Math.min(startOffset,Math.max(0,buf.duration-seconds*rateNow-.1));s.buffer=buf;s.playbackRate.value=rateNow;g.gain.value=trackGain(name,fallback);s.connect(g).connect(masterBus);s.start(when,offset,Math.min(buf.duration-offset,seconds*rateNow+.2));voices.push({s,g})}
    return ()=>{for(const v of voices){try{v.s.stop()}catch{}try{v.s.disconnect()}catch{}try{v.g.disconnect()}catch{}}};
  }
  function estimateDelay(micBuf,refBuf,sr){
    const mic=new Float32Array(micBuf),ref=new Float32Array(refBuf),n=Math.min(mic.length,ref.length),minLag=Math.round(sr*.004),maxLag=Math.min(Math.round(sr*.24),Math.floor(n*.35));
    const scoreAt=(lag,step)=>{let xy=0,xx=0,yy=0,count=0;const start=lag,end=Math.min(n,start+Math.round(sr*1.9));for(let i=start;i<end;i+=step){const x=ref[i-lag],y=mic[i];xy+=x*y;xx+=x*x;yy+=y*y;count++}return count>64?Math.abs(xy)/Math.sqrt(Math.max(1e-18,xx*yy)):0};
    let bestLag=Math.round(sr*.06),best=-1;for(let lag=minLag;lag<=maxLag;lag+=16){const s=scoreAt(lag,16);if(s>best){best=s;bestLag=lag}}const lo=Math.max(minLag,bestLag-48),hi=Math.min(maxLag,bestLag+48);for(let lag=lo;lag<=hi;lag++){const s=scoreAt(lag,4);if(s>best){best=s;bestLag=lag}}return {samples:bestLag,ms:bestLag/sr*1000,score:best};
  }
  function ensureAcousticOverlay(){let el=document.querySelector("#acousticCalibrationOverlay");if(el)return el;el=document.createElement("div");el.id="acousticCalibrationOverlay";el.innerHTML='<div><p>PAD PRACTICE</p><strong>音響調整中</strong><span id="acousticCalibrationText">まだパッドを叩かないでください</span><small id="acousticCalibrationMetric"></small></div>';game.appendChild(el);return el}
  function setAcousticText(text,metric=""){const o=ensureAcousticOverlay();o.querySelector("#acousticCalibrationText").textContent=text;o.querySelector("#acousticCalibrationMetric").textContent=metric}
  const finite=(v,f=0)=>Number.isFinite(v)?v:f,dbfs=v=>(20*Math.log10(Math.max(1e-7,finite(v,0)))).toFixed(1);
  async function runAcousticPreflight(){
    if(!micCalibration||!aecNode)return;document.body.classList.add("acoustic-calibrating");setup.classList.add("hidden");game.classList.remove("hidden");const overlay=ensureAcousticOverlay();overlay.classList.add("show");setCandidateMode("off");
    try{
      await loadCalibrationStems();try{await ac.resume()}catch{}aecNode.port.postMessage({type:"setNoise",noiseRms:micCalibration.noise.rms,padProtect:Math.max(micCalibration.noise.peak*3.2,.008)});aecNode.port.postMessage({type:"adapt",enabled:false});aecNode.port.postMessage({type:"resetFilter"});
      setAcousticText("伴奏の回り込みタイミングを測定しています。まだ叩かないでください");const capturePromise=beginAECapture(AEC_CAPTURE_SEC),stopBed=startCalibrationBed(AEC_CAPTURE_SEC+.25,18),capture=await capturePromise;stopBed();await waitMs(90);
      const delay=estimateDelay(capture.mic,capture.ref,capture.sampleRate||ac.sampleRate);aecNode.port.postMessage({type:"setDelay",samples:delay.samples});aecNode.port.postMessage({type:"resetFilter"});setAcousticText("端末スピーカー→マイクの相殺フィルタを学習しています",`遅延 ${delay.ms.toFixed(1)} ms · 相関 ${(delay.score*100).toFixed(0)}%`);
      aecNode.port.postMessage({type:"adapt",enabled:true});const stopAdapt=startCalibrationBed((AEC_ADAPT_MS+250)/1000,26);await waitMs(AEC_ADAPT_MS);stopAdapt();await waitMs(100);setAcousticText("相殺結果を内部テストしています",`残差 ${dbfs(aecMetrics.residualRms)} dBFS · ERLE ${finite(aecMetrics.erleDb,0).toFixed(1)} dB`);
      const stopTest=startCalibrationBed((AEC_TEST_MS+180)/1000,34);await waitMs(AEC_TEST_MS);stopTest();await waitMs(100);micCalibration.aec={delaySamples:delay.samples,delayMs:delay.ms,correlation:delay.score,erleDb:aecMetrics.erleDb,residualRms:aecMetrics.residualRms};setAcousticText("調整完了。演奏を開始します",`遅延 ${delay.ms.toFixed(1)} ms · 残差 ${dbfs(aecMetrics.residualRms)} dBFS`);await waitMs(420);
    }finally{overlay.classList.remove("show");document.body.classList.remove("acoustic-calibrating");game.classList.add("hidden")}
  }

  const baseStart=startButton.onclick;
  startButton.onclick=async function(e){
    runMode=selectedMode();document.body.dataset.performanceRun=runMode;
    if(runMode==="pad"){
      const before=loadState?.textContent||"";startButton.disabled=true;if(loadState)loadState.textContent="マイクの使用を許可してください…";
      try{await ensureMic();try{await ac.resume()}catch{}if(loadState)loadState.textContent=before;await showCalibration();await runAcousticPreflight()}catch(err){console.error(err);if(loadState)loadState.textContent=err?.name==="NotAllowedError"?"パッド練習にはマイクの許可が必要です":(err?.message||"マイクを開始できません");game.classList.add("hidden");calibrationScreen?.classList.add("hidden");setup.classList.remove("hidden");startButton.disabled=false;return}startButton.disabled=false;
    }
    const out=baseStart?await baseStart.call(this,e):undefined;if(runMode==="pad"&&typeof running!=="undefined"&&running){calStage="play";setCandidateMode("residual")}else if(runMode==="pad"&&typeof running!=="undefined"&&!running)setup.classList.remove("hidden");return out;
  };

  globalThis.DruMasterPerformanceMode={
    getSelectedMode:selectedMode,getRunMode:()=>runMode,isPerformanceRun:()=>isPerformanceMode(runMode),isPadRun:()=>runMode==="pad",consumeNearest,consumePadMicHit,
    stopMic:releaseMic,getMicCalibration:()=>micCalibration,getAECMetrics:()=>({...aecMetrics}),getResidualStream:()=>residualDestination?.stream||null,getRawMicStream:()=>micStream,
    getPadClassifier:()=>({...padClassifier,modelSamples:padModel?.samples?.length||0}),micTimingOffsetSec:()=>globalThis.DruMasterMicJudgeLatency?.getJudgeOffsetSec?.()||0
  };
  addEventListener("pagehide",releaseMic,{once:true});
})();
