// Research-only synchronized-corpus hi-hat context rescoring (v54).
// Teacher MIDI was used offline to fit the coefficients below. Runtime reads audio + predicted events only.
import {monoAt44100} from './hat-forest.js';

const SR=44100,NFFT=2048,BINS=NFFT/2+1;
const WINDOW=Float64Array.from({length:NFFT},(_,i)=>.5-.5*Math.cos(2*Math.PI*i/(NFFT-1)));
const FREQ=Float64Array.from({length:BINS},(_,i)=>i*SR/NFFT);
const TWIDDLES=[];
for(let length=2;length<=NFFT;length*=2){
  const cos=new Float64Array(length/2),sin=new Float64Array(length/2);
  for(let k=0;k<length/2;k++){cos[k]=Math.cos(-2*Math.PI*k/length);sin[k]=Math.sin(-2*Math.PI*k/length);}
  TWIDDLES.push([length,cos,sin]);
}
const COEF=[0.07356140606926889,0.56275391647578,1.0555217105074752,0.4325306347772733,0.05522301362814368,5.4998124844077205,1.3034295310211543,-0.9914057191607057,-2.614797892444778,0.9062749700086186,1.9918108418279574,0.3549704658110302,4.4428901698563905,-0.13369191095197944];
const MEAN=[-1.0181458989095757,-1.2989734811143694,-0.3414375588274532,-0.05567500991111325,-0.36157612254559746,-1.6210324194338361,-1.7131009353149818,-1.0381766945409523,0.39125112765661846,0.19948350213310623,-2.117135685142146,0.32246235084168223,0.2951116165028767,0.3346042125015005];
const SCALE=[0.4115391211046046,1.181484639910803,1.5147492238359146,1.4064053364184974,0.7971614177547414,0.7513568321432882,1.912531832964702,1.6288552783719146,0.111626715888161,0.14861251376763393,1.750918261203404,2.065976052046428,0.120196914436168,0.1412148041946109];
const INTERCEPT=-7.320934108815975;

