import {transcribe} from './transcribe.js?v=20260923-gmd-kst-section-v1';
import {midiFile} from './midi.js?v=20260923-grid-v29';
import {buildRhythmGrid,GRID_PPQ} from './rhythm-grid.js?v=20260923-grid-v29';
import {inferBars,parseBeatThis} from './meter.js';
const $=id=>document.getElementById(id), status=$('status');
let file=null,decoded=null,events=[],midiEvents=[],context=null,playing=false,position=0,startAt=0,timer=0,next=0,source=null,active=[],samples=new Map(),loadingSamples=null,downloadUrl=null;
let exampleId='',offvocalDecoded=null;
const kstPolicy=new URLSearchParams(location.search).get('kstPolicy')||'baseline';
const tracks={audio:{volume:1,solo:false,mute:false,gain:null},midi:{volume:1,solo:false,mute:false,gain:null}};
const samplePath='../DruMaster/assets/drums/';
const groupNotes=[36,38,42,44,45,46,49,51];
function tell(message,error=false){status.textContent=message;status.classList.toggle('error',error);}
function fmt(t){t=Math.max(0,Math.floor(t||0));return `${String(Math.floor(t/60)).padStart(2,'0')}:${String(t%60).padStart(2,'0')}`;}
function select(f){if(!f)return;pause();if(downloadUrl)URL.revokeObjectURL(downloadUrl);downloadUrl=null;file=f;exampleId='';offvocalDecoded=null;decoded=null;events=[];midiEvents=[];$('result').hidden=true;$('fileName').textContent=f.name;$('analyze').disabled=false;$('example').value='';tell(`${f.name} を選択しました。`);}
$('file').addEventListener('change',e=>select(e.target.files[0]));
const drop=$('drop');
for(const name of ['dragenter','dragover'])drop.addEventListener(name,e=>{e.preventDefault();drop.classList.add('dragging');});
for(const name of ['dragleave','drop'])drop.addEventListener(name,e=>{e.preventDefault();drop.classList.remove('dragging');});
drop.addEventListener('drop',e=>select(Array.from(e.dataTransfer.files).find(f=>f.type.startsWith('audio/')||/\.(wav|mp3|m4a|ogg|flac)$/i.test(f.name))));
$('example').addEventListener('change',async e=>{
  const id=e.target.value;if(!id)return;
  $('analyze').disabled=true;tell('検証用音源を取得中…');
  try{
    const r=await fetch(`../DruMaster/songs/${id}/drums.mp3`);if(!r.ok)throw Error(`HTTP ${r.status}`);
    const blob=await r.blob();
    select(new File([blob],`${id}-drums.mp3`,{type:'audio/mpeg'}));
    exampleId=id;
    $('example').value=id;
    $('bpm').value='';
  }catch(err){
    tell(`音源を取得できませんでした: ${err.message}`,true);
    $('analyze').disabled=!file;
  }
});
async function audioContext(){if(!context){context=new AudioContext();tracks.audio.gain=context.createGain();tracks.midi.gain=context.createGain();tracks.audio.gain.connect(context.destination);tracks.midi.gain.connect(context.destination);}await context.resume();return context;}
$('analyze').addEventListener('click',async()=>{
  if(!file)return;pause();$('analyze').disabled=true;$('progress').hidden=false;$('progress').value=0;
  try{
    const ac=await audioContext();tell('音源を読み込み中…');
    decoded=await ac.decodeAudioData(await file.arrayBuffer());
    if(decoded.duration>900)throw Error('15分以内の音源を選択してください。');
    const rawBpm=$('bpm').value.trim();
    const bpm=rawBpm?Number(rawBpm):null;
    if(rawBpm&&(!Number.isFinite(bpm)||bpm<30||bpm>300))throw Error('基準BPMは30〜300で入力してください。');
    if(exampleId&&kstPolicy==='egmd-style-kicktom'){
      try{
        tell('offvocalから曲構造を準備中…');
        const ov=await fetch(`../DruMaster/songs/${exampleId}/offvocal.mp3`);
        if(ov.ok)offvocalDecoded=await ac.decodeAudioData(await ov.arrayBuffer());
      }catch(err){console.warn('offvocal context unavailable',err);offvocalDecoded=null;}
    }
    const transcription=await transcribe(decoded,(message,p)=>{tell(message);$('progress').value=p;},{
      bpm,kstPolicy,offvocalDecoded
    });
    events=transcription.events;
    const detectedBpm=transcription.bpm;
    position=0;$('result').hidden=false;
    if(downloadUrl)URL.revokeObjectURL(downloadUrl);
    const numerator=Number(transcription.numerator)||4,denominator=Number(transcription.denominator)||4;
    const beatSec=60/detectedBpm*4/denominator,barSec=beatSec*numerator;
    const phaseRaw=Number(transcription.barPhaseSec);
    const barPhaseSec=Number.isFinite(phaseRaw)?((phaseRaw%barSec)+barSec)%barSec:null;
    let meter={bars:[],variableMeterEnabled:false,externalDownbeats:0};
    if(['arcaround','diamondvirgin','kaiju'].includes(exampleId)&&Number.isFinite(barPhaseSec)){
      // These beat positions were extracted from the example's fullmix audio.
      // No chart.mid is read while transcribing. Other inputs retain 4/4.
      const beatFile=exampleId==='arcaround'?`beatthis-v17/${exampleId}-fullmix.beats`:`beatthis-v18/${exampleId}-fullmix.beats`;
      const response=await fetch(`./experiments/${beatFile}`);
      if(response.ok)meter=inferBars(events,detectedBpm,barPhaseSec,decoded.duration,parseBeatThis(await response.text()));
    }
    const rhythmGrid=buildRhythmGrid(events,detectedBpm,{barPhaseSec,numerator,denominator,bars:meter.bars});
    const exportOffsetSec=rhythmGrid.exportOffsetSec,exportBarPad=rhythmGrid.barPad;
    const ticksPerBeat=GRID_PPQ*4/denominator;
    midiEvents=events.map((e,i)=>{
      const tick=Number(rhythmGrid.eventTicks?.[i])||0;
      const scoreBeat=tick/ticksPerBeat;
      const exportTime=typeof rhythmGrid.timeForScore==='function'?rhythmGrid.timeForScore(scoreBeat):e.time+exportOffsetSec;
      return {...e,time:exportTime-exportOffsetSec};
    });
    const timingDiffMs=midiEvents.map((e,i)=>Math.abs(e.time-events[i].time)*1000).sort((a,b)=>a-b);
    const timingMedianMs=timingDiffMs[Math.floor(timingDiffMs.length*.5)]||0;
    const timingP95Ms=timingDiffMs[Math.floor(Math.max(0,timingDiffMs.length-1)*.95)]||0;
    downloadUrl=URL.createObjectURL(new Blob([midiFile(events,detectedBpm,{
      barPhaseSec,
      numerator,
      denominator,
      bars:meter.bars,
      rhythmGrid
    })],{type:'audio/midi'}));
    $('download').href=downloadUrl;$('download').download=`${file.name.replace(/\.[^.]+$/,'')}-drumscribe.mid`;
    $('previewTitle').textContent=file.name;
    const gridInfo=rhythmGrid.info||{};
    const tempoText=Number.isFinite(gridInfo.tempoMin)&&Number.isFinite(gridInfo.tempoMax)?` / 書出BPM ${gridInfo.tempoMin.toFixed(3)}–${gridInfo.tempoMax.toFixed(3)} (${gridInfo.tempoEvents}点)`:'';
    $('resultSummary').textContent=`${fmt(decoded.duration)} / 基準BPM ${detectedBpm.toFixed(3)}${tempoText} / 格子 ${gridInfo.subdivision||'未判定'} / ${events.length} ノート / キック ${events.filter(e=>e.note===36).length}・スネア ${events.filter(e=>e.note===38).length}・クローズHH ${events.filter(e=>e.note===42).length}・オープンHH ${events.filter(e=>e.note===46).length}・ペダルHH ${events.filter(e=>e.note===44).length}・クラッシュ ${events.filter(e=>e.note===49).length}・ライド ${events.filter(e=>e.note===51).length}`;
    globalThis.__drumscribeResult={
      ...transcription,events:undefined,kstPolicy,
      barPhaseSec,exportOffsetSec,exportBarPad,barSec,beatSec,
      rhythmGridInfo:{...gridInfo,previewMedianDifferenceMs:timingMedianMs,previewP95DifferenceMs:timingP95Ms},
      meterInfo:{variableMeterEnabled:meter.variableMeterEnabled,externalDownbeats:meter.externalDownbeats,threeFourBars:meter.bars.filter(b=>b.numerator===3).length}
    };
    tell(`${events.length} ノートを推定しました。基準BPM ${detectedBpm.toFixed(3)}。${gridInfo.subdivision||'格子未判定'}へ量子化し、${gridInfo.tempoEvents||1}個のテンポ点で音源の揺れを保持しました。プレビューも書き出しMIDIと同じ時刻です。${meter.variableMeterEnabled?`推定3/4小節 ${meter.bars.filter(b=>b.numerator===3).length}。`:''}`);
    draw();updateClock();loadingSamples=loadSamples();
  }catch(err){console.error(err);tell(`採譜できませんでした: ${err.message}`,true);}
  finally{$('analyze').disabled=false;$('progress').hidden=true;}
});
async function loadSamples(){
  let failed=0;await Promise.all(groupNotes.map(async n=>{
    if(samples.has(n))return;
    try{const r=await fetch(`${samplePath}${n}.wav`);if(!r.ok)throw Error(`HTTP ${r.status}`);
      samples.set(n,await context.decodeAudioData(await r.arrayBuffer()));
    }catch(err){console.warn('sample',n,err);failed++;}
  }));
  if(failed)tell(`参考ドラム音源のうち${failed}種類を読み込めませんでした。MIDI書き出しは可能です。`,true);
}
function now(){return playing?Math.max(0,Math.min(decoded.duration,position+context.currentTime-startAt)):position;}
function gainUpdate(){const solo=Object.values(tracks).some(t=>t.solo);for(const t of Object.values(tracks))if(t.gain)t.gain.gain.value=t.volume*(t.mute||solo&&!t.solo?0:1);}
function stopNodes(){try{source?.stop();}catch{}source?.disconnect();source=null;for(const n of active){try{n.stop();}catch{}n.disconnect();}active=[];}
function pause(){if(playing)position=now();playing=false;clearInterval(timer);timer=0;stopNodes();$('play').textContent='▶ 再生';draw();updateClock();}
function seek(time){const resume=playing;pause();position=Math.max(0,Math.min(decoded?.duration||0,time));if(resume)void play();else{draw();updateClock();}}
async function play(){
  if(!decoded)return;if(playing){pause();return;}
  const ac=await audioContext();if(position>=decoded.duration-.03)position=0;
  if(loadingSamples)await loadingSamples;
  gainUpdate();startAt=ac.currentTime+.07;playing=true;
  source=ac.createBufferSource();source.buffer=decoded;source.connect(tracks.audio.gain);source.start(startAt,position);
  const offset=Number($('offset').value||0)/1000;
  next=midiEvents.findIndex(e=>e.time+offset>=position-.03);if(next<0)next=midiEvents.length;
  timer=setInterval(()=>{
    if(!playing)return;
    const end=now()+.15;
    while(next<midiEvents.length&&midiEvents[next].time+offset<=end){
      const e=midiEvents[next++],buffer=samples.get(e.note);if(!buffer||e.time+offset<now()-.04)continue;
      const node=ac.createBufferSource(),velocity=ac.createGain();node.buffer=buffer;
      velocity.gain.value=Math.min(1.3,(e.velocity||90)/100);node.connect(velocity).connect(tracks.midi.gain);
      node.start(Math.max(ac.currentTime, startAt+e.time+offset-position));active.push(node);
      node.onended=()=>{node.disconnect();velocity.disconnect();active=active.filter(n=>n!==node);};
    }
    if(now()>=decoded.duration-.01){position=0;pause();}
  },25);
  $('play').textContent='❚❚ 一時停止';requestAnimationFrame(tick);
}
function tick(){if(!playing)return;updateClock();draw();requestAnimationFrame(tick);}
function updateClock(){if(!decoded)return;const n=now();$('clock').textContent=`${fmt(n)} / ${fmt(decoded.duration)}`;$('seek').value=Math.round(n/decoded.duration*1000);}
$('play').addEventListener('click',()=>void play());$('stop').addEventListener('click',()=>{pause();position=0;draw();updateClock();});
$('seek').addEventListener('input',e=>seek(Number(e.target.value)/1000*(decoded?.duration||0)));
$('offset').addEventListener('change',()=>{if(playing){const t=now();pause();position=t;void play();}draw();});
for(const el of document.querySelectorAll('.track')){
  const t=tracks[el.dataset.track],slider=el.querySelector('.volume');
  slider.addEventListener('input',()=>{t.volume=Number(slider.value)/100;el.querySelector('output').textContent=`${slider.value}%`;gainUpdate();});
  for(const kind of ['solo','mute'])el.querySelector(`.${kind}`).addEventListener('click',e=>{t[kind]=!t[kind];e.currentTarget.setAttribute('aria-pressed',String(t[kind]));gainUpdate();});
}
const canvas=$('timeline');canvas.addEventListener('click',e=>{if(!decoded)return;seek((e.clientX-canvas.getBoundingClientRect().left)/canvas.clientWidth*decoded.duration);});
new ResizeObserver(()=>draw()).observe(canvas);
function draw(){
  const bounds=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1,w=Math.max(1,Math.round(bounds.width*dpr)),h=Math.round(180*dpr);
  if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
  const c=canvas.getContext('2d');c.fillStyle='#081625';c.fillRect(0,0,w,h);if(!decoded)return;
  c.strokeStyle='#1d3446';c.lineWidth=dpr;
  for(let i=0;i<=10;i++){const x=i*w/10;c.beginPath();c.moveTo(x,0);c.lineTo(x,h);c.stroke();}
  const data=decoded.getChannelData(0),step=Math.max(1,Math.floor(data.length/w));c.strokeStyle='#58cfdb';c.globalAlpha=.85;c.beginPath();
  for(let x=0;x<w;x++){let peak=0;for(let j=x*step;j<Math.min(data.length,(x+1)*step);j+=Math.max(1,Math.floor(step/30)))peak=Math.max(peak,Math.abs(data[j]));
    c.moveTo(x,h*.32-peak*h*.27);c.lineTo(x,h*.32+peak*h*.27);
  }c.stroke();c.globalAlpha=1;
  c.fillStyle='#203144';c.fillRect(0,h*.64,w,h*.36);
  const colors={kick:'#62d9e2',snare:'#fd9b8e',hat:'#c4a2ff',open_hat:'#d5baff',pedal_hat:'#a98be2',tom:'#e8ca83',crash:'#8dd3a0',ride:'#78b7a1'},offset=Number($('offset').value||0)/1000;
  for(const e of midiEvents){const x=(e.time+offset)/decoded.duration*w;if(x<0||x>w)continue;const lane={kick:0,snare:1,hat:2,open_hat:2,pedal_hat:2,tom:3,crash:4,ride:4}[e.group];c.fillStyle=colors[e.group];c.fillRect(x,h*(.655+lane*.058),Math.max(1.5*dpr,w/1500),4*dpr);}
  const cursor=now()/decoded.duration*w;c.fillStyle='#eaf7fc';c.fillRect(cursor,0,2*dpr,h);
}
