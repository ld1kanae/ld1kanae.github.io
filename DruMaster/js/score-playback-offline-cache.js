"use strict";

(()=>{
  const songApi=globalThis.DruMasterSongs,start=document.querySelector("#start"),mode=document.querySelector("#performanceModeSelect");
  if(!songApi?.songs||!songApi.nativeFetch||!start||!mode)return;

  const networkFetch=songApi.nativeFetch.bind(globalThis),assetCache=new Map();
  let preparing=false,readyKey="";

  const keyFor=input=>{
    const raw=typeof input==="string"?input:input?.url;
    return raw?new URL(raw,location.href).href:"";
  };
  const responseFrom=entry=>new Response(entry.bytes.slice(0),{status:entry.status,statusText:entry.statusText,headers:entry.headers});
  const isRunning=()=>{try{return typeof running!=="undefined"&&running}catch{return false}};

  async function fetchAndCache(url){
    const key=keyFor(url);if(assetCache.has(key))return;
    const r=await networkFetch(url,{cache:"force-cache"});
    if(!r.ok)throw Error(`楽譜再生用データを取得できません（HTTP ${r.status}）`);
    const bytes=await r.arrayBuffer();
    assetCache.set(key,{bytes,status:r.status,statusText:r.statusText,headers:new Headers(r.headers)});
  }

  songApi.nativeFetch=async function(input,init){
    const key=keyFor(input),cached=assetCache.get(key);
    if(cached)return responseFrom(cached);
    if(isRunning())throw new DOMException("Network access is disabled during score playback","InvalidStateError");
    return networkFetch(input,init);
  };

  function selectedStemNames(){
    return ["base",...(document.querySelector("#vocalToggle")?.checked?["vocals"]:[]),...(document.querySelector("#guideToggle")?.checked?["drums"]:[])];
  }
  function selectionKey(names){return names.join("+")}

  async function prepareAll(){
    const names=selectedStemNames(),key=selectionKey(names);
    if(readyKey===key)return;
    const load=document.querySelector("#loadState"),songs=Object.values(songApi.songs),urls=[];
    for(const song of songs){
      urls.push(song.midiGzip);
      for(const name of names){const spec=song.stems?.[name];if(spec?.path)urls.push(spec.path)}
    }
    for(let i=0;i<urls.length;i++){
      if(load)load.textContent=`楽譜再生用データを事前取得中… ${i+1}/${urls.length}`;
      await fetchAndCache(urls[i]);
    }
    readyKey=key;
  }

  document.addEventListener("click",async e=>{
    if(e.target!==start||mode.value!=="score"||preparing)return;
    const key=selectionKey(selectedStemNames());
    if(readyKey===key)return;
    e.preventDefault();e.stopImmediatePropagation();
    preparing=true;start.disabled=true;
    try{
      await prepareAll();
      preparing=false;start.disabled=false;
      start.click();
    }catch(err){
      preparing=false;start.disabled=false;
      console.error(err);
      const load=document.querySelector("#loadState");if(load)load.textContent=err?.message||"楽譜再生用データの事前取得に失敗しました";
    }
  },true);

  globalThis.DruMasterScoreOfflineCache={
    isReady:()=>readyKey===selectionKey(selectedStemNames()),
    cachedAssetCount:()=>assetCache.size
  };
})();