function workspace(){return {frame:new Float64Array(NFFT),real:new Float64Array(NFFT),imag:new Float64Array(NFFT),mag:new Float64Array(BINS)};}
function fftMagnitude(input,real,imag,out){
  for(let i=0;i<NFFT;i++){real[i]=input[i];imag[i]=0;}
  for(let i=0,j=0;i<NFFT;i++){
    if(j>i){let z=real[i];real[i]=real[j];real[j]=z;z=imag[i];imag[i]=imag[j];imag[j]=z;}
    let bit=NFFT>>1;while(j&bit){j^=bit;bit>>=1;}j^=bit;
  }
  for(const [length,cos,sin] of TWIDDLES){
    for(let start=0;start<NFFT;start+=length){
      for(let k=0;k<length/2;k++){
        const a=start+k,b=a+length/2,r=cos[k],s=sin[k];
        const vr=real[b]*r-imag[b]*s,vi=real[b]*s+imag[b]*r;
        real[b]=real[a]-vr;imag[b]=imag[a]-vi;real[a]+=vr;imag[a]+=vi;
      }
    }
  }
  for(let i=0;i<BINS;i++)out[i]=Math.hypot(real[i],imag[i])+1e-9;
}
function frameMagnitude(samples,t,w){
  const center=Math.round(t*SR),lo=center-(NFFT>>1);
  for(let i=0;i<NFFT;i++)w.frame[i]=(samples[lo+i]||0)*WINDOW[i];
  fftMagnitude(w.frame,w.real,w.imag,w.mag);return w.mag;
}
function hfCentroid(samples,t,w){
  const m=frameMagnitude(samples,t,w);let hf=1e-9,sum=1e-9,cf=0;
  for(let i=0;i<BINS;i++){const v=m[i];sum+=v;cf+=FREQ[i]*v;if(FREQ[i]>=5000&&FREQ[i]<=18000)hf+=v;}
  return {hf,centroid:cf/sum/22050};
}
function rms(samples,t,a,b){
  const lo=Math.max(0,Math.trunc((t+a)*SR)),hi=Math.min(samples.length,Math.trunc((t+b)*SR));
  if(hi<=lo)return 1e-8;let ss=0;
  for(let i=lo;i<hi;i++){const x=samples[i];ss+=x*x;}
  return Math.sqrt(ss/(hi-lo)+1e-12);
}
function features(samples,t,nextT,w){
  const attack=rms(samples,t,0,.035),out=[];
  for(const [a,b] of [[.04,.09],[.09,.16],[.16,.25],[.25,.4],[.4,.6]]){
    out.push(Math.log((rms(samples,t,a,b)+1e-9)/(attack+1e-9)));
  }
  const onset=hfCentroid(samples,t+.015,w);
  for(const off of [.08,.18,.35])out.push(Math.log((hfCentroid(samples,t+off,w).hf+1e-9)/onset.hf));
  out.push(onset.centroid);
  if(Number.isFinite(nextT)){
    const pre=hfCentroid(samples,nextT-.05,w),post=hfCentroid(samples,nextT+.145,w);
    out.push(Math.min(1.5,Math.max(0,nextT-t)));
    out.push(Math.log((pre.hf+1e-9)/onset.hf));
    out.push(Math.log((post.hf+1e-9)/(pre.hf+1e-9)));
    out.push(pre.centroid,post.centroid);
  }else out.push(1.5,0,0,0,0);
  return out;
}
function probability(x){
  let z=INTERCEPT;
  for(let i=0;i<COEF.length;i++)z+=COEF[i]*(x[i]-MEAN[i])/(SCALE[i]||1);
  return 1/(1+Math.exp(-Math.max(-30,Math.min(30,z))));
}
export async function rescueRideOpenV57(decoded,events,options={}){
  const threshold=Number.isFinite(Number(options.threshold))?Number(options.threshold):.99;
  const minRideCandidates=Number.isFinite(Number(options.minRideCandidates))?Number(options.minRideCandidates):24;
  const rides=events.filter(e=>e.group==='ride');
  const info={enabled:false,threshold,minRideCandidates,rideCandidates:rides.length,scored:0,changed:0};
  if(rides.length<minRideCandidates)return {events,info:{...info,reason:'insufficient-ride-domain'}};
  const samples=await monoAt44100(decoded),w=workspace();
  const all=events.slice().sort((a,b)=>a.time-b.time);
  const art=all.filter(e=>['hat','open_hat','pedal_hat','ride'].includes(e.group));
  const nextMap=new Map();
  for(let i=0;i<art.length;i++)nextMap.set(art[i],art[i+1]?.time);
  let changed=0,scored=0;
  const out=all.map(e=>{
    if(e.group!=='ride')return e;
    const p=probability(features(samples,e.time,nextMap.get(e),w));
    scored++;
    if(p<threshold)return {...e,hatContextProbability:p};
    changed++;
    return {...e,group:'open_hat',note:46,hatContextProbability:p,hatContextRideRescue:true};
  });
  return {events:out,info:{...info,enabled:true,scored,changed}};
}


function highGapThreshold(values,floor=.70,ceiling=.995){
  const xs=values.filter(Number.isFinite).filter(x=>x>=floor&&x<=ceiling).sort((a,b)=>a-b);
  if(xs.length<6)return null;
  let bestGap=-1,best=null;
  for(let i=0;i<xs.length-1;i++){
    const gap=xs[i+1]-xs[i];
    if(gap>bestGap){bestGap=gap;best=(xs[i]+xs[i+1])/2;}
  }
  return bestGap>=.015?best:null;
}

