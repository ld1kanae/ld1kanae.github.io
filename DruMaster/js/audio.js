"use strict";

const FALLBACK_STEMS={
  base:{path:"songs/nanairo/offvocal.mp3",bytes:6314638,sha256:"4dd43973168efdc730112bec742e3dced51024080d222dbd43f7065ef713a8b1"},
  vocals:{path:"songs/nanairo/vocals.mp3",bytes:6314638,sha256:"73e6ba324ffa608fb74b7a33206c9189e2b885a43c48779bd4b0094729e75c2f"},
  drums:{path:"songs/nanairo/drums.mp3",bytes:6314638,sha256:"6d50cf5fe21ab4fb73588d3cda1c8bb8ace2ae5234db1eaaca571374ff8e9eeb"}
};
function stemSpec(name){
  return globalThis.DruMasterSongs?.current?.stems?.[name]||FALLBACK_STEMS[name];
}

fetchJoined=async function(spec,label){
  const paths=Array.isArray(spec.paths)?spec.paths:(spec.parts?Array.from({length:spec.parts},(_,i)=>`${spec.pathPrefix}${String(i).padStart(spec.digits||3,"0")}`):[]);
  if(!paths.length)throw Error(`${label}音源の分割ファイル設定がありません`);
  const parts=[];
  for(let i=0;i<paths.length;i+=8){
    const batch=await Promise.all(paths.slice(i,i+8).map(async p=>{
      const r=await fetch(p,{cache:"no-store"});
      if(!r.ok)throw Error(`${label}音源を取得できません（HTTP ${r.status}）`);
      return r.arrayBuffer();
    }));
    parts.push(...batch);
    $("#loadState").textContent=`${label}音源を読み込み中… ${Math.min(i+8,paths.length)}/${paths.length}`;
  }
  const size=parts.reduce((n,b)=>n+b.byteLength,0),out=new Uint8Array(size);
  let at=0;
  for(const b of parts){out.set(new Uint8Array(b),at);at+=b.byteLength}
  if(spec.bytes&&out.byteLength!==spec.bytes)throw Error(`${label}音源が不完全です（${out.byteLength.toLocaleString()} / ${spec.bytes.toLocaleString()} bytes）`);
  if(spec.sha256&&globalThis.crypto?.subtle){
    $("#loadState").textContent=`${label}音源を検証中…`;
    if((await hashBuffer(out.buffer))!==spec.sha256)throw Error(`${label}音源の内容が一致しません`);
  }
  return out.buffer;
};

loadStem=async function(name,label){
  if(buffers[name])return;
  const spec=stemSpec(name);
  if(!spec)throw Error(`${label}音源の設定がありません`);
  $("#loadState").textContent=`${label}音源を読み込み中…`;
  let encoded;
  if(Array.isArray(spec.paths)||spec.parts){
    encoded=await fetchJoined(spec,label);
  }else{
    const r=await fetch(spec.path,{cache:"no-store"});
    if(!r.ok)throw Error(`${label}音源を取得できません（HTTP ${r.status}）`);
    encoded=await r.arrayBuffer();
    if(spec.bytes&&encoded.byteLength!==spec.bytes)throw Error(`${label}音源が不完全です（${encoded.byteLength.toLocaleString()} / ${spec.bytes.toLocaleString()} bytes）`);
    if(spec.sha256&&globalThis.crypto?.subtle){
      $("#loadState").textContent=`${label}音源を検証中…`;
      if((await hashBuffer(encoded))!==spec.sha256)throw Error(`${label}音源の内容が一致しません`);
    }
  }
  buffers[name]=await ac.decodeAudioData(encoded.slice(0));
  if(Math.abs(buffers[name].duration-duration)>.15)throw Error(`${label}音源の長さが譜面と一致しません`);
};

let drumSampleBuffers={};
function tuneRealtimeLimiter(){
  if(!safetyLimiter)return;
  safetyLimiter.threshold.value=-1.5;
  safetyLimiter.knee.value=1;
  safetyLimiter.ratio.value=20;
  safetyLimiter.attack.value=.001;
  safetyLimiter.release.value=.06;
}

