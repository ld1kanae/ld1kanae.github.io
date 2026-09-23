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
let modelPromise=null,overlayModelPromise=null,gmdPriorPromise=null;
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

async function loadGmdHatPrior(){
  if(!gmdPriorPromise){
    gmdPriorPromise=fetch(new URL('./models/gmd-hat-articulation-prior-v1.json',import.meta.url))
      .then(r=>{if(!r.ok)throw Error('GMDハイハット遷移priorを読み込めません');return r.json();});
  }
  return gmdPriorPromise;
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

function sigmoid(x){return 1/(1+Math.exp(-x));}
function logit(p){
  const q=Math.max(1e-5,Math.min(1-1e-5,Number(p)||0));
  return Math.log(q/(1-q));
}
function median(values){
  if(!values.length)return null;
  const a=values.slice().sort((x,y)=>x-y),m=a.length>>1;
  return a.length&1?a[m]:(a[m-1]+a[m])/2;
}
function clamp(x,lo,hi){return Math.max(lo,Math.min(hi,x));}
function hfAt(samples,t,w){
  const m=frameMagnitude(samples,t,0,w);let s=0;
  for(let i=0;i<BINS;i++)if(FREQ[i]>=5000&&FREQ[i]<=18000)s+=m[i];
  return s+1e-9;
}
function contaminated(events,t,exclude=null){
  for(const e of events){
    if(e===exclude)continue;
    if(!['snare','tom','crash','ride'].includes(e.group))continue;
    if(Math.abs(e.time-t)<=.070)return true;
  }
  return false;
}
function acousticSequenceRescore(samples,hats,events,baseProb,threshold,w){
  // Self-calibrated evidence for the user's two cases:
  //   open -> open: the high-frequency tail remains across the next articulation.
  //   open -> closed/pedal: the next articulation chokes the previous tail.
  // No reference MIDI is read here. Only borderline 42/46 decisions can move.
  const rows=hats.map((h,i)=>({event:h,index:i,p:baseProb[i],tail:null,cut:null}));
  const allArt=events.filter(e=>e.group==='hat'||e.group==='pedal_hat')
    .slice().sort((a,b)=>a.time-b.time);
  const hatIndex=new Map(hats.map((h,i)=>[h,i]));
  for(let ai=0;ai<allArt.length;ai++){
    const e=allArt[ai],i=hatIndex.get(e);
    if(i==null)continue;
    const onset=hfAt(samples,e.time+.015,w);
    const next=allArt[ai+1]||null;
    let probe=e.time+.250;
    if(next){
      const gap=next.time-e.time;
      if(gap>=.11&&gap<=.90)probe=next.time-.050;
      else if(gap<.11)probe=e.time+Math.max(.045,.45*gap);
    }
    if(probe>e.time+.035&&!contaminated(events,probe,e)){
      rows[i].tail=Math.log1p(hfAt(samples,probe,w)/onset);
    }
    const prev=allArt[ai-1]||null;
    if(prev){
      const pi=hatIndex.get(prev);
      const prevTrustedOpen=pi!=null&&baseProb[pi]>=Math.max(.73,threshold+.12);
      if(prevTrustedOpen&&e.time-prev.time>=.11&&e.time-prev.time<=.90){
        const preT=e.time-.050,postT=e.time+.180;
        if(!contaminated(events,preT,e)&&!contaminated(events,postT,e)){
          const pre=hfAt(samples,preT,w),post=hfAt(samples,postT,w);
          rows[i].cut=Math.log1p(post/pre);
        }
      }
    }
  }
  const hi=Math.max(.73,threshold+.12),lo=Math.min(.40,threshold-.15);
  const trustedOpen=rows.filter(r=>r.p>=hi),trustedClosed=rows.filter(r=>r.p<=lo);
  const tailO=trustedOpen.map(r=>r.tail).filter(Number.isFinite);
  const tailC=trustedClosed.map(r=>r.tail).filter(Number.isFinite);
  const cutO=trustedOpen.map(r=>r.cut).filter(Number.isFinite);
  const cutC=trustedClosed.map(r=>r.cut).filter(Number.isFinite);
  const tO=median(tailO),tC=median(tailC),cO=median(cutO),cC=median(cutC);
  const tailSep=Number.isFinite(tO)&&Number.isFinite(tC)?tO-tC:0;
  const cutSep=Number.isFinite(cO)&&Number.isFinite(cC)?cO-cC:0;
  const tailEnabled=tailO.length>=8&&tailC.length>=12&&Math.abs(tailSep)>=.08;
  const cutEnabled=cutO.length>=5&&cutC.length>=5&&Math.abs(cutSep)>=.08;
  const out=baseProb.slice();let changed=0,tailUsed=0,cutUsed=0;
  for(const r of rows){
    if(Math.abs(r.p-threshold)>.18)continue;
    let shift=0;
    if(tailEnabled&&Number.isFinite(r.tail)){
      const mid=(tO+tC)/2;
      shift+=.26*clamp((r.tail-mid)/(Math.abs(tailSep)+1e-6)*Math.sign(tailSep),-1.5,1.5);
      tailUsed++;
    }
    if(cutEnabled&&Number.isFinite(r.cut)){
      const mid=(cO+cC)/2;
      shift+=.20*clamp((r.cut-mid)/(Math.abs(cutSep)+1e-6)*Math.sign(cutSep),-1.5,1.5);
      cutUsed++;
    }
    if(Math.abs(shift)>1e-9){
      const p=sigmoid(logit(r.p)+clamp(shift,-.55,.55));
      if((p>=threshold)!==(r.p>=threshold))changed++;
      out[r.index]=p;
    }
  }
  return {probabilities:out,info:{
    enabled:tailEnabled||cutEnabled,changed,tailEnabled,cutEnabled,tailUsed,cutUsed,
    trustedOpen:trustedOpen.length,trustedClosed:trustedClosed.length,
    tailOpenMedian:tO,tailClosedMedian:tC,cutOpenMedian:cO,cutClosedMedian:cC
  }};
}
function slot16(time,bpm,barPhaseSec){
  const beat=60/Math.max(1e-6,bpm),bar=4*beat;
  let x=(time-barPhaseSec)%bar;if(x<0)x+=bar;
  return ((Math.round(x/(beat/4))%16)+16)%16;
}
function genreMixture(prior,hats,events,bpm,barPhaseSec){
  if(!Number.isFinite(barPhaseSec))return [];
  const art=events.filter(e=>e.group==='hat'||e.group==='pedal_hat');
  const obs=new Array(16).fill(0);
  for(const e of art)obs[slot16(e.time,bpm,barPhaseSec)]++;
  const os=Math.sqrt(obs.reduce((s,x)=>s+x*x,0))||1;
  const rows=[];
  for(const [key,g] of Object.entries(prior.groups||{})){
    if(!key.startsWith('genre:')||Number(g.files||0)<15)continue;
    const ref=(g.slot16||[]).map(x=>Number(x.articulationShare)||0);
    if(ref.length!==16)continue;
    const rs=Math.sqrt(ref.reduce((s,x)=>s+x*x,0))||1;
    let dot=0;for(let i=0;i<16;i++)dot+=obs[i]*ref[i];
    rows.push({key,similarity:dot/(os*rs),group:g});
  }
  rows.sort((a,b)=>b.similarity-a.similarity);
  const top=rows.slice(0,3).filter(x=>x.similarity>=.62);
  if(!top.length)return [];
  const raw=top.map(x=>Math.pow(Math.max(.01,x.similarity),6)),sum=raw.reduce((a,b)=>a+b,0)||1;
  return top.map((x,i)=>({...x,weight:raw[i]/sum}));
}
function gmdTransitionRescore(prior,hats,events,baseProb,bpm,barPhaseSec,threshold){
  const mix=genreMixture(prior,hats,events,bpm,barPhaseSec);
  if(!mix.length)return {probabilities:baseProb.slice(),info:{enabled:false,reason:'no-genre-mixture'}};
  const beat=60/Math.max(1e-6,bpm);
  const allArt=events.filter(e=>e.group==='hat'||e.group==='pedal_hat')
    .slice().sort((a,b)=>a.time-b.time);
  const hatIndex=new Map(hats.map((h,i)=>[h,i]));
  const out=baseProb.slice();let used=0,changed=0,consensusRejected=0;
  for(let ai=0;ai<allArt.length;ai++){
    const cur=allArt[ai],ci=hatIndex.get(cur);
    if(ci==null||Math.abs(baseProb[ci]-threshold)>.18)continue;
    const prev=allArt[ai-1];if(!prev)continue;
    let prevClass=null;
    if(prev.group==='pedal_hat')prevClass='pedal';
    else{
      const pi=hatIndex.get(prev);
      if(pi!=null&&baseProb[pi]>=Math.max(.73,threshold+.12))prevClass='open';
      else if(pi!=null&&baseProb[pi]<=Math.min(.40,threshold-.15))prevClass='closed';
    }
    if(!prevClass)continue;
    const delta=Math.max(0,Math.min(32,Math.round((cur.time-prev.time)/beat*4)));
    const deltas=[];
    for(const m of mix){
      const slot=m.group.slot16?.[slot16(cur.time,bpm,barPhaseSec)];
      const tr=m.group.transitions?.[`${prevClass}|d${delta}`];
      const ps=Number(slot?.openProbability),pt=Number(tr?.openProbability);
      const n=tr?.counts?Object.values(tr.counts).reduce((a,b)=>a+(Number(b)||0),0):0;
      if(!Number.isFinite(ps)||!Number.isFinite(pt)||n<12)continue;
      // Slot-only priors did not generalize in held-out GMD. Use only the
      // transition's odds lift relative to that same genre/slot baseline.
      deltas.push({weight:m.weight,delta:clamp(logit(pt)-logit(ps),-2.5,2.5)});
    }
    if(deltas.length<2)continue;
    const pos=deltas.filter(x=>x.delta>0).length,neg=deltas.filter(x=>x.delta<0).length;
    if(Math.max(pos,neg)<2){consensusRejected++;continue;}
    let sw=0,sd=0;
    for(const x of deltas){sw+=x.weight;sd+=x.weight*x.delta;}
    const d=sd/(sw||1);
    if(Math.abs(d)<.12)continue;
    const p=sigmoid(logit(baseProb[ci])+.20*clamp(d,-2.25,2.25));
    if((p>=threshold)!==(baseProb[ci]>=threshold))changed++;
    out[ci]=p;used++;
  }
  return {probabilities:out,info:{
    enabled:true,used,changed,consensusRejected,
    genres:mix.map(x=>({genre:x.key.slice(6),similarity:x.similarity,weight:x.weight})),
    transitionBlend:Number(prior.policy?.transitionBlend)||.6
  }};
}
function gmdOpenRunRescue(prior,hats,events,baseProb,bpm,threshold){
  // Runtime cannot reliably infer a semantic genre from drum slots alone.
  // Use the genre-trained dataset here only through its aggregate transition
  // statistics, and only in the recall direction: never demote an existing
  // Open. This specifically targets open->open runs represented in GMD.
  const G=prior.groups?.all;
  if(!G)return {probabilities:baseProb.slice(),info:{enabled:false,reason:'no-all-group'}};
  const beat=60/Math.max(1e-6,bpm);
  const allArt=events.filter(e=>e.group==='hat'||e.group==='pedal_hat')
    .slice().sort((a,b)=>a.time-b.time);
  const idx=new Map(hats.map((h,i)=>[h,i]));
  const out=baseProb.slice();let eligible=0,used=0,changed=0;
  for(let ai=1;ai<allArt.length;ai++){
    const cur=allArt[ai],ci=idx.get(cur);if(ci==null)continue;
    const p=out[ci];
    if(p>=threshold||p<threshold-.11)continue;
    const prev=allArt[ai-1],pi=idx.get(prev);
    if(pi==null||out[pi]<Math.max(.64,threshold+.05))continue;
    const d=Math.max(1,Math.min(32,Math.round((cur.time-prev.time)/beat*4)));
    const tr=G.transitions?.[`open|d${d}`];if(!tr)continue;
    const n=tr.counts?Object.values(tr.counts).reduce((a,b)=>a+(Number(b)||0),0):0;
    const pt=Number(tr.openProbability),pg=Number(G.globalOpenProbability);
    if(n<50||!Number.isFinite(pt)||!Number.isFinite(pg)||pt<.28)continue;
    eligible++;
    const lift=clamp(logit(pt)-logit(pg),0,2.2);
    const q=sigmoid(logit(p)+.12*lift);
    out[ci]=q;used++;
    if(q>=threshold)changed++;
  }
  return {probabilities:out,info:{enabled:true,eligible,used,changed,mode:'aggregate-positive-open-run'}};
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

export async function promoteOpenHats(decoded,events,bpm,report=()=>{},context={}){
  const hats=events.filter(e=>e.group==='hat').slice().sort((a,b)=>a.time-b.time);
  const requestedVariant=['base','decay','gmd','combined','gmd-rescue','decay-rescue','ride-open','ride-acoustic','ride-decay','ride-open-decay-rescue','arrangement','arrangement-decay'].includes(context?.variant)?context.variant:'base';
  const baseInfo={mode:'open-hat-extra-trees-v2-gmd128+overlay-v1',variant:requestedVariant,candidates:hats.length,promoted:0,rescued:0,enabled:false};
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
    let probabilities=features.map(x=>predict(model,x));
    const baseProbabilities=probabilities.slice();
    let sequenceInfo={variant:requestedVariant,decay:{enabled:false},gmd:{enabled:false},gmdRescue:{enabled:false},ride:{enabled:false}};
    if(['decay','combined','decay-rescue','ride-decay','ride-open-decay-rescue','arrangement-decay'].includes(requestedVariant)){
      const seq=acousticSequenceRescore(samples,hats,events,probabilities,threshold,w);
      probabilities=seq.probabilities;sequenceInfo.decay=seq.info;
    }
    if(requestedVariant==='gmd'||requestedVariant==='combined'){
      try{
        const prior=await loadGmdHatPrior();
        const seq=gmdTransitionRescore(prior,hats,events,probabilities,bpm,Number(context?.barPhaseSec),threshold);
        probabilities=seq.probabilities;sequenceInfo.gmd=seq.info;
      }catch(gmdErr){
        console.warn('GMD hi-hat prior fallback',gmdErr);
        sequenceInfo.gmd={enabled:false,error:String(gmdErr?.message||gmdErr)};
      }
    }
    if(requestedVariant==='gmd-rescue'||requestedVariant==='decay-rescue'||requestedVariant==='ride-open-decay-rescue'){
      try{
        const prior=await loadGmdHatPrior();
        const seq=gmdOpenRunRescue(prior,hats,events,probabilities,bpm,threshold);
        probabilities=seq.probabilities;sequenceInfo.gmdRescue=seq.info;
      }catch(gmdErr){
        sequenceInfo.gmdRescue={enabled:false,error:String(gmdErr?.message||gmdErr)};
      }
    }
    let probSum=0,maxProbability=0,basePromoted=0;
    for(let i=0;i<hats.length;i++){
      const p=probabilities[i];probSum+=p;maxProbability=Math.max(maxProbability,p);
      if(baseProbabilities[i]>=threshold)basePromoted++;
      if(p>=threshold)openSet.add(hats[i]);
      if(i%48===0)await tick();
    }
    sequenceInfo.basePromoted=basePromoted;
    sequenceInfo.reclassified=openSet.size-basePromoted;
    const hatProbability=new Map(hats.map((h,i)=>[h,{
      probability:probabilities[i],
      baseProbability:baseProbabilities[i]
    }]));

    const rideMap=new Map(),rideProbability=new Map();
    if(['ride-open','ride-acoustic','ride-decay','ride-open-decay-rescue'].includes(requestedVariant)){
      const rides=events.filter(e=>e.group==='ride').slice().sort((a,b)=>a.time-b.time);
      if(requestedVariant==='ride-open'||requestedVariant==='ride-open-decay-rescue'){
        for(const e of rides)rideMap.set(e,'open_hat');
        sequenceInfo.ride={enabled:true,mode:'all-to-open',candidates:rides.length,open:rides.length,closed:0};
      }else{
        const rr=[];
        for(let i=0;i<rides.length;i++){rr.push(timbreFeature(samples,rides[i].time,w,closedTemplate,openTemplate));if(i%24===0)await tick();}
        const rf=normalizeWithStats(rr,stats),rp=rf.map(x=>predict(model,x));
        let ro=0,rc=0;
        for(let i=0;i<rides.length;i++){
          const g=rp[i]>=threshold?'open_hat':'hat';rideMap.set(rides[i],g);
          rideProbability.set(rides[i],{probability:rp[i],baseProbability:rp[i]});
          if(g==='open_hat')ro++;else rc++;
        }
        sequenceInfo.ride={enabled:true,mode:'acoustic-42-46',candidates:rides.length,open:ro,closed:rc,
          meanProbability:rp.length?rp.reduce((a,b)=>a+b,0)/rp.length:0};
      }
    }

    let rescued=[],overlayInfo={enabled:false,rescued:0};
    try{
      const overlay=await loadOverlayModel();
      if(Number(overlay.featureCount)!==29)throw Error(`unexpected overlay feature count ${overlay.featureCount}`);
      const policy=overlay.policy||{},anchors=structuralAnchors(events,hats.concat([...rideMap.keys()]));
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

    const promoted=events.map(e=>{
      const hp=hatProbability.get(e);
      if(hp)return {...e,group:openSet.has(e)?'open_hat':'hat',
        openHatProbability:hp.probability,openHatBaseProbability:hp.baseProbability};
      const rg=rideMap.get(e);
      if(rg){
        const rp=rideProbability.get(e);
        return {...e,group:rg,rideRoundedToHat:true,
          ...(rp?{openHatProbability:rp.probability,openHatBaseProbability:rp.baseProbability}:{})};
      }
      return e;
    }).concat(rescued);
    return {events:promoted,info:{
      ...baseInfo,enabled:true,promoted:openSet.size,rescued:rescued.length,threshold,
      closed:hats.length-openSet.size,modelTrees:model.trees.length,modelFeatures:model.featureCount,
      meanProbability:hats.length?probSum/hats.length:0,maxProbability,sequence:sequenceInfo,overlay:overlayInfo
    }};
  }catch(err){
    console.warn('open-hat classifier fallback',err);
    return {events,info:{...baseInfo,error:String(err?.message||err),skipReason:'error'}};
  }
}
