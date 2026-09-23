// Lightweight arrangement-section analysis for optional off-vocal references.
// This module does not alter drum notes. It only returns section-local context
// that can later weight GMD genre experts.
//
// Design goals:
// - no external runtime dependency
// - usable with an AudioBuffer or a mono Float32Array
// - stable boundaries from timbre/energy changes
// - repeated sections receive the same structural group when sufficiently similar

const EPS=1e-9;

function mean(values){
  if(!values.length)return 0;
  let s=0;for(const v of values)s+=v;return s/values.length;
}
function std(values,m=mean(values)){
  if(values.length<2)return 0;
  let s=0;for(const v of values){const d=v-m;s+=d*d;}
  return Math.sqrt(s/values.length);
}
function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
function cosine(a,b){
  let ab=0,aa=0,bb=0;
  for(let i=0;i<a.length;i++){ab+=a[i]*b[i];aa+=a[i]*a[i];bb+=b[i]*b[i];}
  return ab/Math.sqrt(Math.max(EPS,aa*bb));
}
function dist(a,b){
  let s=0;for(let i=0;i<a.length;i++){const d=a[i]-b[i];s+=d*d;}
  return Math.sqrt(s/Math.max(1,a.length));
}
function averageVectors(rows,start,end){
  if(start>=end||!rows.length)return new Array(rows[0]?.length||0).fill(0);
  const out=new Array(rows[0].length).fill(0);
  let n=0;
  for(let i=Math.max(0,start);i<Math.min(rows.length,end);i++){
    n++;for(let j=0;j<out.length;j++)out[j]+=rows[i][j];
  }
  if(n)for(let j=0;j<out.length;j++)out[j]/=n;
  return out;
}

function monoFromAudioBuffer(buffer){
  const n=buffer.length,channels=buffer.numberOfChannels||1,out=new Float32Array(n);
  for(let c=0;c<channels;c++){
    const data=buffer.getChannelData(c);
    for(let i=0;i<n;i++)out[i]+=data[i]/channels;
  }
  return out;
}

function frameDescriptor(samples,start,end,sampleRate){
  let sum2=0,diff2=0,peak=0,zcr=0,prev=samples[start]||0;
  let lpLow=prev,lpMid=prev,low2=0,mid2=0,high2=0;
  const aLow=1-Math.exp(-2*Math.PI*250/sampleRate);
  const aMid=1-Math.exp(-2*Math.PI*2200/sampleRate);
  const n=Math.max(1,end-start);
  for(let i=start;i<end;i++){
    const x=samples[i]||0;
    sum2+=x*x;peak=Math.max(peak,Math.abs(x));
    const d=x-prev;diff2+=d*d;
    if((x>=0)!=(prev>=0))zcr++;
    lpLow+=aLow*(x-lpLow);
    lpMid+=aMid*(x-lpMid);
    const low=lpLow,mid=lpMid-lpLow,high=x-lpMid;
    low2+=low*low;mid2+=mid*mid;high2+=high*high;
    prev=x;
  }
  const rms=Math.sqrt(sum2/n),total=low2+mid2+high2+EPS;
  return [
    Math.log10(EPS+rms),
    peak/(rms+1e-6),
    Math.sqrt(diff2/n)/(rms+1e-6),
    zcr/n,
    low2/total,
    mid2/total,
    high2/total,
  ];
}

export function extractSectionFeatures(samples,sampleRate,options={}){
  const frameSec=Number(options.frameSec)||1.0;
  const hopSec=Number(options.hopSec)||0.5;
  const frame=Math.max(256,Math.round(frameSec*sampleRate));
  const hop=Math.max(128,Math.round(hopSec*sampleRate));
  const rows=[],times=[];
  for(let start=0;start<samples.length;start+=hop){
    const end=Math.min(samples.length,start+frame);
    if(end-start<Math.min(frame,Math.round(.25*sampleRate)))break;
    rows.push(frameDescriptor(samples,start,end,sampleRate));
    times.push((start+(end-start)/2)/sampleRate);
  }
  if(!rows.length)return {rows:[],normalized:[],times:[],frameSec,hopSec};

  const dim=rows[0].length,mu=[],sd=[];
  for(let j=0;j<dim;j++){
    const col=rows.map(r=>r[j]),m=mean(col);
    mu.push(m);sd.push(Math.max(1e-5,std(col,m)));
  }
  const normalized=rows.map(r=>r.map((v,j)=>(v-mu[j])/sd[j]));
  return {rows,normalized,times,mean:mu,std:sd,frameSec,hopSec};
}

function noveltyCurve(normalized,contextFrames=8){
  const n=normalized.length,out=new Array(n).fill(0);
  for(let i=1;i<n-1;i++){
    const left=averageVectors(normalized,i-contextFrames,i);
    const right=averageVectors(normalized,i+1,i+1+contextFrames);
    out[i]=dist(left,right);
  }
  const smooth=out.map((_,i)=>{
    let s=0,nv=0;
    for(let j=i-1;j<=i+1;j++)if(j>=0&&j<out.length){s+=out[j];nv++;}
    return s/Math.max(1,nv);
  });
  return smooth;
}

