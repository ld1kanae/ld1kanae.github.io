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
let modelPromise=null;
function loadModel(){
  if(!modelPromise)modelPromise=fetch(new URL('./models/alternating-hi-hat-review-v1.json',import.meta.url))
    .then(r=>{if(!r.ok)throw Error('交互ハイハットモデルを読み込めません');return r.json();});
  return modelPromise;
}
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
function bandEnergy(samples,t,bands,w){
  const center=Math.round(t*SR),lo=center-(NFFT>>1);
  for(let i=0;i<NFFT;i++)w.frame[i]=(samples[lo+i]||0)*WINDOW[i];
  fftMagnitude(w.frame,w.real,w.imag,w.mag);
  const out=new Float64Array(bands.length);
  for(let i=0;i<BINS;i++)for(let b=0;b<bands.length;b++)if(FREQ[i]>=bands[b][0]&&FREQ[i]<bands[b][1])out[b]+=w.mag[i];
  return out;
}
function features(samples,t,step,model,w){
  const o=model.offsetsSec||{},bands=model.bands;
  const rows=[
    bandEnergy(samples,t+Number(o.pre??-.05),bands,w),
    bandEnergy(samples,t+Number(o.attack??.0125),bands,w),
    bandEnergy(samples,t+Number(o.tail??.14),bands,w),
    bandEnergy(samples,t+step+Number(o.preNext??-.05),bands,w),
    bandEnergy(samples,t+step+Number(o.postNext??.145),bands,w)
  ];
  const out=[];
  for(let b=0;b<bands.length;b++){
    const pre=rows[0][b]+1e-9,attack=rows[1][b]+1e-9,tail=rows[2][b]+1e-9,preNext=rows[3][b]+1e-9,postNext=rows[4][b]+1e-9;
    out.push(Math.log(attack/pre),Math.log(tail/attack),Math.log(preNext/attack),Math.log(postNext/preNext),Math.log(tail/pre));
  }
  return out;
}
function sigmoid(x){return 1/(1+Math.exp(-x));}
function predict(model,x){
  let z=Number(model.intercept)||0;
  for(let i=0;i<x.length;i++)z+=(Number(model.coef[i])||0)*(x[i]-(Number(model.mean[i])||0))/(Number(model.scale[i])||1);
  return sigmoid(z);
}
function lowerBound(a,x){let lo=0,hi=a.length;while(lo<hi){const m=(lo+hi)>>1;if(a[m]<x)lo=m+1;else hi=m;}return lo;}
function nearIndex(times,t,tol){
  let i=lowerBound(times,t-tol),best=-1,dist=Infinity;
  while(i<times.length&&times[i]<=t+tol){const d=Math.abs(times[i]-t);if(d<dist){dist=d;best=i;}i++;}
  return best;
}
function quantile(a,q){if(!a.length)return 0;const b=a.slice().sort((x,y)=>x-y),p=(b.length-1)*q,l=Math.floor(p),h=Math.ceil(p);return b[l]+(b[h]-b[l])*(p-l);}
function logLikelihood(ps,pattern){let s=0;for(let i=0;i<ps.length;i++){const p=Math.max(1e-6,Math.min(1-1e-6,ps[i]));s+=pattern[i]?Math.log(p):Math.log(1-p);}return s/ps.length;}
function handCount(events,t){return events.filter(e=>['snare','tom','hat','open_hat','crash','ride'].includes(e.group)&&Math.abs(e.time-t)<=.035).length;}

