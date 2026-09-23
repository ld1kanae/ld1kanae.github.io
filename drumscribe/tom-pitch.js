// Audio-only second-stage tom pitch subdivision.
// Tom onset detection/class identity is intentionally untouched.
// The classifier only assigns one of four robust GM tom tiers: 41/45/47/50.

const SIZE=1024;
const SR=11025;
const BINS=513;
const WINDOW=Float32Array.from({length:SIZE},(_,i)=>.5-.5*Math.cos(2*Math.PI*i/(SIZE-1)));
const BITREV=new Uint16Array(SIZE);
for(let i=0;i<SIZE;i++){
  let x=i,r=0;
  for(let b=0;b<10;b++){r=(r<<1)|(x&1);x>>=1;}
  BITREV[i]=r;
}
const STAGES=[];
for(let length=2;length<=SIZE;length*=2){
  const half=length>>1,cos=new Float32Array(half),sin=new Float32Array(half);
  for(let k=0;k<half;k++){
    const a=-2*Math.PI*k/length;cos[k]=Math.cos(a);sin[k]=Math.sin(a);
  }
  STAGES.push({length,half,cos,sin});
}
function fftMagnitude(samples,start,out,real,imag,input){
  for(let i=0;i<SIZE;i++){
    const j=start+i;
    input[i]=(j>=0&&j<samples.length?samples[j]:0)*WINDOW[i];
  }
  for(let i=0;i<SIZE;i++){real[i]=input[BITREV[i]];imag[i]=0;}
  for(const st of STAGES){
    for(let base=0;base<SIZE;base+=st.length){
      for(let k=0;k<st.half;k++){
        const a=base+k,b=a+st.half,wr=st.cos[k],wi=st.sin[k];
        const vr=real[b]*wr-imag[b]*wi,vi=real[b]*wi+imag[b]*wr;
        const ar=real[a],ai=imag[a];
        real[a]=ar+vr;imag[a]=ai+vi;
        real[b]=ar-vr;imag[b]=ai-vi;
      }
    }
  }
  for(let i=0;i<BINS;i++)out[i]=Math.hypot(real[i],imag[i]);
}
function resonantPeak(samples,time){
  const sum=new Float64Array(BINS);
  const mag=new Float32Array(BINS),real=new Float32Array(SIZE),imag=new Float32Array(SIZE),input=new Float32Array(SIZE);
  const onset=Math.round(time*SR),base=onset+Math.round(.015*SR);
  for(const sec of [0,.018,.036,.054]){
    fftMagnitude(samples,base+Math.round(sec*SR),mag,real,imag,input);
    for(let j=0;j<BINS;j++)sum[j]+=mag[j];
  }
  const lo=Math.max(1,Math.ceil(55*SIZE/SR)),hi=Math.min(BINS-1,Math.floor(360*SIZE/SR));
  let best=lo;
  for(let j=lo+1;j<=hi;j++)if(sum[j]>sum[best])best=j;
  return best*SR/SIZE;
}
function segmentCost(prefix,prefix2,i,j){
  const n=j-i,s=prefix[j]-prefix[i],s2=prefix2[j]-prefix2[i];
  return s2-s*s/Math.max(1,n);
}
function optimal1d(values,k){
  const order=values.map((v,i)=>({v,i})).sort((a,b)=>a.v-b.v||a.i-b.i);
  const x=order.map(q=>q.v),n=x.length;
  const p=new Float64Array(n+1),p2=new Float64Array(n+1);
  for(let i=0;i<n;i++){p[i+1]=p[i]+x[i];p2[i+1]=p2[i]+x[i]*x[i];}
  const dp=Array.from({length:k+1},()=>new Float64Array(n+1).fill(Infinity));
  const prev=Array.from({length:k+1},()=>new Int32Array(n+1).fill(-1));
  dp[0][0]=0;
  for(let c=1;c<=k;c++){
    for(let j=c;j<=n;j++){
      for(let i=c-1;i<j;i++){
        const z=dp[c-1][i]+segmentCost(p,p2,i,j);
        if(z<dp[c][j]){dp[c][j]=z;prev[c][j]=i;}
      }
    }
  }
  const bounds=[];let j=n;
  for(let c=k;c>=1;c--){const i=prev[c][j];bounds.push([i,j]);j=i;}
  bounds.reverse();
  const labels=new Int32Array(n),centers=[];
  bounds.forEach(([a,b],c)=>{
    const mid=(a+b-1)/2;
    centers.push(x[Math.floor(mid)]*(1-(mid%1))+x[Math.ceil(mid)]*(mid%1));
    for(let z=a;z<b;z++)labels[z]=c;
  });
  const original=new Int32Array(n);
  order.forEach((q,sorted)=>{original[q.i]=labels[sorted];});
  return {labels:original,centers};
}
function silhouette(values,labels,k){
  const groups=Array.from({length:k},()=>[]);
  for(let i=0;i<values.length;i++)groups[labels[i]].push(i);
  let total=0;
  for(let i=0;i<values.length;i++){
    const g=labels[i],own=groups[g];
    if(own.length<=1)continue;
    let a=0;
    for(const j of own)if(j!==i)a+=Math.abs(values[i]-values[j]);
    a/=own.length-1;
    let b=Infinity;
    for(let h=0;h<k;h++){
      if(h===g||!groups[h].length)continue;
      let d=0;for(const j of groups[h])d+=Math.abs(values[i]-values[j]);
      d/=groups[h].length;if(d<b)b=d;
    }
    total+=(b-a)/Math.max(a,b,1e-9);
  }
  return total/values.length;
}
function absoluteFallback(hz){
  if(hz<110)return 41;
  if(hz<145)return 45;
  if(hz<190)return 47;
  return 50;
}
function mappedNotes(k){
  if(k===2)return [41,45];
  if(k===3)return [41,45,50];
  return [41,45,47,50];
}
export function assignTomPitches(samples,events){
  const toms=events.filter(e=>e.group==='tom');
  const info={enabled:true,method:'song-relative-resonance-cluster-v1',tomCount:toms.length,clusters:0,silhouette:0,counts:{41:0,45:0,47:0,50:0},decisions:[]};
  if(!toms.length)return {events,info};
  const hz=toms.map(e=>resonantPeak(samples,e.time));
  const logHz=hz.map(v=>Math.log(Math.max(40,v)));
  let chosen=null;
  if(toms.length>=4){
    const distinct=new Set(hz.map(v=>v.toFixed(5))).size;
    for(let k=2;k<=Math.min(4,distinct,toms.length-1);k++){
      const c=optimal1d(logHz,k),s=silhouette(logHz,c.labels,k);
      if(!chosen||s>chosen.silhouette)chosen={...c,k,silhouette:s};
    }
  }
  let notes,decisionClusters=new Array(toms.length).fill(null),clusterNoteByRank=null;
  if(!chosen||chosen.silhouette<.35){
    notes=hz.map(absoluteFallback);
    info.method='resonance-absolute-fallback-v1';
  }else{
    const order=chosen.centers.map((v,i)=>({v,i})).sort((a,b)=>a.v-b.v);
    const targets=mappedNotes(chosen.k),clusterNote={};
    order.forEach((q,rank)=>{clusterNote[q.i]=targets[rank];});
    notes=Array.from(chosen.labels,l=>clusterNote[l]);
    decisionClusters=Array.from(chosen.labels,l=>order.findIndex(q=>q.i===l));
    clusterNoteByRank=targets.slice();
    info.clusters=chosen.k;info.silhouette=chosen.silhouette;
    info.centersHz=order.map(q=>Math.exp(q.v));
    info.clusterNoteByRank=clusterNoteByRank;
  }
  for(let i=0;i<toms.length;i++){
    toms[i].tomNote=notes[i];
    toms[i].tomPitchHz=hz[i];
    info.counts[notes[i]]=(info.counts[notes[i]]||0)+1;
    info.decisions.push({time:Number(toms[i].time)||0,hz:Number(hz[i])||0,clusterRank:decisionClusters[i],note:notes[i]});
  }
  return {events,info};
}
