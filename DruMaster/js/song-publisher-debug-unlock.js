"use strict";

(()=>{
  const registerView=document.getElementById("registerView"),editorView=document.getElementById("editorView"),volumeView=document.getElementById("volumeView");
  const editorTab=document.getElementById("editorTab"),volumeTab=document.getElementById("volumeTab");
  if(!registerView||!editorView||!volumeView||!editorTab||!volumeTab)return;

  const DB_NAME="drumasterSongPublishV1",STORE="sessions",DB_VERSION=1;
  const HIT_COUNT=5,HIT_WINDOW_MS=2000;
  const hitTimes={editor:[],volume:[]},debugUnlocked=new Set();
  let debugSessionPromise=null;

  const style=document.createElement("style");
  style.textContent=`
    .tab.locked{color:#465361!important;cursor:pointer!important;background:rgba(255,255,255,.012)!important}
    .tab.locked:hover{color:#596a7b!important;background:rgba(255,255,255,.025)!important}
    .tab.debug-ready .tab-state{color:#f0c868!important}
  `;
  document.head.appendChild(style);

  for(const tab of [editorTab,volumeTab]){
    tab.disabled=false;
    tab.classList.add("locked");
    tab.setAttribute("aria-disabled","true");
  }

  function openDb(){
    return new Promise((resolve,reject)=>{
      const r=indexedDB.open(DB_NAME,DB_VERSION);
      r.onupgradeneeded=()=>{const db=r.result;if(!db.objectStoreNames.contains(STORE))db.createObjectStore(STORE,{keyPath:"sessionId"})};
      r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error||Error("デバッグ用編集DBを開けませんでした"));
    });
  }
  async function putSession(session){
    const db=await openDb();
    await new Promise((resolve,reject)=>{
      const tx=db.transaction(STORE,"readwrite");
      tx.objectStore(STORE).put(session);
      tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error||Error("デバッグセッションを保存できませんでした"));
    });
    db.close();
  }
  async function fetchBlob(path){const r=await fetch(path,{cache:"force-cache"});if(!r.ok)throw Error(`${path} HTTP ${r.status}`);return r.blob()}
  async function fetchMidi(){
    let r=await fetch("songs/ray/chart.mid",{cache:"force-cache"});
    if(r.ok)return r.blob();
    r=await fetch("songs/ray/chart.mid.gz?v=20260826-midi2",{cache:"force-cache"});
    if(!r.ok||typeof DecompressionStream!=="function")throw Error("Ray MIDIを取得できませんでした");
    const ab=await new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
    return new Blob([ab],{type:"audio/midi"});
  }
  function countMidiNotes(ab){
    try{
      const d=new DataView(ab);let p=0,count=0;const str=n=>{let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s},u32=()=>{const v=d.getUint32(p);p+=4;return v},u16=()=>{const v=d.getUint16(p);p+=2;return v},vlq=end=>{let v=0,b;do{if(p>=end)return 0;b=d.getUint8(p++);v=(v<<7)|(b&127)}while(b&128);return v};if(str(4)!=="MThd")return 0;const hl=u32();u16();const tracks=u16();u16();p=8+hl;for(let t=0;t<tracks;t++){if(str(4)!=="MTrk")break;const end=p+u32();let run=0;while(p<end){vlq(end);let first=d.getUint8(p++),status;if(first<128){status=run;p--}else{status=first;if(status<240)run=status}if(status===255){p++;p+=vlq(end)}else if(status===240||status===247){run=0;p+=vlq(end)}else{const hi=status&240,ch=status&15,bytes=(hi===192||hi===208)?1:2,a=d.getUint8(p++),b=bytes===2?d.getUint8(p++):0;if(hi===144&&b>0&&ch===9)count++}}p=end}return count;
    }catch{return 0}
  }
  async function ensureDebugSession(){
    if(debugSessionPromise)return debugSessionPromise;
    debugSessionPromise=(async()=>{
      const [drumsBlob,midiBlob]=await Promise.all([fetchBlob("songs/ray/drums.mp3"),fetchMidi()]);
      const midiAb=await midiBlob.arrayBuffer(),sessionId=`dm-debug-ray-${Date.now()}`;
      const draft={schemaVersion:3,state:"debug",id:"ray",title:"Ray",artist:"BUMP OF CHICKEN",order:null,duration:305.544,bpm:132,timeSignature:{numerator:4,denominator:4},division:480,noteCount:countMidiNotes(midiAb),chart:{pixelsPerQuarter:75,desktopPixelsPerQuarter:100},sourceMode:"base",fullMixOnly:false,playback:{stemOffsetSec:.002,midiMeasureOffset:0,midiOffsetSec:0},midi:"songs/ray/chart.mid",midiGzip:"songs/ray/chart.mid.gz?v=20260826-midi2",mix:{base:.70,vocals:.60,drums:.70},stems:{base:{path:"songs/ray/offvocal.mp3"},vocals:{path:"songs/ray/vocals.mp3"},drums:{path:"songs/ray/drums.mp3"}}};
      const session={sessionId,id:"ray",createdAt:Date.now(),debug:true,draft,originals:{base:drumsBlob,vocals:drumsBlob,drums:drumsBlob},midiBlob,uploadItems:[]};
      await putSession(session);return session;
    })();
    return debugSessionPromise;
  }
  function showDebug(which){
    const pairs={register:[document.getElementById("registerTab"),registerView],editor:[editorTab,editorView],volume:[volumeTab,volumeView]};
    for(const [key,[tab,view]] of Object.entries(pairs)){const active=key===which;tab.classList.toggle("active",active);tab.setAttribute("aria-selected",String(active));view.classList.toggle("active",active)}
  }
  function protectTimingPreview(){
    if(editorView.dataset.debug!=="1")return;
    try{
      const doc=editorView.contentDocument,publish=doc?.getElementById("publish"),auth=doc?.querySelector(".auth"),message=doc?.getElementById("message");
      if(publish){publish.disabled=true;publish.textContent="DEBUG PREVIEW"}
      if(auth)auth.style.display="none";
      if(message)message.textContent="デバッグ表示です。GitHubへのPublishは無効です。";
    }catch{}
  }
  editorView.addEventListener("load",()=>{if(editorView.dataset.debug==="1"){setTimeout(protectTimingPreview,100);setTimeout(protectTimingPreview,700)}});

  async function unlock(which){
    const tab=which==="editor"?editorTab:volumeTab,view=which==="editor"?editorView:volumeView;
    tab.querySelector(".tab-state").textContent="LOADING";
    try{
      const session=await ensureDebugSession();
      debugUnlocked.add(which);tab.classList.remove("locked");tab.classList.add("ready","debug-ready");tab.setAttribute("aria-disabled","false");tab.querySelector(".tab-state").textContent="DEBUG";
      try{view.contentWindow.name=JSON.stringify({dmSongPublisher:{token:"debug-local",repo:"ld1kanae/ld1kanae.github.io",branch:"main",id:"ray",sessionId:session.sessionId,at:Date.now()}})}catch{}
      view.dataset.debug="1";
      view.src=which==="editor"?`song-sync-editor.html?song=ray&session=${encodeURIComponent(session.sessionId)}&embedded=1&debug=1&v=20260828-debugunlock1`:`song-volume-editor.html?song=ray&session=${encodeURIComponent(session.sessionId)}&embedded=1&debug=1&v=20260828-debugunlock1`;
      showDebug(which);
    }catch(e){console.error(e);tab.querySelector(".tab-state").textContent="ERROR";setTimeout(()=>{if(tab.classList.contains("locked"))tab.querySelector(".tab-state").textContent="LOCKED"},1400)}
  }
  function handleLockedClick(which,e){
    const tab=which==="editor"?editorTab:volumeTab;
    if(!tab.classList.contains("locked")){if(debugUnlocked.has(which))showDebug(which);return}
    e.preventDefault();const now=performance.now();hitTimes[which]=hitTimes[which].filter(t=>now-t<=HIT_WINDOW_MS);hitTimes[which].push(now);
    if(hitTimes[which].length>=HIT_COUNT){hitTimes[which]=[];void unlock(which)}
  }
  editorTab.addEventListener("click",e=>handleLockedClick("editor",e));
  volumeTab.addEventListener("click",e=>handleLockedClick("volume",e));

  addEventListener("message",e=>{
    if(e.origin!==location.origin||e.source!==registerView.contentWindow||e.data?.type!=="dm-song-editor-ready")return;
    debugUnlocked.clear();
    for(const [tab,view] of [[editorTab,editorView],[volumeTab,volumeView]]){tab.classList.remove("locked","debug-ready");tab.setAttribute("aria-disabled","false");view.dataset.debug=""}
  });
})();
