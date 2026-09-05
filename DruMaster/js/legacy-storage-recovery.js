(()=>{
  'use strict';

  const TARGET_DB='drumaster-ranking';
  const TARGET_STORE='plays';
  const REPORT_KEY='drumasterLegacyRecoveryReport:v1';
  const MARKER_PREFIX='drumasterLegacyRecovered:v1:';
  const SCORE_KEYS=['score','finalScore','resultScore','totalScore','points','bestScore','best'];
  const SONG_KEYS=['songId','musicId','trackId','chartSongId','song','music'];
  const DATE_KEYS=['playedAtClient','playedAt','timestamp','createdAt','date','time'];
  const PERFECT_KEYS=['perfect','perfectCount'];
  const GREAT_KEYS=['great','greatCount'];
  const GOOD_KEYS=['good','goodCount'];
  const MISS_KEYS=['miss','missCount'];
  const COMBO_KEYS=['maxCombo','comboMax','bestCombo'];
  const RELEVANT=/drum|master|muster|score|result|play|history|record|best/i;
  let running=false;

  const safe=s=>String(s??'').trim().replace(/[^A-Za-z0-9._:-]/g,'_');
  const clampScore=v=>{const n=Number(v);return Number.isFinite(n)?Math.max(0,Math.min(1000000,Math.trunc(n))):null;};
  const first=(obj,keys)=>{for(const k of keys)if(obj&&obj[k]!=null)return obj[k];return null;};
  const asInt=v=>{const n=Number(v);return Number.isFinite(n)?Math.max(0,Math.trunc(n)):0;};
  const currentSongId=()=>document.documentElement.dataset.songId||document.body?.dataset.songId||globalThis.DruMasterSongs?.current?.id||localStorage.getItem('drumasterSongId')||localStorage.getItem('drumusterSongId')||document.querySelector('#songSelect')?.value||'nanairo';
  const chartId=()=>document.body?.dataset.chartId||'default';
  const rankingVersion=()=>document.body?.dataset.rankingVersion||'1';

  function hash32(text){let h=2166136261;for(let i=0;i<text.length;i++){h^=text.charCodeAt(i);h=Math.imul(h,16777619);}return (h>>>0).toString(16).padStart(8,'0');}

  function parseLoose(raw){
    if(raw==null)return null;
    if(typeof raw!=='string')return raw;
    const t=raw.trim();
    if(!t)return null;
    try{return JSON.parse(t);}catch{}
    const n=Number(t.replace(/,/g,''));
    return Number.isFinite(n)?n:t;
  }

  function normalizeCandidate(value,source,context={}){
    if(value==null)return null;
    if(typeof value==='number'){
      if(!RELEVANT.test(source))return null;
      const score=clampScore(value);
      if(score==null||score<=0)return null;
      return {source,score,songId:context.songId||currentSongId(),scoreOnly:true};
    }
    if(typeof value!=='object'||Array.isArray(value))return null;

    const rawScore=first(value,SCORE_KEYS);
    const score=clampScore(rawScore);
    if(score==null||score<=0)return null;

    const perfect=asInt(first(value,PERFECT_KEYS));
    const great=asInt(first(value,GREAT_KEYS));
    const good=asInt(first(value,GOOD_KEYS));
    const miss=asInt(first(value,MISS_KEYS));
    const noteCount=perfect+great+good+miss;
    const rawSong=first(value,SONG_KEYS);
    let songId=typeof rawSong==='object'?(rawSong?.id||rawSong?.songId||rawSong?.slug):rawSong;
    songId=safe(songId||context.songId||currentSongId()).slice(0,80)||currentSongId();
    const playedAt=first(value,DATE_KEYS);
    const parsedDate=playedAt!=null&&Number.isFinite(Date.parse(String(playedAt)))?new Date(String(playedAt)).toISOString():null;
    const auto=Boolean(value.autoPlay||value.autoplay||value.auto||String(value.playMode||'').toLowerCase()==='auto');
    const noScore=Boolean(value.noScore||value.noscore);
    if(auto||noScore)return null;

    return {
      source,score,songId,
      chartId:safe(value.chartId||value.difficulty||context.chartId||chartId()).slice(0,80)||'default',
      rankingVersion:safe(value.rankingVersion||context.rankingVersion||rankingVersion()).slice(0,32)||'1',
      perfect,great,good,miss,noteCount,
      maxCombo:first(value,COMBO_KEYS)==null?null:asInt(first(value,COMBO_KEYS)),
      playedAtClient:parsedDate,
      scoreOnly:noteCount<1
    };
  }

  function walk(value,source,out,depth=0,context={}){
    if(depth>6||value==null)return;
    const c=normalizeCandidate(value,source,context);
    if(c)out.push(c);
    if(typeof value!=='object')return;
    if(Array.isArray(value)){
      for(let i=0;i<value.length&&i<20000;i++)walk(value[i],`${source}[${i}]`,out,depth+1,context);
      return;
    }
    for(const [k,v] of Object.entries(value)){
      if(v&&typeof v==='object')walk(v,`${source}.${k}`,out,depth+1,context);
      else if(typeof v==='string'&&(v.startsWith('{')||v.startsWith('['))){const p=parseLoose(v);if(p&&p!==v)walk(p,`${source}.${k}`,out,depth+1,context);}
    }
  }

  function scanStorage(storage,label,out){
    for(let i=0;i<storage.length;i++){
      const key=storage.key(i);if(!key)continue;
      if(key.startsWith('drumasterRanking')||key.startsWith('drumasterLegacy'))continue;
      const raw=storage.getItem(key);
      const parsed=parseLoose(raw);
      const source=`${label}:${key}`;
      if(typeof parsed==='number'){
        const c=normalizeCandidate(parsed,source,{});if(c)out.push(c);
      }else if(parsed&&typeof parsed==='object')walk(parsed,source,out);
    }
  }

  async function readStore(dbName,storeName,out){
    await new Promise(resolve=>{
      const req=indexedDB.open(dbName);
      req.onerror=()=>resolve();
      req.onsuccess=()=>{
        const db=req.result;
        try{
          if(!db.objectStoreNames.contains(storeName)){db.close();return resolve();}
          const tx=db.transaction(storeName,'readonly');
          const store=tx.objectStore(storeName);
          const get=store.getAll();
          get.onsuccess=()=>{
            const rows=get.result||[];
            for(let i=0;i<rows.length;i++)walk(rows[i],`idb:${dbName}/${storeName}[${i}]`,out);
          };
          tx.oncomplete=()=>{db.close();resolve();};
          tx.onerror=()=>{db.close();resolve();};
          tx.onabort=()=>{db.close();resolve();};
        }catch{db.close();resolve();}
      };
    });
  }

  async function scanIndexedDb(out){
    if(typeof indexedDB.databases!=='function')return;
    let dbs=[];try{dbs=await indexedDB.databases();}catch{return;}
    for(const info of dbs){
      const name=info?.name;if(!name||name===TARGET_DB)continue;
      await new Promise(resolve=>{
        const req=indexedDB.open(name);
        req.onerror=()=>resolve();
        req.onsuccess=async()=>{
          const db=req.result;
          const stores=[...db.objectStoreNames];db.close();
          for(const store of stores)await readStore(name,store,out);
          resolve();
        };
      });
    }
  }

  async function putTarget(play){
    const db=await new Promise((resolve,reject)=>{const r=indexedDB.open(TARGET_DB,1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
    await new Promise((resolve,reject)=>{const tx=db.transaction(TARGET_STORE,'readwrite');tx.objectStore(TARGET_STORE).put(play);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});
    db.close();
  }

  async function recoverFull(c,ranking){
    const playerId=ranking.getPlayerId();
    const displayName=ranking.getPlayerName?.()||'PLAYER';
    const sourceId=hash32(`${c.source}|${c.songId}|${c.score}|${c.perfect}|${c.great}|${c.good}|${c.miss}|${c.playedAtClient||''}`);
    const playId=`recovered:${safe(playerId).slice(0,32)}:${sourceId}`.slice(0,128);
    const marker=MARKER_PREFIX+playId;
    if(localStorage.getItem(marker)==='1')return false;
    const now=new Date().toISOString();
    await putTarget({
      playId,playerId,displayName,songId:c.songId,chartId:c.chartId,rankingVersion:c.rankingVersion,
      chartVersion:'recovered-browser-storage',gameVersion:'legacy-recovery',score:c.score,
      perfect:c.perfect,great:c.great,good:c.good,miss:c.miss,noteCount:c.noteCount,maxCombo:c.maxCombo,
      playMode:'recovered',autoPlay:false,noScore:false,playedAtClient:c.playedAtClient||now,createdAtLocal:now,
      syncStatus:'pending',retryCount:0,lastAttemptAt:null,lastError:null,
      serverResult:{recoveredFromBrowserStorage:true,source:c.source.slice(0,180)}
    });
    localStorage.setItem(marker,'1');
    return true;
  }

  async function recoverScoreOnly(c,ranking){
    const playerId=ranking.getPlayerId();
    const sourceId=`storage-${hash32(`${c.source}|${c.songId}|${c.score}`)}`;
    const marker=`${MARKER_PREFIX}${playerId}:${sourceId}`;
    if(localStorage.getItem(marker)===String(c.score))return false;
    const endpoint=String(ranking.getEndpoint()).replace(/\/$/,'');
    const response=await fetch(`${endpoint}/v1/legacy-best`,{method:'POST',headers:{'content-type':'application/json'},cache:'no-store',body:JSON.stringify({
      playerId,displayName:ranking.getPlayerName?.()||'PLAYER',songId:c.songId,chartId:c.chartId||chartId(),rankingVersion:c.rankingVersion||rankingVersion(),score:c.score,legacySource:sourceId
    })});
    if(!response.ok)throw new Error(`legacy recovery HTTP ${response.status}`);
    const payload=await response.json().catch(()=>({}));
    const now=new Date().toISOString();
    const playId=payload.playId||`recovered-best:${safe(playerId).slice(0,32)}:${hash32(sourceId)}`;
    await putTarget({playId,playerId,displayName:ranking.getPlayerName?.()||'PLAYER',songId:c.songId,chartId:c.chartId||chartId(),rankingVersion:c.rankingVersion||rankingVersion(),chartVersion:'legacy-best-only',gameVersion:'legacy-recovery',score:c.score,perfect:0,great:0,good:0,miss:0,noteCount:0,maxCombo:null,playMode:'legacy',autoPlay:false,noScore:false,playedAtClient:now,createdAtLocal:now,syncStatus:'synced',retryCount:0,lastAttemptAt:now,lastError:null,serverResult:{recoveredFromBrowserStorage:true,legacyBest:true,source:c.source.slice(0,180)}});
    localStorage.setItem(marker,String(c.score));
    return true;
  }

  function dedupe(list){
    const map=new Map();
    for(const c of list){
      const key=`${c.source}|${c.songId}|${c.score}|${c.perfect||0}|${c.great||0}|${c.good||0}|${c.miss||0}|${c.playedAtClient||''}`;
      if(!map.has(key))map.set(key,c);
    }
    return [...map.values()];
  }

  async function run(){
    if(running)return;
    const ranking=globalThis.DruMasterRanking;if(!ranking)return;
    running=true;
    const found=[];
    try{
      scanStorage(localStorage,'localStorage',found);
      try{scanStorage(sessionStorage,'sessionStorage',found);}catch{}
      await scanIndexedDb(found);
      const candidates=dedupe(found);
      let imported=0,full=0,scoreOnly=0,failed=0;
      for(const c of candidates){
        try{
          const changed=c.scoreOnly?await recoverScoreOnly(c,ranking):await recoverFull(c,ranking);
          if(changed){imported++;if(c.scoreOnly)scoreOnly++;else full++;}
        }catch(e){failed++;console.warn('DruMaster storage recovery item failed',c.source,e);}
      }
      if(imported)await ranking.syncAll?.();
      const report={at:new Date().toISOString(),found:candidates.length,imported,full,scoreOnly,failed,sources:candidates.slice(0,200).map(c=>({source:c.source,songId:c.songId,score:c.score,full:!c.scoreOnly}))};
      localStorage.setItem(REPORT_KEY,JSON.stringify(report));
      dispatchEvent(new CustomEvent('drumaster-legacy-storage-recovered',{detail:report}));
      if(imported){
        const el=document.getElementById('rankingSyncState');
        if(el)el.textContent=`過去記録を${imported}件復元 · 同期中…`;
      }
    }finally{running=false;}
  }

  function boot(){run().catch(console.error);addEventListener('focus',()=>run().catch(console.error));setTimeout(()=>run().catch(console.error),5000);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