// Generic synchronized-corpus articulation rescoring.
// No review-song labels, filename, grid parity, or user review ranges are used.
// It only uses the frozen context/choke acoustic model fitted offline from
// synchronized WAV/MIDI pairs and operates on already-generated metal events.
export async function rescoreHatContextGeneralV59(decoded,events,variant='off'){
  const allowed=new Set(['off','score-only','closed-open-995','closed-open-990','closed-open-highgap','bidirectional-extreme']);
  if(!allowed.has(variant)||variant==='off')return {events,info:{enabled:false,variant:'off'}};
  const samples=await monoAt44100(decoded),w=workspace();
  const all=events.slice().sort((a,b)=>a.time-b.time);
  const art=all.filter(e=>['hat','open_hat','pedal_hat','ride'].includes(e.group));
  const nextMap=new Map();
  for(let i=0;i<art.length;i++)nextMap.set(art[i],art[i+1]?.time);
  const eligible=art.filter(e=>e.group==='hat'||e.group==='open_hat');
  const probMap=new Map();
  for(const e of eligible)probMap.set(e,probability(features(samples,e.time,nextMap.get(e),w)));
  const probs=[...probMap.values()];
  const highGap=highGapThreshold(probs);
  const openThreshold=variant==='score-only'?Infinity:
    variant==='closed-open-990'?.99:
    variant==='closed-open-highgap'?(highGap??.995):.995;
  const closeThreshold=.005;
  let promoted=0,demoted=0,scored=0;
  const out=all.map(e=>{
    const p=probMap.get(e);
    if(!Number.isFinite(p))return e;
    scored++;
    if(e.group==='hat'&&p>=openThreshold){
      promoted++;
      return {...e,group:'open_hat',note:46,hatContextProbability:p,hatContextGeneralV59:true};
    }
    if(variant==='bidirectional-extreme'&&e.group==='open_hat'&&p<=closeThreshold){
      demoted++;
      return {...e,group:'hat',note:42,hatContextProbability:p,hatContextGeneralV59:true};
    }
    return {...e,hatContextProbability:p};
  });
  return {events:out,info:{
    enabled:true,variant,scored,promoted,demoted,
    openThreshold,closeThreshold,
    highGapThreshold:highGap,
    probabilityMin:probs.length?Math.min(...probs):null,
    probabilityMax:probs.length?Math.max(...probs):null
  }};
}


let fusionModelPromiseV61=null;
async function loadHatFusionModelV61(){
  if(!fusionModelPromiseV61){
    fusionModelPromiseV61=fetch(new URL('./models/hat-articulation-fusion-v61.json',import.meta.url))
      .then(r=>{if(!r.ok)throw Error('ハイハット音響融合モデルを読み込めません');return r.json();});
  }
  return fusionModelPromiseV61;
}
function rank01(values){
  const n=values.length,out=new Float64Array(n);
  if(n<=1)return out;
  const order=values.map((v,i)=>({v:Number(v)||0,i})).sort((a,b)=>a.v-b.v||a.i-b.i);
  for(let r=0;r<n;r++)out[order[r].i]=r/(n-1);
  return out;
}
function robustZ01(values){
  if(!values.length)return new Float64Array(0);
  const xs=values.map(Number).sort((a,b)=>a-b);
  const q=(p)=>{
    const x=(xs.length-1)*p,lo=Math.floor(x),hi=Math.ceil(x),f=x-lo;
    return xs[lo]*(1-f)+xs[hi]*f;
  };
  const med=q(.5),dev=values.map(v=>Math.abs(Number(v)-med)).sort((a,b)=>a-b);
  const dm=(dev.length-1)*.5,dlo=Math.floor(dm),dhi=Math.ceil(dm),df=dm-dlo;
  const mad=dev[dlo]*(1-df)+dev[dhi]*df;
  const scale=Math.max(1e-6,1.4826*mad);
  return Float64Array.from(values,v=>Math.max(-8,Math.min(8,(Number(v)-med)/scale)));
}
function fusionLogitV61(p){
  const q=Math.max(1e-6,Math.min(1-1e-6,Number(p)||0));
  return Math.log(q/(1-q));
}
function fusionTreeProbability(tree,x){
  let node=0;
  while(tree.left[node]!==-1){
    const f=tree.feature[node];
    node=x[f]<=tree.threshold[node]?tree.left[node]:tree.right[node];
  }
  return Number(tree.prob1[node])||0;
}
function fusionForestProbability(model,row){
  const x=model.features.map(k=>Number(row[k])||0);
  let sum=0;
  for(const tree of model.trees)sum+=fusionTreeProbability(tree,x);
  return sum/Math.max(1,model.trees.length);
}

