"use strict";

/* Let an open hi-hat overlap the following closed/pedal hit very briefly.
   Previously it faded in 25 ms and stopped at 30 ms; use a gentler 65 ms
   fade and stop at 80 ms so the transition feels less abruptly gated. */
chokeOpenHat=function(){
  if(typeof ac==="undefined"||!ac)return;
  const now=ac.currentTime;
  for(const voice of openHatVoices.splice(0)){
    try{
      const param=voice.gain.gain;
      param.cancelScheduledValues(now);
      param.setValueAtTime(Math.max(.001,param.value),now);
      param.exponentialRampToValueAtTime(.001,now+.065);
      voice.source.stop(now+.08);
    }catch{}
  }
};
