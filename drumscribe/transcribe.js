import {transcribeAdtof} from './adtof.js';
import {filterHighResHats} from './hat-forest.js';
// Browser port of experiments/evaluate.py's band-precision candidate detector.
// Reference MIDI is never read here. Times are measured from the audio file start.
const RATE=11025, SIZE=1024, HOP=110, BINS=513;
const NAMES=['kick','snare','hat','tom','cymbal'];
const NOTES=[36,38,42,45,49];
const THRESHOLDS=[.58,.70,.19,1.5,1.0];
const DISTANCES=[.075,.075,.055,.09,.12];
const EDGES=[35,140,900,3000,5500];
const wait=()=>new Promise(resolve=>setTimeout(resolve,0));
const TEMPLATE_GROUPS=['kick','snare','hat','tom','crash','ride','pedal_hat'];
const TEMPLATE_INDEX=Object.fromEntries(TEMPLATE_GROUPS.map((g,i)=>[g,i]));

function percentile(values,q){
  const a=Array.from(values).sort((x,y)=>x-y);
  if(!a.length)return 0;
  return a[Math.max(0,Math.min(a.length-1,Math.floor(q*(a.length-1))))]||0;
}
function rhythmPeaks(signal,pct=.8,minDistanceSec=.11,prominence=.06,maxCount=1400){
  const threshold=percentile(signal,pct),minFrames=Math.max(1,Math.round(minDistanceSec*RATE/HOP));
  const candidates=[];
  for(let i=2;i<signal.length-2;i++){
    const v=signal[i];
    if(v<threshold||v<=signal[i-1]||v<signal[i+1])continue;
    if(v-Math.min(signal[i-2],signal[i+2])<prominence)continue;
    candidates.push(i);
  }
  candidates.sort((a,b)=>signal[b]-signal[a]);
  const kept=[];
  for(const p of candidates){
    if(kept.some(q=>Math.abs(q-p)<minFrames))continue;
    kept.push(p);
    if(kept.length>=maxCount)break;
  }
  kept.sort((a,b)=>a-b);
  return kept.map(frame=>({frame,time:frame*HOP/RATE,weight:Math.max(1e-7,signal[frame])}));
}
function tempoHistogramFromSnare(mid){
  const peaks=rhythmPeaks(mid,.72,.11,.06,1800);
  const lo=50,hi=220,step=.25,n=Math.round((hi-lo)/step)+1,hist=new Float64Array(n);
  for(let i=0;i<peaks.length;i++){
    const a=peaks[i];
    for(let j=i+1;j<Math.min(peaks.length,i+12);j++){
      const dt=peaks[j].time-a.time;
      if(dt>3)break;
      if(dt<.28)continue;
      const w=Math.sqrt(a.weight*peaks[j].weight)/Math.pow(j-i,.55);
      for(let mult=1;mult<=3;mult++){
        const bpm=120*mult/dt;
        if(bpm<lo||bpm>hi)continue;
        const k=Math.round((bpm-lo)/step);
        hist[k]+=w/Math.pow(mult,.45);
      }
    }
  }
  let best=0;
  for(let i=1;i<hist.length;i++)if(hist[i]>hist[best])best=i;
  return {bpm:lo+best*step,score:hist[best],peaks,hist,lo,step};
}
function tempoHistogramFallback(low,mid){
  const mix=new Float32Array(low.length);
  for(let i=0;i<mix.length;i++)mix[i]=1.1*low[i]+mid[i];
  const peaks=rhythmPeaks(mix,.76,.10,.06,1800);
  const lo=50,hi=220,step=.25,n=Math.round((hi-lo)/step)+1,hist=new Float64Array(n);
  for(let i=0;i<peaks.length;i++){
    for(let j=i+1;j<Math.min(peaks.length,i+16);j++){
      const dt=peaks[j].time-peaks[i].time;
      if(dt>2.5)break;
      if(dt<.18)continue;
      const w=Math.sqrt(peaks[i].weight*peaks[j].weight)/Math.pow(j-i,.5);
      for(let mult=1;mult<=4;mult++){
        const bpm=60*mult/dt;
        if(bpm<lo||bpm>hi)continue;
        hist[Math.round((bpm-lo)/step)]+=w/Math.pow(mult,.35);
      }
    }
  }
  let best=0;
  for(let i=1;i<hist.length;i++)if(hist[i]>hist[best])best=i;
  return {bpm:lo+best*step,score:hist[best],peaks};
}
function phaseCoherence(peaks,bpm){
  if(!peaks.length)return 0;
  let cr=0,ci=0,sw=0;
  const factor=2*Math.PI*bpm/60;
  for(const p of peaks){
    const w=Math.max(1e-7,p.weight),a=factor*p.time;
    cr+=w*Math.cos(a);ci+=w*Math.sin(a);sw+=w;
  }
  return Math.hypot(cr,ci)/(sw||1);
}
function circularPhase(peaks,period){
  if(!peaks.length)return 0;
  let cr=0,ci=0;
  for(const p of peaks){
    const a=2*Math.PI*p.time/period,w=p.weight;
    cr+=w*Math.cos(a);ci+=w*Math.sin(a);
  }
  let a=Math.atan2(ci,cr);
  if(a<0)a+=2*Math.PI;
  return a/(2*Math.PI)*period;
}
function robustGridFit(peaks,bpm){
  if(peaks.length<8)return {bpm,phaseSec:0,used:0};
  let period=60/bpm,phase=circularPhase(peaks,period),used=[];
  for(let iter=0;iter<4;iter++){
    const limit=Math.min(.095,.18*period);
    used=[];
    for(const p of peaks){
      const n=Math.round((p.time-phase)/period),res=p.time-(phase+n*period);
      if(Math.abs(res)<=limit)used.push({p,n});
    }
    if(used.length<8)break;
    let sw=0,sn=0,st=0,snn=0,snt=0;
    for(const {p,n} of used){
      const w=Math.max(1e-6,p.weight);
      sw+=w;sn+=w*n;st+=w*p.time;snn+=w*n*n;snt+=w*n*p.time;
    }
    const det=sw*snn-sn*sn;
    if(Math.abs(det)<1e-12)break;
    const nextPhase=(st*snn-sn*snt)/det;
    const nextPeriod=(sw*snt-sn*st)/det;
    if(!(nextPeriod>0))break;
    phase=nextPhase;period=nextPeriod;
  }
  const fitBpm=60/period;
  return {bpm:fitBpm,phaseSec:((phase%period)+period)%period,used:used.length};
}
function estimateTempoFromBands(band){
  const coarseSnare=tempoHistogramFromSnare(band[1]);
  const fallback=tempoHistogramFallback(band[0],band[1]);
  let coarse=coarseSnare.bpm;
  // The snare recurrence is the primary metrical cue. Fall back only when it
  // is too sparse to be meaningful.
  if(coarseSnare.peaks.length<8||coarseSnare.score<=0)coarse=fallback.bpm;
  const kick=rhythmPeaks(band[0],.75,.10,.05,1200);
  const snare=rhythmPeaks(band[1],.80,.12,.07,1200);
  const span=Math.max(1.2,coarse*.012),steps=1600;
  let bestBpm=coarse,best=-Infinity;
  for(let i=0;i<=steps;i++){
    const bpm=coarse-span+2*span*i/steps;
    const score=.68*phaseCoherence(snare,bpm)+.32*phaseCoherence(kick,bpm);
    if(score>best){best=score;bestBpm=bpm;}
  }
  const fitPeaks=rhythmPeaks(band[1],.82,.12,.08,1000);
  const fit=robustGridFit(fitPeaks,bestBpm);
  const finalBpm=Math.abs(fit.bpm-bestBpm)/bestBpm<=.004?fit.bpm:bestBpm;
  return {
    bpm:Math.max(30,Math.min(300,finalBpm)),
    coarseBpm:coarse,
    spectralBpm:bestBpm,
    phaseSec:fit.phaseSec,
    confidence:Math.max(0,Math.min(1,best)),
    snarePeaks:coarseSnare.peaks.length
  };
}
function eventIntervalCandidates(times,kind){
  const lo=50,hi=220,step=.25,n=Math.round((hi-lo)/step)+1,hist=new Float64Array(n);
  const maxNext=kind==='kick'?18:12;
  for(let i=0;i<times.length;i++){
    for(let j=i+1;j<Math.min(times.length,i+maxNext);j++){
      const dt=times[j]-times[i];
      if(dt>(kind==='kick'?2.6:3.2))break;
      if(dt<.16)continue;
      if(kind==='snare'){
        for(let mult=1;mult<=3;mult++){
          const bpm=120*mult/dt;
          if(bpm<lo||bpm>hi)continue;
          hist[Math.round((bpm-lo)/step)]+=1/Math.pow(j-i,.55)/Math.pow(mult,.45);
        }
      }else{
        for(let mult=1;mult<=4;mult++){
          const bpm=60*mult/dt;
          if(bpm<lo||bpm>hi)continue;
          hist[Math.round((bpm-lo)/step)]+=1/Math.pow(j-i,.5)/Math.pow(mult,.35);
        }
      }
    }
  }
  const rows=[];
  for(let i=1;i<n-1;i++)if(hist[i]>=hist[i-1]&&hist[i]>=hist[i+1])rows.push({value:hist[i],bpm:lo+i*step});
  rows.sort((a,b)=>b.value-a.value);
  return rows.slice(0,15);
}
function eventPhaseCoherence(times,bpm){
  if(!times.length)return 0;
  let cr=0,ci=0;
  const f=2*Math.PI*bpm/60;
  for(const t of times){const a=f*t;cr+=Math.cos(a);ci+=Math.sin(a);}
  return Math.hypot(cr,ci)/times.length;
}
function estimateEventTempoFamily(events){
  const kick=events.filter(e=>e.group==='kick').map(e=>e.time).sort((a,b)=>a-b);
  const snare=events.filter(e=>e.group==='snare').map(e=>e.time).sort((a,b)=>a-b);
  const kh=eventIntervalCandidates(kick,'kick'),sh=eventIntervalCandidates(snare,'snare');
  if(!kh.length&&!sh.length)return {bpm:0,score:0,candidates:[]};
  const kmax=kh[0]?.value||1,smax=sh[0]?.value||1,pool=[];
  for(const rows of [kh,sh]){
    for(const row of rows.slice(0,10)){
      for(const ratio of [.5,1,2]){
        const bpm=row.bpm*ratio;
        if(bpm>=50&&bpm<=220)pool.push(bpm);
      }
    }
  }
  const unique=[];
  for(const bpm of pool)if(!unique.some(x=>Math.abs(x-bpm)<.7))unique.push(bpm);
  const nearValue=(rows,bpm)=>{
    let best=0;
    for(const r of rows)if(Math.abs(r.bpm-bpm)<.8)best=Math.max(best,r.value);
    return best;
  };
  const scored=unique.map(bpm=>{
    const kickHist=nearValue(kh,bpm)/Math.max(kmax,1e-9);
    const snareHist=nearValue(sh,bpm)/Math.max(smax,1e-9);
    const kickCoh=eventPhaseCoherence(kick,bpm),snareCoh=eventPhaseCoherence(snare,bpm);
    const score=.55*snareHist+.20*kickHist+.15*snareCoh+.10*kickCoh;
    return {bpm,score,kickHist,snareHist,kickCoh,snareCoh};
  }).sort((a,b)=>b.score-a.score);
  return {bpm:scored[0]?.bpm||0,score:scored[0]?.score||0,candidates:scored.slice(0,8)};
}
function refineTempoAround(band,center){
  const kick=rhythmPeaks(band[0],.75,.10,.05,1200);
  const snare=rhythmPeaks(band[1],.80,.12,.07,1200);
  const span=Math.max(1.2,center*.012),steps=1600;
  let bestBpm=center,best=-Infinity;
  for(let i=0;i<=steps;i++){
    const bpm=center-span+2*span*i/steps;
    const score=.68*phaseCoherence(snare,bpm)+.32*phaseCoherence(kick,bpm);
    if(score>best){best=score;bestBpm=bpm;}
  }
  const fitPeaks=rhythmPeaks(band[1],.82,.12,.08,1000);
  const fit=robustGridFit(fitPeaks,bestBpm);
  const bpm=Math.abs(fit.bpm-bestBpm)/bestBpm<=.004?fit.bpm:bestBpm;
  return {bpm,coarseBpm:center,spectralBpm:bestBpm,phaseSec:fit.phaseSec,confidence:Math.max(0,Math.min(1,best)),fitUsed:fit.used};
}
function circDistance(t,phase,period){
  let x=(t-phase)%period;if(x<0)x+=period;
  return Math.min(x,period-x);
}
function scoreBarHypothesis(events,bpm,phase,mode){
  const beat=60/bpm,bar=4*beat,sigma=Math.max(.025,.10*beat);
  let total=0,den=0;
  for(const e of events){
    if(e.group!=='kick'&&e.group!=='snare')continue;
    const pos=((e.time-phase)%bar+bar)%bar;
    let targets,weight;
    if(mode==='legacy'){targets=[0];weight=e.group==='kick'?1.8:.75;}
    else{
      targets=e.group==='kick'?[0,2*beat]:[beat,3*beat];
      weight=e.group==='kick'?1.25:1.0;
    }
    let d=Infinity;
    for(const target of targets)d=Math.min(d,circDistance(pos,target,bar));
    total+=weight*Math.min(2.2,Math.sqrt(Math.max(e.score||0,0)))*Math.exp(-.5*(d/sigma)**2);
    den+=weight;
  }
  return total/Math.max(1e-9,den);
}
function estimateBarHypothesis(events,bpm,mode){
  const beat=60/bpm,bar=4*beat;
  let bestScore=-Infinity,bestPhase=0;
  for(let q=0;q<512;q++){
    const phase=bar*q/512,score=scoreBarHypothesis(events,bpm,phase,mode);
    if(score>bestScore){bestScore=score;bestPhase=phase;}
  }
  const center=bestPhase;
  for(let i=0;i<=80;i++){
    const d=(-.10+.20*i/80)*beat,phase=((center+d)%bar+bar)%bar;
    const score=scoreBarHypothesis(events,bpm,phase,mode);
    if(score>bestScore){bestScore=score;bestPhase=phase;}
  }
  return {phaseSec:bestPhase,score:bestScore};
}
function crashAnchors(events,sim){
  const out=[];
  for(const e of events){
    if(e.group!=='cymbal_raw')continue;
    const cs=sim[TEMPLATE_INDEX.crash][e.frame],rs=sim[TEMPLATE_INDEX.ride][e.frame],hs=sim[TEMPLATE_INDEX.hat][e.frame];
    if(cs>=.39&&cs>=1.45*rs&&cs>=1.30*hs)out.push({time:e.time,strength:cs});
  }
  return out;
}
function crashAnchorScore(anchors,phase,bpm){
  if(!anchors.length)return 0;
  const beat=60/bpm,bar=4*beat,sigma=.16*beat;
  let sum=0;
  for(const a of anchors){
    const d=circDistance(a.time,phase,bar);
    sum+=(.5+a.strength)*Math.exp(-.5*(d/sigma)**2);
  }
  return sum/anchors.length;
}
function sampleBandAtTime(signal,time,radiusSec=.035){
  const center=Math.round(time*RATE/HOP),r=Math.max(1,Math.round(radiusSec*RATE/HOP));
  let best=0;
  for(let i=Math.max(0,center-r);i<=Math.min(signal.length-1,center+r);i++)best=Math.max(best,signal[i]);
  return best;
}
function meanTop(values,fraction=.2){
  if(!values.length)return 0;
  const a=values.slice().sort((x,y)=>x-y),n=Math.max(1,Math.round(a.length*fraction));
  let s=0;for(let i=a.length-n;i<a.length;i++)s+=a[i];
  return s/n;
}
function barGridCandidateFeatures(events,sim,band,bpm,beatPhase){
  const beat=60/bpm,bar=4*beat,anchors=crashAnchors(events,sim);
  const kicks=events.filter(e=>e.group==='kick'),snares=events.filter(e=>e.group==='snare');
  const align=(list,targets,sigma=.14*beat)=>{
    if(!list.length)return 0;
    let sum=0;
    for(const e of list){
      let d=Infinity;
      for(const target of targets)d=Math.min(d,circDistance(e.time,target,bar));
      sum+=Math.min(2.2,Math.sqrt(Math.max(e.score||0,0)))*Math.exp(-.5*(d/sigma)**2);
    }
    return sum/list.length;
  };
  const high=new Float32Array(band[2].length);
  for(let i=0;i<high.length;i++)high[i]=band[2][i]+band[3][i];
  const rows=[];
  for(let off=0;off<4;off++){
    const phase=((beatPhase+off*beat)%bar+bar)%bar;
    const headTimes=[];
    for(let t=phase;t<band[0].length*HOP/RATE;t+=bar)headTimes.push(t);
    const lowVals=headTimes.map(t=>sampleBandAtTime(band[0],t));
    const midVals=headTimes.map(t=>sampleBandAtTime(band[1],t));
    const highVals=headTimes.map(t=>sampleBandAtTime(high,t));
    const kickHead=align(kicks,[phase]);
    const kickThird=align(kicks,[(phase+2*beat)%bar]);
    const snareBack=align(snares,[(phase+beat)%bar,(phase+3*beat)%bar]);
    const snareFront=align(snares,[phase,(phase+2*beat)%bar]);
    rows.push({
      offset:off,phaseSec:phase,kickHead,kickThird,snareBack,snareFront,
      snareContrast:(snareBack-snareFront)/(snareBack+snareFront+.05),
      crashAnchor:crashAnchorScore(anchors,phase,bpm),
      lowMean:lowVals.reduce((a,b)=>a+b,0)/Math.max(1,lowVals.length),
      lowTop:meanTop(lowVals,.2),
      midMean:midVals.reduce((a,b)=>a+b,0)/Math.max(1,midVals.length),
      highMean:highVals.reduce((a,b)=>a+b,0)/Math.max(1,highVals.length),
      highTop:meanTop(highVals,.2)
    });
  }
  return rows;
}
function refineBarPhaseNear(events,bpm,center,mode){
  const beat=60/bpm,bar=4*beat;
  let bestPhase=((center%bar)+bar)%bar,bestScore=-Infinity;
  for(let i=0;i<=120;i++){
    const d=(-.12+.24*i/120)*beat,phase=((center+d)%bar+bar)%bar;
    const score=scoreBarHypothesis(events,bpm,phase,mode);
    if(score>bestScore){bestScore=score;bestPhase=phase;}
  }
  return {phaseSec:bestPhase,score:bestScore};
}
function estimateBeatPhase(events,bpm){
  const beat=60/bpm;
  let xs=events.filter(e=>e.group==='kick');
  if(!xs.length)xs=events.filter(e=>e.group==='kick'||e.group==='snare');
  if(!xs.length)return {phaseSec:0,score:0,count:0};
  const sigma=.10*beat;
  let bestScore=-1,bestPhase=0;
  for(let q=0;q<512;q++){
    const phase=beat*q/512;
    let sum=0;
    for(const e of xs){
      const d=circDistance(e.time,phase,beat);
      sum+=Math.exp(-.5*(d/sigma)**2);
    }
    const score=sum/xs.length;
    if(score>bestScore){bestScore=score;bestPhase=phase;}
  }
  return {phaseSec:bestPhase,score:bestScore,count:xs.length};
}