function snapBoundary(time,options,duration){
  const bpm=Number(options.bpm);
  if(!Number.isFinite(bpm)||bpm<=0)return clamp(time,0,duration);
  const denominator=Number(options.denominator)||4,numerator=Number(options.numerator)||4;
  const beat=60/bpm*4/denominator;
  const phase=Number(options.barPhaseSec);
  if(Number.isFinite(phase)){
    const bar=beat*numerator;
    const k=Math.round((time-phase)/bar);
    const snapped=phase+k*bar;
    if(Math.abs(snapped-time)<=Math.min(1.5,bar*.55))return clamp(snapped,0,duration);
  }
  const snapped=Math.round(time/beat)*beat;
  return clamp(snapped,0,duration);
}

function pickBoundaries(curve,times,duration,options){
  if(curve.length<3)return [0,duration];
  const m=mean(curve),s=std(curve,m);
  const threshold=m+(Number(options.noveltyStd)||0.72)*s;
  const minSectionSec=Number(options.minSectionSec)||8;
  const candidates=[];
  for(let i=2;i<curve.length-2;i++){
    if(curve[i]<threshold)continue;
    if(curve[i]<curve[i-1]||curve[i]<curve[i+1]||curve[i]<curve[i-2]||curve[i]<curve[i+2])continue;
    candidates.push({time:times[i],score:curve[i]});
  }
  candidates.sort((a,b)=>b.score-a.score);
  const kept=[];
  for(const c of candidates){
    if(c.time<minSectionSec||duration-c.time<minSectionSec)continue;
    if(kept.every(k=>Math.abs(k.time-c.time)>=minSectionSec))kept.push(c);
  }
  kept.sort((a,b)=>a.time-b.time);
  const maxSections=Math.max(2,Number(options.maxSections)||18);
  if(kept.length>maxSections-1){
    kept.sort((a,b)=>b.score-a.score);
    kept.length=maxSections-1;
    kept.sort((a,b)=>a.time-b.time);
  }
  const raw=[0,...kept.map(x=>x.time),duration];
  const snapped=[0];
  for(let i=1;i<raw.length-1;i++){
    const t=snapBoundary(raw[i],options,duration);
    if(t-snapped[snapped.length-1]>=minSectionSec*.65&&duration-t>=minSectionSec*.65)snapped.push(t);
  }
  snapped.push(duration);
  return snapped;
}

function sectionVector(normalized,times,start,end){
  const idx=[];
  for(let i=0;i<times.length;i++)if(times[i]>=start&&times[i]<end)idx.push(i);
  if(!idx.length)return new Array(normalized[0]?.length||0).fill(0);
  return averageVectors(normalized,idx[0],idx[idx.length-1]+1);
}

function assignStructuralGroups(sections){
  const reps=[];
  const alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  for(const section of sections){
    let best=-1,bestSim=-1;
    for(let i=0;i<reps.length;i++){
      const sim=cosine(section.vector,reps[i].vector);
      const ratio=Math.min(section.duration,reps[i].duration)/Math.max(EPS,Math.max(section.duration,reps[i].duration));
      const score=.82*sim+.18*ratio;
      if(score>bestSim){bestSim=score;best=i;}
    }
    if(best>=0&&bestSim>=.87){
      section.group=reps[best].group;
      section.repeatSimilarity=bestSim;
      reps[best].vector=reps[best].vector.map((v,j)=>(v+section.vector[j])*.5);
      reps[best].duration=(reps[best].duration+section.duration)*.5;
    }else{
      section.group=alphabet[reps.length]||`S${reps.length+1}`;
      section.repeatSimilarity=1;
      reps.push({group:section.group,vector:section.vector.slice(),duration:section.duration});
    }
  }
}

export function analyzeSections(input,options={}){
  const isBuffer=input&&typeof input.getChannelData==="function";
  const sampleRate=isBuffer?input.sampleRate:Number(options.sampleRate);
  if(!Number.isFinite(sampleRate)||sampleRate<=0)throw new Error("sampleRate is required");
  const samples=isBuffer?monoFromAudioBuffer(input):input;
  if(!samples?.length)return {duration:0,boundaries:[0],sections:[],novelty:[]};

  const duration=samples.length/sampleRate;
  const features=extractSectionFeatures(samples,sampleRate,options);
  const contextSec=Number(options.contextSec)||4;
  const contextFrames=Math.max(2,Math.round(contextSec/features.hopSec));
  const novelty=noveltyCurve(features.normalized,contextFrames);
  const boundaries=pickBoundaries(novelty,features.times,duration,options);

  const sections=[];
  for(let i=0;i<boundaries.length-1;i++){
    const start=boundaries[i],end=boundaries[i+1];
    sections.push({
      index:i,
      startSec:start,
      endSec:end,
      duration:end-start,
      vector:sectionVector(features.normalized,features.times,start,end),
      // Naming is deliberately structural, not semantic. A/B/C can later be
      // mapped to verse/chorus only when stronger evidence exists.
      group:null,
      repeatSimilarity:0,
    });
  }
  assignStructuralGroups(sections);

  return {
    duration,
    boundaries,
    sections,
    novelty,
    featureTimes:features.times,
    featureSchema:["logRms","crest","diffRmsNorm","zcr","lowRatio","midRatio","highRatio"],
    method:"offvocal-local-timbre-novelty-v1",
  };
}
