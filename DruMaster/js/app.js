"use strict";
const ASSET={midi:"songs/nanairo/chart.mid",manifest:"songs/nanairo/audio-manifest-v2.json",drums:"assets/drumsound-manifest.json"};
const MIDI_MAP={35:"kick",36:"kick",38:"snare",40:"snare",41:"floorTom",43:"floorTom",45:"midTom",47:"midTom",48:"highTom",50:"highTom",42:"hhClosed",44:"hhPedal",46:"hhOpen",49:"crash",52:"crash",55:"crash",57:"crash",51:"ride",53:"ride",59:"ride"};
const GROUP={kick:"kick",snare:"drums",floorTom:"drums",midTom:"drums",highTom:"drums",hhClosed:"hh",hhPedal:"hh",hhOpen:"hh",ride:"hh",crash:"cymbal",special:"hh"};
const PART={kick:"kick",snare:"snare",floorTom:"floorTom",midTom:"midTom",highTom:"highTom",hhClosed:"hh",hhPedal:"hh",hhOpen:"hh",ride:"ride",crash:"crash",special:"special"};
const DEFAULT_NOTE={kick:36,snare:38,floorTom:41,midTom:45,highTom:48,hhClosed:42,hhPedal:44,hhOpen:46,ride:51,crash:49,special:37};
const DEFAULT_TYPE={kick:"kick",snare:"snare",floorTom:"floorTom",midTom:"midTom",highTom:"highTom",hh:"hhClosed",ride:"ride",crash:"crash",special:"special"};
const KEY_PART={KeyQ:"crash",KeyW:"highTom",KeyE:"midTom",KeyP:"crash",KeyA:"hh",KeyS:"snare",KeyD:"special",KeyK:"floorTom",KeyL:"ride"};
// Mix correction relative to the other in-game drum sounds.
// The guide-drum backing stem keeps its own independent volume.
const DRUM_GAIN={kick:1.4,crash:1.2};
const setup=document.querySelector("#setup"),game=document.querySelector("#game"),result=document.querySelector("#result"),canvas=document.querySelector("#chart"),ctx=canvas.getContext("2d");
const $=s=>document.querySelector(s);let ac,masterBus,safetyLimiter,audioManifest,buffers={},drumBuffer=null,drumRegions={},drumSourceVelocity=100,openHatVoices=[],notes=[],duration=0,startedAt=0,rate=1,running=false,paused=false,autoplay=false,loading=false,raf=0,nextKick=0,nextAuto=0,missCursor=0,score=0,maxScore=1,counts={perfect:0,great:0,good:0,miss:0};
function parseMidi(ab){
  const d=new DataView(ab);let p=0;
  const str=n=>{let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s};
  const u32=()=>{const v=d.getUint32(p);p+=4;return v};
  const u16=()=>{const v=d.getUint16(p);p+=2;return v};
  const vlq=()=>{let v=0,b;do{b=d.getUint8(p++);v=(v<<7)|(b&127)}while(b&128);return v};
  if(str(4)!=="MThd")throw Error("MIDI形式を確認できません");
  const headerLength=u32();u16();const tracks=u16(),division=u16();p+=headerLength-6;
  const raw=[],tempos=[{tick:0,us:500000}];
  for(let t=0;t<tracks;t++){
    if(str(4)!=="MTrk")throw Error("MIDIトラックが不正です");
    const trackLength=u32(),end=p+trackLength;let tick=0,runningStatus=0;
    while(p<end){
      tick+=vlq();const next=d.getUint8(p++);let status;
      if(next<128){if(!runningStatus)throw Error("MIDIのランニングステータスが不正です");status=runningStatus;p--}
      else{status=next;if(status<240)runningStatus=status}
      if(status===255){
        const type=d.getUint8(p++),len=vlq();
        if(type===81&&len===3)tempos.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});
        p+=len;
      }else if(status===240||status===247){runningStatus=0;const len=vlq();p+=len}
      else{
        const hi=status&240,ch=status&15;
        if(hi===144||hi===128){const note=d.getUint8(p++),velocity=d.getUint8(p++);if(hi===144&&velocity>0&&ch===9)raw.push({tick,note,velocity})}
        else p+=(hi===192||hi===208)?1:2;
      }
    }
    p=end;
  }
  tempos.sort((a,b)=>a.tick-b.tick);
  const tickToSec=tick=>{let sec=0,last=0,us=500000;for(const x of tempos){if(x.tick>=tick)break;sec+=(x.tick-last)*us/division/1e6;last=x.tick;us=x.us}return sec+(tick-last)*us/division/1e6};
  return raw.map(n=>({...n,time:tickToSec(n.tick),type:MIDI_MAP[n.note]||"special",hit:false})).sort((a,b)=>a.time-b.time);
}
function setupAudioGraph(){masterBus=ac.createGain();masterBus.gain.value=.8;safetyLimiter=ac.createDynamicsCompressor();safetyLimiter.threshold.value=-8;safetyLimiter.knee.value=6;safetyLimiter.ratio.value=20;safetyLimiter.attack.value=.002;safetyLimiter.release.value=.18;masterBus.connect(safetyLimiter).connect(ac.destination)}
function fourCC(d,at){return String.fromCharCode(d.getUint8(at),d.getUint8(at+1),d.getUint8(at+2),d.getUint8(at+3))}
async function hashBuffer(ab){return [...new Uint8Array(await crypto.subtle.digest("SHA-256",ab))].map(x=>x.toString(16).padStart(2,"0")).join("")}
async function verifyStem(ab,spec,label){
  if(ab.byteLength!==spec.bytes)throw Error(`${label}音源が不完全です（${ab.byteLength.toLocaleString()} / ${spec.bytes.toLocaleString()} bytes）`);
  if(ab.byteLength<44)throw Error(`${label}音源のWAVヘッダーが不正です`);
  const d=new DataView(ab),declared=d.getUint32(4,true)+8;
  if(fourCC(d,0)!=="RIFF"||fourCC(d,8)!=="WAVE"||declared!==ab.byteLength)throw Error(`${label}音源のWAVデータが破損しています`);
  if(spec.sha256&&globalThis.crypto?.subtle){
    $("#loadState").textContent=`${label}音源を検証中…`;
    const hash=await hashBuffer(ab);
    if(hash!==spec.sha256)throw Error(`${label}音源の内容が一致しません`);
  }
}
async function fetchJoined(spec,label){
  const paths=spec.paths||Array.from({length:spec.parts},(_,i)=>`${spec.pathPrefix}${String(i).padStart(spec.digits||3,"0")}`),parts=[];
  for(let i=0;i<paths.length;i+=8){
    const batch=await Promise.all(paths.slice(i,i+8).map(p=>fetch(p,{cache:"no-store"}).then(r=>{if(!r.ok)throw Error(`${label}音源を取得できません（HTTP ${r.status}）`);return r.arrayBuffer()})));
    parts.push(...batch);$("#loadState").textContent=`${label}音源を読み込み中… ${Math.min(i+8,paths.length)}/${paths.length}`;
  }
  if(parts.length===1){await verifyStem(parts[0],spec,label);return parts[0]}
  const size=parts.reduce((n,b)=>n+b.byteLength,0),out=new Uint8Array(size);let at=0;
  for(const b of parts){out.set(new Uint8Array(b),at);at+=b.byteLength}
  await verifyStem(out.buffer,spec,label);return out.buffer;
}
async function loadStem(name,label){if(buffers[name])return;const encoded=await fetchJoined(audioManifest[name],label);buffers[name]=await ac.decodeAudioData(encoded);if(Math.abs(buffers[name].duration-duration)>.1)throw Error(`${label}音源の長さが譜面と一致しません`)}
async function loadDrumSource(manifest){
  $("#loadState").textContent="ゲーム内ドラム音源を読み込み中…";
  const [wav,midi]=await Promise.all([
    fetchJoined(manifest.wav,"ゲーム内ドラム"),
    fetch(manifest.midi.path,{cache:"no-store"}).then(r=>{if(!r.ok)throw Error(`ドラム音源MIDIを取得できません（HTTP ${r.status}）`);return r.arrayBuffer()})
  ]);
  if(midi.byteLength!==manifest.midi.bytes)throw Error("ドラム音源MIDIが不完全です");
  if(manifest.midi.sha256&&globalThis.crypto?.subtle&&(await hashBuffer(midi))!==manifest.midi.sha256)throw Error("ドラム音源MIDIの内容が一致しません");
  drumBuffer=await ac.decodeAudioData(wav);const sourceNotes=parseMidi(midi);
  if(!sourceNotes.length)throw Error("ドラム音源MIDIにノートがありません");
  if(manifest.wav.sampleRate&&drumBuffer.sampleRate!==manifest.wav.sampleRate)throw Error("ゲーム内ドラム音源のサンプルレートが一致しません");
  if(manifest.wav.channels&&drumBuffer.numberOfChannels!==manifest.wav.channels)throw Error("ゲーム内ドラム音源のチャンネル数が一致しません");
  drumSourceVelocity=manifest.sourceVelocity||100;
  drumRegions={};
  sourceNotes.forEach((n,i)=>{const end=i+1<sourceNotes.length?sourceNotes[i+1].time:drumBuffer.duration;if(n.time>=drumBuffer.duration||end<=n.time)throw Error(`ドラム音源の再生位置が不正です（MIDI ${n.note}）`);drumRegions[String(n.note)]={offset:n.time,duration:end-n.time}});
  const required=new Set([...notes.map(n=>n.note),...Object.values(DEFAULT_NOTE)]),missing=[...required].filter(note=>!drumRegions[String(note)]);
  if(missing.length)throw Error(`ゲーム内ドラム音源に必要な音がありません（MIDI ${missing.join(", ")}）`);
}
async function init(){try{const [m,manifest,drumManifest]=await Promise.all([fetch(ASSET.midi).then(r=>{if(!r.ok)throw Error(ASSET.midi);return r.arrayBuffer()}),fetch(ASSET.manifest,{cache:"no-store"}).then(r=>{if(!r.ok)throw Error(ASSET.manifest);return r.json()}),fetch(ASSET.drums,{cache:"no-store"}).then(r=>{if(!r.ok)throw Error(ASSET.drums);return r.json()})]);notes=parseMidi(m);audioManifest=manifest;duration=Math.max(...notes.map(n=>n.time),263.05);ac=new (window.AudioContext||window.webkitAudioContext)();setupAudioGraph();await loadDrumSource(drumManifest);maxScore=notes.filter(n=>n.type!=="kick").reduce((s,n)=>s+weight(n.type)*n.velocity/127,0)*1000;setKit();$("#loadState").textContent=`準備完了 · ${notes.length.toLocaleString()} notes`;$("#start").disabled=false}catch(e){console.error(e);$("#loadState").textContent=e.message||"読み込みに失敗しました"}}
function weight(t){return ["snare","highTom","midTom","floorTom"].includes(t)?1.5:["hhClosed","hhOpen","hhPedal"].includes(t)?.8:1}
function setKit(){const used=new Set(notes.map(n=>PART[n.type]));document.querySelectorAll("#hitLayer [data-part]").forEach(el=>el.classList.toggle("inactive",!used.has(el.dataset.part)));document.querySelectorAll("[data-shade]").forEach(el=>el.classList.toggle("on",!used.has(el.dataset.shade)))}
function playBuffer(buf,gain){const s=ac.createBufferSource(),g=ac.createGain();s.buffer=buf;s.playbackRate.value=rate;g.gain.value=gain;s.connect(g).connect(masterBus);s.start();return s}
function chokeOpenHat(){const now=ac.currentTime;for(const voice of openHatVoices.splice(0)){try{voice.gain.gain.cancelScheduledValues(now);voice.gain.gain.setValueAtTime(Math.max(.001,voice.gain.gain.value),now);voice.gain.gain.exponentialRampToValueAtTime(.001,now+.025);voice.source.stop(now+.03)}catch{}}}
function playDrum(note,type,v=.75){if(!ac||!drumBuffer)return;if(type==="hhClosed"||type==="hhPedal")chokeOpenHat();const region=drumRegions[String(note)]||drumRegions[String(DEFAULT_NOTE[type])];if(!region)return;const now=ac.currentTime,source=ac.createBufferSource(),gain=ac.createGain(),mix=DRUM_GAIN[type]||1,sourceVelocity=drumSourceVelocity/127,velocityGain=Math.min(1.25,Math.pow(Math.max(.04,v)/sourceVelocity,.8));source.buffer=drumBuffer;gain.gain.value=.7*velocityGain*mix;source.connect(gain).connect(masterBus);source.start(now,region.offset,region.duration);if(type==="hhOpen"){const voice={source,gain};openHatVoices.push(voice);source.onended=()=>{openHatVoices=openHatVoices.filter(x=>x!==voice)}}}
function current(){return (ac.currentTime-startedAt)*rate}
async function startGame(){if(loading)return;loading=true;$("#start").disabled=true;try{await ac.resume();await loadStem("base","オフボーカル");if($("#vocalToggle").checked)await loadStem("vocals","ボーカル");if($("#guideToggle").checked)await loadStem("drums","ガイドドラム");rate=+$("#tempo").value/100;autoplay=$("#autoToggle").checked;notes.forEach(n=>n.hit=false);score=0;counts={perfect:0,great:0,good:0,miss:0};nextKick=0;nextAuto=0;missCursor=0;setup.classList.add("hidden");result.classList.add("hidden");result.classList.toggle("autoplay",autoplay);game.classList.remove("hidden");$("#score").textContent=autoplay?"AUTO":"000000";playBuffer(buffers.base,.95);if($("#vocalToggle").checked)playBuffer(buffers.vocals,.95);if($("#guideToggle").checked)playBuffer(buffers.drums,.7);startedAt=ac.currentTime;running=true;paused=false;resize();loop()}catch(e){console.error(e);$("#loadState").textContent=e.message||"音源の読み込みに失敗しました";$("#start").disabled=false}finally{loading=false}}
function flashPart(part,el){el=el||document.querySelector(`#hitLayer [data-part="${part}"]:not(.inactive)`);if(!el)return;el.classList.remove("struck");void el.offsetWidth;el.classList.add("struck")}
function input(part,visualEl){if(!running||paused||autoplay)return;const t=current();let best=null,delta=Infinity;for(const n of notes){if(n.hit||PART[n.type]!==part||n.type==="kick")continue;const d=Math.abs(n.time-t);if(d<delta){best=n;delta=d}if(n.time>t+.16)break}const matched=best&&delta<=.16,vel=matched?best.velocity/127:.72,type=matched?best.type:DEFAULT_TYPE[part],note=matched?best.note:DEFAULT_NOTE[type];playDrum(note,type,vel);flashPart(part,visualEl);if(!matched)return;best.hit=true;let mult,label;if(delta<=.055){mult=1;label="PERFECT";counts.perfect++}else if(delta<=.105){mult=.75;label="GREAT";counts.great++}else{mult=.4;label="GOOD";counts.good++}score+=weight(best.type)*best.velocity/127*1000*mult;$("#score").textContent=String(Math.round(score/maxScore*1000000)).padStart(6,"0");showJudge(label)}
function showJudge(s){const fx=$("#judgementFx"),j=$("#judge");j.textContent=s;fx.dataset.grade=s.toLowerCase();fx.classList.remove("play");void fx.offsetWidth;fx.classList.add("play")}
function resize(){const r=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;canvas.width=r.width*dpr;canvas.height=r.height*dpr;ctx.setTransform(dpr,0,0,dpr,0,0)}
function draw(){const w=canvas.clientWidth,h=canvas.clientHeight,t=current(),judgeX=w*.09,laneH=h/4,travel=4.2;ctx.clearRect(0,0,w,h);ctx.fillStyle="#0b1017";ctx.fillRect(0,0,w,h);ctx.strokeStyle="#28313d";ctx.lineWidth=1;for(let i=1;i<4;i++){ctx.beginPath();ctx.moveTo(0,laneH*i);ctx.lineTo(w,laneH*i);ctx.stroke()}ctx.fillStyle="#5e6876";ctx.font=`${Math.max(8,laneH*.16)}px sans-serif`;["CYMBAL","HI-HAT / RIDE / OTHER","SNARE / TOMS","BASS DRUM · AUTO"].forEach((s,i)=>ctx.fillText(s,6,laneH*i+12));ctx.strokeStyle="#ecf3fb";ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(judgeX,0);ctx.lineTo(judgeX,h);ctx.stroke();for(const n of notes){if(n.hit||n.time<t-.25||n.time>t+travel)continue;const x=judgeX+(n.time-t)/travel*(w-judgeX+35),group=GROUP[n.type],lane=group==="cymbal"?0:group==="hh"?1:group==="drums"?2:3,y=laneH*(lane+.58),alpha=.45+.55*n.velocity/127;ctx.globalAlpha=alpha;ctx.lineWidth=Math.max(3,laneH*.07);ctx.strokeStyle=ctx.fillStyle=n.type==="snare"?"#38a9ff":n.type.includes("Tom")?"#ad82ff":group==="cymbal"?"#ffd45a":group==="hh"?"#52dfcf":"#9da5af";ctx.font=`900 ${Math.max(21,laneH*.45)}px sans-serif`;ctx.textAlign="center";ctx.textBaseline="middle";if(n.type==="snare"||n.type.includes("Tom")){ctx.beginPath();ctx.arc(x,y,Math.max(9,laneH*.18),0,Math.PI*2);ctx.fill()}else if(n.type==="hhClosed"||n.type==="hhPedal")ctx.fillText("│",x,y);else if(n.type==="hhOpen")ctx.fillText("||",x,y);else if(n.type==="ride")ctx.fillText("△",x,y);else if(n.type==="crash")ctx.fillText("×",x,y);else if(n.type==="kick"){ctx.globalAlpha=.22+.25*n.velocity/127;ctx.font=`900 ${Math.max(25,laneH*.55)}px sans-serif`;ctx.fillText("┃",x,y)}else ctx.fillText("◇",x,y)}ctx.globalAlpha=1;ctx.textAlign="start"}
function loop(){if(!running||paused)return;const t=current();while(nextKick<notes.length&&notes[nextKick].time<=t+.012){const n=notes[nextKick++];if(n.type==="kick"&&n.time>=t-.04){playDrum(n.note,n.type,n.velocity/127);const e=$("#kickFx");e.classList.remove("hit");void e.offsetWidth;e.classList.add("hit")}}if(autoplay){let played=false;while(nextAuto<notes.length&&notes[nextAuto].time<=t+.012){const n=notes[nextAuto++];if(n.type!=="kick"&&!n.hit){n.hit=true;playDrum(n.note,n.type,n.velocity/127);flashPart(PART[n.type]);played=true}}if(played)showJudge("AUTO")}else{let missed=false;while(missCursor<notes.length&&notes[missCursor].time<t-.18){const n=notes[missCursor++];if(n.type!=="kick"&&!n.hit){n.hit=true;counts.miss++;missed=true}}if(missed)showJudge("MISS")}draw();if(t>=duration+.5)finish();else raf=requestAnimationFrame(loop)}
function finish(){running=false;cancelAnimationFrame(raf);game.classList.add("hidden");result.classList.remove("hidden");const s=Math.round(score/maxScore*1000000),stored=+(localStorage.drumusterBest||0),best=autoplay?stored:Math.max(s,stored);if(!autoplay)localStorage.drumusterBest=best;$("#finalScore").textContent=autoplay?"AUTO PLAY":String(s).padStart(6,"0");$("#bestScore").textContent=String(best).padStart(6,"0");$("#perfectCount").textContent=counts.perfect;$("#greatCount").textContent=counts.great;$("#goodCount").textContent=counts.good;$("#missCount").textContent=counts.miss}
function stop(){running=false;cancelAnimationFrame(raf);location.reload()}
function setPauseTransport(state,label){const b=$("#pause");for(const n of [...b.childNodes])if(n.nodeType===Node.TEXT_NODE)n.remove();b.querySelectorAll(":scope > .pause-transport-icon").forEach(n=>n.remove());b.dataset.transportIcon=state;b.setAttribute("aria-label",label)}
async function togglePause(forceResume=false){if(!running)return;if(!paused&&!forceResume){paused=true;cancelAnimationFrame(raf);await ac.suspend();$("#pausePanel").classList.remove("hidden");setPauseTransport("play","再生を再開")}else{await ac.resume();paused=false;$("#pausePanel").classList.add("hidden");setPauseTransport("pause","一時停止");loop()}}
document.querySelectorAll("#hitLayer [data-part]").forEach(b=>{b.addEventListener("pointerdown",e=>{e.preventDefault();input(b.dataset.part,b)})});
addEventListener("keydown",e=>{if(e.repeat||!KEY_PART[e.code])return;const key=e.code.slice(3),el=document.querySelector(`#hitLayer [data-key="${key}"]:not(.inactive)`);if(!el)return;e.preventDefault();const part=KEY_PART[e.code];el.classList.add("pressed");input(part,el)});
addEventListener("keyup",e=>{if(!KEY_PART[e.code])return;const key=e.code.slice(3);document.querySelector(`#hitLayer [data-key="${key}"]`)?.classList.remove("pressed")});
$("#tempo").addEventListener("input",e=>$("#tempoValue").textContent=e.target.value+"%");[$("#vocalToggle"),$("#guideToggle"),$("#autoToggle")].forEach(x=>x.addEventListener("change",()=>x.closest("label").querySelector("b").textContent=x.checked?"ON":"OFF"));$("#start").onclick=startGame;$("#retry").onclick=()=>location.reload();$("#quit").onclick=stop;$("#pause").onclick=()=>togglePause();$("#resume").onclick=()=>togglePause(true);addEventListener("resize",resize);init();
