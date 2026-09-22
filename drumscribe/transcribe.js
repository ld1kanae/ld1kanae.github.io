// Approximate six-component spectral masking, per-component onsets, then
// repeat-aware musical filtering. Reference MIDI is never loaded in the app.
const RATE=11025, SIZE=1024, HOP=110, BINS=513;
const NAMES=['kick','snare','hat','tom','cymbal'];
const NOTES=[36,38,42,45,49];
const THRESHOLDS=[.58,.70,.19,1.5,1.0];
const DISTANCES=[.075,.075,.055,.09,.12];
const EDGES=[35,140,900,3000,5500];
const wait=()=>new Promise(resolve=>setTimeout(resolve,0));
const sepBands=[[35,140],[140,900],[140,900],[3000,5500],[900,5500],[900,5500]];

async function separateAndDetect(spec,avg,reference,frames,report){
  const white=new Float32Array(BINS),basis=Array.from({length:6},()=>new Float32Array(BINS));
  const floor=Array.from(avg).sort((a,b)=>a-b)[Math.floor(BINS*.35)]||1e-3;
  for(let j=0;j<BINS;j++){
    white[j]=Math.pow(Math.max(avg[j],floor,1e-3),.35);
    for(let k=0;k<5;k++){
      const from=k===0?0:k===1?1:k===2?3:k===4?4:2;
      const sample=k===3?.62*reference.spectra[2][j]+.38*reference.spectra[4][j]:reference.spectra[from][j];
      basis[k][j]=sample/white[j];
    }
    basis[5][j]=avg[j]/white[j];
  }
  for(const row of basis){let norm=0;for(const x of row)norm+=x*x;norm=Math.sqrt(norm)||1;for(let j=0;j<BINS;j++)row[j]/=norm;}
  const gram=Array.from({length:6},(_,k)=>Array.from({length:6},(_,m)=>{
    let dot=0;for(let j=0;j<BINS;j++)dot+=basis[k][j]*basis[m][j];return dot;
  }));
  const stems=Array.from({length:6},()=>new Float32Array(frames)),history=Array.from({length:3},()=>new Float32Array(6*BINS));
  const projection=new Float32Array(6),activity=new Float32Array(6),mix=new Float32Array(6),bands=new Int8Array(6*BINS);
  for(let k=0;k<6;k++)for(let j=0;j<BINS;j++){
    const hz=j*RATE/SIZE;bands[k*BINS+j]=hz>=sepBands[k][0]&&hz<sepBands[k][1]?1:0;
  }
  for(let t=0;t<frames;t++){
    const base=t*BINS;
    projection.fill(0);
    for(let j=0;j<BINS;j++){
      const v=spec[base+j]/white[j];
      for(let k=0;k<6;k++)projection[k]+=basis[k][j]*v;
    }
    for(let k=0;k<6;k++)activity[k]=Math.max(projection[k],1e-7);
    for(let iter=0;iter<9;iter++){
      for(let k=0;k<6;k++){
        let denom=0;for(let m=0;m<6;m++)denom+=gram[k][m]*activity[m];
        mix[k]=activity[k]*Math.max(projection[k],1e-7)/Math.max(denom,1e-7);
      }
      activity.set(mix);
    }
    const current=history[t%3],previous=history[(t+1)%3];
    for(let j=0;j<BINS;j++){
      let total=0;for(let k=0;k<6;k++){mix[k]=basis[k][j]*activity[k];total+=mix[k];}
      for(let k=0;k<6;k++){
        const idx=k*BINS+j,part=spec[base+j]*mix[k]/Math.max(total,1e-7);
        if(t>=2&&bands[idx])stems[k][t]+=Math.max(0,part-previous[idx]);
        current[idx]=part;
      }
    }
    if(t%400===0){report('楽器群に分離中…',47+31*t/frames);await wait();}
  }
  for(const s of stems){
    const clean=new Float32Array(frames);
    for(let t=0;t<frames;t++)clean[t]=Math.max(0,s[t]-.6*localMedian(s,t,50,5));
    const scale=percentile98(clean)+1e-7;
    for(let t=0;t<frames;t++)s[t]=clean[t]/scale;
  }
  return stems;
}

function findCandidates(s,threshold,distance,group,note){
  const peaks=[],min=Math.floor(distance*RATE/HOP);
  for(let t=2;t<s.length-2;t++){
    if(s[t]<=s[t-1]||s[t]<s[t+1]||s[t]<=threshold)continue;
    if(s[t]-Math.min(s[t-2],s[t+2])<.09)continue;
    if(s[t]<2.3*localMedian(s,t,100,10))continue;
    peaks.push(t);
  }
  peaks.sort((a,b)=>s[b]-s[a]);const kept=[];
  for(const p of peaks)if(!kept.some(q=>Math.abs(q-p)<min))kept.push(p);
  return kept.map(p=>({time:p*HOP/RATE,note,group,strength:s[p],velocity:Math.max(40,Math.min(120,Math.round(80+15*Math.log1p(s[p]))))}));
}

