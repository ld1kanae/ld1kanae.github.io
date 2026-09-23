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
let modelPromise=null,overlayModelPromise=null;
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));

async function loadModel(){
  if(!modelPromise){
    modelPromise=fetch(new URL('./models/open-hat-extra-trees-v2.json',import.meta.url))
      .then(r=>{if(!r.ok)throw Error('オープンハイハット分類モデルを読み込めません');return r.json();});
  }
  return modelPromise;
}
async function loadOverlayModel(){
  if(!overlayModelPromise){
    overlayModelPromise=fetch(new URL('./models/open-hat-overlay-extra-trees-v1.json',import.meta.url))
      .then(r=>{if(!r.ok)throw Error('重なりオープンハイハット分類モデルを読み込めません');return r.json();});
  }
  return overlayModelPromise;
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
function robustStats(rows){
  if(!rows.length)return {med:new Float64Array(0),scale:new Float64Array(0)};
  const d=rows[0].length,med=new Float64Array(d),scale=new Float64Array(d);
  for(let j=0;j<d;j++){
    const col=rows.map(r=>r[j]);
    med[j]=quantile(col,.5);
    scale[j]=Math.max(quantile(col,.75)-quantile(col,.25),1e-3);
  }
  return {med,scale};
}
function normalizeWithStats(rows,stats){
  if(!rows.length)return [];
  return rows.map(row=>{
    const z=new Float32Array(row.length);
    for(let j=0;j<row.length;j++)z[j]=Math.fround(Math.max(-8,Math.min(8,(row[j]-stats.med[j])/stats.scale[j])));
    return z;
  });
}
function robustNormalize(rows){
  return normalizeWithStats(rows,robustStats(rows));
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
function nearTime(times,t,w){
  for(const u of times)if(Math.abs(u-t)<=w)return true;
  return false;
}
function structuralAnchors(events,hats){
  const items=[];
  for(const e of events){
    let kind=null;
    if(e.group==='ride'||e.group==='crash')kind='metal';
    else if(e.group==='snare')kind='snare';
    else if(e.group==='kick')kind='kick';
    if(kind)items.push({time:e.time,kind,event:e});
  }
  items.sort((a,b)=>a.time-b.time);
  const hatTimes=hats.map(e=>e.time),out=[];
  for(let i=0;i<items.length;){
    const t0=items[i].time,cluster=[];let j=i;
    while(j<items.length&&items[j].time-t0<=.035)cluster.push(items[j++]);
    const metal=cluster.filter(x=>x.kind==='metal');
    const snare=cluster.filter(x=>x.kind==='snare');
    const kick=cluster.filter(x=>x.kind==='kick');
    const priority=(metal[0]||snare[0]||kick[0]);
    const t=priority.time;
    if(!nearTime(hatTimes,t,.060)){
      let score=0,confidence=0;
      for(const x of cluster){
        score=Math.max(score,Number(x.event.score)||0);
        confidence=Math.max(confidence,Number(x.event.confidence)||0);
      }
      out.push({time:t,metal:metal.length?1:0,snare:snare.length?1:0,kick:kick.length?1:0,
        frame:priority.event.frame,score,confidence});
    }
    i=j;
  }
  return out;
}
function lowerBound(a,x){
  let lo=0,hi=a.length;
  while(lo<hi){const m=(lo+hi)>>1;if(a[m]<x)lo=m+1;else hi=m;}
  return lo;
}
function maxNear(times,probs,target,tol){
  let i=lowerBound(times,target-tol),best=0;
  while(i<times.length&&times[i]<=target+tol){best=Math.max(best,probs[i]);i++;}
  return best;
}
function repeatSupport(times,probs,bpm,policy){
  const beat=60/Math.max(Number(bpm)||0,1e-6),out=new Float64Array(times.length);
  const offsets=policy.neighborBeatOffsets||[.5,1,1.5,2,4],tol=Number(policy.neighborToleranceSec)||.065;
  for(let i=0;i<times.length;i++){
    const vals=[];
    for(const mul of offsets){
      const off=mul*beat;
      for(const sign of [-1,1]){
        const v=maxNear(times,probs,times[i]+sign*off,tol);
        if(v>0)vals.push(v);
      }
    }
    vals.sort((a,b)=>b-a);
    const n=Math.min(4,vals.length);
    if(n){let sum=0;for(let j=0;j<n;j++)sum+=vals[j];out[i]=sum/n;}
  }
  return out;
}

export async function promoteOpenHats(decoded,events,bpm,report=()=>{}){
  const hats=events.filter(e=>e.group==='hat').slice().sort((a,b)=>a.time-b.time);
  const baseInfo={mode:'open-hat-extra-trees-v2-gmd128+overlay-v1',candidates:hats.length,promoted:0,rescued:0,enabled:false};
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
        report('オープンハイハットの音色を判定中…',99.05+.30*i/Math.max(1,hats.length));
        await tick();
      }
    }
    const stats=robustStats(raw),features=normalizeWithStats(raw,stats),openSet=new Set();
    let probSum=0,maxProbability=0;
    for(let i=0;i<hats.length;i++){
      const p=predict(model,features[i]);probSum+=p;maxProbability=Math.max(maxProbability,p);
      if(p>=threshold)openSet.add(hats[i]);
      if(i%48===0)await tick();
    }

    let rescued=[],overlayInfo={enabled:false,rescued:0};
    try{
      const overlay=await loadOverlayModel();
      if(Number(overlay.featureCount)!==29)throw Error(`unexpected overlay feature count ${overlay.featureCount}`);
      const policy=overlay.policy||{},anchors=structuralAnchors(events,hats);
      report('重なりオープンハイハットを確認中…',99.40);
      const overlayRaw=[];
      for(let i=0;i<anchors.length;i++){
        overlayRaw.push(timbreFeature(samples,anchors[i].time,w,closedTemplate,openTemplate));
        if(i%24===0){
          report('重なりオープンハイハットを確認中…',99.40+.35*i/Math.max(1,anchors.length));
          await tick();
        }
      }
      const acoustic=normalizeWithStats(overlayRaw,stats),X=[];
      for(let i=0;i<anchors.length;i++){
        const x=new Float32Array(29);x.set(acoustic[i],0);
        x[26]=anchors[i].metal;x[27]=anchors[i].snare;x[28]=anchors[i].kick;X.push(x);
      }
      const probs=X.map(x=>predict(overlay,x)),times=anchors.map(a=>a.time);
      const rep=repeatSupport(times,probs,bpm,policy);
      const pw=Number(policy.scoreProbabilityWeight??.72),rw=Number(policy.scoreRepeatWeight??.28);
      const scores=probs.map((p,i)=>pw*p+rw*rep[i]);
      const maxProb=probs.length?Math.max(...probs):0,maxScore=scores.length?Math.max(...scores):0;
      const gate=maxProb>=Number(policy.gateMaxProbability??.78)&&maxScore>=Number(policy.gateMaxRepeatScore??.72);
      const scoreThreshold=Math.max(Number(policy.minimumScore??.68),scores.length?quantile(scores,Number(policy.scoreQuantile??.96)):99);
      const openTimes=hats.filter(h=>openSet.has(h)).map(h=>h.time);
      let physicalSkipped=0;
      if(gate){
        for(let i=0;i<anchors.length;i++){
          if(scores[i]<scoreThreshold||probs[i]<Number(policy.minimumProbability??.58)||rep[i]<Number(policy.minimumRepeatSupport??.35))continue;
          const a=anchors[i];
          if(nearTime(openTimes,a.time,Number(policy.existingHatExclusionSec??.060)))continue;
          let hands=0;
          for(const e of events){
            if(!['snare','tom','hat','crash','ride'].includes(e.group))continue;
            if(Math.abs(e.time-a.time)<=Number(policy.handClusterSec??.035))hands++;
          }
          if(hands>=2){physicalSkipped++;continue;}
          rescued.push({time:a.time,frame:a.frame,group:'open_hat',score:Math.max(.2,a.score),confidence:Math.max(.5,a.confidence),overlayRescue:true});
        }
      }
      overlayInfo={enabled:true,gate,candidates:anchors.length,rescued:rescued.length,physicalSkipped,
        maxProbability:maxProb,maxRepeatScore:maxScore,scoreThreshold,
        modelTrees:overlay.trees.length,modelFeatures:overlay.featureCount,policy:policy.name||'repeat_gate_2hands'};
    }catch(overlayErr){
      console.warn('open-hat overlay fallback',overlayErr);
      overlayInfo={enabled:false,rescued:0,error:String(overlayErr?.message||overlayErr)};
    }

    const promoted=events.map(e=>openSet.has(e)?{...e,group:'open_hat'}:e).concat(rescued);
    return {events:promoted,info:{
      ...baseInfo,enabled:true,promoted:openSet.size,rescued:rescued.length,threshold,
      closed:hats.length-openSet.size,modelTrees:model.trees.length,modelFeatures:model.featureCount,
      meanProbability:hats.length?probSum/hats.length:0,maxProbability,overlay:overlayInfo
    }};
  }catch(err){
    console.warn('open-hat classifier fallback',err);
    return {events,info:{...baseInfo,error:String(err?.message||err),skipReason:'error'}};
  }
}