// Production Open/Closed classifier selected by five-song leave-one-song-out
// validation. This is per-hit acoustic classification, not pattern inference:
// single-hit timbre + tail persistence + next-hit choke context are fused.
// It never reads review ranges, song identity or alternating-grid parity.
export async function rescoreHatArticulationFusionV61(decoded,events,options={}){
  const enabled=options.enabled!==false;
  if(!enabled)return {events,info:{enabled:false,variant:'off'}};
  const candidates=events.filter(e=>
    (e.group==='hat'||e.group==='open_hat')&&Number.isFinite(Number(e.openHatProbability))
  );
  if(candidates.length<2)return {events,info:{enabled:false,reason:'insufficient-hat-candidates',candidates:candidates.length}};
  const [model,samples]=await Promise.all([loadHatFusionModelV61(),monoAt44100(decoded)]);
  const w=workspace();
  const art=events.filter(e=>['hat','open_hat','pedal_hat','ride'].includes(e.group))
    .slice().sort((a,b)=>a.time-b.time);
  const nextMap=new Map();
  for(let i=0;i<art.length;i++)nextMap.set(art[i],art[i+1]?.time);
  const base=candidates.map(e=>Number(e.openHatProbability));
  const context=candidates.map(e=>probability(features(samples,e.time,nextMap.get(e),w)));
  const baseRank=rank01(base),contextRank=rank01(context);
  const baseZ=robustZ01(base),contextZ=robustZ01(context);
  const candidateIndex=new Map(candidates.map((e,i)=>[e,i]));
  let promoted=0,demoted=0,changed=0,scored=0;
  const openThreshold=Number(model.confidenceThreshold)||.55;
  const closedThreshold=Number(model.closedThreshold)||.45;
  const out=events.map(e=>{
    const i=candidateIndex.get(e);
    if(i==null)return e;
    const nt=nextMap.get(e);
    const row={
      base_p:base[i],
      ctx_p:context[i],
      base_rank:baseRank[i],
      ctx_rank:contextRank[i],
      base_z:baseZ[i],
      ctx_z:contextZ[i],
      logit_diff:fusionLogitV61(context[i])-fusionLogitV61(base[i]),
      next_gap:Number.isFinite(nt)?Math.max(0,Math.min(1.5,nt-e.time)):1.5,
      score:Number(e.score)||0,
      confidence:Number(e.confidence)||0,
      current_open:e.group==='open_hat'?1:0
    };
    const p=fusionForestProbability(model,row);
    scored++;
    const meta={
      hatFusionProbability:p,
      hatFusionBaseProbability:base[i],
      hatFusionContextProbability:context[i],
      hatFusionV61:true
    };
    if(p>=openThreshold&&e.group!=='open_hat'){
      promoted++;changed++;
      return {...e,...meta,group:'open_hat',note:46};
    }
    if(p<=closedThreshold&&e.group==='open_hat'){
      demoted++;changed++;
      return {...e,...meta,group:'hat',note:42};
    }
    return {...e,...meta};
  });
  return {events:out,info:{
    enabled:true,variant:'acoustic-fusion-v61',
    candidates:candidates.length,scored,changed,promoted,demoted,
    openThreshold,closedThreshold,
    modelTrees:Number(model.treeCount)||model.trees.length,
    reviewSpecificInputsUsed:false,
    patternParityUsed:false
  }};
}


// Research/runtime shared raw per-hit acoustic descriptor.
// Vector order follows features(): five decay-RMS ratios, three HF tail ratios,
// onset centroid, next gap, pre-next persistence, post-next choke ratio,
// pre-next centroid, post-next centroid.
// No chart, review range, beat parity or song identity is read here.
export async function extractHatAcousticFeaturesV63(decoded,events){
  const candidates=events.filter(e=>
    (e.group==='hat'||e.group==='open_hat')&&Number.isFinite(Number(e.openHatProbability))
  );
  if(!candidates.length)return [];
  const samples=await monoAt44100(decoded),w=workspace();
  const art=events.filter(e=>['hat','open_hat','pedal_hat','ride'].includes(e.group))
    .slice().sort((a,b)=>a.time-b.time);
  const nextMap=new Map();
  for(let i=0;i<art.length;i++)nextMap.set(art[i],art[i+1]?.time);
  return candidates.map(e=>({
    time:e.time,
    group:e.group,
    note:e.note,
    score:Number(e.score)||0,
    confidence:Number(e.confidence)||0,
    openHatProbability:Number(e.openHatProbability),
    openHatBaseProbability:Number(e.openHatBaseProbability),
    vector:features(samples,e.time,nextMap.get(e),w)
  }));
}


