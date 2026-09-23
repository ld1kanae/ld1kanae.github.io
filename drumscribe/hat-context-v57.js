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
    return {...e,group:'open_hat',hatContextProbability:p,hatContextRideRescue:true};
  });
  return {events:out,info:{...info,enabled:true,scored,changed}};
}
