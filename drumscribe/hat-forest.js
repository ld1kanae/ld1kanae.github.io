// High-resolution hi-hat false-positive suppressor selected by Cycles 225-227.
// The model is trained offline; inference uses audio + predicted-event context only.
// No reference MIDI or song identity is consulted here.

const SR=44100,NFFT=2048,BINS=NFFT/2+1,PRE_SAMPLES=Math.trunc(.025*SR);
const GROUPS=['kick','snare','hat','pedal_hat','tom','crash','ride','other'];
const BANDS=[[30,180],[180,800],[800,2500],[2500,5000],[5000,10000],[10000,18000],[18000,22000]];
const WINDOW=Float32Array.from({length:NFFT},(_,i)=>.5-.5*Math.cos(2*Math.PI*i/(NFFT-1)));
const FREQ=Float64Array.from({length:BINS},(_,i)=>i*SR/NFFT);
const TWIDDLES=[];
for(let length=2;length<=NFFT;length*=2){
  const cos=new Float32Array(length/2),sin=new Float32Array(length/2);
  for(let k=0;k<length/2;k++){
    cos[k]=Math.cos(-2*Math.PI*k/length);
    sin[k]=Math.sin(-2*Math.PI*k/length);
  }
  TWIDDLES.push([length,cos,sin]);
}
let modelPromise=null;
const monoCache=new WeakMap();

const tick=()=>new Promise(resolve=>setTimeout(resolve,0));

async function loadModel(){
  if(!modelPromise){
    modelPromise=fetch(new URL('./models/hat-extra-trees-v11.json',import.meta.url))
      .then(r=>{if(!r.ok)throw Error('44.1kHzハイハット分類モデルを読み込めません');return r.json();});
  }
  return modelPromise;
}

export async function monoAt44100(decoded){
  if(monoCache.has(decoded))return monoCache.get(decoded);
  const promise=(async()=>{
    try{
      const offline=new OfflineAudioContext(1,Math.ceil(decoded.duration*SR),SR);
      const source=offline.createBufferSource();source.buffer=decoded;
      source.connect(offline.destination);source.start();
      const rendered=await offline.startRendering();
      return new Float32Array(rendered.getChannelData(0));
    }catch{
      const a=decoded.getChannelData(0);
      const b=decoded.numberOfChannels>1?decoded.getChannelData(1):a;
      const out=new Float32Array(Math.ceil(decoded.duration*SR));
      const scale=decoded.sampleRate/SR;
      for(let i=0;i<out.length;i++){
        const p=i*scale,j=Math.min(a.length-2,Math.max(0,p|0)),f=p-j;
        out[i]=.5*((a[j]*(1-f)+a[j+1]*f)+(b[j]*(1-f)+b[j+1]*f));
      }
      return out;
    }
  })();
  monoCache.set(decoded,promise);
  return promise;
}

function fftMagnitude(input,real,imag,out){
  for(let i=0;i<NFFT;i++){real[i]=input[i];imag[i]=0;}
  for(let i=0,j=0;i<NFFT;i++){
    if(j>i){const tr=real[i];real[i]=real[j];real[j]=tr;const ti=imag[i];imag[i]=imag[j];imag[j]=ti;}
    let bit=NFFT>>1;while(j&bit){j^=bit;bit>>=1;}j^=bit;
  }
  for(const [length,cos,sin] of TWIDDLES){
    for(let start=0;start<NFFT;start+=length){
      for(let k=0;k<length/2;k++){
        const r=cos[k],s=sin[k],aa=start+k,bb=aa+length/2;
        const vr=real[bb]*r-imag[bb]*s,vi=real[bb]*s+imag[bb]*r;
        real[bb]=real[aa]-vr;imag[bb]=imag[aa]-vi;
        real[aa]+=vr;imag[aa]+=vi;
      }
    }
  }
  for(let i=0;i<BINS;i++)out[i]=Math.hypot(real[i],imag[i])+1e-9;
}

function lowerBound(xs,x){
  let lo=0,hi=xs.length;
  while(lo<hi){const m=(lo+hi)>>1;if(xs[m]<x)lo=m+1;else hi=m;}
  return lo;
}
function near(xs,t,w){
  const i=lowerBound(xs,t);
  return (i<xs.length&&Math.abs(xs[i]-t)<=w)||(i>0&&Math.abs(xs[i-1]-t)<=w);
}
function nearest(xs,t){
  if(!xs.length)return 9;
  const i=lowerBound(xs,t);let d=9;
  if(i<xs.length)d=Math.min(d,Math.abs(xs[i]-t));
  if(i>0)d=Math.min(d,Math.abs(xs[i-1]-t));
  return d;
}
function periodic(times,t,bpm){
  let best=0;
  for(const step of [30/bpm,60/bpm,120/bpm]){
    let n=0;
    for(const k of [-2,-1,1,2])if(near(times,t+k*step,.060))n++;
    best=Math.max(best,n/4);
  }
  return best;
}

