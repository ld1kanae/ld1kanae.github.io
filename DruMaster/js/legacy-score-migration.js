(()=>{
  'use strict';

  const DB_NAME='drumaster-ranking';
  const DB_VERSION=1;
  const STORE='plays';
  const MARKER_PREFIX='drumasterLegacyBestUploaded:v3:';
  let running=false;

  const clampScore=value=>{
    const n=Number(value);
    return Number.isFinite(n)?Math.max(0,Math.min(1000000,Math.trunc(n))):0;
  };
  const safeId=value=>String(value||'').trim().replace(/[^A-Za-z0-9._:-]/g,'_');

  function currentSongId(){
    return document.documentElement.dataset.songId
      || document.body?.dataset.songId
      || globalThis.DruMasterSongs?.current?.id
      || localStorage.getItem('drumasterSongId')
      || localStorage.getItem('drumusterSongId')
      || document.querySelector('#songSelect')?.value
      || 'nanairo';
  }

  function legacyRecords(){
    const records=[];
    const add=(source,songId,value)=>{
      const score=clampScore(value);
      const song=safeId(songId);
      const src=safeId(source);
      if(score<=0||!song||!src)return;
      records.push({legacySource:src.slice(0,64),songId:song.slice(0,80),score,sourceKey:source});
    };

    // Production DruMuster / DruMaster builds stored the active song's BEST here.
    for(const key of ['drumusterBest','drumasterBest']){
      const value=localStorage.getItem(key);
      if(value!==null)add(key,currentSongId(),value);
    }

    // The earlier DruMaster2 build used a per-song BEST key. localStorage is
    // origin-wide on GitHub Pages, so these records survive path/rename changes.
    // Also accept equivalent DruMaster/DruMuster per-song key spellings from
    // intermediate builds without touching unrelated ld1kanae.github.io data.
    const patterns=[
      /^DruMaster2\.best\.([A-Za-z0-9._:-]+)$/i,
      /^DruMaster\.best\.([A-Za-z0-9._:-]+)$/i,
      /^DruMuster\.best\.([A-Za-z0-9._:-]+)$/i,
      /^drumasterBest[.:_-]([A-Za-z0-9._:-]+)$/i,
      /^drumusterBest[.:_-]([A-Za-z0-9._:-]+)$/i
    ];
    for(let i=0;i<localStorage.length;i++){
      const key=localStorage.key(i);
      if(!key)continue;
      for(const pattern of patterns){
        const match=key.match(pattern);
        if(!match)continue;
        add(key,match[1],localStorage.getItem(key));
        break;
      }
    }

    // A source key is one actual persisted historical snapshot. Keep separate
    // sources separate; only dedupe exact source/song duplicates.
    const unique=new Map();
    for(const record of records){
      const key=`${record.legacySource}::${record.songId}`;
      const previous=unique.get(key);
      if(!previous||record.score>previous.score)unique.set(key,record);
    }
    return [...unique.values()];
  }

  function openDb(){
    return new Promise((resolve,reject)=>{
      const req=indexedDB.open(DB_NAME,DB_VERSION);
      req.onupgradeneeded=()=>{
        const db=req.result;
        if(!db.objectStoreNames.contains(STORE)){
          const store=db.createObjectStore(STORE,{keyPath:'playId'});
          store.createIndex('syncStatus','syncStatus',{unique:false});
          store.createIndex('playedAtClient','playedAtClient',{unique:false});
        }
      };
      req.onsuccess=()=>resolve(req.result);
      req.onerror=()=>reject(req.error);
    });
  }

  function legacyPlayId(playerId,songId,source){
    return `legacy2:${safeId(playerId).slice(0,40)}:${safeId(songId).slice(0,32)}:${safeId(source).slice(0,40)}`.slice(0,128);
  }

  async function ensureLocalLegacy({playerId,displayName,songId,chartId,rankingVersion,score,legacySource,serverPlayId}){
    const playId=serverPlayId||legacyPlayId(playerId,songId,legacySource);
    const db=await openDb();
    return await new Promise((resolve,reject)=>{
      const tx=db.transaction(STORE,'readwrite');
      const store=tx.objectStore(STORE);
      const get=store.get(playId);
      let changed=false;
      get.onsuccess=()=>{
        const existing=get.result;
        if(existing&&Number(existing.score||0)>=score)return;
        const now=new Date().toISOString();
        store.put({
          ...(existing||{}),playId,playerId,displayName,songId,chartId,rankingVersion,
          chartVersion:'legacy-best-only',gameVersion:'legacy-import',score,
          perfect:0,great:0,good:0,miss:0,noteCount:0,maxCombo:null,
          playMode:'legacy',autoPlay:false,noScore:false,
          playedAtClient:existing?.playedAtClient||now,
          receivedAtServer:existing?.receivedAtServer||now,
          createdAtLocal:existing?.createdAtLocal||now,
          syncStatus:'synced',retryCount:0,lastAttemptAt:now,lastError:null,
          serverResult:{...(existing?.serverResult||{}),legacyBest:true,legacySource,importedLocally:true}
        });
        changed=true;
      };
      get.onerror=()=>reject(get.error);
      tx.oncomplete=()=>{db.close();resolve({changed,playId});};
      tx.onerror=()=>{db.close();reject(tx.error);};
      tx.onabort=()=>{db.close();reject(tx.error);};
    });
  }

  async function migrate(){
    if(running)return;
    const ranking=globalThis.DruMasterRanking;
    if(!ranking)return;
    const records=legacyRecords();
    if(!records.length)return;
    const playerId=ranking.getPlayerId?.();
    const endpoint=ranking.getEndpoint?.();
    if(!playerId||!endpoint)return;
    const displayName=ranking.getPlayerName?.()||'PLAYER';
    const chartId=document.body?.dataset.chartId||'default';
    const rankingVersion=document.body?.dataset.rankingVersion||'1';

    running=true;
    let localChanged=0,uploaded=0;
    try{
      for(const record of records){
        const data={playerId,displayName,songId:record.songId,chartId,rankingVersion,score:record.score,legacySource:record.legacySource};
        const marker=`${MARKER_PREFIX}${playerId}:${record.legacySource}:${record.songId}:${chartId}:${rankingVersion}`;
        let serverPlayId=null;
        if(localStorage.getItem(marker)!==String(record.score)){
          const response=await fetch(`${String(endpoint).replace(/\/$/,'')}/v1/legacy-best`,{
            method:'POST',headers:{'content-type':'application/json'},cache:'no-store',body:JSON.stringify(data)
          });
          if(!response.ok)throw new Error(`legacy best HTTP ${response.status}`);
          const payload=await response.json().catch(()=>({}));
          serverPlayId=payload?.playId||null;
          localStorage.setItem(marker,String(record.score));
          uploaded++;
        }
        const local=await ensureLocalLegacy({...data,serverPlayId});
        if(local.changed)localChanged++;
      }
      if(localChanged||uploaded)await ranking.syncAll?.();
      dispatchEvent(new CustomEvent('drumaster-legacy-best-migrated',{detail:{playerId,recovered:records.length,uploaded,localChanged}}));
    }catch(error){
      console.warn('DruMaster legacy best migration failed',error);
    }finally{
      running=false;
    }
  }

  function boot(){
    migrate();
    addEventListener('drumaster-ranking-synced',()=>migrate());
    addEventListener('focus',()=>migrate());
    setInterval(migrate,30000);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
  else boot();
})();
