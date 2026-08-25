"use strict";

(()=>{
  const STORAGE_KEY="drumasterRankingV1";
  const MAX_RECORDS=10;
  const resultEl=document.querySelector("#result");
  if(!resultEl)return;

  function installMarkup(){
    resultEl.innerHTML=`
      <p class="eyebrow">RESULT</p>
      <h2>なないろ</h2>
      <p class="result-song-sub">BUMP OF CHICKEN</p>
      <p class="result-score-label">SCORE</p>
      <strong id="finalScore">0000000</strong>
      <div class="result-summary" aria-label="判定内訳">
        <p><span>PERFECT</span><b id="perfectCount">0</b></p>
        <p><span>GREAT</span><b id="greatCount">0</b></p>
        <p><span>GOOD</span><b id="goodCount">0</b></p>
        <p><span>MISS</span><b id="missCount">0</b></p>
      </div>
      <section class="ranking-panel" aria-label="過去のスコアランキング">
        <div class="ranking-title"><h3>RECORD RANKING</h3><span>TOP 10</span></div>
        <div class="ranking-head"><span>RANK</span><span>SCORE</span><span style="text-align:right">DATE</span></div>
        <div id="rankingList" class="ranking-list"></div>
      </section>
      <button id="retry">RETRY</button>`;
    document.querySelector("#retry").onclick=()=>location.reload();
  }

  function readRanking(){
    try{
      const data=JSON.parse(localStorage.getItem(STORAGE_KEY)||"[]");
      return Array.isArray(data)?data.filter(x=>x&&Number.isFinite(+x.score)&&typeof x.date==="string"):[];
    }catch{return []}
  }

  function writeRanking(rows){
    try{localStorage.setItem(STORAGE_KEY,JSON.stringify(rows))}catch{}
  }

  function localDateString(){
    const d=new Date(),y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,"0"),day=String(d.getDate()).padStart(2,"0");
    return `${y}.${m}.${day}`;
  }

  function scoreText(value){return Math.max(0,Math.round(value)).toLocaleString("en-US")}

  function addRecord(value){
    const id=`${Date.now()}-${Math.random().toString(36).slice(2,8)}`;
    const rows=readRanking();
    rows.push({id,score:Math.max(0,Math.round(value)),date:localDateString()});
    rows.sort((a,b)=>b.score-a.score||String(b.id).localeCompare(String(a.id)));
    const kept=rows.slice(0,MAX_RECORDS);
    writeRanking(kept);
    return {rows:kept,currentId:id};
  }

  function renderRanking(rows,currentId=null){
    const host=document.querySelector("#rankingList");
    if(!host)return;
    host.replaceChildren();
    if(!rows.length){
      const empty=document.createElement("div");
      empty.className="ranking-empty";
      empty.textContent="記録はまだありません";
      host.appendChild(empty);
      return;
    }
    rows.forEach((row,i)=>{
      const item=document.createElement("div");
      item.className="ranking-row"+(row.id===currentId?" current":"");
      const rank=document.createElement("span"),scoreNode=document.createElement("span"),date=document.createElement("span");
      rank.className="rank-no";scoreNode.className="rank-score";date.className="rank-date";
      rank.textContent=`${i+1}`;
      scoreNode.textContent=scoreText(row.score);
      date.textContent=row.date;
      item.append(rank,scoreNode,date);
      host.appendChild(item);
    });
  }

  installMarkup();

  // Replace the legacy single-best result with a persistent dated top-10 ranking.
  finish=function(){
    running=false;
    cancelAnimationFrame(raf);
    game.classList.add("hidden");
    resultEl.classList.remove("hidden");
    resultEl.classList.toggle("autoplay",autoplay);

    const final=Math.max(0,Math.round(score/maxScore*1000000));
    document.querySelector("#perfectCount").textContent=counts.perfect;
    document.querySelector("#greatCount").textContent=counts.great;
    document.querySelector("#goodCount").textContent=counts.good;
    document.querySelector("#missCount").textContent=counts.miss;

    if(autoplay){
      document.querySelector("#finalScore").textContent="AUTO PLAY";
      renderRanking(readRanking());
      return;
    }

    document.querySelector("#finalScore").textContent=scoreText(final);
    const {rows,currentId}=addRecord(final);
    renderRanking(rows,currentId);
  };
})();
