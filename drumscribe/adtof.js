const RATE=44100,HOP=441,FFT=2048,FFT_BINS=1024,N_BINS=84,FPS=100;
const CORE_FRAMES=3000,OVERLAP_FRAMES=200;
const GROUPS=['kick','snare','tom','hat','cymbal'];
const BASE_THRESHOLDS=[.22,.24,.32,.22,.30];
const PRECISION_SCALE=1.15;

let assetsPromise=null;

const wait=()=>new Promise(resolve=>setTimeout(resolve,0));

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
    const [meta,fbBuf]=await Promise.all([
      fetch(new URL('./models/adtof-model.json',import.meta.url)).then(r=>{if(!r.ok)throw Error('ADTOF metadataを読み込めません');return r.json();}),
      fetch(new URL('./models/adtof-filterbank.f32',import.meta.url)).then(r=>{if(!r.ok)throw Error('ADTOF filterbankを読み込めません');return r.arrayBuffer();}),
    ]);
    const filterbank=new Float32Array(fbBuf);
    if(meta.nBins!==N_BINS||filterbank.length!==N_BINS*FFT_BINS)throw Error('ADTOF filterbankの形状が不正です');
    const session=await ort.InferenceSession.create(new URL('./models/adtof-frame-rnn.onnx',import.meta.url).href,{
      executionProviders:['wasm'],
      graphOptimizationLevel:'all'
    });
    return {ort,meta,filterbank,session};
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

function toEvents(acts,scale=PRECISION_SCALE){
  const out=[];
  for(let c=0;c<GROUPS.length;c++){
    const threshold=BASE_THRESHOLDS[c]*scale;
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
  const events=toEvents(acts,scale);
  return {
    events,
    frames,
    thresholdScale:scale,
    backend:'onnxruntime-web/wasm',
    coreFrames:CORE_FRAMES,
    overlapFrames:OVERLAP_FRAMES,
    modelSource:assets.meta.source
  };
}
