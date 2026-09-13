"use strict";

(async()=>{
  const url="js/song-volume-editor-v4.js?v=20260913-tone-selector1";
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
    'function ensureConfig(){session.draft.mix={...(session.draft.mix||{})};const existing=session.draft.midiDrumMix||{};session.draft.midiDrumMix={...MIDI_DEFAULT,...existing,individual:!!existing.individual}}',
    'function ensureConfig(){session.draft.mix={...(session.draft.mix||{})};const existing=session.draft.midiDrumMix||{},existingTone=existing.tone&&typeof existing.tone==="object"?existing.tone:{},tone={...MIDI_TONE_DEFAULT,...existingTone};for(const k of Object.keys(MIDI_TONE_DEFAULT))tone[k]=tone[k]==="B"?"B":"A";session.draft.midiDrumMix={...MIDI_DEFAULT,...existing,individual:!!existing.individual,tone}}',
    "tone config"
  );
  replace(
    'function updateMidiConfig(){const c=session.draft.midiDrumMix;c.master=Number((Number($("midiMaster").value)/100).toFixed(3));c.individual=$("individualToggle").checked;for(const k of ["cymbal","hihatRide","snareTom","kick","other"])c[k]=Number((Number($(k).value)/100).toFixed(3));$("individualPanel").hidden=!c.individual;syncMidiGains();scheduleSave()}',
    'function updateMidiConfig(){const c=session.draft.midiDrumMix;c.master=Number((Number($("midiMaster").value)/100).toFixed(3));c.individual=$("individualToggle").checked;c.tone={...MIDI_TONE_DEFAULT,...(c.tone||{})};for(const k of ["cymbal","hihatRide","snareTom","kick","other"]){c[k]=Number((Number($(k).value)/100).toFixed(3));c.tone[k]=$(k+"Tone")?.value==="B"?"B":"A"}$("individualPanel").hidden=!c.individual;syncMidiGains();scheduleSave()}',
    "tone save"
  );
  replace(
    'function renderMidi(){const c=session.draft.midiDrumMix;$("midiMaster").value=$("midiMasterValue").value=String(Math.round(c.master*100));$("individualToggle").checked=!!c.individual;$("individualPanel").hidden=!c.individual;bindPair("midiMaster","midiMasterValue",updateMidiConfig);for(const k of ["cymbal","hihatRide","snareTom","kick","other"]){const pct=Math.round(midiGroupValue(k)*100);$(k).value=$(k+"Value").value=String(pct);bindPair(k,k+"Value",updateMidiConfig)}$("individualToggle").addEventListener("change",updateMidiConfig);document.querySelectorAll("[data-preview]").forEach(b=>b.addEventListener("click",()=>void previewMidiGroup(b.dataset.preview)))}',
    'function renderMidi(){const c=session.draft.midiDrumMix;$("midiMaster").value=$("midiMasterValue").value=String(Math.round(c.master*100));$("individualToggle").checked=!!c.individual;$("individualPanel").hidden=!c.individual;bindPair("midiMaster","midiMasterValue",updateMidiConfig);for(const k of ["cymbal","hihatRide","snareTom","kick","other"]){const pct=Math.round(midiGroupValue(k)*100),tone=$(k+"Tone");$(k).value=$(k+"Value").value=String(pct);bindPair(k,k+"Value",updateMidiConfig);if(tone){tone.value=c.tone?.[k]==="B"?"B":"A";tone.addEventListener("change",()=>{updateMidiConfig();if(tone.value==="B")status("Bセット音源は未登録です。選択値は保存されています。")})}}$("individualToggle").addEventListener("change",updateMidiConfig);document.querySelectorAll("[data-preview]").forEach(b=>b.addEventListener("click",()=>void previewMidiGroup(b.dataset.preview)))}',
    "tone ui"
  );
  replace(
    'async function previewMidiGroup(group){try{pauseMix(false);await getAC().resume();await loadDrumKit();const notes=MIDI_PREVIEW[group]||[37];',
    'async function previewMidiGroup(group){try{pauseMix(false);const tone=session.draft.midiDrumMix?.tone?.[group]==="B"?"B":"A";if(tone==="B"){status("Bセット音源は未登録です。選択値は保存されています。");return}await getAC().resume();await loadDrumKit();const notes=MIDI_PREVIEW[group]||[37];',
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
