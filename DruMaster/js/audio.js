"use strict";

const FALLBACK_STEMS={
  base:{path:"songs/nanairo/offvocal.mp3",bytes:6314638,sha256:"4dd43973168efdc730112bec742e3dced51024080d222dbd43f7065ef713a8b1"},
  vocals:{path:"songs/nanairo/vocals.mp3",bytes:6314638,sha256:"73e6ba324ffa608fb74b7a33206c9189e2b885a43c48779bd4b0094729e75c2f"},
  drums:{path:"songs/nanairo/drums.mp3",bytes:6314638,sha256:"6d50cf5fe21ab4fb73588d3cda1c8bb8ace2ae5234db1eaaca571374ff8e9eeb"}
};
function stemSpec(name){
  const current=globalThis.DruMasterSongs?.current?.stems?.[name];
  return current||FALLBACK_STEMS[name];
}

/* Chunked WAV is used by the song publisher so large browser-generated files
   stay comfortably below GitHub's per-request practical limits. Existing MP3
   songs keep their stable single-file path. */
fetchJoined=async function(spec,label){
  const paths=Array.isArray(spec.paths)?spec.paths:(spec.parts?Array.from({length:spec.parts},(_,i)=>`${spec.pathPrefix}${String(i).padStart(spec.digits||3,"0")}`):[]),parts=[];
  if(!paths.length)throw Error(`${label}音源の分割ファイル設定がありません`);
  for(let i=0;i<paths.length;i+=8){
    const batch=await Promise.all(paths.slice(i,i+8).map(p=>fetch(p,{cache:"force-cache"}).then(r=>{
      if(!r.ok)throw Error(`${label}音源を取得できません（HTTP ${r.status}）`);
      return r.arrayBuffer();
    })));
    parts.push(...batch);
    $("#loadState").textContent=`${label}音源を読み込み中… ${Math.min(i+8,paths.length)}/${paths.length}`;
  }
  const size=parts.reduce((n,b)=>n+b.byteLength,0),out=new Uint8Array(size);let at=0;
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
    const r=await fetch(spec.path,{cache:"force-cache"});
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

function readWavFormat(ab){
  const d=new DataView(ab);
  if(ab.byteLength<44||fourCC(d,0)!=="RIFF"||fourCC(d,8)!=="WAVE")throw Error("ゲーム内ドラム音源のWAVヘッダーが不正です");
  let p=12;
  while(p+8<=ab.byteLength){
    const id=fourCC(d,p),size=d.getUint32(p+4,true),at=p+8;
    if(id==="fmt "){
      if(size<16||at+16>ab.byteLength)throw Error("ゲーム内ドラム音源のfmtチャンクが不正です");
      return {format:d.getUint16(at,true),channels:d.getUint16(at+2,true),sampleRate:d.getUint32(at+4,true),bitsPerSample:d.getUint16(at+14,true)};
    }
    p=at+size+(size&1);
  }
  throw Error("ゲーム内ドラム音源のfmtチャンクが見つかりません");
}

loadDrumSource=async function(manifest){
  $("#loadState").textContent="ゲーム内ドラム音源を読み込み中…";
  const [wav,midi]=await Promise.all([
    fetchJoined(manifest.wav,"ゲーム内ドラム"),
    fetch(manifest.midi.path,{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error(`ドラム音源MIDIを取得できません（HTTP ${r.status}）`);return r.arrayBuffer()})
  ]);
  if(midi.byteLength!==manifest.midi.bytes)throw Error("ゲーム内ドラム音源MIDIが不完全です");
  if(manifest.midi.sha256&&globalThis.crypto?.subtle&&(await hashBuffer(midi))!==manifest.midi.sha256)throw Error("ゲーム内ドラム音源MIDIの内容が一致しません");

  const fmt=readWavFormat(wav),expectedRate=manifest.wav.sourceSampleRate||manifest.wav.sampleRate;
  if(expectedRate&&fmt.sampleRate!==expectedRate)throw Error(`ゲーム内ドラム音源の元サンプルレートが不正です（${fmt.sampleRate}Hz / ${expectedRate}Hz）`);
  if(manifest.wav.channels&&fmt.channels!==manifest.wav.channels)throw Error("ゲーム内ドラム音源のチャンネル数が一致しません");
  if(manifest.wav.bitsPerSample&&fmt.bitsPerSample!==manifest.wav.bitsPerSample)throw Error("ゲーム内ドラム音源のビット深度が一致しません");

  drumBuffer=await ac.decodeAudioData(wav.slice(0));
  const sourceNotes=parseMidi(midi);
  if(!sourceNotes.length)throw Error("ゲーム内ドラム音源MIDIにノートがありません");
  drumSourceVelocity=manifest.sourceVelocity||100;
  drumRegions={};
  sourceNotes.forEach((n,i)=>{
    const end=i+1<sourceNotes.length?sourceNotes[i+1].time:drumBuffer.duration;
    if(n.time>=drumBuffer.duration||end<=n.time)throw Error(`ドラム音源の再生位置が不正です（MIDI ${n.note}）`);
    drumRegions[String(n.note)]={offset:n.time,duration:end-n.time};
  });
  const required=new Set(Object.values(DEFAULT_NOTE)),missing=[...required].filter(note=>!drumRegions[String(note)]);
  if(missing.length)throw Error(`ゲーム内ドラム音源に必要な基準音がありません（MIDI ${missing.join(", ")}）`);
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

playDrum=function(_chartNote,type,v=.75){
  if(!ac||!drumBuffer)return;
  if(type==="hhClosed"||type==="hhPedal")chokeOpenHat();
  const sampleNote=DEFAULT_NOTE[type];
  const region=drumRegions[String(sampleNote)];
  if(!region)return;
  const now=ac.currentTime,source=ac.createBufferSource(),gain=ac.createGain(),mix=midiDrumMix(type),sourceVelocity=drumSourceVelocity/127,velocityGain=Math.min(1.25,Math.pow(Math.max(.04,v)/sourceVelocity,.8));
  source.buffer=drumBuffer;
  gain.gain.value=.85*velocityGain*mix;
  source.connect(gain).connect(masterBus);

  let voice=null;
  if(type==="hhOpen"){voice={source,gain};openHatVoices.push(voice)}
  const tracked={source,gain};
  activeDrumVoices.add(tracked);
  source.onended=()=>{
    activeDrumVoices.delete(tracked);
    if(voice)openHatVoices=openHatVoices.filter(x=>x!==voice);
    try{source.disconnect()}catch{}
    try{gain.disconnect()}catch{}
  };
  source.start(now,region.offset,region.duration);
};

globalThis.DruMasterAudioControl={
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