let rawAcousticModelPromiseV64=null;
async function loadHatRawAcousticModelV64(){
  if(!rawAcousticModelPromiseV64){
    rawAcousticModelPromiseV64=fetch(new URL('./models/hat-raw-acoustic-v64.json',import.meta.url))
      .then(r=>{if(!r.ok)throw Error('ハイハット生音響モデルを読み込めません');return r.json();});
  }
  return rawAcousticModelPromiseV64;
}
function rankColumnsV64(matrix){
  if(!matrix.length)return [];
  const n=matrix.length,d=matrix[0].length,out=Array.from({length:n},()=>new Float64Array(d));
  for(let j=0;j<d;j++){
    const order=matrix.map((row,i)=>({v:Number(row[j])||0,i})).sort((a,b)=>a.v-b.v||a.i-b.i);
    if(n===1){out[order[0].i][j]=0;continue;}
    for(let r=0;r<n;r++)out[order[r].i][j]=r/(n-1);
  }
  return out;
}
function robustZColumnsV64(matrix){
  if(!matrix.length)return [];
  const n=matrix.length,d=matrix[0].length,out=Array.from({length:n},()=>new Float64Array(d));
  for(let j=0;j<d;j++){
    const vals=matrix.map(r=>Number(r[j])||0).sort((a,b)=>a-b);
    const med=vals.length&1?vals[vals.length>>1]:(vals[(vals.length>>1)-1]+vals[vals.length>>1])/2;
    const dev=vals.map(v=>Math.abs(v-med)).sort((a,b)=>a-b);
    const mad=dev.length&1?dev[dev.length>>1]:(dev[(dev.length>>1)-1]+dev[dev.length>>1])/2;
    const scale=Math.max(1e-6,1.4826*mad);
    for(let i=0;i<n;i++)out[i][j]=Math.max(-8,Math.min(8,((Number(matrix[i][j])||0)-med)/scale));
  }
  return out;
}

// v64: raw per-hit acoustic Open/Closed classifier.
// Uses only attack/decay/tail/choke acoustics, within-song normalization,
// existing single-hit acoustic probability and detector confidence.
// No alternating parity, review interval, song filename or section label.
export async function rescoreHatRawAcousticV64(decoded,events,options={}){
  if(options.enabled===false)return {events,info:{enabled:false,variant:'off'}};
  const candidates=events.filter(e=>
    (e.group==='hat'||e.group==='open_hat')&&Number.isFinite(Number(e.openHatProbability))
  );
  if(candidates.length<2)return {events,info:{enabled:false,reason:'insufficient-hat-candidates',candidates:candidates.length}};
  const [model,samples]=await Promise.all([loadHatRawAcousticModelV64(),monoAt44100(decoded)]);
  const w=workspace();
  const art=events.filter(e=>['hat','open_hat','pedal_hat','ride'].includes(e.group))
    .slice().sort((a,b)=>a.time-b.time);
  const nextMap=new Map();
  for(let i=0;i<art.length;i++)nextMap.set(art[i],art[i+1]?.time);
  const raw=candidates.map(e=>features(samples,e.time,nextMap.get(e),w));
  const rawRank=rankColumnsV64(raw),rawZ=robustZColumnsV64(raw);
  const base=candidates.map(e=>Number(e.openHatProbability));
  const baseRank=rank01(base),baseZ=robustZ01(base);
  const idx=new Map(candidates.map((e,i)=>[e,i]));
  const openThreshold=Number(model.confidenceThreshold)||.55;
  const closedThreshold=Number(model.closedThreshold)||.45;
  let scored=0,changed=0,promoted=0,demoted=0;
  const out=events.map(e=>{
    const i=idx.get(e);if(i==null)return e;
    const row={};
    for(let j=0;j<raw[i].length;j++){
      row['raw'+j]=raw[i][j];
      row['rank'+j]=rawRank[i][j];
      row['z'+j]=rawZ[i][j];
    }
    row.base_p=base[i];row.base_rank=baseRank[i];row.base_z=baseZ[i];
    row.score=Number(e.score)||0;row.confidence=Number(e.confidence)||0;
    row.current_open=e.group==='open_hat'?1:0;
    const p=fusionForestProbability(model,row);scored++;
    const meta={hatRawAcousticProbability:p,hatRawAcousticV64:true};
    if(p>=openThreshold&&e.group!=='open_hat'){
      changed++;promoted++;return {...e,...meta,group:'open_hat',note:46};
    }
    if(p<=closedThreshold&&e.group==='open_hat'){
      changed++;demoted++;return {...e,...meta,group:'hat',note:42};
    }
    return {...e,...meta};
  });
  return {events:out,info:{
    enabled:true,variant:'raw-acoustic-v64',candidates:candidates.length,scored,changed,promoted,demoted,
    openThreshold,closedThreshold,modelTrees:Number(model.treeCount)||model.trees.length,
    reviewSpecificInputsUsed:false,patternParityUsed:false
  }};
}