export async function repairAlternatingHiHats(decoded,events,broadMetal,bpm,barPhaseSec,variant='off'){
  const variants=new Set(['off','articulation','metal-grid','guarded-rescue']);
  if(!variants.has(variant)||variant==='off')return {events,info:{enabled:false,variant:'off'}};
  try{
    const model=await loadModel(),policy=model.policy||{},samples=await monoAt44100(decoded),w=workspace();
    const step=30/Math.max(Number(bpm)||0,1e-6),origin=Number.isFinite(Number(barPhaseSec))?Number(barPhaseSec):0;
    const duration=samples.length/SR;
    const first=Math.ceil((0-origin)/step),last=Math.floor((duration-step-.16-origin)/step);
    const slots=[];
    for(let n=first;n<=last;n++){
      const time=origin+n*step,x=features(samples,time,step,model,w),p=predict(model,x);
      const attack=x.filter((_,i)=>i%5===0).reduce((a,b)=>a+b,0)/4;
      slots.push({n,time,p,attack,voteOpen:0,voteClosed:0,selected:false});
    }
    const broad=(broadMetal||[]).filter(e=>e.group==='hat'||e.group==='cymbal'||e.group==='crash'||e.group==='ride').slice().sort((a,b)=>a.time-b.time);
    const broadTimes=broad.map(e=>e.time),windowSlots=Number(policy.windowSlots)||8;
    const minCoverage=Number(policy.minCandidateCoverage)||.625,minConfidence=Number(policy.minPatternConfidence)||.72;
    const minAccuracy=Number(policy.minPatternAccuracy)||.75,minMargin=Number(policy.minLogLikelihoodMargin)||.5;
    let acceptedWindows=0;
    for(let i=0;i+windowSlots<=slots.length;i++){
      const row=slots.slice(i,i+windowSlots),ps=row.map(s=>s.p),pat0=row.map(s=>(s.n&1)===0),pat1=pat0.map(x=>!x);
      const ll0=logLikelihood(ps,pat0),ll1=logLikelihood(ps,pat1),pattern=ll0>=ll1?pat0:pat1;
      const best=Math.max(ll0,ll1),other=Math.min(ll0,ll1);
      const confidence=pattern.reduce((s,y,j)=>s+(y?ps[j]:1-ps[j]),0)/windowSlots;
      const accuracy=pattern.reduce((s,y,j)=>s+(((ps[j]>=.5)===y)?1:0),0)/windowSlots;
      let covered=0;for(const s of row)if(nearIndex(broadTimes,s.time,Number(policy.broadToleranceSec)||.11)>=0)covered++;
      if(covered/windowSlots<minCoverage||confidence<minConfidence||accuracy<minAccuracy||best-other<minMargin)continue;
      acceptedWindows++;
      for(let j=0;j<windowSlots;j++){row[j].selected=true;if(pattern[j])row[j].voteOpen++;else row[j].voteClosed++;}
    }
    const minRun=Number(policy.minRunSlots)||8;let runStart=-1,runs=[];
    for(let i=0;i<=slots.length;i++){
      if(i<slots.length&&slots[i].selected){if(runStart<0)runStart=i;continue;}
      if(runStart>=0){if(i-runStart>=minRun)runs.push([runStart,i]);else for(let j=runStart;j<i;j++)slots[j].selected=false;runStart=-1;}
    }
    const selected=slots.filter(s=>s.selected),attackFloor=quantile(selected.map(s=>s.attack),Number(policy.rescueAudioQuantile)||.55);
    const current=events.slice().sort((a,b)=>a.time-b.time),metalGroups=new Set(['hat','open_hat','pedal_hat','crash','ride']);
    const currentMetal=current.filter(e=>metalGroups.has(e.group)),currentTimes=currentMetal.map(e=>e.time);
    const used=new Set(),replace=new Map();let changed=0,convertedCymbal=0,removedOffGrid=0,rescued=0;
    for(const s of selected){
      const desired=s.voteOpen>s.voteClosed?'open_hat':'hat';
      const ci=nearIndex(currentTimes,s.time,Number(policy.gridToleranceSec)||.09);
      if(ci>=0){
        const e=currentMetal[ci];used.add(e);
        if(e.group!==desired){changed++;if(e.group==='crash'||e.group==='ride')convertedCymbal++;}
        replace.set(e,{...e,group:desired,alternatingHatRepair:true,alternatingHatProbability:s.p});
        continue;
      }
      if(variant!=='guarded-rescue')continue;
      const bi=nearIndex(broadTimes,s.time,Number(policy.broadToleranceSec)||.11),candidate=bi>=0?broad[bi]:null;
      if(!candidate&&s.attack<attackFloor)continue;
      if(handCount(current,s.time)>=2)continue;
      current.push({...candidate,time:s.time,group:desired,score:Number(candidate?.score)||.2,confidence:Number(candidate?.confidence)||.5,
        alternatingHatRepair:true,alternatingHatRescue:true,alternatingHatProbability:s.p});
      rescued++;
    }
    let out=current.map(e=>replace.get(e)||e);
    if(variant==='metal-grid'||variant==='guarded-rescue'){
      out=out.filter(e=>{
        if(!metalGroups.has(e.group)||e.alternatingHatRescue||used.has(e))return true;
        const si=Math.round((e.time-origin)/step)-first;
        if(si<0||si>=slots.length||!slots[si].selected)return true;
        const d=Math.abs(e.time-slots[si].time);
        if(d<=(Number(policy.gridToleranceSec)||.09))return true;
        removedOffGrid++;return false;
      });
    }
    out.sort((a,b)=>a.time-b.time);
    return {events:out,info:{enabled:true,variant,model:model.name,acceptedWindows,runs:runs.length,selectedSlots:selected.length,
      changed,convertedCymbal,removedOffGrid,rescued,attackFloor}};
  }catch(err){
    console.warn('alternating hi-hat repair fallback',err);
    return {events,info:{enabled:false,variant,error:String(err?.message||err)}};
  }
}
