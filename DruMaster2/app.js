(()=>{
'use strict';

const CHART=Array.isArray(window.NANAIRO_CHART)?window.NANAIRO_CHART:[];
const CHART_END=CHART.length?Math.max(...CHART.map(e=>e.t))+2:263.08;
const FALLBACK_DURATION=Math.max(263.08,CHART_END);
const PATHS={
  offvocal:'songs/nanairo/nanairo-offvocal-192k.mp3',
  vocals:'songs/nanairo/nanairo-vocals-192k.mp3',
  guide:'songs/nanairo/nanairo-drums-192k.mp3',
  drumSprite:'soundset/drums/drumsound2-192k.mp3',
  drumMap:'soundset/drums/drumsound2.mid'
};
const SONG_ID='nanairo';
const BEST_KEY='DruMaster2.best.'+SONG_ID;
const NOTE_INFO={
  36:{lane:4,auto:true,label:'KICK'},
  38:{lane:3,label:'SNARE'},
  42:{lane:2,label:'CLOSED HH'},
  44:{lane:2,auto:true,label:'PEDAL HH'},
  46:{lane:2,label:'OPEN HH'},
  49:{lane:1,label:'CRASH'}
};
const KEYS={KeyF:38,KeyJ:42,KeyK:46,KeyL:49};
const PARTS={38:'drum-snare',42:'drum-hihat',46:'drum-hihat',49:'drum-crash'};
const JUDGE={perfect:55,good:115,miss:165};
const $=s=>document.querySelector(s);
const UI={
  stage:$('#stage'),notes:$('#notesLayer'),judge:$('#judgeText'),score:$('#scoreText'),combo:$('#comboText'),time:$('#timeText'),
  play:$('#playBtn'),pause:$('#pauseBtn'),restart:$('#restartBtn'),settings:$('#settingsBtn'),dialog:$('#settingsDialog'),
  vocals:$('#vocalsToggle'),guide:$('#guideToggle'),auto:$('#autoToggle'),speed:$('#speedRange'),speedValue:$('#speedValue'),
  offset:$('#offsetRange'),offsetValue:$('#offsetValue'),offsetText:$('#offsetText'),audioState:$('#audioState'),
  best:$('#bestText')
};
const STATE={
  playing:false,paused:false,score:0,best:loadBest(),combo:0,approach:2.4,offsetMs:0,judged:new Set(),active:new Map(),autoCursor:0,
  localUrls:[],demoMode:true,demoBase:0,demoStartedAt:0,audioReady:false,
  assets:{offvocal:false,vocals:false,guide:false,drumSprite:false,drumMap:false}
};
const AUDIO={offvocal:new Audio(),vocals:new Audio(),guide:new Audio()};
Object.values(AUDIO).forEach(a=>{a.preload='auto';a.crossOrigin='anonymous'});
AUDIO.offvocal.src=PATHS.offvocal;AUDIO.vocals.src=PATHS.vocals;AUDIO.guide.src=PATHS.guide;
AUDIO.offvocal.volume=.95;AUDIO.vocals.volume=.92;AUDIO.guide.volume=.62;

let audioCtx=null,drumBuffer=null;
let spriteMap=defaultSpriteMap();
const openHatSources=new Set();

function loadBest(){try{return Math.max(0,parseInt(localStorage.getItem(BEST_KEY)||'0',10)||0)}catch{return 0}}
function saveBest(){
  if(UI.auto.checked)return;
  if(STATE.score<=STATE.best)return;
  STATE.best=STATE.score;
  try{localStorage.setItem(BEST_KEY,String(STATE.best))}catch{}
}
function context(){
  if(!audioCtx)audioCtx=new(window.AudioContext||window.webkitAudioContext)({latencyHint:'interactive'});
  if(audioCtx.state==='suspended')audioCtx.resume();
  return audioCtx;
}
function defaultSpriteMap(){
  const m=new Map();
  for(let n=35;n<=81;n++)m.set(n,{start:3.75+(n-35)*2,end:3.75+(n-34)*2});
  return m;
}
function readVar(view,pos){
  let v=0,b;
  do{b=view.getUint8(pos.i++);v=(v<<7)|(b&127)}while(b&128);
  return v;
}
function parseDrumMidi(buf){
  const v=new DataView(buf),tag=o=>String.fromCharCode(...new Uint8Array(buf,o,4));
  if(tag(0)!=='MThd')throw Error('bad midi');
  const hdr=v.getUint32(4),tracks=v.getUint16(10),tpq=v.getUint16(12);
  let off=8+hdr,events=[],tempos=[{tick:0,tempo:500000}];
  for(let ti=0;ti<tracks;ti++){
    if(tag(off)!=='MTrk')throw Error('bad track');
    const len=v.getUint32(off+4),end=off+8+len,p={i:off+8};let tick=0,run=0;
    while(p.i<end){
      tick+=readVar(v,p);let st=v.getUint8(p.i++);
      if(st<128){p.i--;st=run}else run=st;
      if(st===0xff){
        const type=v.getUint8(p.i++),ln=readVar(v,p);
        if(type===0x51&&ln===3){const tempo=(v.getUint8(p.i)<<16)|(v.getUint8(p.i+1)<<8)|v.getUint8(p.i+2);tempos.push({tick,tempo})}
        p.i+=ln;continue;
      }
      if(st===0xf0||st===0xf7){p.i+=readVar(v,p);continue}
      const hi=st&0xf0,ch=st&15;
      if(hi===0xc0||hi===0xd0){p.i+=1;continue}
      const d1=v.getUint8(p.i++),d2=v.getUint8(p.i++);
      if(hi===0x90&&d2>0&&ch===9)events.push({tick,note:d1});
    }
    off=end;
  }
  tempos.sort((a,b)=>a.tick-b.tick);
  const tickToSec=t=>{
    let sec=0,last=0,tempo=tempos[0].tempo;
    for(let i=1;i<tempos.length&&tempos[i].tick<=t;i++){sec+=(tempos[i].tick-last)*tempo/1e6/tpq;last=tempos[i].tick;tempo=tempos[i].tempo}
    return sec+(t-last)*tempo/1e6/tpq;
  };
  events.sort((a,b)=>a.tick-b.tick);
  const m=new Map();
  for(let i=0;i<events.length;i++){
    const start=tickToSec(events[i].tick);
    const end=i+1<events.length?tickToSec(events[i+1].tick):Infinity;
    m.set(events[i].note,{start,end});
  }
  if(!m.size)throw Error('no drum notes');
  return m;
}
async function loadDrumMap(url=PATHS.drumMap){
  try{
    const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw 0;
    spriteMap=parseDrumMidi(await r.arrayBuffer());STATE.assets.drumMap=true;return true;
  }catch{STATE.assets.drumMap=false;return false}
}
async function loadDrumSprite(url=PATHS.drumSprite){
  try{
    const c=context(),r=await fetch(url,{cache:'no-store'});if(!r.ok)throw 0;
    drumBuffer=await c.decodeAudioData(await r.arrayBuffer());STATE.assets.drumSprite=true;return true;
  }catch{drumBuffer=null;STATE.assets.drumSprite=false;return false}
}
function segment(note){
  const s=spriteMap.get(note)||defaultSpriteMap().get(note)||{start:0,end:2};
  const end=Number.isFinite(s.end)?s.end:(drumBuffer?.duration||s.start+2);
  return {start:Math.max(0,s.start),duration:Math.max(.02,end-s.start-.004)};
}
function hitSound(note,velocity=100){
  const c=context();
  if(note===42||note===44){
    for(const src of [...openHatSources]){try{src.stop(c.currentTime+.012)}catch{}openHatSources.delete(src)}
  }
  const gain=Math.max(.18,Math.pow(Math.min(127,velocity)/127,1.45));
  if(drumBuffer){
    const seg=segment(note),src=c.createBufferSource(),g=c.createGain();
    src.buffer=drumBuffer;g.gain.value=gain;src.connect(g).connect(c.destination);
    const dur=Math.min(seg.duration,Math.max(.02,drumBuffer.duration-seg.start));
    src.start(0,seg.start,dur);
    if(note===46){openHatSources.add(src);src.onended=()=>openHatSources.delete(src)}
    return;
  }
  synth(note,gain,c);
}
function synth(note,g,c){
  const t=c.currentTime;
  if(note===38){noise(c,t,.13,g,.6);tone(c,190,105,t,.09,g*.52)}
  else if(note===42||note===44)noise(c,t,note===44?.06:.09,g,.26);
  else if(note===46)noise(c,t,.65,g,.31);
  else if(note===49){noise(c,t,1.35,g,.46);tone(c,440,170,t,.72,g*.18)}
  else if(note===36)tone(c,96,42,t,.13,g*.8);
}
function noise(c,t,d,g,b){
  const len=Math.ceil(c.sampleRate*d),buf=c.createBuffer(1,len,c.sampleRate),data=buf.getChannelData(0);
  for(let i=0;i<len;i++)data[i]=(Math.random()*2-1)*(1-i/len);
  const src=c.createBufferSource(),f=c.createBiquadFilter(),q=c.createGain();
  src.buffer=buf;f.type='highpass';f.frequency.value=b*5000+1000;q.gain.setValueAtTime(g,t);q.gain.exponentialRampToValueAtTime(.001,t+d);
  src.connect(f).connect(q).connect(c.destination);src.start(t);src.stop(t+d);
}
function tone(c,a,b,t,d,g){
  const o=c.createOscillator(),q=c.createGain();
  o.frequency.setValueAtTime(a,t);o.frequency.exponentialRampToValueAtTime(b,t+d);q.gain.setValueAtTime(g,t);q.gain.exponentialRampToValueAtTime(.001,t+d);
  o.connect(q).connect(c.destination);o.start(t);o.stop(t+d);
}
function clock(){
  if(!STATE.demoMode&&Number.isFinite(AUDIO.offvocal.currentTime))return AUDIO.offvocal.currentTime;
  if(!STATE.playing)return STATE.demoBase;
  return STATE.demoBase+(performance.now()-STATE.demoStartedAt)/1000;
}
function duration(){return (!STATE.demoMode&&Number.isFinite(AUDIO.offvocal.duration)&&AUDIO.offvocal.duration>1)?AUDIO.offvocal.duration:FALLBACK_DURATION}
function syncTracks(force=false){
  if(STATE.demoMode)return;
  const t=AUDIO.offvocal.currentTime;
  for(const a of[AUDIO.vocals,AUDIO.guide]){
    if(a.readyState<2)continue;
    if(force||Math.abs(a.currentTime-t)>.045)try{a.currentTime=t}catch{}
  }
}
async function start(){
  context();if(STATE.playing)return;
  STATE.demoMode=!STATE.audioReady;STATE.playing=true;STATE.paused=false;
  if(STATE.demoMode){STATE.demoStartedAt=performance.now();UI.audioState.textContent='DEMO MODE — 楽曲音源未配置 / 打音は仮音源'}
  else{
    syncTracks(true);AUDIO.vocals.muted=!UI.vocals.checked;AUDIO.guide.muted=!UI.guide.checked;
    try{
      await AUDIO.offvocal.play();
      if(STATE.assets.vocals)AUDIO.vocals.play().catch(()=>{});
      if(STATE.assets.guide)AUDIO.guide.play().catch(()=>{});
    }catch{
      STATE.demoMode=true;STATE.demoBase=AUDIO.offvocal.currentTime||0;STATE.demoStartedAt=performance.now();
      UI.audioState.textContent='DEMO MODE — ブラウザで楽曲再生不可';
    }
  }
  UI.play.textContent='▶ PLAYING';UI.play.disabled=true;UI.pause.disabled=false;requestAnimationFrame(frame);
}
function pause(){
  if(!STATE.playing)return;
  if(STATE.demoMode)STATE.demoBase=clock();else Object.values(AUDIO).forEach(a=>a.pause());
  STATE.playing=false;STATE.paused=true;saveBest();drawScore();
  UI.play.textContent='▶ RESUME';UI.play.disabled=false;UI.pause.disabled=true;
}
function restart(){
  saveBest();
  Object.values(AUDIO).forEach(a=>{a.pause();try{a.currentTime=0}catch{}});
  STATE.playing=false;STATE.paused=false;STATE.demoBase=0;STATE.score=0;STATE.combo=0;STATE.judged.clear();STATE.autoCursor=0;
  for(const node of STATE.active.values())node.remove();STATE.active.clear();
  drawScore();UI.play.textContent='▶ START';UI.play.disabled=false;UI.pause.disabled=true;render(0);updateTime(0);
}
function noteY(note){const lane=NOTE_INFO[note]?.lane||3;return((lane-.5)/4)*100}
function render(t){
  const rect=UI.notes.getBoundingClientRect(),judgeX=rect.width*.16,startX=rect.width+30,a=STATE.approach,min=t-.3,max=t+a+.08,visible=new Set();
  for(let i=0;i<CHART.length;i++){
    const e=CHART[i];if(e.t<min||e.t>max)continue;visible.add(i);
    let node=STATE.active.get(i);
    if(!node){node=document.createElement('i');node.className=`note n${e.n}`;node.style.top=noteY(e.n)+'%';UI.notes.appendChild(node);STATE.active.set(i,node)}
    const dt=e.t-(t+STATE.offsetMs/1000),x=judgeX+(dt/a)*(startX-judgeX);
    node.style.left=x+'px';node.style.display=STATE.judged.has(i)?'none':'block';
  }
  for(const [i,node] of [...STATE.active])if(!visible.has(i)){node.remove();STATE.active.delete(i)}
}
function frame(){
  if(!STATE.playing)return;
  const t=clock();
  if(!STATE.demoMode){AUDIO.vocals.muted=!UI.vocals.checked;AUDIO.guide.muted=!UI.guide.checked;syncTracks()}
  autoNotes(t);missNotes(t);render(t);updateTime(t);
  if(t>=duration()-.05){saveBest();pause();UI.play.textContent='▶ AGAIN'}else requestAnimationFrame(frame);
}
function autoNotes(t){
  for(let i=Math.max(0,STATE.autoCursor);i<CHART.length;i++){
    const e=CHART[i];if(e.t>t+.025){STATE.autoCursor=i;break}
    if(STATE.judged.has(i))continue;
    const info=NOTE_INFO[e.n];
    if(info&&(info.auto||UI.auto.checked)){STATE.judged.add(i);hitSound(e.n,e.v);flash(e.n)}
  }
}
function missNotes(t){
  if(UI.auto.checked)return;
  const cut=t+STATE.offsetMs/1000-JUDGE.miss/1000;
  for(let i=0;i<CHART.length;i++){
    const e=CHART[i];if(e.t>cut)break;
    if(STATE.judged.has(i)||NOTE_INFO[e.n]?.auto)continue;
    STATE.judged.add(i);judge('miss');
  }
}
function player(note){
  hitSound(note);flash(note);
  if(!STATE.playing||UI.auto.checked)return;
  const t=clock()+STATE.offsetMs/1000;let best=-1,bestAbs=Infinity;
  for(let i=0;i<CHART.length;i++){
    const e=CHART[i];if(STATE.judged.has(i)||e.n!==note)continue;
    const abs=Math.abs((t-e.t)*1000);if(abs<bestAbs){bestAbs=abs;best=i}if(e.t>t+.25)break;
  }
  if(best<0||bestAbs>JUDGE.miss)return;
  if(bestAbs<=JUDGE.good){STATE.judged.add(best);judge(bestAbs<=JUDGE.perfect?'perfect':'good')}
}
function judge(kind){
  if(kind==='perfect'){STATE.score+=1000;STATE.combo++;showJudge('PERFECT','perfect');UI.stage.classList.remove('flash-perfect');void UI.stage.offsetWidth;UI.stage.classList.add('flash-perfect')}
  else if(kind==='good'){STATE.score+=550;STATE.combo++;showJudge('GOOD','good')}
  else{STATE.combo=0;showJudge('MISS','miss')}
  saveBest();drawScore();
}
function showJudge(text,cls){UI.judge.className=`judge ${cls}`;void UI.judge.offsetWidth;UI.judge.textContent=text;UI.judge.classList.add('show')}
function flash(note){const id=PARTS[note],el=id&&document.getElementById(id);if(!el)return;el.classList.add('hit');clearTimeout(el._t);el._t=setTimeout(()=>el.classList.remove('hit'),90)}
function drawScore(){
  UI.score.textContent=String(STATE.score).padStart(7,'0');
  const best='BEST '+String(STATE.best).padStart(7,'0');
  UI.combo.textContent=UI.auto.checked?'AUTO PLAY · '+best:`${STATE.combo} COMBO · ${best}`;
  if(UI.best)UI.best.textContent=best;
}
function fmt(s){s=Math.max(0,Math.floor(s||0));return`${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`}
function updateTime(t){UI.time.textContent=`${fmt(t)} / ${fmt(duration())}`}
async function probe(){
  const checks=await Promise.all(['offvocal','vocals','guide','drumSprite','drumMap'].map(async key=>{
    try{const r=await fetch(PATHS[key],{method:'HEAD',cache:'no-store'});return[key,r.ok]}catch{return[key,false]}
  }));
  Object.assign(STATE.assets,Object.fromEntries(checks));STATE.audioReady=!!STATE.assets.offvocal;
  if(STATE.assets.drumMap)await loadDrumMap();
  if(STATE.assets.drumSprite)await loadDrumSprite();
  if(STATE.audioReady){STATE.demoMode=false;UI.audioState.textContent=STATE.assets.drumSprite?'音源 READY':'楽曲 READY / 打音は仮音源'}
  else{STATE.demoMode=true;UI.audioState.textContent='DEMO READY — STARTで無音伴奏の仮プレイ'}
}
function bindLocal(input,target){
  input.addEventListener('change',async()=>{
    const f=input.files?.[0];if(!f)return;
    const url=URL.createObjectURL(f);STATE.localUrls.push(url);
    if(target==='drumSprite'){await loadDrumSprite(url);UI.audioState.textContent='ローカル打音 READY';return}
    AUDIO[target].src=url;AUDIO[target].load();STATE.assets[target]=true;
    if(target==='offvocal'){
      await new Promise(r=>{if(AUDIO.offvocal.readyState>=2)return r();AUDIO.offvocal.addEventListener('canplay',r,{once:true});setTimeout(r,2500)});
      STATE.audioReady=true;STATE.demoMode=false;STATE.demoBase=0;UI.audioState.textContent='ローカル楽曲 READY';updateTime(0);
    }
  });
}
UI.play.onclick=start;UI.pause.onclick=pause;UI.restart.onclick=restart;UI.settings.onclick=()=>UI.dialog.showModal();
UI.speed.oninput=()=>{STATE.approach=+UI.speed.value;UI.speedValue.textContent=STATE.approach.toFixed(1)+'s'};
UI.offset.oninput=()=>{STATE.offsetMs=+UI.offset.value;const s=(STATE.offsetMs>0?'+':'')+STATE.offsetMs+'ms';UI.offsetValue.textContent=s;UI.offsetText.textContent='OFFSET '+s};
UI.vocals.onchange=()=>AUDIO.vocals.muted=!UI.vocals.checked;
UI.guide.onchange=()=>AUDIO.guide.muted=!UI.guide.checked;
UI.auto.onchange=drawScore;
document.addEventListener('keydown',e=>{
  if(e.repeat||e.target.matches('input,button'))return;
  const note=KEYS[e.code];if(note){e.preventDefault();player(note)}
  if(e.code==='Space'){e.preventDefault();STATE.playing?pause():start()}
});
document.querySelectorAll('.touch').forEach(z=>z.addEventListener('pointerdown',e=>{e.preventDefault();player(+z.dataset.hit)},{passive:false}));
bindLocal($('#localOffvocal'),'offvocal');bindLocal($('#localVocals'),'vocals');bindLocal($('#localGuide'),'guide');bindLocal($('#localDrumSprite'),'drumSprite');
AUDIO.offvocal.addEventListener('loadedmetadata',()=>updateTime(0));
window.addEventListener('beforeunload',()=>{saveBest();STATE.localUrls.forEach(URL.revokeObjectURL)});
render(0);drawScore();updateTime(0);probe();
})();