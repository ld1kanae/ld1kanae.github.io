"use strict";

(()=>{
  const STORAGE_KEY="drumasterRankingV3",
        PERFORMANCE_STORAGE_KEY="drumasterPerformanceRankingV2",MAX_RECORDS=10,
        RESET_KEY="drumasterRankingReset20260826RawScore1",
        MIN_SCORE_SECONDS=30;

  try{
    if(localStorage.getItem(RESET_KEY)!=="1"){
      ["drumasterRankingV1","drumasterRankingV2","drumasterRankingV3",
       "drumasterPerformanceRankingV1","drumasterPerformanceRankingV2"]
        .forEach(key=>localStorage.removeItem(key));
      localStorage.setItem(RESET_KEY,"1");
    }
  }catch{}

  const resultEl=document.querySelector("#result");
  if(!resultEl)return;

  const song=()=>globalThis.DruMasterSongs?.current||{id:"nanairo",title:"なないろ",artist:"BUMP OF CHICKEN"};

  function clearResultState(){
    resultEl.classList.remove("result-reveal","new-best","new-second","new-third","no-score");
    const panel=resultEl.querySelector(".ranking-panel");
    panel?.classList.remove("best-achieved","silver-achieved","bronze-achieved");
    const note=resultEl.querySelector("#resultScoreNote");
    if(note){note.textContent="";note.classList.add("hidden")}
  }

  function retryCurrentSong(){
    resultEl.classList.add("hidden");
    clearResultState();
    const start=document.querySelector("#start");
    if(!start){location.reload();return}
    start.disabled=false;
    start.click();
  }
  function goHome(){
    const url=new URL(location.href);
    url.searchParams.delete("v");
    location.href=url.toString();
  }

  function installMarkup(){
    const s=song();
    resultEl.innerHTML=`
      <p class="eyebrow result-step result-step-1">RESULT</p>
      <h2 class="result-step result-step-1">${s.title}</h2>
      <p class="result-song-sub result-step result-step-1">${s.artist}</p>
      <p class="result-score-label result-step result-step-2">SCORE</p>
      <strong id="finalScore" class="result-step result-step-score">0</strong>
      <p id="resultScoreNote" class="result-score-note hidden"></p>
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
      <div class="best-celebration" aria-hidden="true"></div>
      <div class="result-actions result-step result-step-5">
        <button id="retry" type="button">リトライ</button>
        <button id="home" type="button">ホーム</button>
      </div>`;
    document.querySelector("#retry").onclick=retryCurrentSong;
    document.querySelector("#home").onclick=goHome;
  }

  function readAll(){
    try{
      const data=JSON.parse(localStorage.getItem(STORAGE_KEY)||"[]");
      return Array.isArray(data)?data.filter(x=>x&&Number.isFinite(+x.score)&&typeof x.date==="string"):[];
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
    const host=document.querySelector("#rankingList"),panel=resultEl.querySelector(".ranking-panel"),meta=resultEl.querySelector(".ranking-title span");
    if(!host)return -1;
    const currentIndex=currentId?rows.findIndex(row=>row.id===currentId):-1;

    resultEl.classList.remove("new-best","new-second","new-third");
    panel?.classList.remove("best-achieved","silver-achieved","bronze-achieved");
    if(currentIndex===0)panel?.classList.add("best-achieved");
    else if(currentIndex===1)panel?.classList.add("silver-achieved");
    else if(currentIndex===2)panel?.classList.add("bronze-achieved");
    if(meta)meta.textContent=currentIndex===0?"NEW BEST":currentIndex===1?"NEW 2ND":currentIndex===2?"NEW 3RD":"TOP 10";

    host.replaceChildren();
    if(!rows.length){
      const empty=document.createElement("div");
      empty.className="ranking-empty";
      empty.textContent="記録はまだありません";
      host.appendChild(empty);
      return currentIndex;
    }

    const podiumNames=["gold","silver","bronze"];
    rows.forEach((row,i)=>{
      const isCurrent=row.id===currentId,podium=podiumNames[i]||"";
      const item=document.createElement("div");
      item.className="ranking-row"+
        (isCurrent?" current":"")+
        (podium?` rank-${podium}`:"")+
        (row.hidden?" hidden-record":"")+
        (row.input==="mic"?" mic-record":"")+
        (isCurrent&&i<3?" podium-record":"")+
        (isCurrent&&i===0?" best-record":"");
      item.style.setProperty("--row-i",String(i));
      const rank=document.createElement("span"),scoreCell=document.createElement("span"),scoreNode=document.createElement("span"),date=document.createElement("span");
      rank.className="rank-no";scoreCell.className="rank-score-cell";scoreNode.className="rank-score";date.className="rank-date";
      rank.textContent=`${i+1}`;
      scoreNode.textContent=scoreText(row.score);
      date.textContent=row.date;
      scoreCell.appendChild(scoreNode);
      if(row.hidden)scoreCell.appendChild(createHiddenMark());
      if(row.input==="mic")scoreCell.appendChild(createMicMark());
      if(isCurrent&&i<3){
        const badge=document.createElement("span");
        badge.className=`podium-badge ${podium}`;
        badge.textContent=i===0?"BEST":i===1?"2ND":"3RD";
        scoreCell.appendChild(badge);
      }
      item.append(rank,scoreCell,date);
      host.appendChild(item);
    });

    if(currentIndex>=0&&currentIndex<3){
      void resultEl.offsetWidth;
      resultEl.classList.add(currentIndex===0?"new-best":currentIndex===1?"new-second":"new-third");
    }
    return currentIndex;
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

  function showNoScore(performanceRun){
    resultEl.classList.add("no-score");
    const scoreNode=document.querySelector("#finalScore"),note=resultEl.querySelector("#resultScoreNote");
    if(scoreNode)scoreNode.textContent="NO SCORE";
    if(note){note.textContent=`演奏時間が${MIN_SCORE_SECONDS}秒未満のためランキング対象外です`;note.classList.remove("hidden")}
    renderRanking(performanceRun?readPerformanceRanking():readRanking());
  }

  function reveal(){
    resultEl.classList.remove("result-reveal");
    void resultEl.offsetWidth;
    resultEl.classList.add("result-reveal");
  }

  function showResult(){
    resultEl.classList.remove("hidden");
    globalThis.DruMasterResultFanfare?.play?.();
    reveal();
  }

  installMarkup();

  finish=function(){
    /* AudioContext time stops while paused, so this is actual active play time
       and does not count time spent on the pause screen. It is intentionally
       independent of the selected tempo percentage. */
    const playedSeconds=Math.max(0,Number(ac?.currentTime||0)-Number(startedAt||0));
    running=false;
    cancelAnimationFrame(raf);
    game.classList.add("hidden");
    clearResultState();

    const final=Math.max(0,Math.round(score));
    document.querySelector("#perfectCount").textContent=counts.perfect;
    document.querySelector("#greatCount").textContent=counts.great;
    document.querySelector("#goodCount").textContent=counts.good;
    document.querySelector("#missCount").textContent=counts.miss;
    resultEl.classList.toggle("autoplay",autoplay);

    const performanceMode=globalThis.DruMasterPerformanceMode,
          performanceRun=!!performanceMode?.isPerformanceRun?.();
    performanceMode?.stopMic?.();

    if(autoplay){
      setRankingKind(false);
      document.querySelector("#finalScore").textContent="AUTO PLAY";
      renderRanking(readRanking());
      showResult();
      return;
    }

    if(playedSeconds<MIN_SCORE_SECONDS){
      setRankingKind(performanceRun);
      showNoScore(performanceRun);
      showResult();
      return;
    }

    if(performanceRun){
      setRankingKind(true);
      const input=performanceMode.isPadRun?.()?"mic":"touch",
            {rows,currentId}=addPerformanceRecord(final,input);
      renderRanking(rows,currentId);
      showResult();
      animateScore(final);
      return;
    }

    setRankingKind(false);
    const mode=globalThis.DruMasterMode,
          hiddenMode=!!(mode?.wasHiddenRun?.()||mode?.isHidden?.()||document.body.dataset.hiddenRun==="1");
    const {rows,currentId}=addRecord(final,hiddenMode);
    renderRanking(rows,currentId);
    showResult();
    animateScore(final);
  };
})();
