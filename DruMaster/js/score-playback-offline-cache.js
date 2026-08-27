"use strict";

(()=>{
  const songApi=globalThis.DruMasterSongs,start=document.querySelector("#start"),mode=document.querySelector("#performanceModeSelect");
  if(!songApi?.songs||!songApi.nativeFetch||!start||!mode)return;

  const CACHE_NAME="drumaster-song-assets-v1",
        VERSION_PARAM="__drumaster_asset_version",
        networkFetch=songApi.nativeFetch.bind(globalThis),
        memoryFallback=new Map(),
        descriptors=new Map();
  let preparing=false,readyKey="",lastStats={reused:0,downloaded:0};

  const absoluteUrl=input=>{
    const raw=typeof input==="string"?input:input?.url;
    return raw?new URL(raw,location.href).href:"";
  };
  const isRunning=()=>{try{return typeof running!=="undefined"&&running}catch{return false}};
  const supportsPersistentCache=()=>typeof caches!=="undefined"&&typeof caches.open==="function";

  function addDescriptor(url,version,bytes=0){
    if(!url)return;
    const absolute=absoluteUrl(url);
    descriptors.set(absolute,{url,absolute,version:String(version||url),bytes:Number(bytes)||0});
  }

  for(const song of Object.values(songApi.songs)){
    addDescriptor(song.midiGzip,`midi:${song.id}:${song.midiGzip}`);
    for(const [name,spec] of Object.entries(song.stems||{})){
      const version=spec.sha256?`stem:${song.id}:${name}:sha256:${spec.sha256}`:`stem:${song.id}:${name}:bytes:${spec.bytes||0}:${spec.path}`;
      addDescriptor(spec.path,version,spec.bytes);
    }
  }

  function persistentRequest(desc){
    const u=new URL(desc.absolute);
    u.searchParams.set(VERSION_PARAM,desc.version);
    return new Request(u.href,{method:"GET"});
  }

  function cloneMemory(entry){
    return new Response(entry.bytes.slice(0),{status:entry.status,statusText:entry.statusText,headers:entry.headers});
  }

  async function persistentMatch(desc){
    if(!supportsPersistentCache()){
      const entry=memoryFallback.get(desc.absolute);
      return entry?cloneMemory(entry):null;
    }
    const cache=await caches.open(CACHE_NAME);
    const hit=await cache.match(persistentRequest(desc));
    return hit?hit.clone():null;
  }

  async function storePersistent(desc,response){
    const bytes=await response.clone().arrayBuffer();
    if(desc.bytes&&bytes.byteLength!==desc.bytes)throw Error(`楽曲データが不完全です（${bytes.byteLength.toLocaleString()} / ${desc.bytes.toLocaleString()} bytes）`);

    if(!supportsPersistentCache()){
      memoryFallback.set(desc.absolute,{bytes,status:response.status,statusText:response.statusText,headers:new Headers(response.headers)});
      return;
    }

    const cache=await caches.open(CACHE_NAME);
    const stored=new Response(bytes,{status:response.status,statusText:response.statusText,headers:new Headers(response.headers)});
    await cache.put(persistentRequest(desc),stored);
  }

  async function ensurePersistent(desc){
    const hit=await persistentMatch(desc);
    if(hit){lastStats.reused++;return hit}

    if(isRunning())throw new DOMException("Network access is disabled during score playback","InvalidStateError");
    const response=await networkFetch(desc.url,{cache:"no-store"});
    if(!response.ok)throw Error(`楽譜再生用データを取得できません（HTTP ${response.status}）`);
    await storePersistent(desc,response);
    lastStats.downloaded++;
    return (await persistentMatch(desc))||response.clone();
  }

  async function pruneObsolete(){
    if(!supportsPersistentCache())return;
    const cache=await caches.open(CACHE_NAME),valid=new Set([...descriptors.values()].map(d=>persistentRequest(d).url));
    for(const request of await cache.keys())if(!valid.has(request.url))await cache.delete(request);
  }
  void pruneObsolete().catch(err=>console.warn("DruMaster persistent cache cleanup failed",err));

  songApi.nativeFetch=async function(input,init){
    const absolute=absoluteUrl(input),desc=descriptors.get(absolute);
    if(desc){
      const hit=await persistentMatch(desc);
      if(hit)return hit;
      if(isRunning())throw new DOMException("Network access is disabled during score playback","InvalidStateError");
      const response=await networkFetch(input,init);
      if(response.ok)await storePersistent(desc,response);
      return (await persistentMatch(desc))||response;
    }
    if(isRunning())throw new DOMException("Network access is disabled during score playback","InvalidStateError");
    return networkFetch(input,init);
  };

  function selectedStemNames(){
    return ["base",...(document.querySelector("#vocalToggle")?.checked?["vocals"]:[]),...(document.querySelector("#guideToggle")?.checked?["drums"]:[])];
  }
  function selectionKey(names){return names.join("+")}
  function descriptorsForSelection(names){
    const wanted=[];
    for(const song of Object.values(songApi.songs)){
      const midi=descriptors.get(absoluteUrl(song.midiGzip));if(midi)wanted.push(midi);
      for(const name of names){
        const spec=song.stems?.[name],desc=spec&&descriptors.get(absoluteUrl(spec.path));
        if(desc)wanted.push(desc);
      }
    }
    return wanted;
  }

  async function prepareAll(){
    const names=selectedStemNames(),key=selectionKey(names);
    if(readyKey===key)return;
    const load=document.querySelector("#loadState"),wanted=descriptorsForSelection(names);
    lastStats={reused:0,downloaded:0};
    for(let i=0;i<wanted.length;i++){
      if(load)load.textContent=`楽譜再生用データを確認中… ${i+1}/${wanted.length}`;
      await ensurePersistent(wanted[i]);
    }
    readyKey=key;
    if(load)load.textContent=lastStats.downloaded?`準備完了 · ${lastStats.downloaded}件を端末に保存`:`準備完了 · 端末キャッシュを使用`;
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
      const load=document.querySelector("#loadState");if(load)load.textContent=err?.message||"楽譜再生用データの準備に失敗しました";
    }
  },true);

  globalThis.DruMasterScoreOfflineCache={
    isReady:()=>readyKey===selectionKey(selectedStemNames()),
    persistent:supportsPersistentCache,
    cachedAssetCount:async()=>supportsPersistentCache()?(await (await caches.open(CACHE_NAME)).keys()).length:memoryFallback.size,
    lastStats:()=>({...lastStats})
  };
})();
