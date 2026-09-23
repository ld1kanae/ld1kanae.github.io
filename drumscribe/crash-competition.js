import {monoAt44100} from './hat-forest.js';

const SR=44100,NFFT=4096,BINS=NFFT/2+1;
const FREQ=Float64Array.from({length:BINS},(_,i)=>i*SR/NFFT);
const WINDOW=Float64Array.from({length:NFFT},(_,i)=>.5-.5*Math.cos(2*Math.PI*i/(NFFT-1)));
const TWIDDLES=[];
for(let length=2;length<=NFFT;length*=2){
  const cos=new Float64Array(length/2),sin=new Float64Array(length/2);
  for(let k=0;k<length/2;k++){cos[k]=Math.cos(-2*Math.PI*k/length);sin[k]=Math.sin(-2*Math.PI*k/length);}
  TWIDDLES.push([length,cos,sin]);
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
  for(let i=0;i<BINS;i++)out[i]=Math.hypot(real[i],imag[i])+1e-12;
}
function lowMidEnergy(samples,t,w){
  const center=Math.round(t*SR),lo=center-(NFFT>>1);
  for(let i=0;i<NFFT;i++)w.frame[i]=(samples[lo+i]||0)*WINDOW[i];
  fftMagnitude(w.frame,w.real,w.imag,w.mag);
  let sum=0;
  for(let i=0;i<BINS;i++)if(FREQ[i]>=800&&FREQ[i]<5000)sum+=w.mag[i];
  return sum;
}
function lowerBound(xs,x){let lo=0,hi=xs.length;while(lo<hi){const m=(lo+hi)>>1;if(xs[m]<x)lo=m+1;else hi=m;}return lo;}
function near(xs,t,w){
  const i=lowerBound(xs,t);
  return (i<xs.length&&Math.abs(xs[i]-t)<=w)||(i>0&&Math.abs(xs[i-1]-t)<=w);
}

const VARIANTS=new Set(['collision-lowmid-final','collision-lowmid-struct','collision-lowmid-run']);

export async function filterCrashHatTail(decoded,events,variant='legacy'){
  if(!VARIANTS.has(variant))return {events,info:{enabled:false,variant}};
  const threshold=.28,windowSec=.075;
  const hats=events.filter(e=>e.group==='hat'||e.group==='open_hat').map(e=>e.time).sort((a,b)=>a-b);
  const candidates=events.filter(e=>e.group==='crash'&&e.cymbalEvidence&&Number(e.cymbalEvidence.headDistance)<=.30&&!e.cymbalEvidence.crashSupport);
  const info={enabled:true,variant,threshold,windowSec,candidates:candidates.length,eligible:0,removed:0,kept:0,rawProtected:0,decisions:[]};
  if(!candidates.length)return {events,info};
  const samples=await monoAt44100(decoded),w=workspace();
  const keep=new Map();
  for(const e of candidates){
    const ev=e.cymbalEvidence;
    const finalHat=near(hats,e.time,windowSec);
    const structuralHat=Boolean(ev.hatSupport);
    const regularRun=Math.max(Number(ev.hatGrid16)||0,Number(ev.hatGrid8)||0)>=.75;
    let eligible=finalHat;
    if(variant==='collision-lowmid-struct')eligible=eligible||structuralHat;
    if(variant==='collision-lowmid-run')eligible=eligible||structuralHat||regularRun;
    if(!eligible)continue;
    info.eligible++;
    const onset=lowMidEnergy(samples,e.time+.012,w)+1e-12;
    const tail=lowMidEnergy(samples,e.time+.180,w);
    const ratio=tail/onset;
    const accepted=ratio>=threshold;
    keep.set(e,accepted);
    if(accepted)info.kept++;else info.removed++;
    info.decisions.push({
      time:e.time,lowMidTail180:ratio,keep:accepted,
      finalHat,structuralHat,regularRun,
      hatGrid16:Number(ev.hatGrid16)||0,hatGrid8:Number(ev.hatGrid8)||0,
      baseConfidence:Number(ev.baseConfidence)||0,
      crashSimilarity:Number(ev.crashSimilarity)||0,
      hatSimilarity:Number(ev.hatSimilarity)||0
    });
  }
  return {events:events.filter(e=>!keep.has(e)||keep.get(e)),info};
}
