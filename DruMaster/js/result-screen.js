"use strict";

(()=>{
  const STORAGE_KEY="drumasterRankingV2",LEGACY_KEY="drumasterRankingV1",
        PERFORMANCE_STORAGE_KEY="drumasterPerformanceRankingV1",MAX_RECORDS=10;
  const resultEl=document.querySelector("#result");
  if(!resultEl)return;

  const song=()=>globalThis.DruMasterSongs?.current||{id:"nanairo",title:"なないろ",artist:"BUMP OF CHICKEN"};

  function installMarkup(){
    const s=song();
    resultEl.innerHTML=`
      <p class="eyebrow result-step result-step-1">RESULT</p>
      <h2 class="result-step result-step-1">${s.title}</h2>
      <p class="result-song-sub result-step result-step-1">${s.artist}</p>
      <p class="result-score-label result-step result-step-2">SCORE</p>
      <strong id="finalScore" class="result-step result-step-score">0</strong>
      <div class="result-summary result-step result-step-3" aria-label="判定内訳">
        <p><span>PERFECT</span><b id="perfectCount">0</b></p>
        <p><span>GREAT</span><b id="greatCount">0</b></p>
        <p><span>GOOD</span><b id="goodCount">0</b></p>
        <p><span>MISS</span><b id="missCount">0</b></p>
      </div>
      <section class="ranking-panel result-step result-step-4" aria-label="過去のスコアランキング">
        <div class="ranking-title"><h3>RECORD RANKING</h3><span>TOP 10</span></div>
        <div class="ranking-head"><span>RANK</span><span>SCORE</span><span style="text-align:right">DATE</span></div>
        <div id="rankingList" class="ranking-list"></div>
      </section>
      <button id="retry" class="result-step result-step-5">RETRY</button>`;
    document.querySelector("#retry").onclick=()=>location.reload();
  }

  function readAll(){
    try{
      let data=JSON.parse(localStorage.getItem(STORAGE_KEY)||"[]");
      if(!Array.isArray(data))data=[];
      if(!data.length){
        const legacy=JSON.parse(localStorage.getItem(LEGACY_KEY)||"[]");
        if(Array.isArray(legacy)&&legacy.length){
          data=legacy.filter(x=>x&&Number.isFinite(+x.score)&&typeof x.date==="string").map(x=>({...x,song:"nanairo"}));
          writeAll(data);
        }
      }
      return data.filter(x=>x&&Number.isFinite(+x.score)&&typeof x.date==="string");
    }catch{return []}
  }
  function writeAll(rows){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(rows))}catch{}}
  function readRanking(){
    const id=song().id;
    return readAll().filter(x=>(x.song||"nanairo")===id).sort((a,b)=>b.score-a.score||String(b.id).localeCompare(String(a.id))).slice(0,MAX_RECORDS);
  }

  function readPerformanceAll(){
    try{
      const data=JSON.parse(localStorage.getItem(PERFORMANCE_STORAGE_KEY)||"[]");
      return Array.isArray(data)?data.filter(x=>x&&Number.isFinite(+x.score)&&typeof x.date==="string"&&["touch","mic"].includes(x.input)):[];
    }catch{return []}
  }
  function writePerformanceAll(rows){try{localStorage.setItem(PERFORMANCE_STORAGE_KEY,JSON.stringify(rows))}catch{}}
  function readPerformanceRanking(){
    const id=song().id;
    return readPerformanceAll().filter(x=>(x.song||"nanairo")===id).sort((a,b)=>b.score-a.score||String(b.id).localeCompare(String(a.id))).slice(0,MAX_RECORDS);
  }

  function localDateString(){
    const d=new Date(),y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,"0"),day=String(d.getDate()).padStart(2,"0");
    return `${y}.${m}.${day}`;
  }
  function scoreText(value){return Math.max(0,Math.round(value)).toLocaleString("en-US")}

  function addRecord(value,hiddenMode){
    const id=`${Date.now()}-${Math.random().toString(36).slice(2,8)}`,songId=song().id;
    const all=readAll();
    all.push({id,score:Math.max(0,Math.round(value)),date:localDateString(),hidden:!!hiddenMode,song:songId});
    const mine=all.filter(x=>(x.song||"nanairo")===songId).sort((a,b)=>b.score-a.score||String(b.id).localeCompare(String(a.id))).slice(0,MAX_RECORDS);
    const others=all.filter(x=>(x.song||"nanairo")!==songId);
    writeAll([...others,...mine]);
    return {rows:mine,currentId:id};
  }

  function addPerformanceRecord(value,input){
    const id=`${Date.now()}-${Math.random().toString(36).slice(2,8)}`,songId=song().id;
    const all=readPerformanceAll();
    all.push({id,score:Math.max(0,Math.round(value)),date:localDateString(),input:input==="mic"?"mic":"touch",song:songId});
    const mine=all.filter(x=>(x.song||"nanairo")===songId).sort((a,b)=>b.score-a.score||String(b.id).localeCompare(String(a.id))).slice(0,MAX_RECORDS);
    const others=all.filter(x=>(x.song||"nanairo")!==songId);
    writePerformanceAll([...others,...mine]);
    return {rows:mine,currentId:id};
  }

  function createHiddenMark(){
    const mark=document.createElement("span");
    mark.className="hidden-mark";
    mark.setAttribute("aria-label","Hidden Mode");
    mark.title="Hidden Mode";
    mark.innerHTML='<svg viewBox="0 0 28 28" aria-hidden="true"><path class="eye" d="M2.5 14s4.3-7.2 11.5-7.2S25.5 14 25.5 14 21.2 21.2 14 21.2 2.5 14 2.5 14Z"/><circle cx="14" cy="14" r="3.6"/><path class="slash" d="M4.2 3.8 23.8 24.2"/></svg>';
    return mark;
  }

  function createMicMark(){
    const mark=document.createElement("span");
    mark.className="mic-mark";
    mark.setAttribute("aria-label","パッド練習（マイク入力）");
    mark.title="パッド練習（マイク入力）";
    mark.innerHTML='<svg viewBox="0 0 28 28" aria-hidden="true"><rect x="9" y="3.5" width="10" height="14" rx="5"/><path d="M5.5 13.5v.8a8.5 8.5 0 0 0 17 0v-.8M14 22.8v2.7M9.5 25.5h9"/></svg>';
    return mark;
  }

  function setRankingKind(performance){
    const title=resultEl.querySelector(".ranking-title h3"),panel=resultEl.querySelector(".ranking-panel");
    if(title)title.textContent=performance?"PERFORMANCE RANKING":"RECORD RANKING";
    if(panel)panel.setAttribute("aria-label",performance?"どこでもタッチ・パッド練習ランキング":"過去のスコアランキング");
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
      item.className="ranking-row"+(row.id===currentId?" current":"")+(row.hidden?" hidden-record":"")+(row.input==="mic"?" mic-record":"");
      item.style.setProperty("--row-i",String(i));
      const rank=document.createElement("span"),scoreCell=document.createElement("span"),scoreNode=document.createElement("span"),date=document.createElement("span");
      rank.className="rank-no";scoreCell.className="rank-score-cell";scoreNode.className="rank-score";date.className="rank-date";
      rank.textContent=`${i+1}`;
      scoreNode.textContent=scoreText(row.score);
      date.textContent=row.date;
      scoreCell.appendChild(scoreNode);
      if(row.hidden)scoreCell.appendChild(createHiddenMark());
      if(row.input==="mic")scoreCell.appendChild(createMicMark());
      item.append(rank,scoreCell,date);
      host.appendChild(item);
    });
  }

  function animateScore(final){
    const node=document.querySelector("#finalScore");
    if(!node)return;
    const start=performance.now(),durationMs=820;
    node.textContent="0";
    const tick=now=>{
      const p=Math.min(1,(now-start)/durationMs),ease=1-Math.pow(1-p,3);
      node.textContent=scoreText(final*ease);
      if(p<1)requestAnimationFrame(tick);
      else node.textContent=scoreText(final);
    };
    requestAnimationFrame(tick);
  }

  function reveal(){
    resultEl.classList.remove("result-reveal");
    void resultEl.offsetWidth;
    resultEl.classList.add("result-reveal");
  }

  installMarkup();

  finish=function(){
    running=false;
    cancelAnimationFrame(raf);
    game.classList.add("hidden");

    const final=Math.max(0,Math.round(score/maxScore*1000000));
    document.querySelector("#perfectCount").textContent=counts.perfect;
    document.querySelector("#greatCount").textContent=counts.great;
    document.querySelector("#goodCount").textContent=counts.good;
    document.querySelector("#missCount").textContent=counts.miss;
    resultEl.classList.toggle("autoplay",autoplay);

    const performanceMode=globalThis.DruMasterPerformanceMode;
    performanceMode?.stopMic?.();

    if(autoplay){
      setRankingKind(false);
      document.querySelector("#finalScore").textContent="AUTO PLAY";
      renderRanking(readRanking());
      resultEl.classList.remove("hidden");
      reveal();
      return;
    }

    if(performanceMode?.isPerformanceRun?.()){
      setRankingKind(true);
      const input=performanceMode.isPadRun?.()?"mic":"touch",
            {rows,currentId}=addPerformanceRecord(final,input);
      renderRanking(rows,currentId);
      resultEl.classList.remove("hidden");
      reveal();
      animateScore(final);
      return;
    }

    setRankingKind(false);
    const mode=globalThis.DruMasterMode,
          hiddenMode=!!(mode?.wasHiddenRun?.()||mode?.isHidden?.()||document.body.dataset.hiddenRun==="1");
    const {rows,currentId}=addRecord(final,hiddenMode);
    renderRanking(rows,currentId);
    resultEl.classList.remove("hidden");
    reveal();
    animateScore(final);
  };
})();
