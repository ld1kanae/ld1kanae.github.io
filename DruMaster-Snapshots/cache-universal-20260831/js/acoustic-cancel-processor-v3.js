class DruMasterAcousticCanceller extends AudioWorkletProcessor {
  constructor(){
    super();
    this.taps=160;
    this.maxDelay=Math.round(sampleRate*0.28);
    let ringSize=1;while(ringSize<this.maxDelay+this.taps+512)ringSize<<=1;
    this.ring=new Float32Array(ringSize);this.mask=ringSize-1;this.w=new Float32Array(this.taps);
    this.write=0;this.delaySamples=Math.round(sampleRate*0.06);this.mu=.16;this.eps=1e-6;this.adapt=false;this.freezeSamples=0;
    this.noiseRms=.0005;this.padProtect=.01;this.gate=1;this.capture=null;
    this.metricFrames=0;this.rawPow=0;this.refPow=0;this.resPow=0;this.metricSamples=0;

    this.candidateMode='off';this.registrationMode=false;this.candidateNoise=.0005;
    this.candidateFast=0;this.candidateSlow=0;this.candidateArmed=true;this.residualAmbient=.0005;
    this.candidatePre=Math.max(48,Math.round(sampleRate*.010));
    this.candidateLength=Math.max(1536,Math.round(sampleRate*.095));
    this.registrationPre=Math.max(64,Math.round(sampleRate*.018));
    this.registrationLength=Math.max(1024,Math.round(sampleRate*.145));
    let preSize=1;while(preSize<Math.max(this.candidatePre,this.registrationPre)+256)preSize<<=1;
    this.preRing=new Float32Array(preSize);this.preMask=preSize-1;this.preWrite=0;
    this.candidates=[];this.registrationCandidate=null;this.registrationRefractory=0;
    this.port.onmessage=e=>this.onMessage(e.data||{});
  }
  onMessage(m){
    if(m.type==='setDelay')this.delaySamples=Math.max(0,Math.min(this.maxDelay,Math.round(m.samples||0)));
    else if(m.type==='setNoise'){this.noiseRms=Math.max(1e-6,+m.noiseRms||1e-6);this.padProtect=Math.max(this.noiseRms*4,+m.padProtect||.01)}
    else if(m.type==='adapt')this.adapt=!!m.enabled;
    else if(m.type==='resetFilter')this.w.fill(0);
    else if(m.type==='freeze')this.freezeSamples=Math.max(this.freezeSamples,Math.round(sampleRate*(+m.ms||0)/1000));
    else if(m.type==='beginCapture'){
      const seconds=+m.seconds||2.6,n=Math.max(1024,Math.min(Math.round(sampleRate*seconds),Math.round(sampleRate*10)));
      this.capture={mic:new Float32Array(n),ref:new Float32Array(n),at:0};
    }else if(m.type==='endCapture')this.finishCapture(true);
    else if(m.type==='candidateMode'){
      const next=(m.mode==='raw'||m.mode==='residual')?m.mode:'off';
      this.candidateMode=next;this.registrationMode=next==='raw'&&m.registration===true;
      this.candidateNoise=Math.max(1e-6,+m.noiseRms||this.noiseRms||1e-6);
      this.candidateFast=this.candidateSlow=0;this.candidateArmed=true;this.candidates=[];this.registrationCandidate=null;this.registrationRefractory=0;
      this.residualAmbient=this.candidateNoise;
    }
  }
  finishCapture(force=false){
    const c=this.capture;if(!c)return;if(!force&&c.at<c.mic.length)return;
    const used=Math.max(0,Math.min(c.at,c.mic.length));if(force&&used<512)return;
    this.capture=null;const mic=used===c.mic.length?c.mic:c.mic.slice(0,used),ref=used===c.ref.length?c.ref:c.ref.slice(0,used);
    this.port.postMessage({type:'capture',mic:mic.buffer,ref:ref.buffer,sampleRate,samples:used},[mic.buffer,ref.buffer]);
  }
  maybeFinishCapture(){this.finishCapture(false)}
  startCandidate(current){
    const buf=new Float32Array(this.candidateLength),pre=Math.min(this.candidatePre,buf.length-1);
    for(let j=0;j<pre;j++)buf[j]=this.preRing[(this.preWrite-pre+j)&this.preMask];
    buf[pre]=current;this.candidates.push({buf,at:pre+1,peak:Math.abs(current)});
  }
  emitCandidate(c){this.port.postMessage({type:'padCandidate',pcm:c.buf.buffer,peak:c.peak,sampleRate,mode:this.candidateMode},[c.buf.buffer])}
  feedRapidCandidate(sample,rawResidual=sample){
    if(this.candidates.length){
      const keep=[];for(const c of this.candidates){
        if(c.at<c.buf.length){c.buf[c.at++]=sample;c.peak=Math.max(c.peak,Math.abs(sample))}
        if(c.at>=c.buf.length)this.emitCandidate(c);else keep.push(c);
      }this.candidates=keep;
    }
    const a=Math.abs(sample),rawA=Math.abs(rawResidual),residual=this.candidateMode==='residual';
    if(residual){
      const ceiling=Math.max(this.candidateNoise*7,this.residualAmbient*3.5);
      if(rawA<ceiling)this.residualAmbient+=.0015*(rawA-this.residualAmbient);
      this.residualAmbient=Math.max(this.candidateNoise*.75,this.residualAmbient);
    }
    this.candidateFast+=.28*(a-this.candidateFast);this.candidateSlow+=.006*(a-this.candidateSlow);
    const floor=residual
      ?Math.max(.00028,this.candidateNoise*2.2,this.residualAmbient*2.8,this.padProtect*.38)
      :Math.max(.00010,this.candidateNoise*.42);
    const trigger=residual
      ?Math.max(floor*1.12,this.candidateSlow*2.05)
      :Math.max(floor,this.candidateSlow*1.42);
    const release=residual
      ?Math.max(floor*.50,this.candidateSlow*1.04)
      :Math.max(floor*.52,this.candidateSlow*1.06);
    if(!this.candidateArmed&&this.candidateFast<release)this.candidateArmed=true;
    if(this.candidateMode!=='off'&&this.candidateArmed&&this.candidateFast>trigger&&a>floor*(residual?1.05:.72)){
      this.startCandidate(sample);this.candidateArmed=false;
    }
  }
  startRegistrationCandidate(current){
    const buf=new Float32Array(this.registrationLength),pre=Math.min(this.registrationPre,buf.length-1);
    for(let j=0;j<pre;j++)buf[j]=this.preRing[(this.preWrite-pre+j)&this.preMask];
    buf[pre]=current;this.registrationCandidate={buf,at:pre+1,peak:Math.abs(current)};this.registrationRefractory=Math.round(sampleRate*.085);
  }
  feedRegistrationCandidate(sample){
    if(this.registrationRefractory>0)this.registrationRefractory--;
    if(this.registrationCandidate){
      const c=this.registrationCandidate;if(c.at<c.buf.length){c.buf[c.at++]=sample;c.peak=Math.max(c.peak,Math.abs(sample))}
      if(c.at>=c.buf.length){this.registrationCandidate=null;this.port.postMessage({type:'padCandidate',pcm:c.buf.buffer,peak:c.peak,sampleRate,mode:'raw'},[c.buf.buffer])}
      return;
    }
    const a=Math.abs(sample);this.candidateFast+=.22*(a-this.candidateFast);this.candidateSlow+=.008*(a-this.candidateSlow);
    const floor=Math.max(.00016,this.candidateNoise*.62),relative=Math.max(floor,this.candidateSlow*1.72);
    if(this.candidateMode!=='off'&&this.registrationRefractory<=0&&this.candidateFast>relative&&a>floor*.85)this.startRegistrationCandidate(sample);
  }
  feedCandidate(sample,rawResidual=sample){
    this.preRing[this.preWrite]=sample;this.preWrite=(this.preWrite+1)&this.preMask;
    if(this.registrationMode)this.feedRegistrationCandidate(sample);else this.feedRapidCandidate(sample,rawResidual);
  }
  process(inputs,outputs){
    const micIn=inputs[0]||[],refIn=inputs[1]||[],out=outputs[0]||[];if(!out[0])return true;
    const mic=micIn[0]||null,refL=refIn[0]||null,refR=refIn[1]||null,dst=out[0],n=dst.length;let rawPow=0,refPow=0,resPow=0;
    for(let i=0;i<n;i++){
      const d=mic?mic[i]||0:0,xl=refL?(refL[i]||0):0,xr=refR?(refR[i]||0):xl,x=refL?(refR?(xl+xr)*.5:xl):0;
      this.ring[this.write]=x;let y=0,norm=this.eps;const base=(this.write-this.delaySamples)&this.mask;
      for(let k=0;k<this.taps;k++){const xv=this.ring[(base-k)&this.mask];y+=this.w[k]*xv;norm+=xv*xv}
      const err=d-y,protectedTransient=Math.abs(err)>this.padProtect||Math.abs(d)>this.padProtect*1.35;
      if(this.adapt&&this.freezeSamples<=0&&!protectedTransient&&norm>this.eps*4){const step=this.mu*err/norm;for(let k=0;k<this.taps;k++)this.w[k]+=step*this.ring[(base-k)&this.mask]}
      if(this.freezeSamples>0)this.freezeSamples--;

      /* The recorded eight-second room-noise RMS is a real rejection floor here,
         not merely a fingerprint hint. Below it the classifier receives silence. */
      const level=Math.abs(err),lo=Math.max(.00006,this.noiseRms*1.45),hi=Math.max(lo*3.4,this.noiseRms*5.2);
      const target=level<=lo?0:level>=hi?1:(level-lo)/(hi-lo);
      const coeff=target<this.gate?.24:.11;
      this.gate+=coeff*(target-this.gate);
      let cleaned=err*this.gate;
      if(level<=lo*1.04)cleaned=0;
      dst[i]=cleaned;for(let c=1;c<out.length;c++)out[c][i]=cleaned;
      rawPow+=d*d;refPow+=x*x;resPow+=cleaned*cleaned;
      if(this.capture){const at=this.capture.at;if(at<this.capture.mic.length){this.capture.mic[at]=d;this.capture.ref[at]=x;this.capture.at=at+1}}
      this.feedCandidate(this.candidateMode==='raw'?d:cleaned,err);this.write=(this.write+1)&this.mask;
    }
    this.maybeFinishCapture();this.rawPow+=rawPow;this.refPow+=refPow;this.resPow+=resPow;this.metricSamples+=n;
    if(++this.metricFrames>=12){
      const count=Math.max(1,this.metricSamples),raw=Math.sqrt(this.rawPow/count),ref=Math.sqrt(this.refPow/count),res=Math.sqrt(this.resPow/count),erle=10*Math.log10((this.rawPow+1e-12)/(this.resPow+1e-12));
      this.port.postMessage({type:'metrics',rawRms:raw,refRms:ref,residualRms:res,erleDb:erle,delaySamples:this.delaySamples,ambientFloor:this.residualAmbient});
      this.metricFrames=0;this.rawPow=this.refPow=this.resPow=0;this.metricSamples=0;
    }
    return true;
  }
}
registerProcessor('drumaster-acoustic-canceller',DruMasterAcousticCanceller);
