const SIZE=2048,HOP=441,BINS=1024,FBINS=84;
const window=Float32Array.from({length:SIZE},(_,i)=>.5-.5*Math.cos(2*Math.PI*i/(SIZE-1)));
const bitrev=new Uint16Array(SIZE);
for(let i=0;i<SIZE;i++){
  let x=i,r=0;
  for(let b=0;b<11;b++){r=(r<<1)|(x&1);x>>=1;}
  bitrev[i]=r;
}
const stages=[];
for(let length=2;length<=SIZE;length*=2){
  const half=length>>1,cos=new Float32Array(half),sin=new Float32Array(half);
  for(let k=0;k<half;k++){
    const a=-2*Math.PI*k/length;
    cos[k]=Math.cos(a);sin[k]=Math.sin(a);
  }
  stages.push({length,half,cos,sin});
}
function fftMagnitude(input,real,imag,out){
  for(let i=0;i<SIZE;i++){real[i]=input[bitrev[i]];imag[i]=0;}
  for(const st of stages){
    const {length,half,cos,sin}=st;
    for(let start=0;start<SIZE;start+=length){
      for(let k=0;k<half;k++){
        const a=start+k,b=a+half,wr=cos[k],wi=sin[k];
        const br=real[b],bi=imag[b];
        const vr=br*wr-bi*wi,vi=br*wi+bi*wr;
        const ar=real[a],ai=imag[a];
        real[a]=ar+vr;imag[a]=ai+vi;
        real[b]=ar-vr;imag[b]=ai-vi;
      }
    }
  }
  for(let i=0;i<BINS;i++)out[i]=Math.hypot(real[i],imag[i]);
}
self.onmessage=e=>{
  const {samples,startFrame,endFrame,sampleStart,filterbank}=e.data;
  const x=new Float32Array(samples),fb=new Float32Array(filterbank);
  const count=endFrame-startFrame;
  const features=new Float32Array(count*FBINS);
  const real=new Float32Array(SIZE),imag=new Float32Array(SIZE);
  const input=new Float32Array(SIZE),mag=new Float32Array(BINS);
  for(let t=startFrame;t<endFrame;t++){
    const center=t*HOP,base=(t-startFrame)*FBINS;
    for(let i=0;i<SIZE;i++){
      const gi=center+i-(SIZE>>1),li=gi-sampleStart;
      input[i]=(li>=0&&li<x.length?x[li]:0)*window[i];
    }
    fftMagnitude(input,real,imag,mag);
    for(let f=0;f<FBINS;f++){
      let sum=0,off=f*BINS;
      for(let j=0;j<BINS;j++)sum+=fb[off+j]*mag[j];
      features[base+f]=Math.log10(1+sum);
    }
  }
  self.postMessage({startFrame,endFrame,features:features.buffer},[features.buffer]);
};