function rhythmicFilter(events,stems,bpm){
  const envelope=stems[0].map((v,i)=>Math.max(v,stems[1][i]));
  let beat;
  if(bpm!=null){beat=Math.round(60/bpm*RATE/HOP);}
  else{
    let high=-1;for(let lag=Math.round(.27*RATE/HOP);lag<Math.round(.85*RATE/HOP);lag++){
      let correlation=0;for(let i=lag;i<envelope.length;i+=2)correlation+=envelope[i]*envelope[i-lag];
      if(correlation>high){high=correlation;beat=lag;}
    }
  }
  if(beat<20)return events;
  const step=beat/2,strong=events.filter(e=>(e.group==='kick'||e.group==='snare')&&e.strength>.65).map(e=>Math.round(e.time*RATE/HOP));
  if(!strong.length)return events;
  let phase=0,max=-1;
  for(let p=0;p<Math.round(step);p++){
    let vote=0;for(const x of strong){const distance=((x-p+step/2)%step+step)%step-step/2;vote+=Math.exp(-distance*distance/18);}
    if(vote>max){max=vote;phase=p;}
  }
  const cym=events.filter(e=>e.group==='cymbal').sort((a,b)=>a.time-b.time);
  const repeats=e=>{
    const at=e.time*RATE/HOP,bar=4*beat;
    return cym.some(other=>other!==e&&Math.abs(Math.abs(other.time*RATE/HOP-at)-bar)<6);
  };
  return events.filter(e=>{
    if(e.group!=='cymbal'||e.strength>=1.15)return true;
    const p=e.time*RATE/HOP,off=Math.abs(((p-phase+step/2)%step+step)%step-step/2);
    const fill=events.some(n=>n.group==='tom'&&Math.abs(n.time-e.time)<.45);
    return off<=7||repeats(e)||fill;
  });
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

export async function transcribe(decoded,report=()=>{},{referenceBpm=null}={}){
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
    if(t%500===0){report('周波数の特徴を計算中…',43+4*t/frames);await wait();}
  }
  for(let b=0;b<4;b++){
    const flux=band[b];const clean=new Float32Array(frames);
    for(let t=0;t<frames;t++)clean[t]=Math.max(0,flux[t]-.6*localMedian(flux,t,50,5));
    const scale=percentile98(clean)+1e-7;
    for(let t=0;t<frames;t++)band[b][t]=clean[t]/scale;
  }
  const separated=await separateAndDetect(spectrum,avg,sampleTemplates,frames,report);
  report('楽器群ごとの打点を推定中…',82);await wait();
  const signals=[band[0],band[1],band[3],band[1],band[2]],events=[];
  for(let k of [0,4]){
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
    for(const p of kept)events.push({time:p*HOP/RATE,note:NOTES[k],group:NAMES[k],strength:s[p],velocity:Math.max(40,Math.min(120,Math.round(80+15*Math.log1p(s[p]))))});
  }
  for(const [k,threshold,distance,group,note] of [[1,.65,.075,'snare',38],[2,2.1,.09,'tom',45],[3,.31,.055,'hat',42]]){
    events.push(...findCandidates(separated[k],threshold,distance,group,note));
  }
  // The residual class is uncertain: only unusually isolated, strong attacks
  // become a generic percussion note, rather than forcing them into a drum.
  for(const e of findCandidates(separated[5],2.4,.12,'other',60)){
    const p=Math.round(e.time*RATE/HOP);
    if(Math.max(...separated.slice(0,5).map(s=>s[p]))<.35*e.strength)events.push(e);
  }
  const refined=rhythmicFilter(events,separated,referenceBpm);
  // Articulation remains a tentative timbre decision: a sustained metallic
  // tail and room for it to ring can indicate an open hat; dense repeated
  // cymbal ticks are mapped to ride, isolated accents to crash.
  const hats=refined.filter(e=>e.group==='hat').sort((a,b)=>a.time-b.time);
  const cymbals=refined.filter(e=>e.group==='cymbal').sort((a,b)=>a.time-b.time);
  const metalEnergy=p=>{
    let energy=0;for(let j=279;j<BINS;j++)energy+=spectrum[Math.min(frames-1,p)*BINS+j];return energy;
  };
  for(let i=0;i<hats.length;i++){
    const e=hats[i],p=Math.round(e.time*RATE/HOP),next=hats[i+1]?.time??Infinity;
    if(next-e.time>.19&&metalEnergy(p+12)>.56*metalEnergy(p))e.note=46;
  }
  for(let i=0;i<cymbals.length;i++){
    const t=cymbals[i].time;
    const prev=cymbals[i-1]?.time??-Infinity,next=cymbals[i+1]?.time??Infinity;
    if(t-prev<.48&&next-t<.48)cymbals[i].note=51;
  }
  for(const e of refined.filter(n=>n.group==='tom')){
    const p=Math.round(e.time*RATE/HOP),base=p*BINS;let low=0,high=0;
    for(let j=14;j<83;j++){if(j<45)low+=spectrum[base+j];else high+=spectrum[base+j];}
    if(high>1.7*low)e.note=48;
  }
  report('完了しました',100);
  return refined.sort((a,b)=>a.time-b.time||a.note-b.note);
}