function estimateHybridBarPhase(events,sim,bpm,beatPhase,band){
  const rows=barGridCandidateFeatures(events,sim,band,bpm,beatPhase);
  const maxContrast=Math.max(...rows.map(r=>Math.abs(r.snareContrast)));
  let pool,source,refineMode;
  if(maxContrast>=.15){
    pool=rows.filter(r=>r.snareContrast>0);
    if(!pool.length)pool=rows;
    for(const r of pool)r.selectionScore=r.kickHead+.05*r.lowMean;
    pool.sort((a,b)=>b.selectionScore-a.selectionScore);
    source='backbeat_kick';
    refineMode='roles';
  }else{
    pool=rows.slice();
    for(const r of pool)r.selectionScore=r.lowMean;
    pool.sort((a,b)=>b.selectionScore-a.selectionScore);
    source='low_fallback';
    refineMode='legacy';
  }
  const coarse=pool[0];
  const refined=refineBarPhaseNear(events,bpm,coarse.phaseSec,refineMode);
  return {
    phaseSec:refined.phaseSec,source,maxSnareContrast:maxContrast,
    selectedOffset:coarse.offset,coarsePhaseSec:coarse.phaseSec,
    selectionScore:coarse.selectionScore,refinedScore:refined.score,
    crashAnchors:crashAnchors(events,sim).length,
    gridCandidates:rows
  };
}

