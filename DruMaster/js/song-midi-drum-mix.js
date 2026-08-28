"use strict";

(()=>{
  const song=globalThis.DruMasterSongs?.current,config=song?.midiDrumMix;
  if(!config||typeof DRUM_GAIN==="undefined")return;
  const defaults={cymbal:1.2,hihatRide:1,snareTom:1,kick:1.4,other:1};
  const groups={
    cymbal:["crash"],
    hihatRide:["hhClosed","hhPedal","hhOpen","ride"],
    snareTom:["snare","floorTom","midTom","highTom"],
    kick:["kick"],
    other:["special"]
  };
  const finite=(v,f)=>Number.isFinite(Number(v))?Number(v):f,master=Math.max(0,finite(config.master,1)),individual=!!config.individual;
  for(const [group,types] of Object.entries(groups)){
    const groupGain=Math.max(0,individual?finite(config[group],defaults[group]):defaults[group]);
    const gain=Math.max(.000001,master*groupGain);
    for(const type of types)DRUM_GAIN[type]=gain;
  }
})();
