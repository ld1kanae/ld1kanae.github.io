"use strict";

(async()=>{
  const url="js/song-volume-editor-v4.js?v=20260830-midibounds2";
  const r=await fetch(url,{cache:"no-store"});
  if(!r.ok)throw Error(`音量バランス本体を取得できません（HTTP ${r.status}）`);
  let src=await r.text();
  const replace=(from,to,label)=>{
    if(!src.includes(from))throw Error(`MIDI安全化パッチ対象が見つかりません: ${label}`);
    src=src.replace(from,to);
  };

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
