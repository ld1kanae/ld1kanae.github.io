// Open/closed hi-hat articulation classifier.
// The onset detector is intentionally untouched: this module only promotes
// already-retained closed-hat candidates (GM 42) to open hi-hat (GM 46).
// Training/evaluation: experiments/open_hat_*_loo.py.
// Default is closed; a candidate becomes open only above the fixed model threshold.

import {monoAt44100} from './hat-forest.js';

const SR=44100,NFFT=2048,BINS=NFFT/2+1;
const BANDS=[[1000,3000],[3000,6000],[6000,9000],[9000,13000],[13000,18000],[18000,22000]];
const DECAY_WINDOWS=[[0,.025],[.025,.060],[.060,.120],[.120,.220],[.220,.400],[.400,.650]];
const DECAY_CENTERS=DECAY_WINDOWS.map(([a,b])=>(a+b)/2);
const WINDOW=Float64Array.from({length:NFFT},(_,i)=>.5-.5*Math.cos(2*Math.PI*i/(NFFT-1)));
const FREQ=Float64Array.from({length:BINS},(_,i)=>i*SR/NFFT);
const TWIDDLES=[];
for(let length=2;length<=NFFT;length*=2){
  const cos=new Float64Array(length/2),sin=new Float64Array(length/2);
  for(let k=0;k<length/2;k++){
    cos[k]=Math.cos(-2*Math.PI*k/length);
    sin[k]=Math.sin(-2*Math.PI*k/length);
  }
  TWIDDLES.push([length,cos,sin]);
}
let modelPromise=null;
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));

async function loadModel(){
  if(!modelPromise){
    modelPromise=fetch(new URL('./models/open-hat-extra-trees-v1.json',import.meta.url))
      .then(r=>{if(!r.ok)throw Error('オープンハイハット分類モデルを読み込めません');return r.json();});
  }
  return modelPromise;
}

function workspace(){
  return {
    frame:new Float64Array(NFFT),
    real:new Float64Array(NFFT),
    imag:new Float64Array(NFFT),
    mag:new Float64Array(BINS)
  };
}
function fftMagnitude(input,real,imag,out){
  for(let i=0;i<NFFT;i++){real[i]=input[i];imag[i]=0;}
  for(let i=0,j=0;i<NFFT;i++){
    if(j>i){
      const tr=real[i];real[i]=real[j];real[j]=tr;
      const ti=imag[i];imag[i]=imag[j];imag[j]=ti;
    }
    let bit=NFFT>>1;
    while(j&bit){j^=bit;bit>>=1;}
    j^=bit;
  }
  for(const [length,cos,sin] of TWIDDLES){
    for(let start=0;start<NFFT;start+=length){
      for(let k=0;k<length/2;k++){
        const aa=start+k,bb=aa+length/2,r=cos[k],s=sin[k];
        const vr=real[bb]*r-imag[bb]*s,vi=real[bb]*s+imag[bb]*r;
        real[bb]=real[aa]-vr;imag[bb]=imag[aa]-vi;
        real[aa]+=vr;imag[aa]+=vi;
      }
    }
  }
  for(let i=0;i<BINS;i++)out[i]=Math.hypot(real[i],imag[i])+1e-9;
}
function frameMagnitude(samples,t,offset,w){
  const center=Math.round((t+offset)*SR),lo=center-(NFFT>>1);
  for(let i=0;i<NFFT;i++)w.frame[i]=(samples[lo+i]||0)*WINDOW[i];
  fftMagnitude(w.frame,w.real,w.imag,w.mag);
  return w.mag;
}
function rmsWindow(samples,t,a,b){
  const lo=Math.max(0,Math.trunc((t+a)*SR));
  const hi=Math.min(samples.length,Math.trunc((t+b)*SR));
  if(hi<=lo)return 1e-8;
  let ss=0;
  for(let i=lo;i<hi;i++){const x=samples[i];ss+=x*x;}
  return Math.sqrt(ss/(hi-lo)+1e-12);
}
function decayFeature(samples,t){
  const floor=rmsWindow(samples,t,-.100,-.025);
  const env=DECAY_WINDOWS.map(([a,b])=>{
    const r=rmsWindow(samples,t,a,b);
    return Math.sqrt(Math.max(r*r-floor*floor,1e-12));
  });
  const e0=Math.max(env[0],1e-8);
  const logrel=env.map(e=>Math.log(Math.max(e,1e-8)/e0));
  const mx=DECAY_CENTERS.reduce((a,b)=>a+b,0)/DECAY_CENTERS.length;
  const my=logrel.reduce((a,b)=>a+b,0)/logrel.length;
  let num=0,den=0;
  for(let i=0;i<DECAY_CENTERS.length;i++){
    const dx=DECAY_CENTERS[i]-mx;
    num+=dx*(logrel[i]-my);den+=dx*dx;
  }
  const slope=den?num/den:0;
  const weights=env.map(e=>Math.max(e-floor,0));
  const wsum=weights.reduce((a,b)=>a+b,0)+1e-12;
  let tcent=0;
  for(let i=0;i<weights.length;i++)tcent+=DECAY_CENTERS[i]*weights[i];
  tcent/=wsum;
  const tail=(env[3]+env[4]+env[5])/(3*e0+1e-12);
  const late=env[env.length-1]/(e0+1e-12);
  const pre=floor/e0;
  return logrel.concat([slope,tcent,tail,late,pre]);
}
function cosine(a,b){
  let dot=0,aa=0,bb=0;
  for(let i=0;i<a.length;i++){dot+=a[i]*b[i];aa+=a[i]*a[i];bb+=b[i]*b[i];}
  return dot/(Math.sqrt(aa)*Math.sqrt(bb)+1e-12);
}
function timbreFeature(samples,t,w,closedTemplate,openTemplate){
  const out=decayFeature(samples,t);
  const m=frameMagnitude(samples,t,.015,w);
  let total=0,centroidNumer=0,logSum=0,mean=0,norm=0,onsetHF=0;
  for(let i=0;i<BINS;i++){
    const v=m[i];
    total+=v;centroidNumer+=FREQ[i]*v;logSum+=Math.log(v);mean+=v;norm+=v*v;
    if(FREQ[i]>=5000)onsetHF+=v;
  }
  total+=1e-12;mean/=BINS;onsetHF+=1e-12;
  for(const [lo,hi] of BANDS){
    let sum=0;
    for(let i=0;i<BINS;i++)if(FREQ[i]>=lo&&FREQ[i]<hi)sum+=m[i];
    out.push(Math.log1p(100*sum/total));
  }
  const centroid=centroidNumer/total/22050;
  const flat=Math.exp(logSum/BINS)/(mean+1e-12);
  let cumulative=0,roll=FREQ[BINS-1]/22050;
  for(let i=0;i<BINS;i++){
    cumulative+=m[i];
    if(cumulative>=.85*total){roll=FREQ[i]/22050;break;}
  }
  const sim42=cosine(m,closedTemplate),sim46=cosine(m,openTemplate);
  out.push(centroid,flat,roll,sim42,sim46,sim46-sim42);
  for(const offset of [.080,.180,.350]){
    const late=frameMagnitude(samples,t,offset,w);
    let hf=0;
    for(let i=0;i<BINS;i++)if(FREQ[i]>=5000)hf+=late[i];
    out.push(Math.log1p(hf/onsetHF));
  }
  return out.map(Math.fround);
}
function quantile(values,q){
  const a=Array.from(values).sort((x,y)=>x-y);
  if(!a.length)return 0;
  const p=(a.length-1)*q,lo=Math.floor(p),hi=Math.ceil(p),f=p-lo;
  return a[lo]*(1-f)+a[hi]*f;
}
function robustNormalize(rows){
  if(!rows.length)return [];
  const d=rows[0].length,med=new Float64Array(d),scale=new Float64Array(d);
  for(let j=0;j<d;j++){
    const col=rows.map(r=>r[j]);
    med[j]=quantile(col,.5);
    scale[j]=Math.max(quantile(col,.75)-quantile(col,.25),1e-3);
  }
  return rows.map(row=>{
    const z=new Float32Array(d);
    for(let j=0;j<d;j++)z[j]=Math.fround(Math.max(-8,Math.min(8,(row[j]-med[j])/scale[j])));
    return z;
  });
}
function predict(model,x){
  let sum=0;
  for(const tree of model.trees){
    let node=0;
    while(tree.left[node]!==-1){
      node=x[tree.feature[node]]<=tree.threshold[node]?tree.left[node]:tree.right[node];
    }
    sum+=tree.prob1[node];
  }
  return sum/model.trees.length;
}