const twiddles=[];
for(let length=2;length<=SIZE;length*=2){
  const cos=new Float32Array(length/2),sin=new Float32Array(length/2);
  for(let k=0;k<length/2;k++){cos[k]=Math.cos(-2*Math.PI*k/length);sin[k]=Math.sin(-2*Math.PI*k/length);}
  twiddles.push([length,cos,sin]);
}
function fftMagnitude(input,real,imag,out){
  for(let i=0;i<SIZE;i++){real[i]=input[i];imag[i]=0;}
  for(let i=0,j=0;i<SIZE;i++){
    if(j>i){const tmp=real[i];real[i]=real[j];real[j]=tmp;}
    let bit=SIZE>>1;while(j&bit){j^=bit;bit>>=1;}j^=bit;
  }
  // In-place radix-2 FFT; windowed input is already stored in input.
  for(const [length,cos,sin] of twiddles){
    for(let start=0;start<SIZE;start+=length){
      for(let k=0;k<length/2;k++){
        const r=cos[k],s=sin[k],a=start+k,b=a+length/2;
        const vr=real[b]*r-imag[b]*s,vi=real[b]*s+imag[b]*r;
        real[b]=real[a]-vr;imag[b]=imag[a]-vi;
        real[a]+=vr;imag[a]+=vi;
      }
    }
  }
  for(let i=0;i<BINS;i++)out[i]=Math.hypot(real[i],imag[i]);
}