function workspace(){
  return {
    cur:new Float32Array(NFFT),pre:new Float32Array(NFFT),
    real:new Float32Array(NFFT),imag:new Float32Array(NFFT),
    s:new Float32Array(BINS),p:new Float32Array(BINS)
  };
}
function windowed(samples,center,out){
  const lo=center-(NFFT>>1);
  for(let i=0;i<NFFT;i++)out[i]=(samples[lo+i]||0)*WINDOW[i];
}
function spectral(samples,t,w){
  const center=Math.round(t*SR);
  windowed(samples,center,w.cur);
  windowed(samples,center-PRE_SAMPLES,w.pre);
  fftMagnitude(w.cur,w.real,w.imag,w.s);
  fftMagnitude(w.pre,w.real,w.imag,w.p);

  let total=0,ptotal=0,centroidNumer=0,logSum=0,mean=0;
  for(let i=0;i<BINS;i++){
    const s=w.s[i],p=w.p[i];
    total+=s;ptotal+=p;centroidNumer+=FREQ[i]*s;logSum+=Math.log(s);mean+=s;
  }
  total+=1e-9;ptotal+=1e-9;mean/=BINS;
  const v=[];
  for(const [lo,hi] of BANDS){
    let se=0,pe=0;
    for(let i=0;i<BINS;i++)if(FREQ[i]>=lo&&FREQ[i]<hi){se+=w.s[i];pe+=w.p[i];}
    const e=se/total,prev=pe/ptotal;
    v.push(Math.log1p(100*e),Math.log1p(100*Math.max(0,e-prev)));
  }
  let sq=0,crest=0,zc=0;
  for(let i=0;i<NFFT;i++){
    const x=w.cur[i];sq+=x*x;crest=Math.max(crest,Math.abs(x));
    if(i&&((w.cur[i]<0)!==(w.cur[i-1]<0)))zc++;
  }
  const rms=Math.sqrt(sq/NFFT)+1e-9;
  const centroid=centroidNumer/total/22050;
  const flat=Math.exp(logSum/BINS)/(mean+1e-9);
  return v.concat([centroid,flat,Math.log1p(rms*1000),crest/(rms+1e-9)/10,zc/(NFFT-1)]);
}

function contexts(events){
  const by=Object.fromEntries(GROUPS.map(g=>[g,[]]));
  for(const e of events)if(by[e.group])by[e.group].push(e.time);
  for(const xs of Object.values(by))xs.sort((a,b)=>a-b);
  return by;
}
function feature(samples,t,hatIndex,by,bpm,phase,w){
  const beat=60/bpm,bar=4*beat,hats=by.hat;
  const prev=hatIndex>0?t-hats[hatIndex-1]:9;
  const next=hatIndex+1<hats.length?hats[hatIndex+1]-t:9;
  let xx=(t-phase)%bar;if(xx<0)xx+=bar;
  const slot=xx/bar*16,sloterr=Math.abs(slot-Math.round(slot)),head=Math.min(xx,bar-xx)/beat;
  return spectral(samples,t,w).concat([
    Math.min(nearest(by.kick,t),.25)/.25,
    Math.min(nearest(by.snare,t),.25)/.25,
    Math.min(nearest(by.crash,t),.25)/.25,
    Math.min(nearest(by.ride,t),.25)/.25,
    Math.min(nearest(by.pedal_hat,t),.25)/.25,
    near(by.kick,t,.025)?1:0,
    near(by.kick,t,.045)?1:0,
    near(by.kick,t,.070)?1:0,
    near(by.snare,t,.045)?1:0,
    Math.min(prev,.5)/.5,
    Math.min(next,.5)/.5,
    periodic(hats,t,bpm),
    Math.min(sloterr,.5)*2,
    Math.min(head,2)/2,
    Math.sin(2*Math.PI*slot/16),
    Math.cos(2*Math.PI*slot/16)
  ]);
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

export async function filterHighResHats(decoded,events,bpm,barPhaseSec,report=()=>{},options={}){
  const hats=events.filter(e=>e.group==='hat').slice().sort((a,b)=>a.time-b.time);
  const kicks=events.filter(e=>e.group==='kick');
  const ratio=hats.length/Math.max(1,kicks.length);
  const baseInfo={
    mode:'extra-trees-v11',sampleRate:SR,candidates:hats.length,kicks:kicks.length,
    hatKickRatio:ratio,enabled:false,removed:0
  };
  if(!hats.length||ratio<.55){
    return {events,info:{...baseInfo,skipReason:!hats.length?'no-hat':'low-density'}};
  }

  try{
    const model=await loadModel();
    if(Number(model.nFeatures)!==35)throw Error(`unexpected feature count ${model.nFeatures}`);
    const policy=model.policy||{};
    const thresholdMultiplier=Number.isFinite(Number(options.thresholdMultiplier))&&Number(options.thresholdMultiplier)>=0&&Number(options.thresholdMultiplier)<=2?Number(options.thresholdMultiplier):1;
    const probThreshold=Number(policy.probThreshold??.55)*thresholdMultiplier;
    const repeatRescue=Number(policy.repeatRescue??1);
    const intersectionWindow=Number(policy.intersectionWindowSec??.060);
    report('ハイハットを高域まで再確認中…',98.2);
    const samples=await monoAt44100(decoded);
    const by=contexts(events),w=workspace(),accepted=[];
    let probSum=0;
    for(let i=0;i<by.hat.length;i++){
      const t=by.hat[i],x=feature(samples,t,i,by,bpm,barPhaseSec,w);
      const p=predict(model,x);probSum+=p;
      if(p>=probThreshold||periodic(by.hat,t,bpm)>=repeatRescue)accepted.push(t);
      if(i%32===0){
        report('ハイハットを高域まで再確認中…',98.2+1.2*i/Math.max(1,by.hat.length));
        await tick();
      }
    }
    const filtered=events.filter(e=>e.group!=='hat'||near(accepted,e.time,intersectionWindow));
    const kept=filtered.filter(e=>e.group==='hat').length;
    return {events:filtered,info:{
      ...baseInfo,enabled:true,kept,removed:hats.length-kept,
      accepted:accepted.length,probThreshold,thresholdMultiplier,repeatRescue,intersectionWindow,
      modelTrees:model.trees.length,modelFeatures:model.nFeatures,
      meanProbability:by.hat.length?probSum/by.hat.length:0
    }};
  }catch(err){
    console.warn('high-resolution hat filter fallback',err);
    return {events,info:{...baseInfo,error:String(err?.message||err),skipReason:'error'}};
  }
}
