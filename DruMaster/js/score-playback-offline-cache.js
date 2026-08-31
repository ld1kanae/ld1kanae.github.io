"use strict";

(()=>{
  /*
   * Shared persistent cache for every DruMaster playback mode.
   * Callers may keep using cache:"no-store" for deterministic network reads:
   * this layer checks versioned device storage before the request reaches the
   * network, and stores a verified response after the first successful fetch.
   */
  const songApi=globalThis.DruMasterSongs;
  if(!songApi?.songs||typeof globalThis.fetch!=="function")return;

  const DB_NAME="drumaster-assets-v3",
        DB_VERSION=1,
        STORE_NAME="assets",
        CACHE_NAME="drumaster-assets-v3-fallback",
        SCHEMA_VERSION="20260831-universal1",
        DRUM_VERSION="drumsound-v2:22:17243836:6fe934d11bf77704d51686ad520dab601f6cf7f46d32d3cb69086c1dc678d5a3",
        baseFetch=globalThis.fetch.bind(globalThis),
        memory=new Map(),
        descriptors=new Map(),
        inflight=new Map();
  let dbPromise=null,stats={reused:0,downloaded:0,invalidated:0};

  const absolute=input=>{
    const raw=typeof input==="string"?input:input?.url;
    try{return raw?new URL(raw,location.href).href:""}catch{return ""}
  };
  const clean=input=>absolute(input).split("#")[0];
  const keyFor=desc=>`${desc.absolute}::${desc.version}`;
  const bytesOf=value=>Number.isFinite(Number(value))?Math.max(0,Number(value)):0;
  const hashOf=value=>typeof value==="string"&&/^[a-f0-9]{64}$/i.test(value)?value.toLowerCase():"";

  function add(url,version,bytes=0,sha256=""){
    const urlAbsolute=clean(url);
    if(!urlAbsolute)return;
    descriptors.set(urlAbsolute,{
      absolute:urlAbsolute,
      version:String(version||`${SCHEMA_VERSION}:${urlAbsolute}`),
      bytes:bytesOf(bytes),
      sha256:hashOf(sha256)
    });
  }
  function addStem(song,name,spec){
    if(!spec)return;
    const version=spec.sha256
      ?`stem:${song.id}:${name}:sha256:${spec.sha256}`
      :`stem:${song.id}:${name}:bytes:${spec.bytes||0}:${spec.path||spec.pathPrefix||""}`;
    if(spec.path)add(spec.path,version,spec.bytes,spec.sha256);
    const paths=Array.isArray(spec.paths)
      ?spec.paths
      :(spec.parts&&spec.pathPrefix
        ?Array.from({length:spec.parts},(_,i)=>`${spec.pathPrefix}${String(i).padStart(spec.digits||3,"0")}`)
        :[]);
    for(const path of paths)add(path,version);
  }

  for(const song of Object.values(songApi.songs)){
    const midiVersion=`midi:${song.id}:${song.midiGzip||song.midi}`;
    add(song.midi,midiVersion);
    add(song.midiGzip,midiVersion);
    for(const [name,spec] of Object.entries(song.stems||{}))addStem(song,name,spec);
  }

  add("assets/drumsound-manifest.json",DRUM_VERSION);
  add("assets/drumsound.mid",DRUM_VERSION,6366,"6fe934d11bf77704d51686ad520dab601f6cf7f46d32d3cb69086c1dc678d5a3");
  for(let i=0;i<22;i++)add(`assets/drumsound-v2-${String(i).padStart(3,"0")}`,DRUM_VERSION);

  function descriptorFor(input){
    const url=clean(input);
    if(!url)return null;
    const known=descriptors.get(url);
    if(known)return known;
    let parsed;
    try{parsed=new URL(url)}catch{return null}
    if(parsed.origin!==location.origin)return null;
    const root=new URL(".",location.href).pathname;
    const path=parsed.pathname;
    const assetPath=path.startsWith(root+"songs/")||path.startsWith(root+"assets/");
    if(!assetPath||!/(?:\.mp3|\.wav|\.mid|\.gz|audio-|drumsound)/i.test(path))return null;
    const fallback={absolute:url,version:`fallback:${SCHEMA_VERSION}:${url}`,bytes:0,sha256:""};
    descriptors.set(url,fallback);
    return fallback;
  }

  function timeout(promise,ms,message){
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error(message)),ms);
      Promise.resolve(promise).then(
        value=>{clearTimeout(timer);resolve(value)},
        error=>{clearTimeout(timer);reject(error)}
      );
    });
  }
  function openDb(){
    if(typeof indexedDB==="undefined")return Promise.resolve(null);
    if(dbPromise)return dbPromise;
    dbPromise=new Promise((resolve,reject)=>{
      const request=indexedDB.open(DB_NAME,DB_VERSION);
      const timer=setTimeout(()=>reject(new Error("端末キャッシュを開けませんでした")),5000);
      request.onupgradeneeded=()=>{
        const db=request.result;
        if(!db.objectStoreNames.contains(STORE_NAME))db.createObjectStore(STORE_NAME,{keyPath:"key"});
      };
      request.onsuccess=()=>{clearTimeout(timer);resolve(request.result)};
      request.onerror=()=>{clearTimeout(timer);reject(request.error||new Error("端末キャッシュを開けませんでした"))};
    }).catch(error=>{dbPromise=null;throw error});
    return dbPromise;
  }
  async function idbGet(key){
    const db=await openDb();
    if(!db)return null;
    return timeout(new Promise((resolve,reject)=>{
      const request=db.transaction(STORE_NAME,"readonly").objectStore(STORE_NAME).get(key);
      request.onsuccess=()=>resolve(request.result||null);
      request.onerror=()=>reject(request.error);
    }),8000,"端末キャッシュの読み込みがタイムアウトしました");
  }
  async function idbPut(entry){
    const db=await openDb();
    if(!db)throw new Error("IndexedDBを利用できません");
    return timeout(new Promise((resolve,reject)=>{
      const tx=db.transaction(STORE_NAME,"readwrite");
      tx.objectStore(STORE_NAME).put(entry);
      tx.oncomplete=resolve;
      tx.onerror=()=>reject(tx.error);
      tx.onabort=()=>reject(tx.error);
    }),20000,"端末キャッシュの保存がタイムアウトしました");
  }
  async function idbDelete(key){
    const db=await openDb();
    if(!db)return;
    await timeout(new Promise((resolve,reject)=>{
      const tx=db.transaction(STORE_NAME,"readwrite");
      tx.objectStore(STORE_NAME).delete(key);
      tx.oncomplete=resolve;
      tx.onerror=()=>reject(tx.error);
    }),8000,"端末キャッシュの削除がタイムアウトしました");
  }

  const fallbackRequest=desc=>{
    const url=new URL(desc.absolute);
    url.searchParams.set("__drumaster_cache_version",desc.version);
    return new Request(url.href);
  };
  async function fallbackGet(desc){
    if(typeof caches==="undefined")return null;
    try{
      const cache=await timeout(caches.open(CACHE_NAME),4000,"Cache Storageを開けませんでした");
      const response=await timeout(cache.match(fallbackRequest(desc)),4000,"Cache Storageの確認がタイムアウトしました");
      if(!response)return null;
      const bytes=await response.arrayBuffer();
      return {key:keyFor(desc),bytes,status:response.status,statusText:response.statusText,headers:[...response.headers.entries()]};
    }catch{return null}
  }
  async function fallbackPut(desc,entry){
    if(typeof caches==="undefined")return false;
    try{
      const cache=await timeout(caches.open(CACHE_NAME),4000,"Cache Storageを開けませんでした");
      await timeout(cache.put(fallbackRequest(desc),entryResponse(entry)),20000,"Cache Storageへの保存がタイムアウトしました");
      return true;
    }catch{return false}
  }
  async function fallbackDelete(desc){
    if(typeof caches==="undefined")return;
    try{
      const cache=await caches.open(CACHE_NAME);
      await cache.delete(fallbackRequest(desc));
    }catch{}
  }

  function entryResponse(entry){
    return new Response(entry.bytes.slice(0),{
      status:entry.status||200,
      statusText:entry.statusText||"",
      headers:entry.headers||[]
    });
  }
  async function digest(buffer){
    if(!globalThis.crypto?.subtle)return "";
    return [...new Uint8Array(await crypto.subtle.digest("SHA-256",buffer))]
      .map(x=>x.toString(16).padStart(2,"0")).join("");
  }
  async function validEntry(desc,entry){
    if(!entry?.bytes)return false;
    if(desc.bytes&&entry.bytes.byteLength!==desc.bytes)return false;
    if(desc.sha256&&(await digest(entry.bytes))!==desc.sha256)return false;
    return true;
  }
  async function remove(desc){
    const key=keyFor(desc);
    memory.delete(key);
    try{await idbDelete(key)}catch{}
    await fallbackDelete(desc);
    stats.invalidated++;
  }
  async function stored(desc){
    const key=keyFor(desc),mem=memory.get(key);
    if(mem){
      if(await validEntry(desc,mem))return mem;
      await remove(desc);
    }
    let entry=null;
    try{entry=await idbGet(key)}catch(error){console.warn("DruMaster cache read failed",error)}
    if(!entry)entry=await fallbackGet(desc);
    if(entry&&await validEntry(desc,entry)){
      memory.set(key,entry);
      return entry;
    }
    if(entry)await remove(desc);
    return null;
  }
  async function persist(desc,entry){
    memory.set(entry.key,entry);
    try{await idbPut(entry);return true}
    catch(error){console.warn("DruMaster IndexedDB store failed",error)}
    return fallbackPut(desc,entry);
  }

  async function fetchAndStore(input,init,desc){
    const response=await baseFetch(input,{...(init||{}),cache:"no-store"});
    if(!response.ok)return response;
    const bytes=await response.arrayBuffer();
    if(desc.bytes&&bytes.byteLength!==desc.bytes)throw new Error(`取得データが不完全です（${bytes.byteLength.toLocaleString()} / ${desc.bytes.toLocaleString()} bytes）`);
    if(desc.sha256&&(await digest(bytes))!==desc.sha256)throw new Error("取得データの内容が一致しません");
    const entry={
      key:keyFor(desc),
      url:desc.absolute,
      version:desc.version,
      bytes,
      status:response.status,
      statusText:response.statusText,
      headers:[...response.headers.entries()],
      savedAt:Date.now()
    };
    await persist(desc,entry);
    stats.downloaded++;
    return entryResponse(entry);
  }

  async function cachedFetch(input,init){
    const method=String(init?.method||input?.method||"GET").toUpperCase();
    if(method!=="GET")return baseFetch(input,init);
    const desc=descriptorFor(input);
    if(!desc)return baseFetch(input,init);
    const entry=await stored(desc);
    if(entry){stats.reused++;return entryResponse(entry)}
    const key=keyFor(desc);
    if(!inflight.has(key))inflight.set(key,fetchAndStore(input,init,desc).finally(()=>inflight.delete(key)));
    return (await inflight.get(key)).clone();
  }

  globalThis.fetch=cachedFetch;
  songApi.nativeFetch=cachedFetch;
  globalThis.DruMasterAssetCache={
    descriptorFor,
    invalidate:async input=>{const desc=descriptorFor(input);if(desc)await remove(desc)},
    persistent:()=>typeof indexedDB!=="undefined"||typeof caches!=="undefined",
    cachedAssetCount:async()=>{
      try{
        const db=await openDb();
        if(!db)return memory.size;
        return await timeout(new Promise((resolve,reject)=>{
          const request=db.transaction(STORE_NAME,"readonly").objectStore(STORE_NAME).count();
          request.onsuccess=()=>resolve(request.result);
          request.onerror=()=>reject(request.error);
        }),5000,"キャッシュ件数の取得がタイムアウトしました");
      }catch{return memory.size}
    },
    stats:()=>({...stats})
  };
  globalThis.DruMasterScoreOfflineCache={
    isReady:()=>true,
    persistent:globalThis.DruMasterAssetCache.persistent,
    cachedAssetCount:globalThis.DruMasterAssetCache.cachedAssetCount,
    lastStats:globalThis.DruMasterAssetCache.stats
  };
})();
