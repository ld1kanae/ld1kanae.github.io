const RATE=44100,HOP=441,FFT=2048,FFT_BINS=1024,N_BINS=84,FPS=100;
const CORE_FRAMES=3000,OVERLAP_FRAMES=200;
const GROUPS=['kick','snare','tom','hat','cymbal'];
const BASE_THRESHOLDS=[.22,.24,.32,.22,.30];
const PRECISION_SCALE=1.15;

let assetsPromise=null;

const wait=()=>new Promise(resolve=>setTimeout(resolve,0));
function thresholdMul(multipliers,key){
  const v=Number(multipliers?.[key]);
  return Number.isFinite(v)&&v>0?v:1;
}

async function mono44100(decoded){
  if(decoded.sampleRate===RATE){
    const n=decoded.length,out=new Float32Array(n);
    for(let ch=0;ch<decoded.numberOfChannels;ch++){
      const x=decoded.getChannelData(ch),w=1/decoded.numberOfChannels;
      for(let i=0;i<n;i++)out[i]+=x[i]*w;
    }
    return out;
  }
  try{
    const offline=new OfflineAudioContext(1,Math.ceil(decoded.duration*RATE),RATE);
    const src=offline.createBufferSource();src.buffer=decoded;src.connect(offline.destination);src.start();
    return new Float32Array((await offline.startRendering()).getChannelData(0));
  }catch{
    const channels=Array.from({length:decoded.numberOfChannels},(_,i)=>decoded.getChannelData(i));
    const n=Math.ceil(decoded.duration*RATE),out=new Float32Array(n);
    for(let i=0;i<n;i++){
      const p=i*decoded.sampleRate/RATE,j=Math.min(decoded.length-2,Math.max(0,Math.floor(p))),f=p-j;
      let v=0;
      for(const x of channels)v+=(x[j]*(1-f)+x[j+1]*f)/channels.length;
      out[i]=v;
    }
    return out;
  }
}

async function loadAssets(){
  if(assetsPromise)return assetsPromise;
  assetsPromise=(async()=>{
    const ort=globalThis.ort;
    if(!ort)throw Error('ONNX Runtime Web が読み込まれていません');
    ort.env.wasm.numThreads=1;
    ort.env.wasm.wasmPaths=new URL('./vendor/ort/',import.meta.url).href;
    const [meta,fbBuf,kstModel]=await Promise.all([
      fetch(new URL('./models/adtof-model.json',import.meta.url)).then(r=>{if(!r.ok)throw Error('ADTOF metadataを読み込めません');return r.json();}),
      fetch(new URL('./models/adtof-filterbank.f32',import.meta.url)).then(r=>{if(!r.ok)throw Error('ADTOF filterbankを読み込めません');return r.arrayBuffer();}),
      fetch(new URL('./models/egmd-kst-reclassifier-v4.json',import.meta.url))
        .then(r=>r.ok?r.json():null).catch(()=>null),
    ]);
    const filterbank=new Float32Array(fbBuf);
    if(meta.nBins!==N_BINS||filterbank.length!==N_BINS*FFT_BINS)throw Error('ADTOF filterbankの形状が不正です');
    const session=await ort.InferenceSession.create(new URL('./models/adtof-frame-rnn.onnx',import.meta.url).href,{
      executionProviders:['wasm'],
      graphOptimizationLevel:'all'
    });
    return {ort,meta,filterbank,session,kstModel};
  })();
  return assetsPromise;
}

