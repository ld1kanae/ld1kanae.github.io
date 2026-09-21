const $=id=>document.getElementById(id);
const STORE='drumscribe-review-v1';
const SAMPLE_ROOT='../DruMaster/assets/drums/';
let manifest,currentCandidate,currentSong,metricCache=new Map(),midiCache=new Map(),sampleCache=new Map();
let ctx,gainNode,playback=null;

function readStore(){
  try{return JSON.parse(localStorage.getItem(STORE)||'{}')}catch{return {}}
}
function writeStore(v){localStorage.setItem(STORE,JSON.stringify(v))}
function key(){return currentSong+':'+currentCandidate.id}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function candidateById(id){return manifest.candidates.find(c=>c.id===id)}

async function loadManifest(){
  manifest=await fetch('review-manifest.json?v=20260922-1').then(r=>r.json());
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

async function renderMetrics(){
  const result=await metricsFor(currentCandidate);
  const s=result.songs[currentSong],sum=result.summary;
  const groups=['kick','snare','hat','tom','crash','ride'];
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

async function refresh(){
  stopPlayback(false);
  currentSong=$('song').value;
  currentCandidate=candidateById($('candidate').value);
  $('candidateDescription').textContent=currentCandidate.description;
  $('source').src=sourceUrl(currentSong);
  $('midiDownload').href=midiUrl(currentCandidate,currentSong);
  $('midiDownload').download=currentSong+'-'+currentCandidate.id+'.mid';
  $('chartDownload').href=chartUrl(currentSong);
  $('chartDownload').download=currentSong+'-chart.mid';
  await renderMetrics();
  loadReview();
  $('status').textContent='準備完了。音源の好きな位置へ移動して「音源 + MIDI」を押してください。';
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
    schema:1,
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

async function midiEvents(){
  const url=midiUrl(currentCandidate,currentSong);
  if(midiCache.has(url))return midiCache.get(url);
  const events=parseMidi(await fetch(url).then(r=>{if(!r.ok)throw Error('MIDI取得失敗');return r.arrayBuffer()}));
  midiCache.set(url,events);return events;
}
async function audioContext(){
  if(!ctx){
    ctx=new AudioContext();
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
  const c=await audioContext(),events=await midiEvents(),src=$('source');
  const pos=src.currentTime||0;
  const notes=[...new Set(events.map(e=>e.pitch))];
  await Promise.all(notes.map(n=>sample(n).catch(()=>null)));
  playback={events,index:lowerBound(events,pos-.02),ctxStart:c.currentTime,sourceStart:pos,nodes:new Set(),timer:null,lastPos:pos};
  src.volume=Number($('sourceVolume').value)/100;
  await src.play();
  function tick(){
    if(!playback)return;
    const now=src.currentTime;
    if(Math.abs(now-playback.lastPos)>.65){
      playback.index=lowerBound(events,now-.02);
      playback.ctxStart=c.currentTime;playback.sourceStart=now;
    }
    playback.lastPos=now;
    if(src.paused)return;
    const horizon=now+.28;
    while(playback.index<events.length&&events[playback.index].time<=horizon){
      const e=events[playback.index++];
      if(e.time<now-.03)continue;
      const buf=sampleCache.get(e.pitch);
      if(!buf||typeof buf.then==='function')continue;
      const node=c.createBufferSource(),g=c.createGain();
      node.buffer=buf;g.gain.value=Math.max(.12,Math.min(1,e.velocity/110));
      node.connect(g);g.connect(gainNode);
      node.start(c.currentTime+Math.max(0,e.time-now));
      playback.nodes.add(node);node.onended=()=>playback?.nodes.delete(node);
    }
  }
  playback.timer=setInterval(tick,55);tick();
  $('status').textContent=currentCandidate.label+' を原音に重ねて再生中。';
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
$('syncPlay').addEventListener('click',()=>startPlayback().catch(e=>$('status').textContent='再生エラー: '+e.message));
$('stop').addEventListener('click',()=>stopPlayback(true));
$('saveReview').addEventListener('click',saveReview);
$('clearReview').addEventListener('click',clearReview);
$('copyReviews').addEventListener('click',()=>copyReviews().catch(e=>$('saveState').textContent='コピー失敗: '+e.message));
$('downloadReviews').addEventListener('click',downloadReviews);
$('source').addEventListener('ended',()=>stopPlayback(false));
window.addEventListener('beforeunload',()=>stopPlayback(false));

loadManifest().catch(e=>{
  console.error(e);
  $('status').textContent='比較ページの読み込みに失敗しました: '+e.message;
});
