"use strict";

(async()=>{
  const url="js/song-volume-editor-v4.js?v=20260913-tone-b1";
  const r=await fetch(url,{cache:"no-store"});
  if(!r.ok)throw Error(`音量バランス本体を取得できません（HTTP ${r.status}）`);
  let src=await r.text();
  const replace=(from,to,label)=>{
    if(!src.includes(from))throw Error(`MIDI安全化パッチ対象が見つかりません: ${label}`);
    src=src.replace(from,to);
  };

  replace(
    'const MIDI_DEFAULT={master:1,individual:false,cymbal:1.2,hihatRide:1,snareTom:1,kick:1.4,other:1};',
    'const MIDI_DEFAULT={master:1,individual:false,cymbal:1.2,hihatRide:1,snareTom:1,kick:1.4,other:1};\n  const MIDI_TONE_DEFAULT={cymbal:"A",hihatRide:"A",snareTom:"A",kick:"A",other:"A"};',
    "tone defaults"
  );
  replace(
    'let drumBuffer=null,drumRegions=null,drumLoadPromise=null,drumSourceVelocity=100,midiNotes=[],midiCursor=0,midiTimer=0,midiVoices=new Set(),openHatVoices=[];',
    'let drumBuffer=null,drumRegions=null,drumLoadPromise=null,drumSourceVelocity=100,drumKits={},drumKitPromises={},midiNotes=[],midiCursor=0,midiTimer=0,midiVoices=new Set(),openHatVoices=[];',
    "tone kit state"
  );
  replace(
    'function ensureConfig(){session.draft.mix={...(session.draft.mix||{})};const existing=session.draft.midiDrumMix||{};session.draft.midiDrumMix={...MIDI_DEFAULT,...existing,individual:!!existing.individual}}',
    'function ensureConfig(){session.draft.mix={...(session.draft.mix||{})};const existing=session.draft.midiDrumMix||{},existingTone=existing.tone&&typeof existing.tone==="object"?existing.tone:{},tone={...MIDI_TONE_DEFAULT,...existingTone};for(const k of Object.keys(MIDI_TONE_DEFAULT))tone[k]=tone[k]==="B"?"B":"A";session.draft.midiDrumMix={...MIDI_DEFAULT,...existing,individual:!!existing.individual,tone}}',
    "tone config"
  );
  replace(
    'function effectiveGroup(group){return session.draft.midiDrumMix.individual?midiGroupValue(group):MIDI_DEFAULT[group]}',
    'function effectiveGroup(group){return session.draft.midiDrumMix.individual?midiGroupValue(group):MIDI_DEFAULT[group]}\n  function midiTone(group){return session.draft.midiDrumMix.individual&&session.draft.midiDrumMix?.tone?.[group]==="B"?"B":"A"}',
    "tone resolver"
  );
  replace(
    'function updateMidiConfig(){const c=session.draft.midiDrumMix;c.master=Number((Number($("midiMaster").value)/100).toFixed(3));c.individual=$("individualToggle").checked;for(const k of ["cymbal","hihatRide","snareTom","kick","other"])c[k]=Number((Number($(k).value)/100).toFixed(3));$("individualPanel").hidden=!c.individual;syncMidiGains();scheduleSave()}',
    'function updateMidiConfig(){const c=session.draft.midiDrumMix;c.master=Number((Number($("midiMaster").value)/100).toFixed(3));c.individual=$("individualToggle").checked;c.tone={...MIDI_TONE_DEFAULT,...(c.tone||{})};for(const k of ["cymbal","hihatRide","snareTom","kick","other"]){c[k]=Number((Number($(k).value)/100).toFixed(3));c.tone[k]=$(k+"Tone")?.value==="B"?"B":"A"}$("individualPanel").hidden=!c.individual;syncMidiGains();scheduleSave()}',
    "tone save"
  );
  replace(
    'function renderMidi(){const c=session.draft.midiDrumMix;$("midiMaster").value=$("midiMasterValue").value=String(Math.round(c.master*100));$("individualToggle").checked=!!c.individual;$("individualPanel").hidden=!c.individual;bindPair("midiMaster","midiMasterValue",updateMidiConfig);for(const k of ["cymbal","hihatRide","snareTom","kick","other"]){const pct=Math.round(midiGroupValue(k)*100);$(k).value=$(k+"Value").value=String(pct);bindPair(k,k+"Value",updateMidiConfig)}$("individualToggle").addEventListener("change",updateMidiConfig);document.querySelectorAll("[data-preview]").forEach(b=>b.addEventListener("click",()=>void previewMidiGroup(b.dataset.preview)))}',
    'function renderMidi(){const c=session.draft.midiDrumMix;$("midiMaster").value=$("midiMasterValue").value=String(Math.round(c.master*100));$("individualToggle").checked=!!c.individual;$("individualPanel").hidden=!c.individual;bindPair("midiMaster","midiMasterValue",updateMidiConfig);for(const k of ["cymbal","hihatRide","snareTom","kick","other"]){const pct=Math.round(midiGroupValue(k)*100),tone=$(k+"Tone");$(k).value=$(k+"Value").value=String(pct);bindPair(k,k+"Value",updateMidiConfig);if(tone){tone.value=c.tone?.[k]==="B"?"B":"A";tone.addEventListener("change",()=>{updateMidiConfig();if(tone.value==="B")void loadDrumKit("B").catch(e=>{console.error(e);status(e.message||String(e))})})}}$("individualToggle").addEventListener("change",updateMidiConfig);document.querySelectorAll("[data-preview]").forEach(b=>b.addEventListener("click",()=>void previewMidiGroup(b.dataset.preview)))}',
    "tone ui"
  );

  replace(
    'async function loadDrumKit(){if(drumBuffer&&drumRegions)return;if(drumLoadPromise)return drumLoadPromise;drumLoadPromise=(async()=>{const manifest=await fetch("assets/drumsound-manifest.json",{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error("ドラム音源設定を取得できません");return r.json()}),paths=Array.from({length:manifest.wav.parts},(_,i)=>`${manifest.wav.pathPrefix}${String(i).padStart(manifest.wav.digits||3,"0")}`),parts=[];for(let i=0;i<paths.length;i+=8)parts.push(...await Promise.all(paths.slice(i,i+8).map(p=>fetch(p,{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error("ドラム音源を取得できません");return r.arrayBuffer()}))));const size=parts.reduce((n,b)=>n+b.byteLength,0),joined=new Uint8Array(size);let at=0;for(const part of parts){joined.set(new Uint8Array(part),at);at+=part.byteLength}const srcMidi=await fetch(manifest.midi.path,{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error("ドラム音源MIDIを取得できません");return r.arrayBuffer()}),sourceNotes=parseSourceMidi(srcMidi);drumBuffer=await getAC().decodeAudioData(joined.buffer.slice(0));drumSourceVelocity=Number(manifest.sourceVelocity)||100;drumRegions={};sourceNotes.forEach((n,i)=>{const end=i+1<sourceNotes.length?sourceNotes[i+1].time:drumBuffer.duration;drumRegions[String(n.note)]={offset:n.time,duration:Math.max(.03,end-n.time)}});ensureMidiBus()})();return drumLoadPromise}',
    'async function loadDrumKit(tone="A"){tone=tone==="B"?"B":"A";if(drumKits[tone])return drumKits[tone];if(drumKitPromises[tone])return drumKitPromises[tone];drumKitPromises[tone]=(async()=>{const manifestPath=tone==="B"?"assets/drumsoundB-manifest.json":"assets/drumsound-manifest.json",manifest=await fetch(manifestPath,{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error(`ドラム音源${tone}設定を取得できません`);return r.json()}),paths=Array.from({length:manifest.wav.parts},(_,i)=>`${manifest.wav.pathPrefix}${String(i).padStart(manifest.wav.digits||3,"0")}`),parts=[];for(let i=0;i<paths.length;i+=8)parts.push(...await Promise.all(paths.slice(i,i+8).map(p=>fetch(p,{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error(`ドラム音源${tone}を取得できません`);return r.arrayBuffer()}))));const size=parts.reduce((n,b)=>n+b.byteLength,0),joined=new Uint8Array(size);let at=0;for(const part of parts){joined.set(new Uint8Array(part),at);at+=part.byteLength}if(manifest.wav.bytes&&joined.byteLength!==manifest.wav.bytes)throw Error(`ドラム音源${tone}が不完全です`);const srcMidi=await fetch(manifest.midi.path,{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error("ドラム音源MIDIを取得できません");return r.arrayBuffer()}),sourceNotes=parseSourceMidi(srcMidi),buffer=await getAC().decodeAudioData(joined.buffer.slice(0)),sourceVelocity=Number(manifest.sourceVelocity)||100,regions={};sourceNotes.forEach((n,i)=>{const end=i+1<sourceNotes.length?sourceNotes[i+1].time:buffer.duration;regions[String(n.note)]={offset:n.time,duration:Math.max(.03,end-n.time)}});const kit={buffer,regions,sourceVelocity};drumKits[tone]=kit;if(tone==="A"){drumBuffer=buffer;drumRegions=regions;drumSourceVelocity=sourceVelocity}ensureMidiBus();return kit})().catch(e=>{drumKitPromises[tone]=null;throw e});return drumKitPromises[tone]}',
    "tone kit loader"
  );
  replace(
    'function scheduleMidi(){if(!playing||!drumBuffer||!drumRegions)return;const now=nowLogical(),ahead=now+AHEAD,off=Number(session.draft.playback?.midiOffsetSec)||0;while(midiCursor<midiNotes.length&&midiNotes[midiCursor].time+off<ahead){const n=midiNotes[midiCursor++],logical=n.time+off;if(logical<now-.03)continue;const type=typeForNote(n.note),sample=SAMPLE_NOTE[type]??37,region=drumRegions[String(sample)];if(!region)continue;const when=Math.max(getAC().currentTime,contextStart+(logical-logicalStart));if(type==="hhClosed"||type==="hhPedal"){for(const v of openHatVoices.splice(0)){try{v.gain.gain.cancelScheduledValues(when);v.gain.gain.setValueAtTime(Math.max(.001,v.gain.gain.value),when);v.gain.gain.exponentialRampToValueAtTime(.001,when+.025);v.source.stop(when+.03)}catch{}}}const source=getAC().createBufferSource(),gain=getAC().createGain(),voice={source,gain},sourceV=drumSourceVelocity/127,velocityGain=Math.min(1.25,Math.pow(Math.max(.04,n.velocity/127)/sourceV,.8));source.buffer=drumBuffer;gain.gain.value=.85*velocityGain;source.connect(gain).connect(midiGroups[groupForType(type)]||midiBus);midiVoices.add(voice);if(type==="hhOpen")openHatVoices.push(voice);source.onended=()=>{midiVoices.delete(voice);openHatVoices=openHatVoices.filter(x=>x!==voice);try{source.disconnect()}catch{}try{gain.disconnect()}catch{}};source.start(when,region.offset,region.duration)}}',
    'function scheduleMidi(){if(!playing)return;const now=nowLogical(),ahead=now+AHEAD,off=Number(session.draft.playback?.midiOffsetSec)||0;while(midiCursor<midiNotes.length&&midiNotes[midiCursor].time+off<ahead){const n=midiNotes[midiCursor++],logical=n.time+off;if(logical<now-.03)continue;const type=typeForNote(n.note),group=groupForType(type),tone=midiTone(group),kit=drumKits[tone]||drumKits.A,sample=SAMPLE_NOTE[type]??37,region=kit?.regions?.[String(sample)];if(!region)continue;const when=Math.max(getAC().currentTime,contextStart+(logical-logicalStart));if(type==="hhClosed"||type==="hhPedal"){for(const v of openHatVoices.splice(0)){try{v.gain.gain.cancelScheduledValues(when);v.gain.gain.setValueAtTime(Math.max(.001,v.gain.gain.value),when);v.gain.gain.exponentialRampToValueAtTime(.001,when+.025);v.source.stop(when+.03)}catch{}}}const source=getAC().createBufferSource(),gain=getAC().createGain(),voice={source,gain},sourceV=kit.sourceVelocity/127,velocityGain=Math.min(1.25,Math.pow(Math.max(.04,n.velocity/127)/sourceV,.8));source.buffer=kit.buffer;gain.gain.value=.85*velocityGain;source.connect(gain).connect(midiGroups[group]||midiBus);midiVoices.add(voice);if(type==="hhOpen")openHatVoices.push(voice);source.onended=()=>{midiVoices.delete(voice);openHatVoices=openHatVoices.filter(x=>x!==voice);try{source.disconnect()}catch{}try{gain.disconnect()}catch{}};source.start(when,region.offset,region.duration)}}',
    "tone mix playback"
  );
  replace(
    'async function playMix(){try{status("再生データを読み込み中…");await getAC().resume();await Promise.all([loadAllStems(),loadSongMidi(),loadDrumKit()]);if(cursor>=duration()-.01)cursor=0;',
    'async function playMix(){try{status("再生データを読み込み中…");await getAC().resume();const tones=new Set(["A"]);if(session.draft.midiDrumMix.individual)for(const group of ["cymbal","hihatRide","snareTom","kick","other"])if(midiTone(group)==="B")tones.add("B");await Promise.all([loadAllStems(),loadSongMidi(),...Array.from(tones,t=>loadDrumKit(t))]);if(cursor>=duration()-.01)cursor=0;',
    "tone mix preload"
  );
  replace(
    'async function previewMidiGroup(group){try{pauseMix(false);await getAC().resume();await loadDrumKit();const notes=MIDI_PREVIEW[group]||[37];notes.forEach((note,i)=>{const type=typeForNote(note),region=drumRegions[String(SAMPLE_NOTE[type]??37)];if(!region)return;const source=getAC().createBufferSource(),gain=getAC().createGain(),voice={source,gain};source.buffer=drumBuffer;gain.gain.value=.85;source.connect(gain).connect(midiGroups[group]||midiBus);previewVoices.add(voice);source.onended=()=>{previewVoices.delete(voice);try{source.disconnect()}catch{}try{gain.disconnect()}catch{}};source.start(getAC().currentTime+.02+i*.25,region.offset,region.duration)});status(`${group} を試聴中`)}catch(e){console.error(e);status(e.message||String(e))}}',
    'async function previewMidiGroup(group){try{pauseMix(false);await getAC().resume();const tone=midiTone(group),kit=await loadDrumKit(tone),notes=MIDI_PREVIEW[group]||[37];notes.forEach((note,i)=>{const type=typeForNote(note),region=kit.regions[String(SAMPLE_NOTE[type]??37)];if(!region)return;const source=getAC().createBufferSource(),gain=getAC().createGain(),voice={source,gain};source.buffer=kit.buffer;gain.gain.value=.85;source.connect(gain).connect(midiGroups[group]||midiBus);previewVoices.add(voice);source.onended=()=>{previewVoices.delete(voice);try{source.disconnect()}catch{}try{gain.disconnect()}catch{}};source.start(getAC().currentTime+.02+i*.25,region.offset,region.duration)});status(`${group} / 音色${tone} を試聴中`)}catch(e){console.error(e);status(e.message||String(e))}}',
    "tone preview"
  );

  replace(
    'const need=(n,end=d.byteLength)=>{if(p+n>end)throw Error("MIDIが途中で切れています")}',
    'const need=(n,end=d.byteLength)=>{const limit=Math.min(Number.isFinite(end)?end:d.byteLength,d.byteLength);if(!Number.isFinite(n)||n<0||p<0||p+n>limit)throw Error("MIDIが途中で切れています")}',
    "song need"
  );
  replace(
    'p=8+hl;const raw=[],tempos=[{tick:0,us:500000}];',
    'p=8+hl;if(hl<6||p>d.byteLength)throw Error("MIDIヘッダーが不正です");const raw=[],tempos=[{tick:0,us:500000}];',
    "song header"
  );
  replace(
    'const len=u32(),end=p+len;let tick=0,run=0;while(p<end){tick+=vlq(end);let first=d.getUint8(p++),status;',
    'const len=u32(),end=p+len;if(end>d.byteLength)throw Error("MIDIトラックが途中で切れています");let tick=0,run=0;while(p<end){tick+=vlq(end);need(1,end);let first=d.getUint8(p++),status;',
    "song track"
  );
  replace(
    'if(status===255){const type=d.getUint8(p++),n=vlq(end);if(type===81&&n===3)tempos.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});p+=n;continue}',
    'if(status===255){need(1,end);const type=d.getUint8(p++),n=vlq(end);need(n,end);if(type===81&&n===3)tempos.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});p+=n;continue}',
    "song meta"
  );
  replace(
    'if(status===240||status===247){run=0;p+=vlq(end);continue}',
    'if(status===240||status===247){run=0;const n=vlq(end);need(n,end);p+=n;continue}',
    "song sysex"
  );

  const sourceStart='function parseSourceMidi(ab){const d=new DataView(ab);let p=0;const str=n=>{let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s},u32=()=>{const v=d.getUint32(p);p+=4;return v},u16=()=>{const v=d.getUint16(p);p+=2;return v},vlq=()=>{let v=0,b;do{b=d.getUint8(p++);v=(v<<7)|(b&127)}while(b&128);return v};';
  const sourceSafe='function parseSourceMidi(ab){const d=new DataView(ab);let p=0;const need=(n,end=d.byteLength)=>{const limit=Math.min(Number.isFinite(end)?end:d.byteLength,d.byteLength);if(!Number.isFinite(n)||n<0||p<0||p+n>limit)throw Error("ドラム音源MIDIが途中で切れています")},str=n=>{need(n);let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s},u32=()=>{need(4);const v=d.getUint32(p);p+=4;return v},u16=()=>{need(2);const v=d.getUint16(p);p+=2;return v},vlq=end=>{let v=0,b,c=0;do{need(1,end);b=d.getUint8(p++);v=(v<<7)|(b&127);if(++c>4)throw Error("ドラム音源MIDI VLQ error")}while(b&128);return v};';
  replace(sourceStart,sourceSafe,"source parser");
  replace(
    'p=8+hl;const raw=[],tempos=[{tick:0,us:500000}];for(let t=0;t<tracks;t++){if(str(4)!=="MTrk")throw Error("ドラム音源MIDIが不正です");const len=u32(),end=p+len;let tick=0,run=0;while(p<end){tick+=vlq();let first=d.getUint8(p++),status;',
    'p=8+hl;if(hl<6||p>d.byteLength)throw Error("ドラム音源MIDIヘッダーが不正です");const raw=[],tempos=[{tick:0,us:500000}];for(let t=0;t<tracks;t++){if(str(4)!=="MTrk")throw Error("ドラム音源MIDIが不正です");const len=u32(),end=p+len;if(end>d.byteLength)throw Error("ドラム音源MIDIトラックが途中で切れています");let tick=0,run=0;while(p<end){tick+=vlq(end);need(1,end);let first=d.getUint8(p++),status;',
    "source track"
  );
  replace(
    'if(status===255){const type=d.getUint8(p++),n=vlq();if(type===81&&n===3)tempos.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});p+=n}else if(status===240||status===247){run=0;p+=vlq()}else{const hi=status&240,ch=status&15,bytes=(hi===192||hi===208)?1:2,a=d.getUint8(p++),b=bytes===2?d.getUint8(p++):0;',
    'if(status===255){need(1,end);const type=d.getUint8(p++),n=vlq(end);need(n,end);if(type===81&&n===3)tempos.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});p+=n}else if(status===240||status===247){run=0;const n=vlq(end);need(n,end);p+=n}else{const hi=status&240,ch=status&15,bytes=(hi===192||hi===208)?1:2;need(bytes,end);const a=d.getUint8(p++),b=bytes===2?d.getUint8(p++):0;',
    "source events"
  );

  (0,eval)(`${src}\n//# sourceURL=song-volume-editor-v4.patched.js`);
})().catch(e=>{
  console.error(e);
  const status=document.getElementById("status"),save=document.getElementById("saveState");
  if(status)status.textContent=e?.message||String(e);
  if(save)save.textContent="ERROR";
});
