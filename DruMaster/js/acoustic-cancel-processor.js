class DruMasterAcousticCanceller extends AudioWorkletProcessor {
  constructor(){
    super();
    this.taps=160;
    this.maxDelay=Math.round(sampleRate*0.28);
    let ringSize=1;
    while(ringSize<this.maxDelay+this.taps+512) ringSize<<=1;
    this.ring=new Float32Array(ringSize);
    this.mask=ringSize-1;
    this.w=new Float32Array(this.taps);
    this.write=0;
    this.delaySamples=Math.round(sampleRate*0.06);
    this.mu=.16;
    this.eps=1e-6;
    this.adapt=false;
    this.freezeSamples=0;
    this.noiseRms=0.0005;
    this.padProtect=0.01;
    this.gate=1;
    this.capture=null;
    this.metricFrames=0;
    this.rawPow=0;this.refPow=0;this.resPow=0;this.metricSamples=0;

    /* Candidate extraction is edge-triggered and candidates may overlap.
       There is deliberately no fixed refractory/dead-time after a hit. */
    this.candidateMode='off';
    this.candidateNoise=0.0005;
    this.candidateFast=0;
    this.candidateSlow=0;
    this.candidateArmed=true;
    this.candidatePre=Math.max(48,Math.round(sampleRate*.010));
    this.candidateLength=Math.max(1536,Math.round(sampleRate*.095));
    let preSize=1;while(preSize<this.candidatePre+256)preSize<<=1;
    this.preRing=new Float32Array(preSize);this.preMask=preSize-1;this.preWrite=0;
    this.candidates=[];

    this.port.onmessage=e=>this.onMessage(e.data||{});
  }
  onMessage(m){
    if(m.type==='setDelay') this.delaySamples=Math.max(0,Math.min(this.maxDelay,Math.round(m.samples||0)));
    else if(m.type==='setNoise') {this.noiseRms=Math.max(1e-6,+m.noiseRms||1e-6);this.padProtect=Math.max(this.noiseRms*4,+m.padProtect||0.01);}
    else if(m.type==='adapt') this.adapt=!!m.enabled;
    else if(m.type==='resetFilter') this.w.fill(0);
    else if(m.type==='freeze') this.freezeSamples=Math.max(this.freezeSamples,Math.round(sampleRate*(+m.ms||0)/1000));
    else if(m.type==='beginCapture'){
      const n=Math.max(1024,Math.min(Math.round(sampleRate*(+m.seconds||2.6)),Math.round(sampleRate*10)));
      this.capture={mic:new Float32Array(n),ref:new Float32Array(n),at:0};
    }else if(m.type==='endCapture'){
      this.finishCapture(true);
    }else if(m.type==='candidateMode'){
      this.candidateMode=(m.mode==='raw'||m.mode==='residual')?m.mode:'off';
      this.candidateNoise=Math.max(1e-6,+m.noiseRms||this.noiseRms||1e-6);
      this.candidateFast=this.candidateSlow=0;this.candidateArmed=true;this.candidates=[];
    }else if(m.type==='suppressCandidates'){
      /* Kept as a no-op for compatibility. Rapid rolls must never be blocked
         by a post-hit timer. Re-arming is based only on the signal release. */
    }
  }
  finishCapture(force=false){
    const c=this.capture;
    if(!c)return;
    if(!force&&c.at<c.mic.length)return;
    const used=Math.max(0,Math.min(c.at,c.mic.length));
    if(force&&used<512)return;
    this.capture=null;
    const mic=used===c.mic.length?c.mic:c.mic.slice(0,used);
    const ref=used===c.ref.length?c.ref:c.ref.slice(0,used);
    this.port.postMessage({type:'capture',mic:mic.buffer,ref:ref.buffer,sampleRate,samples:used},[mic.buffer,ref.buffer]);
  }
  maybeFinishCapture(){this.finishCapture(false)}
  startCandidate(current){
    const buf=new Float32Array(this.candidateLength),pre=Math.min(this.candidatePre,buf.length-1);
    for(let j=0;j<pre;j++)buf[j]=this.preRing[(this.preWrite-pre+j)&this.preMask];
    buf[pre]=current;
    this.candidates.push({buf,at:pre+1,peak:Math.abs(current)});
  }
  feedCandidate(sample){
    this.preRing[this.preWrite]=sample;this.preWrite=(this.preWrite+1)&this.preMask;

    if(this.candidates.length){
      const keep=[];
      for(const c of this.candidates){
        if(c.at<c.buf.length){c.buf[c.at++]=sample;c.peak=Math.max(c.peak,Math.abs(sample));}
        if(c.at>=c.buf.length){
          this.port.postMessage({type:'padCandidate',pcm:c.buf.buffer,peak:c.peak,sampleRate,mode:this.candidateMode},[c.buf.buffer]);
        }else keep.push(c);
      }
      this.candidates=keep;
    }

    const a=Math.abs(sample);
    this.candidateFast+=.28*(a-this.candidateFast);
    this.candidateSlow+=.006*(a-this.candidateSlow);
    const floor=Math.max(.00014,this.candidateNoise*.56);
    const trigger=Math.max(floor,this.candidateSlow*1.58);
    const release=Math.max(floor*.56,this.candidateSlow*1.10);

    if(!this.candidateArmed&&this.candidateFast<release)this.candidateArmed=true;
    if(this.candidateMode!=='off'&&this.candidateArmed&&this.candidateFast>trigger&&a>floor*.78){
      this.startCandidate(sample);
      this.candidateArmed=false;
    }
  }
  process(inputs,outputs){
    const micIn=inputs[0]||[],refIn=inputs[1]||[],out=outputs[0]||[];
    if(!out[0])return true;
    const mic=micIn[0]||null,refL=refIn[0]||null,refR=refIn[1]||null,dst=out[0],n=dst.length;
    let rawPow=0,refPow=0,resPow=0;
    for(let i=0;i<n;i++){
      const d=mic?mic[i]||0:0;
      const xl=refL?(refL[i]||0):0,xr=refR?(refR[i]||0):xl,x=refL?(refR?(xl+xr)*.5:xl):0;
      this.ring[this.write]=x;
      let y=0,norm=this.eps;
      const base=(this.write-this.delaySamples)&this.mask;
      for(let k=0;k<this.taps;k++){
        const xv=this.ring[(base-k)&this.mask];
        y+=this.w[k]*xv;
        norm+=xv*xv;
      }
      const err=d-y;
      const protectedTransient=Math.abs(err)>this.padProtect || Math.abs(d)>this.padProtect*1.35;
      if(this.adapt&&this.freezeSamples<=0&&!protectedTransient&&norm>this.eps*4){
        const step=this.mu*err/norm;
        for(let k=0;k<this.taps;k++)this.w[k]+=step*this.ring[(base-k)&this.mask];
      }
      if(this.freezeSamples>0)this.freezeSamples--;
      const level=Math.abs(err),lo=this.noiseRms*1.15,hi=this.noiseRms*4.5;
      const target=level<=lo?.08:level>=hi?1:.08+.92*(level-lo)/(hi-lo);
      const coeff=target<this.gate?.18:.055;
      this.gate+=coeff*(target-this.gate);
      const cleaned=err*this.gate;
      dst[i]=cleaned;
      for(let c=1;c<out.length;c++)out[c][i]=cleaned;
      rawPow+=d*d;refPow+=x*x;resPow+=cleaned*cleaned;
      if(this.capture){
        const at=this.capture.at;
        if(at<this.capture.mic.length){this.capture.mic[at]=d;this.capture.ref[at]=x;this.capture.at=at+1;}
      }
      this.feedCandidate(this.candidateMode==='raw'?d:cleaned);
      this.write=(this.write+1)&this.mask;
    }
    this.maybeFinishCapture();
    this.rawPow+=rawPow;this.refPow+=refPow;this.resPow+=resPow;this.metricSamples+=n;
    if(++this.metricFrames>=12){
      const count=Math.max(1,this.metricSamples),raw=Math.sqrt(this.rawPow/count),ref=Math.sqrt(this.refPow/count),res=Math.sqrt(this.resPow/count),erle=10*Math.log10((this.rawPow+1e-12)/(this.resPow+1e-12));
      this.port.postMessage({type:'metrics',rawRms:raw,refRms:ref,residualRms:res,erleDb:erle,delaySamples:this.delaySamples});
      this.metricFrames=0;this.rawPow=this.refPow=this.resPow=0;this.metricSamples=0;
    }
    return true;
  }
}
registerProcessor('drumaster-acoustic-canceller',DruMasterAcousticCanceller);
