(()=>{
  'use strict';

  const MAX_RECORDS=10;
  let renderToken=0;

  const currentSongId=()=>globalThis.DruMasterSongs?.current?.id
    || document.documentElement.dataset.songId
    || document.body?.dataset.songId
    || document.querySelector('#songSelect')?.value
    || 'nanairo';

  const dateText=value=>{
    const d=new Date(value||Date.now());
    if(!Number.isFinite(d.getTime()))return '';
    const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0');
    return `${y}.${m}.${day}`;
  };

  const scoreText=value=>Math.max(0,Math.round(Number(value)||0)).toLocaleString('en-US');

  async function fetchHistory(){
    const ranking=globalThis.DruMasterRanking;
    if(!ranking)return [];
    const endpoint=String(ranking.getEndpoint?.()||'').replace(/\/$/,'');
    if(!endpoint)return [];
    const ids=[ranking.getPlayerId?.(),...(ranking.getLinkedPlayerIds?.()||[])].filter(Boolean);
    const seen=new Set(),all=[];
    for(const id of [...new Set(ids)]){
      try{
        const r=await fetch(`${endpoint}/v1/players/${encodeURIComponent(id)}/plays?limit=5000`,{cache:'no-store',headers:{accept:'application/json'}});
        if(!r.ok)continue;
        const payload=await r.json();
        for(const p of Array.isArray(payload?.plays)?payload.plays:[]){
          if(!p?.playId||seen.has(p.playId)||p.autoPlay||p.noScore)continue;
          seen.add(p.playId);all.push(p);
        }
      }catch{}
    }
    return all;
  }

  function render(rows){
    const host=document.querySelector('#rankingList');
    const result=document.querySelector('#result');
    if(!host||!result||result.classList.contains('hidden'))return;
    const panel=result.querySelector('.ranking-panel');
    const title=panel?.querySelector('.ranking-title h3');
    const meta=panel?.querySelector('.ranking-title span');
    if(title)title.textContent='RECORD RANKING';
    if(meta)meta.textContent='TOP 10';
    panel?.classList.remove('best-achieved','silver-achieved','bronze-achieved');
    result.classList.remove('new-best','new-second','new-third');
    host.replaceChildren();
    if(!rows.length){
      const empty=document.createElement('div');
      empty.className='ranking-empty';
      empty.textContent='記録はまだありません';
      host.appendChild(empty);
      return;
    }
    const podiumNames=['gold','silver','bronze'];
    rows.forEach((row,i)=>{
      const item=document.createElement('div');
      const podium=podiumNames[i]||'';
      item.className='ranking-row'+(podium?` rank-${podium}`:'');
      item.style.setProperty('--row-i',String(i));
      const rank=document.createElement('span');
      const scoreCell=document.createElement('span');
      const scoreNode=document.createElement('span');
      const date=document.createElement('span');
      rank.className='rank-no';scoreCell.className='rank-score-cell';scoreNode.className='rank-score';date.className='rank-date';
      rank.textContent=String(i+1);
      scoreNode.textContent=scoreText(row.score);
      date.textContent=dateText(row.playedAtClient||row.receivedAtServer||row.createdAtLocal);
      scoreCell.appendChild(scoreNode);
      item.append(rank,scoreCell,date);
      host.appendChild(item);
    });
  }

  async function refresh(){
    const token=++renderToken;
    const result=document.querySelector('#result');
    if(!result||result.classList.contains('hidden')||result.classList.contains('autoplay')||result.classList.contains('no-score'))return;
    const all=await fetchHistory();
    if(token!==renderToken)return;
    const songId=currentSongId();
    const rows=all
      .filter(p=>(p.songId||'nanairo')===songId)
      .sort((a,b)=>Number(b.score||0)-Number(a.score||0)||String(a.receivedAtServer||a.playedAtClient||'').localeCompare(String(b.receivedAtServer||b.playedAtClient||'')))
      .slice(0,MAX_RECORDS);
    render(rows);
  }

  function install(){
    const result=document.querySelector('#result');
    if(result){
      const observer=new MutationObserver(()=>{if(!result.classList.contains('hidden'))setTimeout(()=>refresh().catch(console.error),0)});
      observer.observe(result,{attributes:true,attributeFilter:['class']});
    }
    addEventListener('drumaster-ranking-synced',()=>refresh().catch(console.error));
    setTimeout(()=>refresh().catch(console.error),1500);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();
