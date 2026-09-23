(()=>{
'use strict';
const $=id=>document.getElementById(id),canvas=$('timeline');
const card=$('reviewCard'),popover=$('reviewPopover'),rangeOut=$('selectionRange'),rangeHint=$('selectionHint'),category=$('reviewCategory'),text=$('reviewText'),save=$('addReview'),list=$('reviewList'),status=$('reviewStatus'),prompt=$('aiPromptPreview'),undoButton=$('reviewUndo'),redoButton=$('reviewRedo');
let api=null,selection=null,reviews=[],source={fileName:'',exampleId:'',duration:0},undoStack=[],redoStack=[],editingId=null,drag=null,playToken=0;
const HISTORY_LIMIT=5;
const clone=value=>JSON.parse(JSON.stringify(value));
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const fmt=t=>{t=Math.max(0,Number(t)||0);const m=Math.floor(t/60),s=Math.floor(t%60),ms=Math.floor((t-Math.floor(t))*1000);return String(m).padStart(2,'0')+':'+String(s).padStart(2,'0')+'.'+String(ms).padStart(3,'0')};
const key=()=>source.fileName?'drumscribe-review-v1:'+source.fileName+':'+Number(source.duration||0).toFixed(3):'';
function setStatus(message,error=false){status.textContent=message;status.classList.toggle('error',error)}
function persist(){const k=key();if(!k)return;try{localStorage.setItem(k,JSON.stringify({reviews}))}catch{}}
function load(){reviews=[];const k=key();if(k)try{const data=JSON.parse(localStorage.getItem(k)||'{}');if(Array.isArray(data.reviews))reviews=data.reviews}catch{}undoStack=[];redoStack=[];editingId=null;closeEditor(false);render()}
function analysisSummary(){
  const a=api?.getAnalysis?.()||{},g=a.rhythmGridInfo||{};
  return {bpm:Number.isFinite(a.bpm)?a.bpm:null,numerator:a.numerator||null,denominator:a.denominator||null,barPhaseSec:Number.isFinite(a.barPhaseSec)?a.barPhaseSec:null,subdivision:g.subdivision||null,tempoMin:Number.isFinite(g.tempoMin)?g.tempoMin:null,tempoMax:Number.isFinite(g.tempoMax)?g.tempoMax:null,tempoEvents:g.tempoEvents||null};
}
function payload(){return {schema:'drumscribe-review-v1',createdAt:new Date().toISOString(),page:location.href,source:{...source},analysis:analysisSummary(),reviews:reviews.map((r,i)=>({index:i+1,startSec:r.start,endSec:r.end,beats:r.beats??null,category:r.category,comment:r.comment}))}}
function buildPrompt(){
  const p=payload(),lines=[
    'DrumScribe の機能修正を依頼します。','','対象音源: '+(p.source.fileName||'不明'),
    p.source.exampleId?'検証曲ID: '+p.source.exampleId:'',
    '長さ: '+Number(p.source.duration||0).toFixed(3)+' sec',
    '解析情報: '+JSON.stringify(p.analysis),'',
    '以下は波形と生成MIDIを重ねて確認し、拍グリッドへスナップした時間範囲を指定して記録したレビューです。',
    '各範囲について原因を実装上まで追い、既存の kick / snare / tom 精度を不用意に退行させない形で修正してください。',
    '修正後は、該当範囲と既存検証データの両方で再確認し、変更点と検証結果を残してください。',''
  ].filter(Boolean);
  if(!p.reviews.length)lines.push('レビューはまだありません。');
  for(const r of p.reviews){lines.push('## Review '+r.index+' ['+fmt(r.startSec)+' – '+fmt(r.endSec)+'] ['+r.category+']');lines.push(r.comment);lines.push('範囲(sec): '+r.startSec.toFixed(3)+' – '+r.endSec.toFixed(3)+(r.beats?' / '+r.beats+'拍':''));lines.push('');}
  lines.push('--- machine-readable review ---');lines.push(JSON.stringify(p,null,2));return lines.join('\n');
}
function updateHistory(){undoButton.disabled=!undoStack.length;redoButton.disabled=!redoStack.length;$('reviewHistoryState').textContent='戻る '+undoStack.length+'/'+HISTORY_LIMIT+' · やり直し '+redoStack.length}
function mutate(fn){undoStack.push(clone(reviews));if(undoStack.length>HISTORY_LIMIT)undoStack.shift();fn();redoStack=[];persist();render()}
function undo(){if(!undoStack.length)return;redoStack.push(clone(reviews));reviews=undoStack.pop();persist();closeEditor(false);render()}
function redo(){if(!redoStack.length)return;undoStack.push(clone(reviews));if(undoStack.length>HISTORY_LIMIT)undoStack.shift();reviews=redoStack.pop();persist();closeEditor(false);render()}
function snapRange(start,end){
  const snapped=api?.snapRangeToBeats?.(start,end);
  if(snapped&&Number.isFinite(snapped.start)&&Number.isFinite(snapped.end))return snapped;
  const d=api?.getDuration?.()||0,a=clamp(Number(start)||0,0,d),b=clamp(Number(end)||0,0,d);
  return {start:Math.min(a,b),end:Math.max(a,b),beats:null};
}
function positionPopover(){
  if(popover.hidden||!selection||!api)return;
  const stage=$('timelineStage'),view=api.getView?.();
  if(!stage||!view)return;
  const leftPx=(selection.start-view.start)*view.pxPerSec,rightPx=(selection.end-view.start)*view.pxPerSec;
  const desired=(leftPx+rightPx)/2,half=Math.max(1,popover.offsetWidth/2);
  const center=clamp(desired,half+8,Math.max(half+8,stage.clientWidth-half-8));
  const arrowX=clamp(desired-(center-half),18,Math.max(18,popover.offsetWidth-18));
  popover.style.left=center+'px';
  popover.style.setProperty('--review-arrow-x',arrowX+'px');
}
function setSelection(start,end,focus=false,{open=true,snap=true}={}){
  if(!api)return;
  const next=snap?snapRange(start,end):{start:Math.min(start,end),end:Math.max(start,end),beats:null};
  selection={start:next.start,end:next.end,beats:next.beats??null};
  api.setSelection(selection.start,selection.end);
  rangeOut.textContent=fmt(selection.start)+' – '+fmt(selection.end);
  rangeHint.textContent=(selection.beats?selection.beats+'拍 / ':'')+(selection.end-selection.start).toFixed(3)+' sec';
  if(focus)api.focusRange(selection.start,selection.end);
  if(open){popover.hidden=false;requestAnimationFrame(positionPopover)}
}
function closeEditor(clear=true){
  popover.hidden=true;editingId=null;save.textContent='保存';
  text.value='';category.value='採譜ミス';
  if(clear){selection=null;api?.clearSelection?.();}
}
async function playRange(r=selection){
  if(!api||!r||r.end-r.start<.005)return;
  const token=++playToken;api.pause();api.seek(r.start);await api.play();
  const loop=()=>{if(token!==playToken)return;if(api.getCurrentTime()>=r.end-.005){api.pause();return}requestAnimationFrame(loop)};requestAnimationFrame(loop);
}
function openExisting(r){
  editingId=r.id;setSelection(r.start,r.end,true,{open:true,snap:false});
  selection.beats=r.beats??null;
  rangeHint.textContent=(selection.beats?selection.beats+'拍 / ':'')+(selection.end-selection.start).toFixed(3)+' sec';
  category.value=r.category;text.value=r.comment;save.textContent='変更を保存';requestAnimationFrame(()=>text.focus());
}
function render(){
  list.textContent='';
  if(!reviews.length){const li=document.createElement('li');li.className='review-empty';li.textContent='保存済みレビューはまだありません。波形上で範囲をドラッグすると入力吹き出しが開きます。';list.appendChild(li)}
  reviews.forEach((r,i)=>{
    const li=document.createElement('li');li.className='review-item review-log-block';li.tabIndex=0;li.setAttribute('role','button');li.setAttribute('aria-label','レビュー '+(i+1)+' を編集');
    const head=document.createElement('div');head.className='review-item-head';
    const time=document.createElement('span');time.className='review-item-time';time.textContent='#'+(i+1)+' '+fmt(r.start)+' – '+fmt(r.end)+(r.beats?' / '+r.beats+'拍':'');
    const cat=document.createElement('span');cat.className='review-item-category';cat.textContent=r.category;
    const actions=document.createElement('span');actions.className='review-item-actions';
    const play=document.createElement('button');play.type='button';play.textContent='▶ 再生';play.addEventListener('click',e=>{e.stopPropagation();playRange(r)});
    const edit=document.createElement('button');edit.type='button';edit.textContent='編集';edit.addEventListener('click',e=>{e.stopPropagation();openExisting(r)});
    const del=document.createElement('button');del.type='button';del.textContent='削除';del.addEventListener('click',e=>{e.stopPropagation();mutate(()=>{reviews=reviews.filter(x=>x.id!==r.id);if(editingId===r.id)closeEditor()})});
    actions.append(play,edit,del);head.append(time,cat,actions);
    const body=document.createElement('div');body.className='review-item-text';body.textContent=r.comment;li.append(head,body);
    li.addEventListener('click',()=>openExisting(r));
    li.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openExisting(r)}});
    list.appendChild(li);
  });
  prompt.value=buildPrompt();updateHistory();globalThis.__drumscribeReviewPayload=payload();
}
function submitReview(){
  const wasEditing=Boolean(editingId);
  const comment=text.value.trim();
  if(!selection||selection.end-selection.start<.005){setStatus('先に波形上でレビュー範囲を選択してください。',true);return}
  if(!comment){setStatus('レビュー内容を入力してください。',true);text.focus();return}
  const entry={id:editingId||('r-'+Date.now()+'-'+Math.round(selection.start*1000)),start:selection.start,end:selection.end,beats:selection.beats??null,category:category.value,comment};
  mutate(()=>{
    if(editingId){const i=reviews.findIndex(r=>r.id===editingId);if(i>=0)reviews[i]=entry;else reviews.push(entry)}
    else reviews.push(entry);
    reviews.sort((a,b)=>a.start-b.start||a.end-b.end);
  });
  closeEditor();setStatus(wasEditing?'レビューを更新しました。':'レビューを保存しました。');
}
async function copyPrompt(){
  const value=buildPrompt();try{await navigator.clipboard.writeText(value);setStatus('AI修正依頼文をクリップボードへコピーしました。')}catch{prompt.focus();prompt.select();document.execCommand('copy');setStatus('AI修正依頼文をコピーしました。')}
}
function downloadJson(){
  const blob=new Blob([JSON.stringify(payload(),null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=(source.fileName||'drumscribe').replace(/\.[^.]+$/,'')+'-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);setStatus('レビューJSONを書き出しました。');
}
function installTimeline(){
  api=globalThis.DrumScribeTimeline;if(!api)return false;
  const pointTime=e=>api.clientXToTime(e.clientX);
  const move=e=>{
    if(!drag||e.pointerId!==drag.id)return;
    if(e.cancelable)e.preventDefault();
    drag.lastX=e.clientX;
    if(Math.abs(e.clientX-drag.x)>3)drag.moved=true;
    if(drag.moved)setSelection(drag.start,pointTime(e),false,{open:false,snap:true});
  };
  const finish=e=>{
    if(!drag||e.pointerId!==drag.id)return;
    if(e.cancelable)e.preventDefault();
    const d=drag;drag=null;
    try{if(canvas.hasPointerCapture?.(e.pointerId))canvas.releasePointerCapture(e.pointerId)}catch{}
    if(d.moved){
      editingId=null;text.value='';category.value='採譜ミス';save.textContent='保存';
      setSelection(d.start,pointTime(e),false,{open:true,snap:true});
      setStatus('1拍単位にスナップしました。レビューを書いて保存してください。');
    }else{
      closeEditor();api.seek(pointTime(e));
    }
  };
  const cancel=e=>{if(drag&&e.pointerId===drag.id){drag=null;api.clearSelection?.();}};
  canvas.addEventListener('pointerdown',e=>{
    if(!api.getDuration()||e.isPrimary===false)return;
    if(e.pointerType==='mouse'&&e.button!==0)return;
    if(e.cancelable)e.preventDefault();
    playToken++;api.pause();closeEditor();
    drag={id:e.pointerId,x:e.clientX,lastX:e.clientX,start:pointTime(e),moved:false};
    try{canvas.setPointerCapture?.(e.pointerId)}catch{}
  },{passive:false});
  window.addEventListener('pointermove',move,{capture:true,passive:false});
  window.addEventListener('pointerup',finish,{capture:true,passive:false});
  window.addEventListener('pointercancel',cancel,{capture:true});
  return true;
}
$('playSelection').addEventListener('click',()=>playRange());
$('clearSelection').addEventListener('click',()=>closeEditor());
save.addEventListener('click',submitReview);
undoButton.addEventListener('click',undo);redoButton.addEventListener('click',redo);
$('copyAiPrompt').addEventListener('click',copyPrompt);$('downloadReview').addEventListener('click',downloadJson);
for(const id of ['zoom','timelineScroll'])$(id)?.addEventListener('input',()=>requestAnimationFrame(positionPopover));
$('fitTimeline')?.addEventListener('click',()=>requestAnimationFrame(positionPopover));
addEventListener('resize',()=>requestAnimationFrame(positionPopover));
addEventListener('keydown',e=>{
  if(e.key==='Escape'&&!popover.hidden){closeEditor();return}
  if(!(e.ctrlKey||e.metaKey)||e.altKey)return;
  const tag=e.target?.tagName;if(tag==='INPUT'||tag==='TEXTAREA'||tag==='SELECT'||e.target?.isContentEditable)return;
  const k=e.key.toLowerCase();
  if(k==='z'){e.preventDefault();if(e.shiftKey)redo();else undo()}else if(k==='y'){e.preventDefault();redo()}
});
addEventListener('drumscribe:file-selected',()=>{card.hidden=true;playToken++;closeEditor(false)});
addEventListener('drumscribe:analysis-complete',e=>{
  source={fileName:e.detail.fileName||api?.getFileName?.()||'',exampleId:e.detail.exampleId||'',duration:Number(e.detail.duration)||api?.getDuration?.()||0};
  card.hidden=false;closeEditor();load();setStatus('波形上をドラッグすると、範囲を1拍単位へスナップして入力吹き出しを表示します。');
});
if(!installTimeline()){addEventListener('drumscribe:timeline-ready',installTimeline,{once:true})}
render();
})();