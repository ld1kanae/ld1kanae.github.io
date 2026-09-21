// Browser port of experiments/evaluate.py's band-precision candidate detector.
// Reference MIDI is never read here. Times are measured from the audio file start.
const RATE=11025, SIZE=1024, HOP=110, BINS=513;
const NAMES=['kick','snare','hat','tom','cymbal'];
const NOTES=[36,38,42,45,49];
const THRESHOLDS=[.58,.70,.19,1.5,1.0];
const DISTANCES=[.075,.075,.055,.09,.12];
const EDGES=[35,140,900,3000,5500];
const wait=()=>new Promise(resolve=>setTimeout(resolve,0));

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
  const frames=Math.ceil(samples.length/HOP),spectrum=new Float32Array(frames*BINS),mean=new Float64Array(BINS);
  const real=new Float32Array(SIZE),imag=new Float32Array(SIZE),windowed=new Float32Array(SIZE),mag=new Float32Array(BINS);
  const window=Float32Array.from({length:SIZE},(_,i)=>.5-.5*Math.cos(2*Math.PI*i/(SIZE-1)));
  for(let t=0;t<frames;t++){
    const center=t*HOP;
    for(let i=0;i<SIZE;i++)windowed[i]=(samples[center+i-SIZE/2]||0)*window[i];
    fftMagnitude(windowed,real,imag,mag);
    for(let j=0;j<BINS;j++){spectrum[t*BINS+j]=mag[j];mean[j]+=mag[j];}
    if(t%450===0){report('周波数を調べています…',10+36*t/frames);await wait();}
  }
  const sampleTemplates=await fetch('templates.json').then(r=>{if(!r.ok)throw Error('参照サンプルを読み込めません');return r.json();});
  const band=new Array(4).fill(0).map(()=>new Float32Array(frames));
  const sim=new Array(5).fill(0).map(()=>new Float32Array(frames));
  const white=new Float32Array(BINS),vectors=new Array(5).fill(0).map(()=>new Float32Array(BINS));
  const avg=Array.from(mean,x=>x/frames),floor=Array.from(avg).sort((a,b)=>a-b)[Math.floor(BINS*.35)]||.001;
  for(let j=0;j<BINS;j++)white[j]=Math.pow(Math.max(avg[j],floor,.001),.6);
  for(let k=0;k<5;k++){
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
    for(let k of [0,1,3,4]){let dot=0;for(let j=0;j<BINS;j++)dot+=vectors[k][j]*rise[j];sim[k][t]=dot/norm;}
    if(t%500===0){report('打点の候補を整理中…',48+29*t/frames);await wait();}
  }
  for(let b=0;b<4;b++){
    const flux=band[b];const clean=new Float32Array(frames);
    for(let t=0;t<frames;t++)clean[t]=Math.max(0,flux[t]-.6*localMedian(flux,t,50,5));
    const scale=percentile98(clean)+1e-7;
    for(let t=0;t<frames;t++)band[b][t]=clean[t]/scale;
  }
  report('ノートに変換中…',82);await wait();
  const bpm=Number(options?.bpm)||0;
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
      if(k===4&&sim[4][t]<.39)continue;
      peaks.push(t);
    }
    peaks.sort((a,b)=>s[b]-s[a]);const kept=[];
    for(const p of peaks)if(!kept.some(q=>Math.abs(q-p)<minDistance))kept.push(p);
    for(const p of kept)raw.push({time:p*HOP/RATE,frame:p,group:groupNames[k],score:s[p]});
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
  const cym=base.filter(e=>e.group==='cymbal_raw');
  const structural=base.filter(e=>e.group!=='cymbal_raw');
  let phase=0;
  if(bpm>=30&&bpm<=300){
    const beat=60/bpm,bar=beat*4,sigma=Math.max(.035,beat*.11);
    let bestScore=-1;
    for(let i=0;i<96;i++){
      const ph=bar*i/96;let score=0;
      for(const e of base){
        const weight=e.group==='cymbal_raw'?3.2:(e.group==='kick'?1.8:(e.group==='snare'?0.8:0.1));
        const x=(e.time-ph)%bar,d0=Math.abs(x),d=Math.min(d0,bar-d0);
        score+=weight*e.score*Math.exp(-.5*(d/sigma)**2);
      }
      if(score>bestScore){bestScore=score;phase=ph;}
    }
  }
  function downbeatStrength(t){
    if(!(bpm>=30&&bpm<=300))return 0;
    const beat=60/bpm,bar=beat*4,sigma=Math.max(.04,beat*.13);
    let x=(t-phase)%bar;if(x<0)x+=bar;const d=Math.min(x,bar-x);
    return Math.exp(-.5*(d/sigma)**2);
  }
  const cymTimes=cym.map(e=>e.time);
  function periodicSupport(i){
    if(!(bpm>=30&&bpm<=300)||cymTimes.length<3)return 0;
    const t=cymTimes[i];let best=0;
    for(const step of [30/bpm,60/bpm,120/bpm]){
      let count=0;
      for(const k of [-2,-1,1,2]){
        const target=t+k*step;
        if(cymTimes.some(x=>Math.abs(x-target)<=.07))count++;
      }
      best=Math.max(best,count/4);
    }
    return best;
  }

  const final=[...structural];
  for(let i=0;i<cym.length;i++){
    const e=cym[i];
    if(bpm>=30&&bpm<=300){
      const db=downbeatStrength(e.time),per=periodicSupport(i);
      const crash=(db>=.42)||(e.score>=1.85&&db>=.10);
      const ride=per>=.75&&band[3][e.frame]>=.55*band[2][e.frame];
      if(crash&&(!ride||db>=.70))final.push({...e,group:'crash'});
      else if(ride)final.push({...e,group:'ride'});
    }else if(e.score>=1.25){
      final.push({...e,group:'crash'});
    }
  }

  const noteOf={kick:36,snare:38,hat:42,tom:45,crash:49,ride:51};
  const events=final.filter(e=>noteOf[e.group]).map(e=>({
    time:e.time,note:noteOf[e.group],group:e.group,
    velocity:Math.max(40,Math.min(120,Math.round(80+15*Math.log1p(e.score))))
  }));
  report('完了しました',100);
  return events.sort((a,b)=>a.time-b.time||a.note-b.note);
}
