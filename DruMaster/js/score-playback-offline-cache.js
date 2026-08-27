"use strict";

(()=>{
  const songApi=globalThis.DruMasterSongs,start=document.querySelector("#start"),mode=document.querySelector("#performanceModeSelect");
  if(!songApi?.songs||!songApi.nativeFetch||!start||!mode)return;

  const DB_NAME="drumaster-song-assets-v2",
        DB_VERSION=1,
        STORE_NAME="assets",
        LEGACY_CACHE_NAME="drumaster-song-assets-v1",
        VERSION_PARAM="__drumaster_asset_version",
        networkFetch=songApi.nativeFetch.bind(globalThis),
        memoryFallback=new Map(),
        descriptors=new Map();
  let preparing=false,readyKey="",dbPromise=null,lastStats={reused:0,downloaded:0,migrated:0};

  const absoluteUrl=input=>{
    const raw=typeof input==="string"?input:input?.url;
    return raw?new URL(raw,location.href).href:"";
  };
  const isRunning=()=>{try{return typeof running!=="undefined"&&running}catch{return false}};
  const supportsIdb=()=>typeof indexedDB!=="undefined";
  const supportsCacheStorage=()=>typeof caches!=="undefined"&&typeof caches.open==="function";
  const storageKey=desc=>`${desc.absolute}::${desc.version}`;

  function withTimeout(promise,ms,message){
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error(message)),ms);
      Promise.resolve(promise).then(v=>{clearTimeout(timer);resolve(v)},e=>{clearTimeout(timer);reject(e)});
    });
  }

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

  function legacyRequest(desc){
    const u=new URL(desc.absolute);
    u.searchParams.set(VERSION_PARAM,desc.version);
    return new Request(u.href,{method:"GET"});
  }

  function entryToResponse(entry){
    return new Response(entry.bytes.slice(0),{status:entry.status||200,statusText:entry.statusText||"",headers:entry.headers||[]});
  }

  function openDb(){
    if(!supportsIdb())return Promise.resolve(null);
    if(dbPromise)return dbPromise;
    dbPromise=new Promise((resolve,reject)=>{
      let settled=false;
      const req=indexedDB.open(DB_NAME,DB_VERSION);
      const timer=setTimeout(()=>{if(!settled){settled=true;reject(new Error("端末キャッシュを開けませんでした"))}},5000);
      req.onupgradeneeded=()=>{
        const db=req.result;
        if(!db.objectStoreNames.contains(STORE_NAME))db.createObjectStore(STORE_NAME,{keyPath:"key"});
      };
      req.onsuccess=()=>{if(settled){req.result.close();return}settled=true;clearTimeout(timer);resolve(req.result)};
      req.onerror=()=>{if(settled)return;settled=true;clearTimeout(timer);reject(req.error||new Error("端末キャッシュを開けませんでした"))};
      req.onblocked=()=>{if(settled)return;settled=true;clearTimeout(timer);reject(new Error("端末キャッシュが別タブで使用中です"))};
    }).catch(err=>{dbPromise=null;throw err});
    return dbPromise;
  }

  async function idbGet(key){
    const db=await openDb();if(!db)return null;
    return withTimeout(new Promise((resolve,reject)=>{
      const tx=db.transaction(STORE_NAME,"readonly"),req=tx.objectStore(STORE_NAME).get(key);
      req.onsuccess=()=>resolve(req.result||null);
      req.onerror=()=>reject(req.error||new Error("端末キャッシュの読み込みに失敗しました"));
    }),5000,"端末キャッシュの読み込みがタイムアウトしました");
  }

  async function idbPut(entry){
    const db=await openDb();if(!db)throw new Error("IndexedDBを利用できません");
    return withTimeout(new Promise((resolve,reject)=>{
      const tx=db.transaction(STORE_NAME,"readwrite");
      tx.objectStore(STORE_NAME).put(entry);
      tx.oncomplete=()=>resolve();
      tx.onerror=()=>reject(tx.error||new Error("端末キャッシュの保存に失敗しました"));
      tx.onabort=()=>reject(tx.error||new Error("端末キャッシュの保存が中断されました"));
    }),12000,"端末キャッシュの保存がタイムアウトしました");
  }

  async function cacheStorageGet(desc){
    if(!supportsCacheStorage())return null;
    try{
      const cache=await withTimeout(caches.open(LEGACY_CACHE_NAME),2500,"旧キャッシュを開けませんでした");
      const hit=await withTimeout(cache.match(legacyRequest(desc)),2500,"旧キャッシュの確認がタイムアウトしました");
      if(!hit)return null;
      const bytes=await withTimeout(hit.arrayBuffer(),12000,"旧キャッシュの読み込みがタイムアウトしました");
      if(desc.bytes&&bytes.byteLength!==desc.bytes)return null;
      return {key:storageKey(desc),url:desc.absolute,version:desc.version,bytes,status:hit.status,statusText:hit.statusText,headers:[...hit.headers.entries()]};
    }catch(err){
      console.warn("DruMaster legacy cache read skipped",err);
      return null;
    }
  }

  async function cacheStoragePut(desc,entry){
    if(!supportsCacheStorage())return false;
    try{
      const cache=await withTimeout(caches.open(LEGACY_CACHE_NAME),2500,"Cache Storageを開けませんでした");
      const response=entryToResponse(entry);
      await withTimeout(cache.put(legacyRequest(desc),response),12000,"Cache Storageへの保存がタイムアウトしました");
      return true;
    }catch(err){
      console.warn("DruMaster Cache Storage fallback failed",err);
      return false;
    }
  }

  async function persistentEntry(desc){
    const key=storageKey(desc),mem=memoryFallback.get(key);
    if(mem)return mem;

    if(supportsIdb()){
      try{
        const entry=await idbGet(key);
        if(entry&&(!desc.bytes||entry.bytes?.byteLength===desc.bytes)){
          memoryFallback.set(key,entry);
          return entry;
        }
      }catch(err){console.warn("DruMaster IndexedDB read failed",err)}
    }

    const legacy=await cacheStorageGet(desc);
    if(legacy){
      memoryFallback.set(key,legacy);
      if(supportsIdb()){
        try{await idbPut(legacy);lastStats.migrated++}catch(err){console.warn("DruMaster cache migration failed",err)}
      }
      return legacy;
    }
    return null;
  }

  async function storePersistent(desc,entry){
    const key=storageKey(desc);
    memoryFallback.set(key,entry);
    if(supportsIdb()){
      try{await idbPut(entry);return true}catch(err){console.warn("DruMaster IndexedDB store failed",err)}
    }
    return cacheStoragePut(desc,entry);
  }

  function headersArray(headers){return [...headers.entries()]}

  async function downloadEntry(desc,index,total,attempt=1){
    const load=document.querySelector("#loadState"),controller=new AbortController();
    let lastUi=0;
    const timeout=setTimeout(()=>controller.abort(),90000);
    try{
      if(load)load.textContent=`楽譜再生用データを取得中… ${index}/${total}${attempt>1?" · 再試行":""}`;
      const response=await networkFetch(desc.url,{cache:"no-store",signal:controller.signal});
      if(!response.ok)throw Error(`楽譜再生用データを取得できません（HTTP ${response.status}）`);

      const expected=Number(response.headers.get("content-length"))||desc.bytes||0;
      let bytes;
      if(response.body?.getReader){
        const reader=response.body.getReader(),chunks=[];
        let received=0;
        while(true){
          const {done,value}=await reader.read();
          if(done)break;
          if(value?.byteLength){chunks.push(value);received+=value.byteLength}
          const now=performance.now();
          if(load&&expected&&now-lastUi>120){
            lastUi=now;
            const pct=Math.min(99,Math.floor(received/expected*100));
            load.textContent=`楽譜再生用データを取得中… ${index}/${total} · ${pct}%${attempt>1?" · 再試行":""}`;
          }
        }
        const merged=new Uint8Array(received);let offset=0;
        for(const chunk of chunks){merged.set(chunk,offset);offset+=chunk.byteLength}
        bytes=merged.buffer;
      }else{
        bytes=await response.arrayBuffer();
      }

      if(desc.bytes&&bytes.byteLength!==desc.bytes)throw Error(`楽曲データが不完全です（${bytes.byteLength.toLocaleString()} / ${desc.bytes.toLocaleString()} bytes）`);
      return {key:storageKey(desc),url:desc.absolute,version:desc.version,bytes,status:response.status,statusText:response.statusText,headers:headersArray(response.headers)};
    }finally{clearTimeout(timeout)}
  }

  async function ensurePersistent(desc,index=0,total=0){
    const hit=await persistentEntry(desc);
    if(hit){lastStats.reused++;return entryToResponse(hit)}
    if(isRunning())throw new DOMException("Network access is disabled during score playback","InvalidStateError");

    let entry,lastError;
    for(let attempt=1;attempt<=2;attempt++){
      try{entry=await downloadEntry(desc,index,total,attempt);break}
      catch(err){
        lastError=err;
        if(attempt>=2)throw err;
        await new Promise(r=>setTimeout(r,350));
      }
    }
    if(!entry)throw lastError||new Error("楽曲データの取得に失敗しました");
    await storePersistent(desc,entry);
    lastStats.downloaded++;
    return entryToResponse(entry);
  }

  async function pruneObsolete(){
    if(!supportsIdb())return;
    try{
      const db=await openDb(),valid=new Set([...descriptors.values()].map(storageKey));
      if(!db)return;
      await withTimeout(new Promise((resolve,reject)=>{
        const tx=db.transaction(STORE_NAME,"readwrite"),store=tx.objectStore(STORE_NAME),req=store.openCursor();
        req.onsuccess=()=>{const cursor=req.result;if(!cursor)return;if(!valid.has(cursor.key))cursor.delete();cursor.continue()};
        req.onerror=()=>reject(req.error);
        tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);
      }),8000,"古いキャッシュの整理がタイムアウトしました");
    }catch(err){console.warn("DruMaster persistent cache cleanup failed",err)}
  }
  void pruneObsolete();

  songApi.nativeFetch=async function(input,init){
    const absolute=absoluteUrl(input),desc=descriptors.get(absolute);
    if(desc){
      const hit=await persistentEntry(desc);
      if(hit)return entryToResponse(hit);
      if(isRunning())throw new DOMException("Network access is disabled during score playback","InvalidStateError");
      return ensurePersistent(desc,1,1);
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
    lastStats={reused:0,downloaded:0,migrated:0};
    for(let i=0;i<wanted.length;i++){
      if(load)load.textContent=`楽譜再生用データを確認中… ${i+1}/${wanted.length}`;
      await ensurePersistent(wanted[i],i+1,wanted.length);
    }
    readyKey=key;
    if(load){
      if(lastStats.downloaded)load.textContent=`準備完了 · ${lastStats.downloaded}件を端末に保存`;
      else load.textContent=`準備完了 · 端末キャッシュを使用`;
    }
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
      const load=document.querySelector("#loadState");
      if(load)load.textContent=err?.name==="AbortError"?"楽曲データ取得がタイムアウトしました。もう一度STARTを押してください":err?.message||"楽譜再生用データの準備に失敗しました";
    }
  },true);

  globalThis.DruMasterScoreOfflineCache={
    isReady:()=>readyKey===selectionKey(selectedStemNames()),
    persistent:()=>supportsIdb()||supportsCacheStorage(),
    cachedAssetCount:async()=>{
      if(supportsIdb()){
        try{
          const db=await openDb();
          return await withTimeout(new Promise((resolve,reject)=>{
            const tx=db.transaction(STORE_NAME,"readonly"),req=tx.objectStore(STORE_NAME).count();
            req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);
          }),4000,"キャッシュ件数取得タイムアウト");
        }catch{}
      }
      return memoryFallback.size;
    },
    lastStats:()=>({...lastStats})
  };
})();
