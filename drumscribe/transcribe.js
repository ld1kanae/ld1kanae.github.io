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

export async function transcribe(decoded,report=()=>{}){
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
  const signals=[band[0],band[1],band[3],band[1],band[2]],events=[];
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
    // scipy.find_peaks(distance=...) keeps the strongest peak locally.
    peaks.sort((a,b)=>s[b]-s[a]);const kept=[];
    for(const p of peaks)if(!kept.some(q=>Math.abs(q-p)<minDistance))kept.push(p);
    for(const p of kept)events.push({time:p*HOP/RATE,note:NOTES[k],group:NAMES[k],velocity:Math.max(40,Math.min(120,Math.round(80+15*Math.log1p(s[p]))))});
    report('ノートに変換中…',82+16*(k+1)/5);await wait();
  }
  report('完了しました',100);
  return events.sort((a,b)=>a.time-b.time||a.note-b.note);
}