async function frontend(samples,filterbank,report){
  const frames=Math.floor(samples.length/HOP)+1;
  const features=new Float32Array(frames*N_BINS);
  if(typeof Worker==='undefined')throw Error('Web Worker非対応のためADTOFを実行できません');
  const cores=Math.max(2,Number(globalThis.navigator?.hardwareConcurrency)||2);
  const count=Math.min(4,Math.max(2,cores-1),Math.max(1,Math.ceil(frames/2500)));
  let done=0;
  const jobs=[];
  for(let w=0;w<count;w++){
    const startFrame=Math.floor(frames*w/count),endFrame=Math.floor(frames*(w+1)/count);
    if(endFrame<=startFrame)continue;
    const globalStart=startFrame*HOP-(FFT>>1);
    const globalEnd=(endFrame-1)*HOP+(FFT>>1);
    const clipStart=Math.max(0,globalStart),clipEnd=Math.min(samples.length,globalEnd+1);
    const segment=samples.slice(clipStart,clipEnd);
    jobs.push(new Promise((resolve,reject)=>{
      const worker=new Worker(new URL('./adtof-worker.js',import.meta.url));
      const cleanup=()=>worker.terminate();
      worker.onerror=e=>{cleanup();reject(e.error||Error(e.message||'ADTOF frontend worker failed'));};
      worker.onmessage=e=>{
        const part=new Float32Array(e.data.features);
        features.set(part,startFrame*N_BINS);
        done++;
        report('ADTOF特徴量を計算中…',62+12*done/count);
        cleanup();resolve();
      };
      worker.postMessage({
        samples:segment.buffer,
        startFrame,endFrame,
        sampleStart:clipStart,
        filterbank:filterbank.buffer
      },[segment.buffer]);
    }));
  }
  await Promise.all(jobs);
  return {features,frames};
}

async function inferChunks(features,frames,assets,report){
  const acts=new Float32Array(frames*5);
  let chunks=0;
  for(let a=0;a<frames;a+=CORE_FRAMES)chunks++;
  let done=0;
  for(let a=0;a<frames;a+=CORE_FRAMES){
    const b=Math.min(frames,a+CORE_FRAMES);
    const sa=Math.max(0,a-OVERLAP_FRAMES),sb=Math.min(frames,b+OVERLAP_FRAMES);
    const input=new Float32Array(features.subarray(sa*N_BINS,sb*N_BINS));
    const tensor=new assets.ort.Tensor('float32',input,[1,sb-sa,N_BINS,1]);
    const output=await assets.session.run({input:tensor});
    const y=output.activations.data;
    const ka=(a-sa)*5,count=(b-a)*5;
    acts.set(y.subarray(ka,ka+count),a*5);
    done++;
    report('ADTOFモデルで推定中…',75+16*done/chunks);
    await wait();
  }
  return acts;
}

function movingResidual(x,left=10,right=1){
  const y=new Float32Array(x.length),size=left+1+right;
  for(let i=0;i<x.length;i++){
    let sum=0;
    for(let d=-left;d<=right;d++){
      const j=Math.max(0,Math.min(x.length-1,i+d));
      sum+=x[j];
    }
    y[i]=Math.max(0,x[i]-sum/size);
  }
  return y;
}

function pickClass(acts,classIndex,threshold){
  const x=new Float32Array(Math.floor(acts.length/5));
  for(let i=0;i<x.length;i++)x[i]=acts[i*5+classIndex];
  const p=movingResidual(x,10,1),peaks=[];
  for(let i=0;i<p.length;i++){
    let mx=-Infinity;
    for(let d=-2;d<=1;d++)mx=Math.max(mx,p[Math.max(0,Math.min(p.length-1,i+d))]);
    if(p[i]>=mx&&p[i]>=threshold)peaks.push(i);
  }
  if(!peaks.length)return [];
  const groups=[];let cur=[peaks[0]];
  for(let i=1;i<peaks.length;i++){
    if(peaks[i]-cur[cur.length-1]<=2)cur.push(peaks[i]);
    else{groups.push(cur);cur=[peaks[i]];}
  }
  groups.push(cur);
  return groups.map(g=>{
    let best=g[0];
    for(const i of g)if(p[i]>p[best])best=i;
    return {frame:best,time:best/FPS,activation:x[best],residual:p[best]};
  });
}

function percentileSorted(sorted,q){
  if(!sorted.length)return 0;
  const x=(sorted.length-1)*q,lo=Math.floor(x),hi=Math.ceil(x),f=x-lo;
  return sorted[lo]*(1-f)+sorted[hi]*f;
}

function upperBound(sorted,v){
  let lo=0,hi=sorted.length;
  while(lo<hi){
    const mid=(lo+hi)>>1;
    if(sorted[mid]<=v)lo=mid+1;else hi=mid;
  }
  return lo;
}

