"use strict";

(()=>{
  const DB_NAME="drumasterSongPublishV1",STORE="sessions",DB_VERSION=1;
  const params=new URLSearchParams(location.search),sessionId=params.get("session"),songId=params.get("song");
  const $=id=>document.getElementById(id);
  const STEM_DEFAULT={fullmix:.95,base:.95,vocals:.95,drums:.70};
  const MIDI_DEFAULT={master:1,individual:false,cymbal:1.2,hihatRide:1,snareTom:1,kick:1.4,other:1};
  const MIDI_PREVIEW={cymbal:[49],hihatRide:[42,51],snareTom:[38,45],kick:[36],other:[37]};
  let session=null,saveTimer=0,ac=null,media={},drumBuffer=null,drumRegions=null,drumLoadPromise=null;

  function openDb(){return new Promise((resolve,reject)=>{const r=indexedDB.open(DB_NAME,DB_VERSION);r.onupgradeneeded=()=>{const db=r.result;if(!db.objectStoreNames.contains(STORE))db.createObjectStore(STORE,{keyPath:"sessionId"})};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error||Error("編集セッションDBを開けませんでした"))})}
  async function getSession(){const db=await openDb();return new Promise((resolve,reject)=>{const tx=db.transaction(STORE,"readonly"),r=tx.objectStore(STORE).get(sessionId);r.onsuccess=()=>resolve(r.result||null);r.onerror=()=>reject(r.error);tx.oncomplete=()=>db.close()})}
  async function putSession(){const db=await openDb();return new Promise((resolve,reject)=>{const tx=db.transaction(STORE,"readwrite");tx.objectStore(STORE).put(session);tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>{db.close();reject(tx.error)}})}
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  function status(text,ok=false){$("status").textContent=text;$("status").classList.toggle("ok",ok)}
  function scheduleSave(){clearTimeout(saveTimer);$("saveState").textContent="保存中…";saveTimer=setTimeout(async()=>{try{await putSession();$("saveState").textContent="保存済み";parent!==window&&parent.postMessage({type:"dm-volume-updated",id:songId},location.origin)}catch(e){console.error(e);$("saveState").textContent="保存失敗"}},100)}
  function ensureConfig(){
    session.draft.mix={...(session.draft.mix||{})};
    const existing=session.draft.midiDrumMix||{};
    session.draft.midiDrumMix={...MIDI_DEFAULT,...existing,individual:!!existing.individual};
  }
  function stemKeys(){
    const s=session?.draft?.stems||{},available=[];
    if(session.draft.fullMixOnly&&s.fullmix)return ["fullmix"];
    if(s.base)available.push("base");if(s.vocals)available.push("vocals");if(s.drums)available.push("drums");
    if(!available.length&&s.fullmix)available.push("fullmix");
    return available;
  }
  function stemLabel(k){return {fullmix:"原曲",base:"オフボーカル",vocals:"ボーカル",drums:"ガイドドラム"}[k]||k}
  function stemValue(k){const v=Number(session.draft.mix?.[k]);return Number.isFinite(v)?v:STEM_DEFAULT[k]}
  function setStemValue(k,pct){const v=clamp(Number(pct)||0,0,150)/100;session.draft.mix[k]=Number(v.toFixed(3));if(media[k]?.gain)media[k].gain.gain.value=v;scheduleSave()}
  function renderStemRows(){
    const host=$("stemRows");host.replaceChildren();
    for(const key of stemKeys()){
      const pct=Math.round(stemValue(key)*100),row=document.createElement("div");row.className="row";row.innerHTML=`<label>${stemLabel(key)}</label><input id="stem-${key}" type="range" min="0" max="150" step="1" value="${pct}"><input id="stem-${key}-value" class="value" type="number" min="0" max="150" step="1" value="${pct}"><button class="preview" data-stem-preview="${key}" type="button">試聴</button>`;host.appendChild(row);
      bindPair(`stem-${key}`,`stem-${key}-value`,v=>setStemValue(key,v));
      row.querySelector("[data-stem-preview]").addEventListener("click",()=>previewStem(key));
    }
  }
  function bindPair(rangeId,valueId,onValue){
    const range=$(rangeId),value=$(valueId);if(!range||!value)return;
    const apply=(raw,fromRange)=>{const min=Number(range.min),max=Number(range.max),v=clamp(Number(raw)||0,min,max);range.value=String(v);value.value=String(v);onValue(v);if(!fromRange)value.select?.()};
    range.addEventListener("input",()=>apply(range.value,true));value.addEventListener("change",()=>apply(value.value,false));value.addEventListener("keydown",e=>{if(e.key==="Enter")value.blur()});
  }
  function midiGroupValue(k){const v=Number(session.draft.midiDrumMix[k]);return Number.isFinite(v)?v:MIDI_DEFAULT[k]}
  function updateMidiConfig(){
    const c=session.draft.midiDrumMix;c.master=Number((Number($("midiMaster").value)/100).toFixed(3));c.individual=$("individualToggle").checked;
    for(const k of ["cymbal","hihatRide","snareTom","kick","other"])c[k]=Number((Number($(k).value)/100).toFixed(3));
    $("individualPanel").hidden=!c.individual;scheduleSave();
  }
  function renderMidi(){
    const c=session.draft.midiDrumMix;$("midiMaster").value=$("midiMasterValue").value=String(Math.round(c.master*100));$("individualToggle").checked=!!c.individual;$("individualPanel").hidden=!c.individual;
    bindPair("midiMaster","midiMasterValue",updateMidiConfig);
    for(const k of ["cymbal","hihatRide","snareTom","kick","other"]){const pct=Math.round(midiGroupValue(k)*100);$(k).value=$(k+"Value").value=String(pct);bindPair(k,k+"Value",updateMidiConfig)}
    $("individualToggle").addEventListener("change",updateMidiConfig);
    document.querySelectorAll("[data-preview]").forEach(b=>b.addEventListener("click",()=>previewMidiGroup(b.dataset.preview)));
  }
  function getAC(){return ac||(ac=new (window.AudioContext||window.webkitAudioContext)({latencyHint:"interactive"}))}
  async function ensureMedia(key){
    if(media[key])return media[key];
    let blob=session.originals?.[key];
    if(!blob){
      const path=session.draft?.stems?.[key]?.path;
      if(!path)throw Error(`${stemLabel(key)}の音源がありません`);
      const r=await fetch(path,{cache:"no-store"});
      if(!r.ok)throw Error(`${stemLabel(key)}の既存音源を取得できません（HTTP ${r.status}）`);
      blob=await r.blob();
    }
    const audio=new Audio(URL.createObjectURL(blob));audio.preload="auto";const context=getAC(),source=context.createMediaElementSource(audio),gain=context.createGain();gain.gain.value=stemValue(key);source.connect(gain).connect(context.destination);media[key]={audio,source,gain};return media[key];
  }
  async function previewStem(key){try{await getAC().resume();const m=await ensureMedia(key);for(const x of Object.values(media)){x.audio.pause();x.audio.currentTime=0}m.audio.currentTime=0;await m.audio.play();setTimeout(()=>{if(!m.audio.paused){m.audio.pause();m.audio.currentTime=0}},3000)}catch(e){console.error(e);status(e.message||String(e))}}
  async function playMix(){
    try{await getAC().resume();const list=[];for(const key of stemKeys())list.push(await ensureMedia(key));for(const m of list){m.audio.pause();m.audio.currentTime=0}await Promise.all(list.map(m=>m.audio.play()));$("mixStop").disabled=false;status("MIXを再生中")}
    catch(e){console.error(e);status(e.message||String(e))}
  }
  function stopMix(){for(const m of Object.values(media)){m.audio.pause();try{m.audio.currentTime=0}catch{}}status("停止しました")}
  function parseSourceMidi(ab){
    const d=new DataView(ab);let p=0;const str=n=>{let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s},u32=()=>{const v=d.getUint32(p);p+=4;return v},u16=()=>{const v=d.getUint16(p);p+=2;return v},vlq=()=>{let v=0,b;do{b=d.getUint8(p++);v=(v<<7)|(b&127)}while(b&128);return v};if(str(4)!=="MThd")throw Error("ドラム音源MIDIが不正です");const hl=u32();u16();const tracks=u16(),division=u16();p=8+hl;const raw=[],tempos=[{tick:0,us:500000}];for(let t=0;t<tracks;t++){if(str(4)!=="MTrk")throw Error("ドラム音源MIDIが不正です");const len=u32(),end=p+len;let tick=0,run=0;while(p<end){tick+=vlq();let first=d.getUint8(p++),status;if(first<128){status=run;p--}else{status=first;if(status<240)run=status}if(status===255){const type=d.getUint8(p++),n=vlq();if(type===81&&n===3)tempos.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});p+=n}else if(status===240||status===247){run=0;p+=vlq()}else{const hi=status&240,ch=status&15,bytes=(hi===192||hi===208)?1:2,a=d.getUint8(p++),b=bytes===2?d.getUint8(p++):0;if(hi===144&&b>0&&ch===9)raw.push({tick,note:a})}}p=end}tempos.sort((a,b)=>a.tick-b.tick);const toSec=tick=>{let sec=0,last=0,us=500000;for(const x of tempos){if(x.tick>=tick)break;sec+=(x.tick-last)*us/division/1e6;last=x.tick;us=x.us}return sec+(tick-last)*us/division/1e6};return raw.map(n=>({note:n.note,time:toSec(n.tick)})).sort((a,b)=>a.time-b.time)}
  async function loadDrumKit(){
    if(drumBuffer&&drumRegions)return;if(drumLoadPromise)return drumLoadPromise;
    drumLoadPromise=(async()=>{status("ゲーム内ドラム音源を読み込み中…");const manifest=await fetch("assets/drumsound-manifest.json",{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error("ドラム音源設定を取得できません");return r.json()}),paths=Array.from({length:manifest.wav.parts},(_,i)=>`${manifest.wav.pathPrefix}${String(i).padStart(manifest.wav.digits||3,"0")}`),parts=[];for(let i=0;i<paths.length;i+=8){parts.push(...await Promise.all(paths.slice(i,i+8).map(p=>fetch(p,{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error("ドラム音源を取得できません");return r.arrayBuffer()}))))}const size=parts.reduce((n,b)=>n+b.byteLength,0),joined=new Uint8Array(size);let at=0;for(const p of parts){joined.set(new Uint8Array(p),at);at+=p.byteLength}const midi=await fetch(manifest.midi.path,{cache:"force-cache"}).then(r=>r.arrayBuffer()),sourceNotes=parseSourceMidi(midi);drumBuffer=await getAC().decodeAudioData(joined.buffer.slice(0));drumRegions={};sourceNotes.forEach((n,i)=>{const end=i+1<sourceNotes.length?sourceNotes[i+1].time:drumBuffer.duration;drumRegions[String(n.note)]={offset:n.time,duration:Math.max(.03,end-n.time)}});status("調整値は自動保存されます。",true)})();return drumLoadPromise;
  }
  function effectiveMidiGroup(group){const c=session.draft.midiDrumMix;if(!c.individual)return MIDI_DEFAULT[group];return midiGroupValue(group)}
  async function previewMidiGroup(group){
    try{await getAC().resume();await loadDrumKit();const notes=MIDI_PREVIEW[group]||[37],master=Number(session.draft.midiDrumMix.master)||0,groupGain=effectiveMidiGroup(group);notes.forEach((note,i)=>{const region=drumRegions[String(note)];if(!region)return;const source=getAC().createBufferSource(),gain=getAC().createGain(),when=getAC().currentTime+.02+i*.25;source.buffer=drumBuffer;gain.gain.value=.85*master*groupGain;source.connect(gain).connect(getAC().destination);source.start(when,region.offset,region.duration)})}catch(e){console.error(e);status(e.message||String(e))}
  }
  async function init(){
    try{if(!sessionId||!songId)throw Error("編集セッションがありません");session=await getSession();if(!session||session.id!==songId)throw Error("ローカル編集セッションが見つかりません");ensureConfig();$("songTitle").textContent=`${session.draft.title} — ${session.draft.artist}`;renderStemRows();renderMidi();await putSession();$("mixPlay").disabled=false;$("mixStop").disabled=false;status("調整値は自動保存されます。",true);$("saveState").textContent="保存済み"}catch(e){console.error(e);status(e.message||String(e));$("saveState").textContent="ERROR"}}
  $("mixPlay").addEventListener("click",playMix);$("mixStop").addEventListener("click",stopMix);addEventListener("beforeunload",stopMix);init();
})();
