(()=>{
  'use strict';

  const LEGACY_KEYS=['drumusterBest','drumasterBest'];
  const MARKER_PREFIX='drumasterLegacyBestUploaded:';
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

  async function migrate(){
    if(running)return;
    const ranking=globalThis.DruMasterRanking;
    if(!ranking)return;
    const score=legacyBest();
    if(score<=0)return;
    const playerId=ranking.getPlayerId?.();
    const endpoint=ranking.getEndpoint?.();
    if(!playerId||!endpoint)return;
    const marker=MARKER_PREFIX+playerId;
    const sent=Number(localStorage.getItem(marker)||0);
    if(sent>=score)return;

    running=true;
    try{
      const response=await fetch(`${String(endpoint).replace(/\/$/,'')}/v1/legacy-best`,{
        method:'POST',
        headers:{'content-type':'application/json'},
        cache:'no-store',
        body:JSON.stringify({
          playerId,
          displayName:ranking.getPlayerName?.()||'PLAYER',
          songId:songId(),
          chartId:document.body?.dataset.chartId||'default',
          rankingVersion:document.body?.dataset.rankingVersion||'1',
          score
        })
      });
      if(!response.ok)throw new Error(`legacy best HTTP ${response.status}`);
      localStorage.setItem(marker,String(score));
      await ranking.syncAll?.();
      dispatchEvent(new CustomEvent('drumaster-legacy-best-migrated',{detail:{playerId,score}}));
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
