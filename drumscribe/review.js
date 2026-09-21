const $=id=>document.getElementById(id);
const STORE='drumscribe-review-v1';
const SAMPLE_ROOT='../DruMaster/assets/drums/';
let manifest,currentCandidate,currentSong,metricCache=new Map(),midiCache=new Map(),sampleCache=new Map();
let ctx,gainNode,playback=null,refreshVersion=0,currentMidiInfo={count:0,first:null};
let playbackStats={loaded:0,failed:0,scheduled:0,song:null,candidate:null,autoJumped:false};

function readStore(){
  try{return JSON.parse(localStorage.getItem(STORE)||'{}')}catch{return {}}
}
function writeStore(v){localStorage.setItem(STORE,JSON.stringify(v))}
function key(){return currentSong+':'+currentCandidate.id}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function candidateById(id){return manifest.candidates.find(c=>c.id===id)}

async function loadManifest(){
  manifest=await fetch('review-manifest.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('候補一覧を読み込めません');return r.json();});
  $('song').innerHTML=manifest.songs.map(s=>'<option value="'+esc(s.id)+'">'+esc(s.label)+'</option>').join('');
  $('candidate').innerHTML=manifest.candidates.map(c=>'<option value="'+esc(c.id)+'">'+esc(c.label)+'</option>').join('');
  currentSong=$('song').value;
  currentCandidate=candidateById($('candidate').value);
  renderTags();
  await refresh();
}

function renderTags(){
  $('tags').innerHTML=manifest.tags.map((t,i)=>
    '<label><input type="checkbox" data-tag="'+esc(t)+'" id="tag'+i+'"> '+esc(t)+'</label>'
  ).join('');
}

async function metricsFor(c){
  if(metricCache.has(c.id))return metricCache.get(c.id);
  const data=await fetch(c.metricsFile).then(r=>r.json());
  const cycle=data.cycles.find(x=>x.cycle===c.cycle);
  const result=cycle?.candidates?.[c.key];
  if(!result)throw Error('評価結果を読めません: '+c.label);
  metricCache.set(c.id,result);
  return result;
}

function ratio(n,d){return d?Math.round(n/d*100)/100:null}
function fmt(v,d=3){return Number.isFinite(v)?Number(v).toFixed(d):'-'}
function groupStats(g){
  if(!g)return {precision:null,recall:null,f1:null,ratio:null};
  const precision=g.predicted?g.tp/g.predicted:0;
  const recall=g.reference?g.tp/g.reference:0;
  const f1=(g.predicted+g.reference)?2*g.tp/(g.predicted+g.reference):0;
  return {precision,recall,f1,ratio:ratio(g.predicted,g.reference)};
}

function renderMetrics(result,song){
  const s=result.songs[song],sum=result.summary;
  const groups=['kick','snare','hat','pedal_hat','tom','crash','ride'];
  const cards=[
    ['曲F1',fmt(s.f1)],
    ['Precision',fmt(s.precision)],
    ['Recall',fmt(s.recall)],
    ['総合F1',fmt(sum.f1)],
    ['Kick→Snare',s.confusion?.kick_to_snare??'-'],
    ['2音制約違反',s.two_limb_violations??'-']
  ];
  for(const g of groups){
    const st=groupStats(s.by_group?.[g]);
    cards.push([g+' F1',fmt(st.f1)]);
    cards.push([g+' 数比',st.ratio==null?'-':fmt(st.ratio,2)]);
  }
  $('metricCards').innerHTML=cards.map((x,i)=>
    '<div class="metric'+(i>=6?'':'')+'"><small>'+esc(x[0])+'</small><b>'+esc(x[1])+'</b></div>'
  ).join('');
}

function midiUrl(c,song){return c.midiBase+'/'+song+'.mid'}
function sourceUrl(song){return '../DruMaster/songs/'+song+'/drums.mp3'}
function chartUrl(song){return '../DruMaster/songs/'+song+'/chart.mid'}

async function prepareSource(song,version){
  const src=$('source');
  if(src.dataset.song===song&&src.readyState>=2)return;
  src.pause();
  src.dataset.song=song;
  src.src=sourceUrl(song);
  src.load();
  await new Promise((resolve,reject)=>{
    if(src.readyState>=2){resolve();return}
    let timer;
    const done=()=>{cleanup();resolve()};
    const fail=()=>{cleanup();reject(Error('音源を読み込めません'))};
    const cleanup=()=>{
      clearTimeout(timer);
      src.removeEventListener('canplay',done);
      src.removeEventListener('loadeddata',done);
      src.removeEventListener('error',fail);
    };
    src.addEventListener('canplay',done,{once:true});
    src.addEventListener('loadeddata',done,{once:true});
    src.addEventListener('error',fail,{once:true});
    timer=setTimeout(()=>{cleanup();reject(Error('音源の読み込みがタイムアウトしました'))},20000);
  });
  if(version!==refreshVersion)return;
}

async function refresh(){
  const version=++refreshVersion;
  // Song/candidate switching must fully stop the previous transport. Keeping
  // the previous media element playing while replacing src leaves Safari and
  // some Chromium builds in a dead playback state.
  stopPlayback(true);

  const song=$('song').value,candidate=candidateById($('candidate').value);
  currentSong=song;currentCandidate=candidate;
  $('saveReview').disabled=true;
  $('syncPlay').disabled=true;
  $('candidateDescription').textContent=candidate.description;
  $('status').textContent='音源と候補を準備中…';

  $('midiDownload').href=midiUrl(candidate,song);
  $('midiDownload').download=song+'-'+candidate.id+'.mid';
  $('chartDownload').href=chartUrl(song);
  $('chartDownload').download=song+'-chart.mid';

  const [result,,events]=await Promise.all([
    metricsFor(candidate),
    prepareSource(song,version),
    midiEvents(candidate,song)
  ]);
  if(version!==refreshVersion)return;

  currentMidiInfo={count:events.length,first:events[0]?.time??null};
  renderMetrics(result,song);
  loadReview();
  $('saveReview').disabled=false;
  $('syncPlay').disabled=false;
  $('status').textContent=`準備完了 / MIDI ${currentMidiInfo.count}音 / 最初の打点 ${currentMidiInfo.first==null?'-':currentMidiInfo.first.toFixed(2)+'秒'}。`;
}
function rangeOutput(input){
  const out=input.parentElement.querySelector('output');
  if(out)out.value=input.value;
}
document.addEventListener('input',e=>{
  if(e.target.matches('input[type="range"]'))rangeOutput(e.target);
  if(e.target.id==='sourceVolume')$('source').volume=Number(e.target.value)/100;
  if(e.target.id==='midiVolume'&&gainNode)gainNode.gain.value=Number(e.target.value)/100;
});

function reviewValue(){
  const tags=[...$('tags').querySelectorAll('input:checked')].map(x=>x.dataset.tag);
  return {
    song:currentSong,
    candidate:currentCandidate.id,
    candidateLabel:currentCandidate.label,
    ratings:{
      overall:Number($('overall').value),
      kickSnare:Number($('kickSnare').value),
      hatRide:Number($('hatRide').value),
      cymbal:Number($('cymbal').value),
      naturalness:Number($('naturalness').value)
    },
    tags,
    notes:$('notes').value.trim(),
    savedAt:new Date().toISOString()
  };
}
function saveReview(){
  const store=readStore();store[key()]=reviewValue();writeStore(store);
  $('saveState').textContent='保存しました。';
  renderExport();
}
function loadReview(){
  const v=readStore()[key()];
  for(const id of ['overall','kickSnare','hatRide','cymbal','naturalness']){
    $(id).value=v?.ratings?.[id]??3;rangeOutput($(id));
  }
  $('notes').value=v?.notes??'';
  for(const input of $('tags').querySelectorAll('input'))input.checked=Boolean(v?.tags?.includes(input.dataset.tag));
  $('saveState').textContent=v?'保存済みレビューを読み込みました。':'未保存です。';
  renderExport();
}
function clearReview(){
  const store=readStore();delete store[key()];writeStore(store);loadReview();
  $('saveState').textContent='このレビューを消去しました。';
}

function exported(){
  const store=readStore();
  return {
    schema:2,
    manifestVersion:manifest?.version??null,
    exportedAt:new Date().toISOString(),
    purpose:'DrumScribe candidate human review',
    reviews:Object.values(store)
  };
}
function renderExport(){
  $('reviewPreview').textContent=JSON.stringify(exported(),null,2);
}
async function copyReviews(){
  const text=JSON.stringify(exported(),null,2);
  await navigator.clipboard.writeText(text);
  $('saveState').textContent='レビューJSONをコピーしました。';
}
function downloadReviews(){
  const blob=new Blob([JSON.stringify(exported(),null,2)+'\n'],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='drumscribe-reviews.json';a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}

function u32(a,i){return (a[i]*0x1000000)+(a[i+1]<<16)+(a[i+2]<<8)+a[i+3]}
function readVar(a,i){let v=0,b;do{b=a[i++];v=(v<<7)|(b&127)}while(b&128);return [v,i]}
function parseMidi(buf){
  const a=new Uint8Array(buf);
  if(String.fromCharCode(...a.slice(0,4))!=='MThd')throw Error('MIDI形式ではありません。');
  const hlen=u32(a,4),tracks=(a[10]<<8)|a[11],division=(a[12]<<8)|a[13];
  let pos=8+hlen,notes=[],tempos=[];
  for(let tr=0;tr<tracks;tr++){
    if(String.fromCharCode(...a.slice(pos,pos+4))!=='MTrk')break;
    const len=u32(a,pos+4),end=pos+8+len;let i=pos+8,tick=0,running=0;
    while(i<end){
      let z=readVar(a,i);tick+=z[0];i=z[1];
      let st=a[i];
      if(st&128){running=st;i++}else st=running;
      if(st===0xff){
        const type=a[i++];z=readVar(a,i);const n=z[0];i=z[1];
        if(type===0x51&&n===3)tempos.push({tick,us:(a[i]<<16)|(a[i+1]<<8)|a[i+2]});
        i+=n;
      }else if(st===0xf0||st===0xf7){
        z=readVar(a,i);i=z[1]+z[0];
      }else{
        const op=st&0xf0,n=(op===0xc0||op===0xd0)?1:2;
        const pitch=a[i],vel=n===2?a[i+1]:0;i+=n;
        if(op===0x90&&vel>0)notes.push({tick,pitch,velocity:vel});
      }
    }
    pos=end;
  }
  tempos.sort((x,y)=>x.tick-y.tick);
  if(!tempos.length||tempos[0].tick!==0)tempos.unshift({tick:0,us:500000});
  const starts=[0];
  for(let i=1;i<tempos.length;i++){
    const prev=tempos[i-1],cur=tempos[i];
    starts[i]=starts[i-1]+(cur.tick-prev.tick)*prev.us/1000000/division;
  }
  function sec(tick){
    let i=tempos.length-1;
    while(i>0&&tempos[i].tick>tick)i--;
    return starts[i]+(tick-tempos[i].tick)*tempos[i].us/1000000/division;
  }
  return notes.map(n=>({time:sec(n.tick),pitch:n.pitch,velocity:n.velocity})).sort((a,b)=>a.time-b.time);
}

async function midiEvents(candidate=currentCandidate,song=currentSong){
  const url=midiUrl(candidate,song);
  if(midiCache.has(url))return midiCache.get(url);
  const events=parseMidi(await fetch(url,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('MIDI取得失敗');return r.arrayBuffer()}));
  midiCache.set(url,events);return events;
}
async function audioContext(){
  if(!ctx){
    const AudioCtx=window.AudioContext||window.webkitAudioContext;if(!AudioCtx)throw Error('このブラウザはWeb Audioに対応していません');ctx=new AudioCtx();
    gainNode=ctx.createGain();gainNode.gain.value=Number($('midiVolume').value)/100;gainNode.connect(ctx.destination);
  }
  await ctx.resume();return ctx;
}
async function sample(note){
  if(sampleCache.has(note))return sampleCache.get(note);
  const c=await audioContext();
  const p=fetch(SAMPLE_ROOT+note+'.wav')
    .then(r=>{if(!r.ok)throw Error('sample '+note);return r.arrayBuffer()})
    .then(b=>c.decodeAudioData(b))
    .then(buf=>{sampleCache.set(note,buf);return buf});
  sampleCache.set(note,p);return p;
}
function lowerBound(events,t){
  let lo=0,hi=events.length;
  while(lo<hi){const m=(lo+hi)>>1;if(events[m].time<t)lo=m+1;else hi=m}
  return lo;
}
async function startPlayback(){
  stopPlayback(false);
  const src=$('source');
  if(src.readyState<2)throw Error('音源の準備が完了していません');

  // The comparison MIDI may legitimately have a long drumless intro. When
  // starting from the beginning, jump just before its first hit so switching
  // songs never looks like a broken MIDI player.
  const cachedEvents=midiCache.get(midiUrl(currentCandidate,currentSong));
  let autoJumped=false;
  if((src.currentTime||0)<.5&&cachedEvents?.length&&cachedEvents[0].time>3){
    try{src.currentTime=Math.max(0,cachedEvents[0].time-.25);autoJumped=true}catch{}
  }
  const pos=src.currentTime||0;

  // Start the media element immediately while the click still counts as a
  // user gesture. Safari/iOS can reject play() if we wait for MIDI/sample
  // network/decode work first.
  src.volume=Number($('sourceVolume').value)/100;
  const sourcePlay=src.paused?src.play():Promise.resolve();
  const c=await audioContext();
  await sourcePlay;

  playbackStats={loaded:0,failed:0,scheduled:0,song:currentSong,candidate:currentCandidate.id,autoJumped};
  $('status').textContent='MIDI音源を読み込み中…';

  const events=await midiEvents(currentCandidate,currentSong);
  const notes=[...new Set(events.map(e=>e.pitch))];
  const loaded=await Promise.all(notes.map(async n=>{
    try{await sample(n);playbackStats.loaded++;return true}
    catch(err){console.warn('sample load failed',n,err);playbackStats.failed++;return false}
  }));

  if(!playbackStats.loaded){
    src.pause();
    throw Error('MIDI用ドラム音源を1つも読み込めませんでした');
  }

  const now=src.currentTime;
  playback={
    events,
    index:lowerBound(events,now-.02),
    ctxStart:c.currentTime,
    sourceStart:now,
    nodes:new Set(),
    timer:null,
    lastPos:now
  };

  function tick(){
    if(!playback)return;
    if(src.paused)return;
    const mediaNow=playback.sourceStart+(c.currentTime-playback.ctxStart);
    playback.lastPos=mediaNow;
    const horizon=mediaNow+.30;
    while(playback.index<events.length&&events[playback.index].time<=horizon){
      const e=events[playback.index++];
      if(e.time<mediaNow-.035)continue;
      const buf=sampleCache.get(e.pitch);
      if(!buf||typeof buf.then==='function')continue;
      const node=c.createBufferSource(),g=c.createGain();
      node.buffer=buf;
      g.gain.value=Math.max(.14,Math.min(1.15,e.velocity/105));
      node.connect(g);g.connect(gainNode);
      node.start(c.currentTime+Math.max(0,e.time-mediaNow));
      playback.nodes.add(node);
      playbackStats.scheduled++;
      node.onended=()=>playback?.nodes.delete(node);
    }

    $('status').textContent=
      currentCandidate.label+' / MIDI '+playbackStats.scheduled+'音再生'+
      (playbackStats.autoJumped?' / 最初の打点へ移動':'')+
      (playbackStats.failed?' / サンプル失敗 '+playbackStats.failed:'');
  }

  playback.timer=setInterval(tick,45);
  tick();
}
function resyncPlaybackClock(){
  if(!playback||!ctx)return;
  const t=$('source').currentTime||0;
  playback.sourceStart=t;
  playback.ctxStart=ctx.currentTime;
  playback.lastPos=t;
  playback.index=lowerBound(playback.events,t-.02);
}
async function playFromFirstMidi(){
  if(currentMidiInfo.first==null)throw Error('MIDI打点がありません');
  stopPlayback(true);
  const src=$('source');
  src.currentTime=Math.max(0,currentMidiInfo.first-.25);
  await startPlayback();
}
function stopPlayback(pauseSource=true){
  if(!playback){if(pauseSource)$('source').pause();return}
  clearInterval(playback.timer);
  for(const n of playback.nodes){try{n.stop()}catch{}}
  playback=null;
  if(pauseSource)$('source').pause();
  $('status').textContent='停止しました。';
}

$('song').addEventListener('change',refresh);
$('candidate').addEventListener('change',refresh);
$('syncPlay').addEventListener('click',()=>startPlayback().catch(e=>$('status').textContent='再生エラー: '+e.message));\n$('jumpMidi').addEventListener('click',()=>playFromFirstMidi().catch(e=>$('status').textContent='再生エラー: '+e.message));
$('stop').addEventListener('click',()=>stopPlayback(true));
$('saveReview').addEventListener('click',saveReview);
$('clearReview').addEventListener('click',clearReview);
$('copyReviews').addEventListener('click',()=>copyReviews().catch(e=>$('saveState').textContent='コピー失敗: '+e.message));
$('downloadReviews').addEventListener('click',downloadReviews);
$('source').addEventListener('seeked',resyncPlaybackClock);
$('source').addEventListener('play',()=>{if(playback)resyncPlaybackClock()});
$('source').addEventListener('ended',()=>stopPlayback(false));
window.addEventListener('beforeunload',()=>stopPlayback(false));

loadManifest().catch(e=>{
  console.error(e);
  $('status').textContent='比較ページの読み込みに失敗しました: '+e.message;
});

window.__drumscribeReviewDebug=()=>({
  contextState:ctx?.state??'none',
  playbackActive:Boolean(playback),
  loadedSamples:playbackStats.loaded,
  failedSamples:playbackStats.failed,
  scheduledNotes:playbackStats.scheduled,
  song:playbackStats.song,
  candidate:playbackStats.candidate,
  autoJumped:playbackStats.autoJumped,
  eventCount:playback?.events?.length??currentMidiInfo.count,
  firstEventTime:playback?.events?.[0]?.time??currentMidiInfo.first,
  nextEventTime:playback?.events?.[playback?.index??0]?.time??null,
  mediaTime:$('source')?.currentTime??0,
  contextTime:ctx?.currentTime??0,
  playbackIndex:playback?.index??null,
  sourceStart:playback?.sourceStart??null,
  contextStart:playback?.ctxStart??null,
  timerActive:Boolean(playback?.timer),
  sourcePaused:$('source')?.paused??true
});
