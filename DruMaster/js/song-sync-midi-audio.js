"use strict";

(()=>{
  const MIDI_MAP={35:"kick",36:"kick",38:"snare",40:"snare",41:"floorTom",43:"floorTom",45:"midTom",47:"midTom",48:"highTom",50:"highTom",42:"hhClosed",44:"hhPedal",46:"hhOpen",49:"crash",52:"crash",55:"crash",57:"crash",51:"ride",53:"ride",59:"ride"};
  const SAMPLE_NOTE={kick:36,snare:38,floorTom:41,midTom:45,highTom:48,hhClosed:42,hhPedal:44,hhOpen:46,ride:51,crash:49,special:37};
  let ac=null,buffer=null,regions=null,sourceVelocity=100,loading=null,openHats=[],voices=new Set();

  function typeFor(note){return MIDI_MAP[note]||"special"}
  function status(text){const el=document.getElementById("status");if(el)el.textContent=text}
  function parseMidi(ab){
    const d=new DataView(ab);let p=0;
    const str=n=>{let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s};
    const u32=()=>{const v=d.getUint32(p);p+=4;return v};
    const u16=()=>{const v=d.getUint16(p);p+=2;return v};
    const vlq=()=>{let v=0,b;do{b=d.getUint8(p++);v=(v<<7)|(b&127)}while(b&128);return v};
    if(str(4)!=="MThd")throw Error("ドラム音源MIDIが不正です");
    const hl=u32();u16();const tracks=u16(),division=u16();p=8+hl;
    const raw=[],tempos=[{tick:0,us:500000}];
    for(let t=0;t<tracks;t++){
      if(str(4)!=="MTrk")throw Error("ドラム音源MIDIが不正です");
      const len=u32(),end=p+len;let tick=0,run=0;
      while(p<end){
        tick+=vlq();let first=d.getUint8(p++),st;
        if(first<128){st=run;p--}else{st=first;if(st<240)run=st}
        if(st===255){const type=d.getUint8(p++),n=vlq();if(type===81&&n===3)tempos.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});p+=n;continue}
        if(st===240||st===247){run=0;p+=vlq();continue}
        const hi=st&240,ch=st&15,bytes=(hi===192||hi===208)?1:2,a=d.getUint8(p++),b=bytes===2?d.getUint8(p++):0;
        if(hi===144&&b>0&&ch===9)raw.push({tick,note:a});
      }
      p=end;
    }
    tempos.sort((a,b)=>a.tick-b.tick);
    const toSec=tick=>{let sec=0,last=0,us=500000;for(const x of tempos){if(x.tick>=tick)break;sec+=(x.tick-last)*us/division/1e6;last=x.tick;us=x.us}return sec+(tick-last)*us/division/1e6};
    return raw.map(n=>({note:n.note,time:toSec(n.tick)})).sort((a,b)=>a.time-b.time);
  }

  async function ready(context){
    ac=context||ac;if(buffer&&regions)return true;if(loading)return loading;
    loading=(async()=>{
      status("MIDIドラム音源を読み込み中…");
      const manifest=await fetch("assets/drumsound-manifest.json",{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error("ドラム音源設定を取得できません");return r.json()});
      const paths=Array.from({length:manifest.wav.parts},(_,i)=>`${manifest.wav.pathPrefix}${String(i).padStart(manifest.wav.digits||3,"0")}`),parts=[];
      for(let i=0;i<paths.length;i+=8){
        parts.push(...await Promise.all(paths.slice(i,i+8).map(path=>fetch(path,{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error("ドラム音源を取得できません");return r.arrayBuffer()}))));
      }
      const bytes=parts.reduce((n,b)=>n+b.byteLength,0),joined=new Uint8Array(bytes);let at=0;
      for(const part of parts){joined.set(new Uint8Array(part),at);at+=part.byteLength}
      const sourceMidi=await fetch(manifest.midi.path,{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error("ドラム音源MIDIを取得できません");return r.arrayBuffer()});
      const sourceNotes=parseMidi(sourceMidi);
      buffer=await ac.decodeAudioData(joined.buffer.slice(0));
      sourceVelocity=Number(manifest.sourceVelocity)||100;regions={};
      sourceNotes.forEach((n,i)=>{const end=i+1<sourceNotes.length?sourceNotes[i+1].time:buffer.duration;regions[String(n.note)]={offset:n.time,duration:Math.max(.03,end-n.time)}});
      status("調整可能");return true;
    })().catch(e=>{console.error(e);loading=null;status("MIDI音源の読み込みに失敗");return false});
    return loading;
  }

  function play(noteEvent,when,context){
    ac=context||ac;if(!ac||!buffer||!regions)return false;
    const type=typeFor(noteEvent.note),sample=SAMPLE_NOTE[type]??37,region=regions[String(sample)];if(!region)return false;
    if(type==="hhClosed"||type==="hhPedal"){
      for(const v of openHats.splice(0)){
        try{v.gain.gain.cancelScheduledValues(when);v.gain.gain.setValueAtTime(Math.max(.001,v.gain.gain.value),when);v.gain.gain.exponentialRampToValueAtTime(.001,when+.025);v.source.stop(when+.03)}catch{}
      }
    }
    const source=ac.createBufferSource(),gain=ac.createGain(),sourceV=sourceVelocity/127,velocity=Math.max(.04,(Number(noteEvent.velocity)||100)/127),velocityGain=Math.min(1.25,Math.pow(velocity/sourceV,.8)),voice={source,gain};
    source.buffer=buffer;gain.gain.value=.85*velocityGain;source.connect(gain).connect(ac.destination);voices.add(voice);
    if(type==="hhOpen")openHats.push(voice);
    source.onended=()=>{voices.delete(voice);openHats=openHats.filter(v=>v!==voice);try{source.disconnect()}catch{}try{gain.disconnect()}catch{}};
    source.start(Math.max(ac.currentTime,when),region.offset,region.duration);return true;
  }

  function stop(){
    openHats=[];
    for(const v of [...voices]){try{v.source.onended=null;v.source.stop()}catch{}try{v.source.disconnect()}catch{}try{v.gain.disconnect()}catch{}}
    voices.clear();
  }

  globalThis.DruMasterTimingMidi={ready,play,stop};
})();
