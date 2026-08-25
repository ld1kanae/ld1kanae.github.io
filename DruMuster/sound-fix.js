"use strict";

// Use the exact MP3 stems supplied for Nanairo instead of the converted WAV chunk set.
const DIRECT_STEMS={
  base:{path:"songs/nanairo/offvocal.mp3",bytes:6314638,sha256:"4dd43973168efdc730112bec742e3dced51024080d222dbd43f7065ef713a8b1"},
  vocals:{path:"songs/nanairo/vocals.mp3",bytes:6314638,sha256:"73e6ba324ffa608fb74b7a33206c9189e2b885a43c48779bd4b0094729e75c2f"},
  drums:{path:"songs/nanairo/drums.mp3",bytes:6314638,sha256:"6d50cf5fe21ab4fb73588d3cda1c8bb8ace2ae5234db1eaaca571374ff8e9eeb"}
};

loadStem=async function(name,label){
  if(buffers[name])return;
  const spec=DIRECT_STEMS[name];
  if(!spec)throw Error(`${label}音源の設定がありません`);
  $("#loadState").textContent=`${label}音源を読み込み中…`;
  const r=await fetch(spec.path,{cache:"no-store"});
  if(!r.ok)throw Error(`${label}音源を取得できません（HTTP ${r.status}）`);
  const encoded=await r.arrayBuffer();
  if(encoded.byteLength!==spec.bytes)throw Error(`${label}音源が不完全です（${encoded.byteLength.toLocaleString()} / ${spec.bytes.toLocaleString()} bytes）`);
  if(spec.sha256&&globalThis.crypto?.subtle){
    $("#loadState").textContent=`${label}音源を検証中…`;
    if((await hashBuffer(encoded))!==spec.sha256)throw Error(`${label}音源の内容が一致しません`);
  }
  buffers[name]=await ac.decodeAudioData(encoded.slice(0));
  if(Math.abs(buffers[name].duration-duration)>.1)throw Error(`${label}音源の長さが譜面と一致しません`);
};

// One canonical recording per drum articulation. Chart-note aliases only affect notation;
// velocity changes loudness, never which recorded sample is selected.
playDrum=function(_chartNote,type,v=.75){
  if(!ac||!drumBuffer)return;
  if(type==="hhClosed"||type==="hhPedal")chokeOpenHat();
  const sampleNote=DEFAULT_NOTE[type];
  const region=drumRegions[String(sampleNote)];
  if(!region)return;
  const now=ac.currentTime,
        source=ac.createBufferSource(),
        gain=ac.createGain(),
        mix=DRUM_GAIN[type]||1,
        sourceVelocity=drumSourceVelocity/127,
        velocityGain=Math.min(1.25,Math.pow(Math.max(.04,v)/sourceVelocity,.8));
  source.buffer=drumBuffer;
  gain.gain.value=.7*velocityGain*mix;
  source.connect(gain).connect(masterBus);
  source.start(now,region.offset,region.duration);
  if(type==="hhOpen"){
    const voice={source,gain};
    openHatVoices.push(voice);
    source.onended=()=>{openHatVoices=openHatVoices.filter(x=>x!==voice)};
  }
};