export async function promoteOpenHats(decoded,events,report=()=>{}){
  const hats=events.filter(e=>e.group==='hat').slice().sort((a,b)=>a.time-b.time);
  const baseInfo={mode:'open-hat-extra-trees-v1',candidates:hats.length,promoted:0,enabled:false};
  if(!hats.length)return {events,info:{...baseInfo,skipReason:'no-hat'}};
  try{
    const model=await loadModel();
    if(Number(model.featureCount)!==26)throw Error(`unexpected open-hat feature count ${model.featureCount}`);
    const closedTemplate=model.assetTemplates?.closed42,openTemplate=model.assetTemplates?.open46;
    if(!closedTemplate||!openTemplate||closedTemplate.length!==BINS||openTemplate.length!==BINS)throw Error('open-hat asset templates are invalid');
    const threshold=Number(model.probThreshold??.55);
    report('オープンハイハットの音色を判定中…',99.05);
    const samples=await monoAt44100(decoded),w=workspace(),raw=[];
    for(let i=0;i<hats.length;i++){
      raw.push(timbreFeature(samples,hats[i].time,w,closedTemplate,openTemplate));
      if(i%24===0){
        report('オープンハイハットの音色を判定中…',99.05+.45*i/Math.max(1,hats.length));
        await tick();
      }
    }
    const features=robustNormalize(raw),openSet=new Set();
    let probSum=0,maxProbability=0;
    for(let i=0;i<hats.length;i++){
      const p=predict(model,features[i]);probSum+=p;maxProbability=Math.max(maxProbability,p);
      if(p>=threshold)openSet.add(hats[i]);
      if(i%48===0)await tick();
    }
    const promoted=events.map(e=>openSet.has(e)?{...e,group:'open_hat'}:e);
    return {events:promoted,info:{
      ...baseInfo,enabled:true,promoted:openSet.size,threshold,
      closed:hats.length-openSet.size,modelTrees:model.trees.length,modelFeatures:model.featureCount,
      meanProbability:hats.length?probSum/hats.length:0,maxProbability
    }};
  }catch(err){
    console.warn('open-hat classifier fallback',err);
    return {events,info:{...baseInfo,error:String(err?.message||err),skipReason:'error'}};
  }
}