function sigmoid(x){
  if(x>=0)return 1/(1+Math.exp(-x));
  const z=Math.exp(x);return z/(1+z);
}

function buildKstStats(acts){
  const frames=Math.floor(acts.length/5);
  const cols=Array.from({length:5},()=>new Float32Array(frames));
  for(let i=0;i<frames;i++)for(let c=0;c<5;c++)cols[c][i]=acts[i*5+c];
  const residuals=cols.map(x=>movingResidual(x,10,1));
  const sortedActs=cols.map(x=>Array.from(x).sort((a,b)=>a-b));
  const sortedResiduals=residuals.map(x=>Array.from(x).sort((a,b)=>a-b));
  const aq=sortedActs.map(x=>Math.max(percentileSorted(x,.95),1e-4));
  const rq=sortedResiduals.map(x=>Math.max(percentileSorted(x,.95),1e-5));
  return {frames,cols,residuals,sortedActs,sortedResiduals,aq,rq};
}

function kstFeature(st,frame,target){
  const lo=Math.max(0,frame-2),hi=Math.min(st.frames,frame+3);
  const cur=new Array(5),res=new Array(5),mean=new Array(5).fill(0),mx=new Array(5).fill(-Infinity);
  for(let c=0;c<5;c++){
    cur[c]=st.cols[c][frame]/st.aq[c];
    res[c]=st.residuals[c][frame]/st.rq[c];
    for(let i=lo;i<hi;i++){
      const z=st.cols[c][i]/st.aq[c];
      mean[c]+=z; if(z>mx[c])mx[c]=z;
    }
    mean[c]/=Math.max(1,hi-lo);
  }
  const atn=d=>st.cols[target][Math.max(0,Math.min(st.frames-1,frame+d))]/st.aq[target];
  let other=1e-5,rother=1e-5;
  for(let c=0;c<5;c++)if(c!==target){other=Math.max(other,cur[c]);rother=Math.max(rother,res[c]);}
  const rawAct=st.cols[target][frame],rawRes=st.residuals[target][frame];
  return [
    ...cur,...res,...mean,...mx,
    atn(-2),atn(-1),atn(1),atn(2),
    upperBound(st.sortedActs[target],rawAct)/Math.max(1,st.frames),
    upperBound(st.sortedResiduals[target],rawRes)/Math.max(1,st.frames),
    cur[target]/other,res[target]/rother
  ];
}

function logisticPredict(model,x){
  if(!model||!Array.isArray(model.coef)||model.coef.length!==x.length)return 0;
  let z=Number(model.intercept)||0;
  for(let i=0;i<x.length;i++){
    const scale=Math.max(Number(model.scale?.[i])||0,1e-12);
    z+=((x[i]-(Number(model.mean?.[i])||0))/scale)*(Number(model.coef[i])||0);
  }
  return sigmoid(z);
}

function egmdProbability(kstModel,st,group,classIndex,frame){
  const model=kstModel?.models?.[group];
  if(!model||!st)return {probability:null,modelThreshold:null,hypothesis:null};
  return {
    probability:logisticPredict(model,kstFeature(st,frame,classIndex)),
    modelThreshold:Number(model.threshold)||.6,
    hypothesis:model.hypothesis||null
  };
}

function egmdSnareCandidates(acts,kstModel,thresholdMultiplier=1){
  const model=kstModel?.models?.snare;
  if(!model)return [];
  const st=buildKstStats(acts);
  const lowScale=Number(kstModel.lowScale)||.2;
  const threshold=BASE_THRESHOLDS[1]*lowScale;
  return pickClass(acts,1,threshold).map(p=>({
    time:p.time,
    group:'snare',
    score:p.activation,
    residual:p.residual,
    probability:logisticPredict(model,kstFeature(st,p.frame,1)),
    modelThreshold:(Number(model.threshold)||.6)*thresholdMultiplier,
    kickActivation:st.cols[0][p.frame],
    snareActivation:st.cols[1][p.frame],
    tomActivation:st.cols[2][p.frame],
    egmdKst:true
  }));
}