loadDrumSource=async function(manifest){
  const sampleNotes=[...new Set(Object.values(DEFAULT_NOTE).map(Number))];
  drumSampleBuffers={};
  for(let i=0;i<sampleNotes.length;i++){
    const note=sampleNotes[i];
    $("#loadState").textContent=`ゲーム内ドラム音源を読み込み中… ${i+1}/${sampleNotes.length}`;
    const r=await fetch(`assets/drums/${note}.wav`,{cache:"no-store"});
    if(!r.ok)throw Error(`ゲーム内ドラム音源を取得できません（MIDI ${note} / HTTP ${r.status}）`);
    const encoded=await r.arrayBuffer();
    drumSampleBuffers[String(note)]=await ac.decodeAudioData(encoded.slice(0));
  }
  drumSourceVelocity=manifest?.sourceVelocity||100;
  drumBuffer=null;
  drumRegions={};
  tuneRealtimeLimiter();
};

const activeDrumVoices=new Set();
const MIDI_DRUM_BALANCE_DEFAULT={cymbal:1.2,hihatRide:1,snareTom:1,kick:1.4,other:1};
function midiDrumGroup(type){
  if(type==="crash"||type==="crash2")return "cymbal";
  if(["hhClosed","hhPedal","hhOpen","ride"].includes(type))return "hihatRide";
  if(["snare","floorTom","midTom","highTom"].includes(type))return "snareTom";
  if(type==="kick")return "kick";
  return "other";
}
function midiDrumMix(type){
  const base=DRUM_GAIN[type]||1,config=globalThis.DruMasterSongs?.current?.midiDrumMix;
  if(!config)return base;
  const master=Number.isFinite(Number(config.master))?Math.max(0,Number(config.master)):1;
  if(!config.individual)return master*base;
  const group=midiDrumGroup(type),configured=Number(config[group]),groupGain=Number.isFinite(configured)?Math.max(0,configured):MIDI_DRUM_BALANCE_DEFAULT[group];
  return master*groupGain;
}

function startDrumVoice(type,v=.75,when){
  if(!ac)return null;
  if(type==="hhClosed"||type==="hhPedal")chokeOpenHat();
  const sample=drumSampleBuffers[String(DEFAULT_NOTE[type])];
  if(!sample)return null;
  const startAt=Number.isFinite(Number(when))?Math.max(ac.currentTime,Number(when)):ac.currentTime,
        source=ac.createBufferSource(),gain=ac.createGain(),mix=midiDrumMix(type),sourceVelocity=drumSourceVelocity/127,
        velocityGain=Math.min(1.25,Math.pow(Math.max(.04,v)/sourceVelocity,.8));
  source.buffer=sample;
  gain.gain.value=.85*velocityGain*mix;
  source.connect(gain).connect(masterBus);
  let voice=null;
  if(type==="hhOpen"){voice={source,gain};openHatVoices.push(voice)}
  const tracked={source,gain,endsAt:startAt+sample.duration};
  activeDrumVoices.add(tracked);
  source.onended=()=>{
    activeDrumVoices.delete(tracked);
    if(voice)openHatVoices=openHatVoices.filter(x=>x!==voice);
    try{source.disconnect()}catch{}
    try{gain.disconnect()}catch{}
  };
  source.start(startAt);
  return tracked;
}

playDrum=function(_chartNote,type,v=.75){
  return startDrumVoice(type,v,ac?.currentTime);
};

globalThis.DruMasterAudioControl={
  scheduleKick(v,when){return startDrumVoice("kick",v,when)},
  getStats(){return {activeVoices:activeDrumVoices.size,sampleBuffers:Object.keys(drumSampleBuffers).length}},
  stopAllDrumVoices(){
    const now=ac?.currentTime||0;
    openHatVoices=[];
    for(const voice of [...activeDrumVoices]){
      activeDrumVoices.delete(voice);
      try{voice.source.onended=null;voice.source.stop(now)}catch{}
      try{voice.source.disconnect()}catch{}
      try{voice.gain.disconnect()}catch{}
    }
  }
};