// The reference Python computes a 101-frame local median, then a 201-frame
// signal median. A subsampled local median keeps long files responsive in JS.
function localMedian(values,index,radius,step){
  const arr=[];for(let j=Math.max(0,index-radius);j<=Math.min(values.length-1,index+radius);j+=step)arr.push(values[j]);
  arr.sort((a,b)=>a-b);return arr[arr.length>>1]||0;
}
function percentile98(values){const copy=Array.from(values).sort((a,b)=>a-b);return copy[Math.floor(.98*(copy.length-1))]||0;}
async function parallelSpectrum(samples,frames,report){
  if(typeof Worker==='undefined'||frames<1800)return null;
  const cores=Math.max(2,Number(globalThis.navigator?.hardwareConcurrency)||2);
  const count=Math.min(4,Math.max(2,cores-1),Math.max(1,Math.ceil(frames/1800)));
  const spectrum=new Float32Array(frames*BINS),mean=new Float64Array(BINS);
  let completed=0;
  const jobs=[];
  for(let w=0;w<count;w++){
    const startFrame=Math.floor(frames*w/count),endFrame=Math.floor(frames*(w+1)/count);
    if(endFrame<=startFrame)continue;
    const globalStart=startFrame*HOP-(SIZE>>1);
    const globalEnd=(endFrame-1)*HOP+(SIZE>>1);
    const clipStart=Math.max(0,globalStart),clipEnd=Math.min(samples.length,globalEnd+1);
    const segment=samples.slice(clipStart,clipEnd);
    jobs.push(new Promise((resolve,reject)=>{
      const worker=new Worker(new URL('./fft-worker.js',import.meta.url));
      const cleanup=()=>worker.terminate();
      worker.onerror=e=>{cleanup();reject(e.error||Error(e.message||'FFT worker failed'));};
      worker.onmessage=e=>{
        const part=new Float32Array(e.data.spectrum),m=new Float64Array(e.data.mean);
        spectrum.set(part,startFrame*BINS);
        for(let j=0;j<BINS;j++)mean[j]+=m[j];
        completed++;report('周波数を並列解析中…',10+36*completed/count);
        cleanup();resolve();
      };
      worker.postMessage({samples:segment.buffer,startFrame,endFrame,sampleStart:clipStart},[segment.buffer]);
    }));
  }
  await Promise.all(jobs);
  return {spectrum,mean};
}


