(()=>{
  'use strict';

  if(globalThis.DruMasterLocalHistory)return;

  const DB_NAME='drumaster-local-history';
  const DB_VERSION=1;
  const STORE='plays';
  const TOP10_KEY='drumasterLocalTop10V1';
  const MAX_TOP=10;
  let dbPromise;
  let capturedForVisibleResult=false;

  const uuid=()=>crypto.randomUUID?.()||`${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;

  function currentSongId(){
    const select=document.querySelector('#songSelect');
    return select?.value
      || globalThis.DruMasterSongs?.current?.id
      || document.body?.dataset.songId
      || document.documentElement.dataset.songId
      || localStorage.getItem('drumasterSongId')
      || localStorage.getItem('drumusterSongId')
      || 'nanairo';
  }

  function numberFrom(selector){
    const raw=document.querySelector(selector)?.textContent||'';
    const match=raw.replace(/,/g,'').match(/-?\d+/);
    return match?Number(match[0]):0;
  }

  function isRankableResult(){
    const result=document.querySelector('#result');
    if(!result||result.classList.contains('hidden'))return false;
    const finalText=document.querySelector('#finalScore')?.textContent?.trim()||'';
    const auto=result.classList.contains('autoplay')
      ||document.body?.classList.contains('autoplay')
      ||document.querySelector('#autoToggle')?.checked
      ||/AUTO/i.test(finalText);
    const noScore=result.classList.contains('no-score')||document.body?.classList.contains('no-score');
    return !auto&&!noScore;
  }

  function openDb(){
    if(dbPromise)return dbPromise;
    dbPromise=new Promise((resolve,reject)=>{
      const req=indexedDB.open(DB_NAME,DB_VERSION);
      req.onupgradeneeded=()=>{
        const db=req.result;
        if(!db.objectStoreNames.contains(STORE)){
          const store=db.createObjectStore(STORE,{keyPath:'playId'});
          store.createIndex('songId','songId',{unique:false});
          store.createIndex('playedAtClient','playedAtClient',{unique:false});
        }
      };
      req.onsuccess=()=>resolve(req.result);
      req.onerror=()=>reject(req.error);
    });
    return dbPromise;
  }

  async function put(play){
    const db=await openDb();
    await new Promise((resolve,reject)=>{
      const tx=db.transaction(STORE,'readwrite');
      tx.objectStore(STORE).put(play);
      tx.oncomplete=resolve;
      tx.onerror=()=>reject(tx.error);
      tx.onabort=()=>reject(tx.error);
    });
  }

  async function all(){
    const db=await openDb();
    return await new Promise((resolve,reject)=>{
      const tx=db.transaction(STORE,'readonly');
      const req=tx.objectStore(STORE).getAll();
      req.onsuccess=()=>resolve(req.result||[]);
      req.onerror=()=>reject(req.error);
    });
  }

  function topMap(){
    try{
      const value=JSON.parse(localStorage.getItem(TOP10_KEY)||'{}');
      return value&&typeof value==='object'&&!Array.isArray(value)?value:{};
    }catch{return {}}
  }

  function saveTop(play){
    const map=topMap();
    const songId=String(play.songId||'nanairo');
    const rows=Array.isArray(map[songId])?map[songId]:[];
    rows.push({
      playId:play.playId,
      songId,
      score:Number(play.score||0),
      perfect:Number(play.perfect||0),
      great:Number(play.great||0),
      good:Number(play.good||0),
      miss:Number(play.miss||0),
      maxCombo:play.maxCombo==null?null:Number(play.maxCombo),
      playedAtClient:play.playedAtClient,
      createdAtLocal:play.createdAtLocal,
      localOnly:true
    });
    rows.sort((a,b)=>Number(b.score||0)-Number(a.score||0)||String(a.playedAtClient||'').localeCompare(String(b.playedAtClient||'')));
    map[songId]=rows.slice(0,MAX_TOP);
    try{localStorage.setItem(TOP10_KEY,JSON.stringify(map))}catch(error){console.warn('Local TOP10 mirror write failed',error)}
  }

  function getTop(songId=currentSongId()){
    const rows=topMap()[String(songId)]||[];
    return Array.isArray(rows)?rows:[];
  }

  async function seedFromShared(){
    try{
      const shared=await globalThis.DruMasterRanking?.getLocalPlays?.();
      if(!Array.isArray(shared)||!shared.length)return;
      const existing=new Set((await all()).map(p=>String(p?.playId||'')));
      for(const play of shared){
        if(!play?.playId||existing.has(String(play.playId))||play.autoPlay||play.noScore)continue;
        const copy={...play,localSeeded:true};
        await put(copy);
        saveTop(copy);
        existing.add(String(play.playId));
      }
    }catch(error){console.warn('Local history seed failed',error)}
  }

  async function capture(){
    if(capturedForVisibleResult||!isRankableResult())return null;
    const perfect=numberFrom('#perfectCount');
    const great=numberFrom('#greatCount');
    const good=numberFrom('#goodCount');
    const miss=numberFrom('#missCount');
    const noteCount=perfect+great+good+miss;
    if(noteCount<1)return null;

    capturedForVisibleResult=true;
    const now=new Date().toISOString();
    const play={
      playId:`local:${uuid()}`,
      songId:currentSongId(),
      chartId:document.body?.dataset.chartId||'default',
      rankingVersion:document.body?.dataset.rankingVersion||'1',
      score:numberFrom('#finalScore'),
      perfect,great,good,miss,noteCount,
      maxCombo:numberFrom('#maxCombo')||null,
      playedAtClient:now,
      createdAtLocal:now,
      localOnly:true,
      autoPlay:false,
      noScore:false
    };

    /* The tiny TOP10 mirror is written first. Even if IndexedDB or the network
       is unavailable, the result screen can still recover the local record. */
    saveTop(play);
    try{await put(play)}catch(error){console.error('Local play history write failed',error)}
    dispatchEvent(new CustomEvent('drumaster-local-play-saved',{detail:play}));
    return play;
  }

  function scheduleCapture(){
    requestAnimationFrame(()=>setTimeout(()=>capture().catch(console.error),0));
  }

  function install(){
    const result=document.querySelector('#result');
    if(result){
      const observer=new MutationObserver(()=>{
        if(result.classList.contains('hidden')){
          capturedForVisibleResult=false;
          return;
        }
        scheduleCapture();
      });
      observer.observe(result,{attributes:true,attributeFilter:['class']});
      if(!result.classList.contains('hidden'))scheduleCapture();
    }
    setTimeout(()=>seedFromShared(),1200);
    addEventListener('drumaster-ranking-synced',()=>seedFromShared());
  }

  globalThis.DruMasterLocalHistory={
    getPlays:all,
    getTop,
    captureNow:capture,
    getCurrentSongId:currentSongId,
    seedFromShared
  };

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();
