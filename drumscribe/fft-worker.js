const SIZE=1024,HOP=110,BINS=513;
const window=Float32Array.from({length:SIZE},(_,i)=>.5-.5*Math.cos(2*Math.PI*i/(SIZE-1)));
const bitrev=new Uint16Array(SIZE);
for(let i=0;i<SIZE;i++){
  let x=i,r=0;
  for(let b=0;b<10;b++){r=(r<<1)|(x&1);x>>=1;}
  bitrev[i]=r;
}
const stages=[];
for(let length=2;length<=SIZE;length*=2){
  const half=length>>1,cos=new Float32Array(half),sin=new Float32Array(half);
  for(let k=0;k<half;k++){
    const a=-2*Math.PI*k/length;cos[k]=Math.cos(a);sin[k]=Math.sin(a);
  }
  stages.push({length,half,cos,sin});
}
function fftMagnitude(input,real,imag,out){
  for(let i=0;i<SIZE;i++){real[i]=input[bitrev[i]];imag[i]=0;}
  for(let si=0;si<stages.length;si++){
    const st=stages[si],length=st.length,half=st.half,cos=st.cos,sin=st.sin;
    for(let start=0;start<SIZE;start+=length){
      for(let k=0;k<half;k++){
        const a=start+k,b=a+half,r=cos[k],s=sin[k];
        const vr=real[b]*r-imag[b]*s,vi=real[b]*s+imag[b]*r;
        const ar=real[a],ai=imag[a];
        real[a]=ar+vr;imag[a]=ai+vi;real[b]=ar-vr;imag[b]=ai-vi;
      }
    }
  }
  for(let i=0;i<BINS;i++){const r=real[i],im=imag[i];out[i]=Math.sqrt(r*r+im*im);}
}
self.onmessage=e=>{
  const {samples,startFrame,endFrame,sampleStart}=e.data;
  const x=new Float32Array(samples),count=endFrame-startFrame;
  const spectrum=new Float32Array(count*BINS),mean=new Float64Array(BINS);
  const real=new Float32Array(SIZE),imag=new Float32Array(SIZE),input=new Float32Array(SIZE),mag=new Float32Array(BINS);
  for(let t=startFrame;t<endFrame;t++){
    const center=t*HOP,base=(t-startFrame)*BINS;
    for(let i=0;i<SIZE;i++){
      const gi=center+i-(SIZE>>1),li=gi-sampleStart;
      input[i]=(li>=0&&li<x.length?x[li]:0)*window[i];
    }
    fftMagnitude(input,real,imag,mag);
    for(let j=0;j<BINS;j++){const v=mag[j];spectrum[base+j]=v;mean[j]+=v;}
  }
  self.postMessage({startFrame,endFrame,spectrum:spectrum.buffer,mean:mean.buffer},[spectrum.buffer,mean.buffer]);
};