export async function transcribe(decoded,report=()=>{},options={}){
  report('音声を解析用に変換中…',5);
  let samples;
  try{
    const offline=new OfflineAudioContext(1,Math.ceil(decoded.duration*RATE),RATE);
    const source=offline.createBufferSource();source.buffer=decoded;
    source.connect(offline.destination);source.start();
    samples=(await offline.startRendering()).getChannelData(0);
  }catch{
    // A browser without low-rate OfflineAudioContext can still transcribe.
    const a=decoded.getChannelData(0),b=decoded.numberOfChannels>1?decoded.getChannelData(1):a;
    samples=new Float32Array(Math.ceil(decoded.duration*RATE));
    for(let i=0;i<samples.length;i++){
      const p=i*decoded.sampleRate/RATE,j=Math.min(a.length-2,p|0),f=p-j;
      samples[i]=((a[j]+b[j])*(1-f)+(a[j+1]+b[j+1])*f)*.5;
    }
  }
  const frames=Math.ceil(samples.length/HOP);
  let spectrum,mean;
  try{
    const parallel=await parallelSpectrum(samples,frames,report);
    if(parallel){spectrum=parallel.spectrum;mean=parallel.mean;}
  }catch(err){console.warn('parallel FFT fallback',err);}
  if(!spectrum){
    spectrum=new Float32Array(frames*BINS);mean=new Float64Array(BINS);
    const real=new Float32Array(SIZE),imag=new Float32Array(SIZE),windowed=new Float32Array(SIZE),mag=new Float32Array(BINS);
    const window=Float32Array.from({length:SIZE},(_,i)=>.5-.5*Math.cos(2*Math.PI*i/(SIZE-1)));
    for(let t=0;t<frames;t++){
      const center=t*HOP;
      for(let i=0;i<SIZE;i++)windowed[i]=(samples[center+i-SIZE/2]||0)*window[i];
      fftMagnitude(windowed,real,imag,mag);
      for(let j=0;j<BINS;j++){spectrum[t*BINS+j]=mag[j];mean[j]+=mag[j];}
      if(t%450===0){report('周波数を調べています…',10+36*t/frames);await wait();}
    }
  }
  const sampleTemplates=await fetch('templates-v2.json').then(r=>{if(!r.ok)throw Error('参照サンプルを読み込めません');return r.json();});
  const band=new Array(4).fill(0).map(()=>new Float32Array(frames));
  const sim=new Array(TEMPLATE_GROUPS.length).fill(0).map(()=>new Float32Array(frames));
  const white=new Float32Array(BINS),vectors=new Array(TEMPLATE_GROUPS.length).fill(0).map(()=>new Float32Array(BINS));
  const avg=Array.from(mean,x=>x/frames),floor=Array.from(avg).sort((a,b)=>a-b)[Math.floor(BINS*.35)]||.001;
  for(let j=0;j<BINS;j++)white[j]=Math.pow(Math.max(avg[j],floor,.001),.6);
  for(let k=0;k<TEMPLATE_GROUPS.length;k++){
    let norm=0;for(let j=0;j<BINS;j++){const x=sampleTemplates.spectra[k][j]/white[j];vectors[k][j]=x;norm+=x*x;}
    norm=Math.sqrt(norm)+1e-8;for(let j=0;j<BINS;j++)vectors[k][j]/=norm;
  }
  const bandOf=new Int8Array(BINS);
  for(let j=0;j<BINS;j++){const hz=j*RATE/SIZE;bandOf[j]=hz<EDGES[0]?-1:hz<EDGES[1]?0:hz<EDGES[2]?1:hz<EDGES[3]?2:hz<EDGES[4]?3:-1;}
  const rise=new Float32Array(BINS);
  for(let t=0;t<frames;t++){
    let norm=0;const base=t*BINS,prev=Math.max(0,t-2)*BINS;
    for(let j=0;j<BINS;j++){
      const x=Math.max(0,spectrum[base+j]-(t>=2?spectrum[prev+j]:0));rise[j]=x/white[j];norm+=rise[j]*rise[j];
      if(bandOf[j]>=0)band[bandOf[j]][t]+=x;
    }
    norm=Math.sqrt(norm)+1e-8;
    // Only two similarity gates survive the experiment: tom and cymbal.
    for(let k=0;k<TEMPLATE_GROUPS.length;k++){let dot=0;for(let j=0;j<BINS;j++)dot+=vectors[k][j]*rise[j];sim[k][t]=dot/norm;}
    if(t%500===0){report('打点の候補を整理中…',48+29*t/frames);await wait();}
  }
  for(let b=0;b<4;b++){
    const flux=band[b];const clean=new Float32Array(frames);
    for(let t=0;t<frames;t++)clean[t]=Math.max(0,flux[t]-.6*localMedian(flux,t,50,5));
    const scale=percentile98(clean)+1e-7;
    for(let t=0;t<frames;t++)band[b][t]=clean[t]/scale;
  }
  report('ノートに変換中…',82);await wait();
  const manualBpm=Number(options?.bpm)||0;
  const signals=[band[0],band[1],band[3],band[1],band[2]];
  const raw=[],groupNames=['kick','snare','hat','tom','cymbal_raw'];
  for(let k=0;k<5;k++){
    const s=signals[k],peaks=[],minDistance=Math.floor(DISTANCES[k]*RATE/HOP);
    for(let t=2;t<frames-2;t++){
      if(s[t]<=s[t-1]||s[t]<s[t+1]||s[t]<THRESHOLDS[k])continue;
      if(s[t]-Math.min(s[t-2],s[t+2])<.07)continue;
      if(s[t]<2.4*localMedian(s,t,100,10))continue;
      if(k===0&&band[0][t]<.48*band[1][t])continue;
      if(k===1&&band[1][t]<.62*band[0][t])continue;
      if(k===3&&(sim[3][t]<.44||sim[3][t]<.85*Math.max(sim[0][t],sim[1][t])))continue;
      if(k===4&&Math.max(sim[TEMPLATE_INDEX.crash][t],sim[TEMPLATE_INDEX.ride][t])<.39)continue;
      peaks.push(t);
    }
    peaks.sort((a,b)=>s[b]-s[a]);const kept=[];
    for(const p of peaks)if(!kept.some(q=>Math.abs(q-p)<minDistance))kept.push(p);
    for(const p of kept){
      let confidence=s[p]/THRESHOLDS[k];
      if(k===0||k===1)confidence+=.45*sim[k][p];
      if(k===3)confidence+=.6*sim[3][p];
      if(k===4)confidence+=.7*Math.max(sim[TEMPLATE_INDEX.crash][p],sim[TEMPLATE_INDEX.ride][p]);
      raw.push({time:p*HOP/RATE,frame:p,group:groupNames[k],score:s[p],confidence});
    }
    report('ノートに変換中…',82+10*(k+1)/5);await wait();
  }

  // Kick and snare used to be independent detectors, so the same bass-drum
  // onset could become both notes. Resolve competing events before export.
  const alive=new Set(raw.map((_,i)=>i));
  const kicks=raw.map((e,i)=>[e,i]).filter(([e])=>e.group==='kick');
  const snares=raw.map((e,i)=>[e,i]).filter(([e])=>e.group==='snare');
  const usedSnare=new Set();
  for(const [k,ki] of kicks){
    const near=snares.filter(([s,si])=>!usedSnare.has(si)&&Math.abs(s.time-k.time)<=.04);
    if(!near.length)continue;
    near.sort((a,b)=>Math.abs(a[0].time-k.time)-Math.abs(b[0].time-k.time));
    const [s,si]=near[0];usedSnare.add(si);
    const p=k.frame,b0=band[0][p],b1=band[1][p],kr=b0/(b1+1e-7),sr=b1/(b0+1e-7);
    const sk=sim[0][p],ss=sim[1][p];
    const layered=sk>=.52&&ss>=.56&&kr>=.72&&kr<=1.38;
    if(layered)continue;
    const snareStrong=(sr>=1.55&&ss>=.42)||(ss>=sk+.18&&sr>=1.15);
    if(snareStrong)alive.delete(ki);else alive.delete(si);
  }

  const base=raw.filter((_,i)=>alive.has(i));
  let tempoInfo;
  if(manualBpm>=30&&manualBpm<=300){
    tempoInfo={bpm:manualBpm,coarseBpm:manualBpm,spectralBpm:manualBpm,phaseSec:0,confidence:1,source:'manual'};
  }else{
    const initial=estimateTempoFromBands(band);
    const eventFamily=estimateEventTempoFamily(base);
    const familyGap=eventFamily.bpm?Math.abs(initial.bpm/eventFamily.bpm-1):0;
    if(initial.confidence<.10&&eventFamily.bpm&&familyGap>.08){
      const corrected=refineTempoAround(band,eventFamily.bpm);
      tempoInfo={...corrected,source:'audio-event-corrected',initialBpm:initial.bpm,initialConfidence:initial.confidence,eventFamily};
    }else{
      tempoInfo={...initial,source:'audio',eventFamily};
    }
  }
  const bpm=tempoInfo.bpm;
  const beatInfo=estimateBeatPhase(base,bpm);
  const barInfo=estimateHybridBarPhase(base,sim,bpm,beatInfo.phaseSec,band);
  const cym=base.filter(e=>e.group==='cymbal_raw');
  let structural=base.filter(e=>e.group!=='cymbal_raw');
  let adtofCymbal=[];
  let adtofSnareRescue=[];
  let adtofInfo={enabled:false,fallback:true};
  try{
    const ad=await transcribeAdtof(decoded,(message,p)=>{
      const mapped=92+Math.max(0,Math.min(1,(p-58)/42))*6;
      report(message,mapped);
    },{thresholdScale:1.15});
    const replacement=ad.events.filter(e=>e.group!=='cymbal');
    adtofCymbal=ad.events.filter(e=>e.group==='cymbal');
    adtofSnareRescue=ad.snareRescue||[];
    if(replacement.length){
      structural=replacement;
      adtofInfo={
        enabled:true,fallback:false,
        thresholdScale:ad.thresholdScale,
        snareRescueScale:ad.snareRescueScale,
        snareRescueCandidates:adtofSnareRescue.length,
        backend:ad.backend,
        frames:ad.frames,
        coreFrames:ad.coreFrames,
        overlapFrames:ad.overlapFrames,
        counts:Object.fromEntries(['kick','snare','tom','hat','cymbal'].map(g=>[g,ad.events.filter(e=>e.group===g).length]))
      };
    }
  }catch(err){
    console.warn('ADTOF fallback',err);
    adtofInfo={enabled:false,fallback:true,error:String(err?.message||err)};
  }
  // Structural-priority post-processing. Kick/snare/tom matter more than
  // metal classes, so only use narrowly targeted corrections that preserve
  // the high-precision ADTOF baseline.
  if(adtofInfo.enabled){
    const nearEvent=(events,t,w)=>events.find(e=>Math.abs(e.time-t)<=w);
    const kickEvents=structural.filter(e=>e.group==='kick');
    const snareEvents=structural.filter(e=>e.group==='snare');
    const beat=60/bpm,bar=4*beat,phase=barInfo.phaseSec;
    const wrapBar=t=>{let x=(t-phase)%bar;if(x<0)x+=bar;return x;};
    const slot16=t=>Math.round(wrapBar(t)/(beat/4))%16;
    const barIndex=t=>Math.floor((t-phase)/bar);
    const rescueDensity=adtofSnareRescue.length/Math.max(1,snareEvents.length);
    const snareKickDensity=snareEvents.length/Math.max(1,kickEvents.length);
    const adaptiveSnareRescue=rescueDensity>=1.24&&snareKickDensity<=.30;
    const lowSnare=adaptiveSnareRescue
      ? adtofSnareRescue.filter(e=>!nearEvent(snareEvents,e.time,.035)&&nearEvent(kickEvents,e.time,.040))
      : [];
    const patternTimes=adtofSnareRescue.map(e=>e.time);
    const repeatedAtSlot=t=>{
      const s=slot16(t),b=barIndex(t);let n=0;
      for(const x of patternTimes){
        if(Math.abs(x-t)<=.035)continue;
        if(Math.abs(barIndex(x)-b)>8)continue;
        if(slot16(x)===s)n++;
      }
      return n;
    };
    const rescued=[];
    for(const e of lowSnare){
      const k=nearEvent(kickEvents,e.time,.035);
      if(!k)continue;
      const repeat=repeatedAtSlot(e.time);
      if(e.score<.12||e.score<.25*(k.score||0)||repeat<2)continue;
      rescued.push({...e,group:'snare',confidence:e.confidence,rescuedSnare:true,repeatSupport:repeat});
    }
    if(rescued.length)structural.push(...rescued);

    // The current five-song set contains kick/tom bleed false positives.
    // GMD shows kick+tom is not globally rare, so keep this veto deliberately
    // narrow: only weak, isolated toms colliding with a kick are suppressed.
    const toms=structural.filter(e=>e.group==='tom');
    let tomKickRemoved=0;
    structural=structural.filter(e=>{
      if(e.group!=='tom')return true;
      const k=nearEvent(kickEvents,e.time,.030);
      if(!k)return true;
      const inRun=toms.some(x=>x!==e&&Math.abs(x.time-e.time)>=.045&&Math.abs(x.time-e.time)<=.24);
      if(inRun||(e.confidence||0)>=1.45)return true;
      tomKickRemoved++;return false;
    });
    adtofInfo.structuralPriority={
      mode:'layered-snare-rescue+kick-tom-veto-v1',
      snareRescueCandidates:adtofSnareRescue.length,
      rescueDensity,
      snareKickDensity,
      adaptiveSnareRescue,
      snareLayeredCandidates:lowSnare.length,
      snareRescued:rescued.length,
      snareMinActivation:.12,
      snareKickRatio:.25,
      snareRepeatBars:2,
      tomKickRemoved,
      tomStrongKeep:1.45,
      tomRunWindowSec:.24
    };
  }

  // Fixed hi-hat overtrigger suppressor selected by the current
  // audio-only browser search. It only removes weak hats colliding with
  // kick/snare unless a strong repeating hat pattern supports the event.
  if(adtofInfo.enabled){
    const hats=structural.filter(e=>e.group==='hat');
    const hatTimes=hats.map(e=>e.time).sort((a,b)=>a-b);
    const bodyTimes=structural.filter(e=>e.group==='kick'||e.group==='snare').map(e=>e.time).sort((a,b)=>a-b);
    const beat=60/bpm;
    const nearTime=(xs,t,w)=>xs.some(x=>Math.abs(x-t)<=w);
    const repSupport=t=>{
      let best=0;
      for(const step of [beat/4,beat/2,beat]){
        let n=0;
        for(const k of [-2,-1,1,2]){
          const target=t+k*step;
          if(hatTimes.some(x=>Math.abs(x-target)<=.045))n++;
        }
        best=Math.max(best,n);
      }
      return best;
    };
    let removed=0;
    structural=structural.filter(e=>{
      if(e.group!=='hat')return true;
      const fr=Math.max(0,Math.min(frames-1,Math.round(e.time*RATE/HOP)));
      const hs=sim[TEMPLATE_INDEX.hat][fr]||0;
      const body=Math.max(sim[TEMPLATE_INDEX.kick][fr]||0,sim[TEMPLATE_INDEX.snare][fr]||0);
      const rep=repSupport(e.time);
      if(hs<.20&&rep<2){removed++;return false;}
      if(nearTime(bodyTimes,e.time,.025)&&hs<.70*Math.max(.03,body)&&rep<4){removed++;return false;}
      return true;
    });
    adtofInfo.hatFilter={mode:'collision-periodic-v2',removed,absMin:.20,collisionRatio:.70,collisionWindowSec:.025,periodicRescue:4,weakRescue:2};

    // GMD train-split symbolic prior + audio decay pedal-hat decoder.
    // Fixed policy selected by the chart-scoring-only benchmark:
    // prior_w=1.5, tail2_w=.35, tail3_w=.35, near8_w=-.25, threshold=.4.
    // No DruMaster chart is read here.
    try{
      const gmd=await fetch('models/gmd-metal-prior.json').then(r=>{if(!r.ok)throw Error('GMD priorを読み込めません');return r.json();});
      const beat=60/bpm,bar=4*beat,phase=barInfo.phaseSec;
      const hatEvents=structural.filter(e=>e.group==='hat');
      const hatTimes=hatEvents.map(e=>e.time).sort((a,b)=>a-b);
      const kicks=structural.filter(e=>e.group==='kick').map(e=>e.time).sort((a,b)=>a-b);
      const snares=structural.filter(e=>e.group==='snare').map(e=>e.time).sort((a,b)=>a-b);
      const toms=structural.filter(e=>e.group==='tom').map(e=>e.time).sort((a,b)=>a-b);
      const near=(xs,t,w)=>xs.some(v=>Math.abs(v-t)<=w);
      const high=new Float64Array(frames);
      const j0=Math.max(0,Math.ceil(1800*SIZE/RATE)),j1=Math.min(BINS,Math.floor(5400*SIZE/RATE)+1);
      for(let t=0;t<frames;t++){
        let sum=0,base=t*BINS;
        for(let j=j0;j<j1;j++)sum+=spectrum[base+j];
        high[t]=sum;
      }
      const meanRange=(arr,a,b)=>{
        const aa=Math.max(0,a),bb=Math.min(arr.length,b);
        if(bb<=aa)return 0;
        let sum=0;for(let i=aa;i<bb;i++)sum+=arr[i];
        return sum/(bb-aa);
      };
      const maxRange=(arr,a,b)=>{
        const aa=Math.max(0,a),bb=Math.min(arr.length,b);
        let m=0;for(let i=aa;i<bb;i++)if(arr[i]>m)m=arr[i];
        return m;
      };
      let converted=0;
      structural=structural.map(e=>{
        if(e.group!=='hat')return e;
        const t=e.time,fr=Math.max(0,Math.min(frames-1,Math.round(t*RATE/HOP)));
        let x=(t-phase)%bar;if(x<0)x+=bar;
        const slot=Math.round(x/(beat/4))%16;
        const ctx=[];
        if(near(kicks,t,.045))ctx.push('kick');
        if(near(snares,t,.045))ctx.push('snare');
        if(near(toms,t,.045))ctx.push('tom');
        const ctxKey=ctx.length?ctx.join('+'):'none';
        const prior=(gmd.context?.[slot+'|'+ctxKey]||gmd.slot16?.[String(slot)]||gmd.globalProb||{});
        const ph=Math.max(1e-6,Number(prior.hat)||1e-6);
        const pp=Math.max(1e-6,Number(prior.pedal_hat)||1e-6);
        const pre=meanRange(high,fr-12,fr-3);
        const on=maxRange(high,fr-1,fr+3);
        const amp=Math.max(on-pre,1e-7);
        const tail2=Math.max(0,meanRange(high,fr+11,fr+21)-pre)/amp;
        const tail3=Math.max(0,meanRange(high,fr+21,fr+36)-pre)/amp;
        const others=hatTimes.filter(v=>Math.abs(v-t)>.035);
        const near8=near(others,t-beat/2,.055)||near(others,t+beat/2,.055);
        const score=1.5*Math.log(pp/ph)-.35*Math.min(tail2,3)-.35*Math.min(tail3,3)-.25*(near8?1:0);
        if(score>=.4){converted++;return {...e,group:'pedal_hat',pedalScore:score};}
        return e;
      });
      adtofInfo.pedalPolicy={
        mode:'gmd-symbolic-decay-v1',
        converted,
        priorWeight:1.5,
        tail2Weight:.35,
        tail3Weight:.35,
        near8Weight:-.25,
        threshold:.4
      };
    }catch(err){
      console.warn('GMD pedal prior fallback',err);
      adtofInfo.pedalPolicy={mode:'disabled',error:String(err?.message||err)};
    }
  }
  const phase=barInfo.phaseSec;
  function measureHeadDistanceBeats(t){
    if(!(bpm>=30&&bpm<=300))return Infinity;
    const beat=60/bpm,bar=beat*4;
    let x=(t-phase)%bar;if(x<0)x+=bar;
    return Math.min(x,bar-x)/beat;
  }
  // Raw spectral cymbals are retained only as class evidence. They are no
  // longer emitted directly: this removes the over-ringing failure mode.
  const cymTimes=cym.map(e=>e.time);
  function periodicSupportTimes(times,t){
    if(!(bpm>=30&&bpm<=300)||times.length<3)return 0;
    let best=0;
    for(const step of [30/bpm,60/bpm,120/bpm]){
      let count=0;
      for(const k of [-2,-1,1,2]){
        const target=t+k*step;
        if(times.some(x=>Math.abs(x-target)<=.07))count++;
      }
      best=Math.max(best,count/4);
    }
    return best;
  }
  const rawCrashEvidence=[],rawRideEvidence=[];
  for(const e of cym){
    const headDistance=measureHeadDistanceBeats(e.time);
    const per=periodicSupportTimes(cymTimes,e.time);
    const crash=headDistance<=.14;
    const ride=per>=.75&&band[3][e.frame]>=.55*band[2][e.frame];
    if(crash&&(!ride||headDistance<=.055))rawCrashEvidence.push(e.time);
    else if(ride)rawRideEvidence.push(e.time);
  }

  const final=[...structural];
  if(adtofInfo.enabled&&adtofCymbal.length){
    const adTimes=adtofCymbal.map(e=>e.time);
    const selected=[];
    for(const e of adtofCymbal){
      const headDistance=measureHeadDistanceBeats(e.time);
      const per=periodicSupportTimes(adTimes,e.time);
      const crashSupport=rawCrashEvidence.some(t=>Math.abs(t-e.time)<=.07);
      const rideSupport=rawRideEvidence.some(t=>Math.abs(t-e.time)<=.07);
      let group=null;
      // Winner of the corrected audio-time search:
      // head <= .30 beat => crash; otherwise require complete periodic
      // support or independent ride evidence; residual raw crash evidence may
      // rescue a crash. Raw candidates never emit by themselves.
      if(headDistance<=.30)group='crash';
      else if(per>=1.0||rideSupport)group='ride';
      else if(crashSupport)group='crash';
      if(group)selected.push({...e,group,confidence:e.confidence*(1+(group==='crash'?.35:.25)*Math.max(per,headDistance<=.30?1:0))});
    }
    selected.sort((a,b)=>a.time-b.time);
    const ded=[];
    for(const e of selected){
      const prev=ded[ded.length-1];
      if(prev&&e.time-prev.time<.05){
        if(e.group==='crash'&&prev.group==='ride')ded[ded.length-1]=e;
        continue;
      }
      ded.push(e);
    }
    final.push(...ded);
    adtofInfo.cymbalPolicy={
      mode:'adtof-barhead-periodic',
      broad:adtofCymbal.length,
      emitted:ded.length,
      crash:ded.filter(e=>e.group==='crash').length,
      ride:ded.filter(e=>e.group==='ride').length,
      rawCrashEvidence:rawCrashEvidence.length,
      rawRideEvidence:rawRideEvidence.length
    };
  }else{
    // Fallback preserves the previous browser behavior only when ADTOF could
    // not run, so the app remains usable on unsupported browsers.
    for(let i=0;i<cym.length;i++){
      const e=cym[i],headDistance=measureHeadDistanceBeats(e.time);
      const per=periodicSupportTimes(cymTimes,e.time);
      const crash=headDistance<=.14;
      const ride=per>=.75&&band[3][e.frame]>=.55*band[2][e.frame];
      if(crash&&(!ride||headDistance<=.055))final.push({...e,group:'crash'});
      else if(ride)final.push({...e,group:'ride'});
    }
  }

  // A drummer has two hands: among snare/tom/hat/crash/ride, keep at most
  // two near-simultaneous hits. Kick is foot-operated and exempt. A future
  // pedal_hat class is also intended to be exempt.
  const limited=new Set(['snare','hat','tom','crash','ride']);
  const ordered=final.slice().sort((a,b)=>a.time-b.time);
  let pruned=[];
  for(let i=0;i<ordered.length;){
    const start=ordered[i].time,cluster=[];let j=i;
    while(j<ordered.length&&ordered[j].time-start<=.035)cluster.push(ordered[j++]);
    const exempt=cluster.filter(e=>!limited.has(e.group));
    const limb=cluster.filter(e=>limited.has(e.group)).sort((a,b)=>(b.confidence||b.score)-(a.confidence||a.score));
    pruned.push(...exempt,...limb.slice(0,2));
    i=j;
  }

  // Cycles 225-227: fixed-threshold 44.1 kHz ExtraTrees suppressor.
  // Apply after cymbal/pedal classification and the initial two-hand pass,
  // because the model was trained on the final browser event context. It only
  // removes hats, so it cannot create a new hand-polyphony violation.
  const highHat=await filterHighResHats(decoded,pruned,bpm,barInfo.phaseSec,(message,p)=>report(message,p));
  pruned=highHat.events;
  adtofInfo.hatHighRes=highHat.info;

  const noteOf={kick:36,snare:38,hat:42,pedal_hat:44,tom:45,crash:49,ride:51};
  const events=pruned.filter(e=>noteOf[e.group]).map(e=>({
    time:e.time,note:noteOf[e.group],group:e.group,
    velocity:Math.max(40,Math.min(120,Math.round(80+15*Math.log1p(e.score))))
  }));
  report('完了しました',100);
  return {
    events:events.sort((a,b)=>a.time-b.time||a.note-b.note),
    bpm,
    tempoInfo,
    beatPhaseSec:beatInfo.phaseSec,
    beatPhaseScore:beatInfo.score,
    barPhaseSec:barInfo.phaseSec,
    barPhaseInfo:barInfo,
    adtofInfo,
    numerator:4,
    denominator:4
  };
}