let hatSyncCandidateModelPromiseV66=null;
async function loadHatSyncCandidateModelV66(){
  if(!hatSyncCandidateModelPromiseV66){
    hatSyncCandidateModelPromiseV66=fetch(new URL('./models/hat-sync-candidate-rf-v66.json',import.meta.url))
      .then(r=>{if(!r.ok)throw Error('同期ハイハット候補モデルを読み込めません');return r.json();});
  }
  return hatSyncCandidateModelPromiseV66;
}

// v66 portable synchronized-candidate classifier.
// Trained from five fully synchronized WAV/MIDI pairs using the actual
// DrumScribe hat/open-hat candidate distribution. The MIDI teacher is offline
// only; runtime inputs are audio plus generated candidate metadata.
// Negative training examples include Closed/Pedal/Ride/Crash/unmatched cases.
// This stage only relabels existing GM42/46 candidates and cannot touch K/S/T.
export async function rescoreHatSyncCandidateV66(decoded,events,options={}){
  if(options.enabled===false)return {events,info:{enabled:false,variant:'off'}};
  const candidates=events.filter(e=>
    (e.group==='hat'||e.group==='open_hat')&&Number.isFinite(Number(e.openHatProbability))
  );
  if(candidates.length<2)return {events,info:{enabled:false,reason:'insufficient-hat-candidates',candidates:candidates.length}};
  const [model,samples]=await Promise.all([loadHatSyncCandidateModelV66(),monoAt44100(decoded)]);
  const w=workspace();
  const art=events.filter(e=>['hat','open_hat','pedal_hat','ride'].includes(e.group))
    .slice().sort((a,b)=>a.time-b.time);
  const nextMap=new Map();
  for(let i=0;i<art.length;i++)nextMap.set(art[i],art[i+1]?.time);
  const idx=new Map(candidates.map((e,i)=>[e,i]));
  const raw=candidates.map(e=>features(samples,e.time,nextMap.get(e),w));
  const openThreshold=Number(model.confidenceThreshold)||.55;
  const closedThreshold=Number(model.closedThreshold)||.45;
  let scored=0,changed=0,promoted=0,demoted=0;
  const out=events.map(e=>{
    const i=idx.get(e);if(i==null)return e;
    const row={};
    for(let j=0;j<raw[i].length;j++)row['raw'+j]=raw[i][j];
    row.base_p=Number(e.openHatProbability)||0;
    row.score=Number(e.score)||0;
    row.confidence=Number(e.confidence)||0;
    row.current_open=e.group==='open_hat'?1:0;
    const p=fusionForestProbability(model,row);scored++;
    const meta={hatSyncCandidateProbability:p,hatSyncCandidateV66:true};
    if(p>=openThreshold&&e.group!=='open_hat'){
      changed++;promoted++;return {...e,...meta,group:'open_hat',note:46};
    }
    if(p<=closedThreshold&&e.group==='open_hat'){
      changed++;demoted++;return {...e,...meta,group:'hat',note:42};
    }
    return {...e,...meta};
  });
  return {events:out,info:{
    enabled:true,variant:'sync-candidate-rf-v66',
    candidates:candidates.length,scored,changed,promoted,demoted,
    openThreshold,closedThreshold,modelTrees:Number(model.treeCount)||model.trees.length,
    reviewSpecificInputsUsed:false,patternParityUsed:false,
    trainingRows:Number(model.trainingRows)||null
  }};
}
