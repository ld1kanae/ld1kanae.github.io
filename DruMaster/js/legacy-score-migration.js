(()=>{
  'use strict';

  const LEGACY_KEYS=['drumusterBest','drumasterBest'];
  const MARKER_PREFIX='drumasterLegacyBestUploaded:';
  const DB_NAME='drumaster-ranking';
  const DB_VERSION=1;
  const STORE='plays';
  let running=false;

  function legacyBest(){
    let best=0;
    for(const key of LEGACY_KEYS){
      const value=Number(localStorage.getItem(key)||0);
      if(Number.isFinite(value))best=Math.max(best,Math.max(0,Math.min(1000000,Math.trunc(value))));
    }
    return best;
  }

  function songId(){
    return document.documentElement.dataset.songId
      || document.body?.dataset.songId
      || localStorage.getItem('drumasterSongId')
      || localStorage.getItem('drumusterSongId')
      || document.querySelector('#songSelect')?.value
      || 'nanairo';
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

  async function ensureLocalLegacy({playerId,displayName,songId,chartId,rankingVersion,score}){
    const safe=s=>String(s).replace(/[^A-Za-z0-9._:-]/g,'_');
    const playId=`legacy:${safe(playerId)}:${safe(songId)}:${safe(chartId)}:${safe(rankingVersion)}`.slice(0,128);
    const db=await openDb();
    return await new Promise((resolve,reject)=>{
      const tx=db.transaction(STORE,'readwrite');
      const store=tx.objectStore(STORE);
      const get=store.get(playId);
      let changed=false;
      get.onsuccess=()=>{
        const existing=get.result;
        if(existing && Number(existing.score||0)>=score){
          resolve({changed:false,playId});
          return;
        }
        const now=new Date().toISOString();
        store.put({
          ...(existing||{}),
          playId,
          playerId,
          displayName,
          songId,
          chartId,
          rankingVersion,
          chartVersion:'legacy-best-only',
          gameVersion:'legacy-import',
          score,
          perfect:0,
          great:0,
          good:0,
          miss:0,
          noteCount:0,
          maxCombo:null,
          playMode:'legacy',
          autoPlay:false,
          noScore:false,
          playedAtClient:existing?.playedAtClient||now,
          receivedAtServer:existing?.receivedAtServer||now,
          createdAtLocal:existing?.createdAtLocal||now,
          syncStatus:'synced',
          retryCount:0,
          lastAttemptAt:now,
          lastError:null,
          serverResult:{...(existing?.serverResult||{}),legacyBest:true,importedLocally:true}
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
    const score=legacyBest();
    if(score<=0)return;
    const playerId=ranking.getPlayerId?.();
    const endpoint=ranking.getEndpoint?.();
    if(!playerId||!endpoint)return;

    const data={
      playerId,
      displayName:ranking.getPlayerName?.()||'PLAYER',
      songId:songId(),
      chartId:document.body?.dataset.chartId||'default',
      rankingVersion:document.body?.dataset.rankingVersion||'1',
      score
    };
    const marker=MARKER_PREFIX+playerId;
    const sent=Number(localStorage.getItem(marker)||0);

    running=true;
    try{
      let uploaded=sent>=score;
      if(!uploaded){
        const response=await fetch(`${String(endpoint).replace(/\/$/,'')}/v1/legacy-best`,{
          method:'POST',
          headers:{'content-type':'application/json'},
          cache:'no-store',
          body:JSON.stringify(data)
        });
        if(!response.ok)throw new Error(`legacy best HTTP ${response.status}`);
        localStorage.setItem(marker,String(score));
        uploaded=true;
      }

      const local=await ensureLocalLegacy(data);
      if(uploaded && local.changed){
        await ranking.syncAll?.();
      }
      dispatchEvent(new CustomEvent('drumaster-legacy-best-migrated',{detail:{playerId,score,localImported:true}}));
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