function toEvents(acts,scale=PRECISION_SCALE,thresholdMultipliers={}){
  const out=[];
  for(let c=0;c<GROUPS.length;c++){
    const threshold=BASE_THRESHOLDS[c]*scale*thresholdMul(thresholdMultipliers,GROUPS[c]);
    for(const p of pickClass(acts,c,threshold)){
      out.push({
        time:p.time,
        group:GROUPS[c],
        score:p.activation,
        confidence:p.activation/threshold,
        adtof:true
      });
    }
  }
  out.sort((a,b)=>a.time-b.time||GROUPS.indexOf(a.group)-GROUPS.indexOf(b.group));
  return out;
}

export async function transcribeAdtof(decoded,report=()=>{},options={}){
  report('ADTOFを準備中…',58);
  const assets=await loadAssets();
  const samples=await mono44100(decoded);
  report('ADTOF特徴量を計算中…',60);
  const {features,frames}=await frontend(samples,assets.filterbank,report);
  const acts=await inferChunks(features,frames,assets,report);
  const scale=Number.isFinite(options.thresholdScale)?options.thresholdScale:PRECISION_SCALE;
  const thresholdMultipliers=options.thresholdMultipliers||{};
  const events=toEvents(acts,scale,thresholdMultipliers);
  // Keep a lower-threshold snare stream for conservative post-processing.
  // It is never emitted directly; transcribe.js may rescue only candidates
  // that are independently supported by a simultaneous kick and repetition.
  const snareRescueScale=Number.isFinite(options.snareRescueScale)?options.snareRescueScale:.50;
  const snareRescueThreshold=BASE_THRESHOLDS[1]*snareRescueScale*thresholdMul(thresholdMultipliers,'snareRescue');
  const snareRescue=pickClass(acts,1,snareRescueThreshold).map(p=>({
    time:p.time,
    group:'snare',
    score:p.activation,
    confidence:p.activation/(BASE_THRESHOLDS[1]*scale),
    rescueConfidence:p.activation/snareRescueThreshold,
    adtof:true,
    rescue:true
  }));
  const egmdSnareSupport=egmdSnareCandidates(acts,assets.kstModel,thresholdMul(thresholdMultipliers,'egmdSnare'));
  // Experiment-only broad K/S/T streams. These candidates are never emitted
  // into production transcription unless a caller explicitly requests them.
  // They let arrangement/repetition experiments rescore real acoustic
  // candidates instead of copying notes from another section.
  let diagnosticKstCandidates=null;
  if(options.diagnosticKst===true){
    const diagnosticScales={kick:.65,snare:.50,tom:.65};
    const diagnosticStats=assets.kstModel?buildKstStats(acts):null;
    diagnosticKstCandidates={};
    for(const [group,classIndex] of [['kick',0],['snare',1],['tom',2]]){
      const broadScale=diagnosticScales[group];
      const broadThreshold=BASE_THRESHOLDS[classIndex]*broadScale;
      const productionThreshold=BASE_THRESHOLDS[classIndex]*scale;
      diagnosticKstCandidates[group]=pickClass(acts,classIndex,broadThreshold).map(p=>{
        const egmd=egmdProbability(assets.kstModel,diagnosticStats,group,classIndex,p.frame);
        return {
          time:p.time,
          group,
          score:p.activation,
          residual:p.residual,
          confidence:p.activation/productionThreshold,
          broadConfidence:p.activation/broadThreshold,
          egmdProbability:egmd.probability,
          egmdModelThreshold:egmd.modelThreshold,
          egmdHypothesis:egmd.hypothesis,
          diagnostic:true
        };
      });
    }
  }
  return {
    events,
    snareRescue,
    egmdSnareSupport,
    diagnosticKstCandidates,
    frames,
    thresholdScale:scale,
    snareRescueScale,
    thresholdMultipliers,
    backend:'onnxruntime-web/wasm',
    coreFrames:CORE_FRAMES,
    overlapFrames:OVERLAP_FRAMES,
    modelSource:assets.meta.source,
    egmdKstModel:assets.kstModel?.kind||null
  };
}
