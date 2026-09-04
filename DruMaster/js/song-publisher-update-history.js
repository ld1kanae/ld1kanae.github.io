"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;

  const STORE_KEY="drumasterPublisherUpdateHistoryV1";
  const MAX_HISTORY=60;
  const LABEL={fullmix:"原曲",base:"オフボーカル",drums:"ドラムのみ",vocals:"ボーカルのみ",midi:"MIDI"};
  const FINAL_SUCCESS=new Set(["GitHub更新完了","登録データ更新完了"]);
  const FINAL_ERROR=new Set(["GitHub更新エラー","エラー"]);
  const IDLE=new Set(["待機中","入力エラー"]);
  const VERIFY_RETRY_MS=[0,700,1200,1800,2600,3600,5000,7000,9000,12000];

  let boundDoc=null,stageObserver=null,modeObserver=null,current=null,baselineById=new Map(),runtimeErrors=[];

  function doc(){try{return frame.contentDocument}catch{return null}}
  function nowIso(){return new Date().toISOString()}
  function delay(ms){return new Promise(r=>setTimeout(r,ms))}
  function safeText(v){return String(v??"").trim()}
  function statusClass(status){return status==="SUCCESS"?"success":status==="ERROR"?"error":"uploading"}
  function readHistory(){
    try{const v=JSON.parse(localStorage.getItem(STORE_KEY)||"[]");return Array.isArray(v)?v:[]}catch{return []}
  }
  function writeHistory(items){
    try{localStorage.setItem(STORE_KEY,JSON.stringify(items.slice(0,MAX_HISTORY)))}catch{}
  }
  function normalizeInterrupted(){
    const items=readHistory();let changed=false;
    for(const item of items){
      if(item?.status==="UPLOADING"){
        item.status="ERROR";item.finishedAt=nowIso();
        item.error="ページの再読み込みまたは終了により更新処理が中断されました。";
        item.logs=[...(item.logs||[]),`[${nowIso()}] ERROR: ${item.error}`];changed=true;
      }
    }
    if(changed)writeHistory(items);
  }
  normalizeInterrupted();
  if(document.documentElement.dataset.dmHistoryParentErrorBound!=="1"){
    document.documentElement.dataset.dmHistoryParentErrorBound="1";
    addEventListener("error",e=>{if(current){runtimeErrors.push(`parent error: ${e.error?.stack||e.message||"unknown"}`);if(runtimeErrors.length>30)runtimeErrors=runtimeErrors.slice(-30)}});
    addEventListener("unhandledrejection",e=>{if(current){const r=e.reason;runtimeErrors.push(`parent unhandledrejection: ${r?.stack||r?.message||String(r||"unknown")}`);if(runtimeErrors.length>30)runtimeErrors=runtimeErrors.slice(-30)}});
  }

  function historyPanel(d){return d.getElementById("dmUpdateHistory")}
  function ensureStyle(d){
    if(d.getElementById("dmUpdateHistoryStyle"))return;
    const s=d.createElement("style");s.id="dmUpdateHistoryStyle";s.textContent=`
      #dmUpdateHistory{display:none}
      body.dm-publisher-update #dmUpdateHistory{display:block}
      .dm-history-head{display:grid;grid-template-columns:116px minmax(0,1fr) 96px;gap:10px;padding:0 8px 8px;color:#6f8294;font-size:9px;font-weight:800;letter-spacing:.08em}
      .dm-history-list{display:grid;gap:7px;max-height:310px;overflow:auto;padding-right:2px}
      .dm-history-empty{padding:18px 10px;text-align:center;color:#708194;font-size:10px;border:1px dashed #283a4a;border-radius:8px}
      .dm-history-item{border:1px solid #263847;border-radius:8px;background:#080f16;overflow:hidden}
      .dm-history-main{display:grid;grid-template-columns:116px minmax(0,1fr) 96px;gap:10px;align-items:start;padding:10px 8px}
      .dm-history-time{color:#77899b;font:9px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:nowrap}
      .dm-history-detail{min-width:0;color:#bac8d5;font-size:10px;line-height:1.55;overflow-wrap:anywhere}
      .dm-history-detail b{color:#edf5fb;font-weight:800}
      .dm-history-status{justify-self:end;font:850 9px/1 Inter,"Noto Sans JP",system-ui,sans-serif;letter-spacing:.07em;padding:6px 7px;border:1px solid;border-radius:999px;white-space:nowrap}
      .dm-history-status.uploading{color:#ffb667;border-color:rgba(255,182,103,.52);background:rgba(255,142,40,.10)}
      .dm-history-status.success{color:#72d6a6;border-color:rgba(114,214,166,.50);background:rgba(54,178,120,.10)}
      .dm-history-status.error{color:#ff7d8d;border-color:rgba(255,125,141,.55);background:rgba(220,57,79,.11)}
      .dm-history-diag{border-top:1px solid #21313e;background:#050a0f;padding:9px}
      .dm-history-diag summary{cursor:pointer;color:#8fa2b4;font-size:9px;font-weight:800;letter-spacing:.06em}
      .dm-history-item.error .dm-history-diag summary{color:#ff9aa6}
      .dm-history-log{margin:8px 0 0;max-height:210px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;color:#91a6b8;font:9px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace}
      .dm-history-item.error .dm-history-log{color:#e9a0aa}
      @media(max-width:640px){.dm-history-head{display:none}.dm-history-main{grid-template-columns:1fr auto}.dm-history-time{grid-column:1}.dm-history-detail{grid-column:1/-1;grid-row:2}.dm-history-status{grid-column:2;grid-row:1}}
    `;d.head.appendChild(s);
  }
  function ensurePanel(d){
    ensureStyle(d);
    let panel=historyPanel(d);if(panel)return panel;
    const grid=d.querySelector(".grid"),mode=d.getElementById("dmPublisherMode");if(!grid||!mode)return null;
    panel=d.createElement("section");panel.id="dmUpdateHistory";panel.className="panel full";
    panel.innerHTML='<h2>UPDATE HISTORY</h2><div class="dm-history-head"><span>TIME</span><span>DETAIL</span><span style="text-align:right">STATUS</span></div><div id="dmUpdateHistoryList" class="dm-history-list"></div>';
    mode.insertAdjacentElement("afterend",panel);render(d);return panel;
  }
  function formatTime(iso){
    try{return new Intl.DateTimeFormat("ja-JP",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false}).format(new Date(iso))}catch{return iso||""}
  }
  function render(d=doc()){
    if(!d)return;const panel=ensurePanel(d);if(!panel)return;
    const list=d.getElementById("dmUpdateHistoryList");if(!list)return;
    const items=readHistory();list.replaceChildren();
    if(!items.length){const empty=d.createElement("div");empty.className="dm-history-empty";empty.textContent="更新履歴はまだありません。";list.appendChild(empty);return}
    for(const item of items){
      const row=d.createElement("article");row.className=`dm-history-item ${statusClass(item.status)}`;
      const main=d.createElement("div");main.className="dm-history-main";
      const time=d.createElement("div");time.className="dm-history-time";time.textContent=formatTime(item.startedAt);
      const detail=d.createElement("div");detail.className="dm-history-detail";
      const song=d.createElement("b");song.textContent=item.songTitle?`${item.songTitle} (${item.songId})`:item.songId||"不明な楽曲";detail.append(song,d.createTextNode(` — ${item.detail||"更新内容不明"}`));
      const status=d.createElement("span");status.className=`dm-history-status ${statusClass(item.status)}`;status.textContent=item.status||"UPLOADING";
      main.append(time,detail,status);row.appendChild(main);
      const logs=Array.isArray(item.logs)?item.logs:[];
      if(logs.length||item.error||item.diagnostics){
        const diag=d.createElement("details");diag.className="dm-history-diag";if(item.status==="ERROR")diag.open=true;
        const summary=d.createElement("summary");summary.textContent=item.status==="ERROR"?"ERROR LOG / DIAGNOSTICS":"DIAGNOSTICS";
        const pre=d.createElement("pre");pre.className="dm-history-log";
        pre.textContent=[item.error?`ERROR: ${item.error}`:"",item.diagnostics||"",...logs].filter(Boolean).join("\n");
        diag.append(summary,pre);row.appendChild(diag);
      }
      list.appendChild(row);
    }
  }
  function upsertHistory(item,d=doc()){
    const items=readHistory(),i=items.findIndex(x=>x.id===item.id);
    const clean={...item};delete clean._midiHashPromise;delete clean._midiFile;
    if(i>=0)items[i]=clean;else items.unshift(clean);writeHistory(items);render(d);
  }
  function appendLog(tx,message,d=doc()){
    if(!tx)return;tx.logs=tx.logs||[];tx.logs.push(`[${nowIso()}] ${message}`);if(tx.logs.length>120)tx.logs=tx.logs.slice(-120);upsertHistory(tx,d);
  }

  function currentSongId(d){return safeText(d.getElementById("dmExistingSong")?.value||d.getElementById("songId")?.value)}
  function currentSongTitle(d){return safeText(d.getElementById("title")?.value)||currentSongId(d)}
  function snapMetadata(d){return {title:safeText(d.getElementById("title")?.value),artist:safeText(d.getElementById("artist")?.value),order:safeText(d.getElementById("order")?.value)}}
  function captureBaseline(d){const id=currentSongId(d);if(id)baselineById.set(id,snapMetadata(d))}
  function scheduleBaseline(d){setTimeout(()=>captureBaseline(d),0);setTimeout(()=>captureBaseline(d),120)}

  function collectChanges(d){
    const id=currentSongId(d),baseline=baselineById.get(id),now=snapMetadata(d),parts=[],assetKeys=[];
    for(const wrap of d.querySelectorAll(".dm-update-control")){
      const select=wrap.querySelector(".dm-update-action"),input=wrap.querySelector('input[type="file"]'),meta=wrap.querySelector(".dm-update-meta");if(!select)continue;
      const key=select.dataset.key||"",label=LABEL[key]||key,action=select.value;
      if(action==="replace"||input?.files?.length){const name=input?.files?.[0]?.name||"ファイル";parts.push(`${label}: ${safeText(meta?.textContent).includes("未登録")?"追加":"差し替え"} (${name})`);assetKeys.push(key)}
      else if(action==="delete"){parts.push(`${label}: 削除`);assetKeys.push(key)}
    }
    if(baseline){
      if(now.title!==baseline.title)parts.push(`曲名: 「${baseline.title}」→「${now.title}」`);
      if(now.artist!==baseline.artist)parts.push(`アーティスト: 「${baseline.artist}」→「${now.artist}」`);
      if(now.order!==baseline.order)parts.push(`表示順: ${baseline.order||"未指定"}→${now.order||"未指定"}`);
    }else{
      if(now.order)parts.push(`表示順: ${now.order}`);
    }
    return {detail:parts.length?parts.join(" / "):"メタデータ更新",assetKeys,includesMidi:assetKeys.includes("midi"),midiFile:d.getElementById("midi")?.files?.[0]||null};
  }

  async function hashBuffer(ab){const h=await crypto.subtle.digest("SHA-256",ab);return [...new Uint8Array(h)].map(v=>v.toString(16).padStart(2,"0")).join("")}
  function parseMidiForGame(ab){
    const d=new DataView(ab);let p=0;
    const need=n=>{if(p+n>d.byteLength)throw Error(`MIDI EOF at ${p}, need ${n}, size ${d.byteLength}`)},str=n=>{need(n);let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s},u32=()=>{need(4);const v=d.getUint32(p);p+=4;return v},u16=()=>{need(2);const v=d.getUint16(p);p+=2;return v},vlq=end=>{let v=0,b,c=0;do{if(p>=end)throw Error(`MIDI VLQ EOF at ${p}/${end}`);b=d.getUint8(p++);v=(v<<7)|(b&127);if(++c>4)throw Error("MIDI VLQ > 4 bytes")}while(b&128);return v};
    if(str(4)!=="MThd")throw Error("MIDI header is not MThd");const header=u32();const format=u16(),tracks=u16(),division=u16();if(division&0x8000)throw Error("SMPTE MIDI is unsupported by game");if(header<6)throw Error(`Invalid MIDI header length: ${header}`);p=8+header;let drumNotes=0,totalNotes=0;
    for(let tr=0;tr<tracks;tr++){
      if(str(4)!=="MTrk")throw Error(`Track ${tr}: MTrk not found`);const len=u32(),end=p+len;if(end>d.byteLength)throw Error(`Track ${tr}: declared length exceeds file`);let run=0;
      while(p<end){vlq(end);let first=d.getUint8(p++),status;if(first<128){if(!run)throw Error(`Track ${tr}: running status missing`);status=run;p--}else{status=first;if(status<240)run=status}
        if(status===255){need(1);p++;const n=vlq(end);if(p+n>end)throw Error(`Track ${tr}: meta event exceeds track`);p+=n;continue}
        if(status===240||status===247){run=0;const n=vlq(end);if(p+n>end)throw Error(`Track ${tr}: sysex exceeds track`);p+=n;continue}
        const hi=status&240,ch=status&15,bytes=(hi===192||hi===208)?1:2;need(bytes);p++;const b=bytes===2?d.getUint8(p++):0;if(hi===144&&b>0){totalNotes++;if(ch===9)drumNotes++}
      }p=end;
    }
    if(!drumNotes)throw Error("Game parser found 0 drum notes on MIDI channel 10");
    return {format,tracks,division,drumNotes,totalNotes};
  }
  function withProbe(url,attempt){const u=new URL(url,location.href);u.searchParams.set("dmGameLoadCheck",`${Date.now()}-${attempt}`);return u.href}
  async function fetchJson(url){const r=await fetch(url,{cache:"no-store"});if(!r.ok)throw Error(`HTTP ${r.status}: ${url}`);return r.json()}
  async function verifyGameLoad(tx,d){
    const expectedFile=tx._midiFile,expectedBytes=expectedFile?.size||null,expectedHash=expectedFile?await tx._midiHashPromise:null;
    const attempts=[];let lastError=null;
    for(let i=0;i<VERIFY_RETRY_MS.length;i++){
      if(VERIFY_RETRY_MS[i])await delay(VERIFY_RETRY_MS[i]);
      try{
        appendLog(tx,`GAME LOAD CHECK ${i+1}/${VERIFY_RETRY_MS.length}: registry取得`,d);
        let meta=null,source="registry.json";
        try{const registry=await fetchJson(withProbe("songs/registry.json",i));meta=registry?.[tx.songId]||null}catch(e){lastError=e}
        if(!meta){source=`songs/${tx.songId}/song-draft.json`;meta=await fetchJson(withProbe(source,i))}
        if(!meta?.midi)throw Error(`${source}: midi URL がありません`);
        const midiPath=new URL(meta.midi,location.href).pathname;
        if(!midiPath.includes(`/songs/${tx.songId}/chart.mid`))throw Error(`MIDI route mismatch: song=${tx.songId}, midi=${meta.midi}`);
        const midiUrl=withProbe(meta.midi,i),r=await fetch(midiUrl,{cache:"no-store"});if(!r.ok)throw Error(`MIDI HTTP ${r.status}: ${midiUrl}`);
        const ab=await r.arrayBuffer(),actualHash=await hashBuffer(ab),parsed=parseMidiForGame(ab);
        if(expectedBytes!=null&&ab.byteLength!==expectedBytes)throw Error(`MIDI bytes mismatch: upload=${expectedBytes}, game=${ab.byteLength}`);
        if(expectedHash&&actualHash!==expectedHash)throw Error(`MIDI SHA-256 mismatch: upload=${expectedHash}, game=${actualHash}`);
        if(meta.midiBytes!=null&&Number(meta.midiBytes)!==ab.byteLength)throw Error(`Metadata midiBytes mismatch: meta=${meta.midiBytes}, game=${ab.byteLength}`);
        if(meta.midiSha256&&String(meta.midiSha256)!==actualHash)throw Error(`Metadata midiSha256 mismatch: meta=${meta.midiSha256}, game=${actualHash}`);
        if(meta.noteCount!=null&&Number(meta.noteCount)!==parsed.drumNotes)throw Error(`Metadata noteCount mismatch: meta=${meta.noteCount}, parser=${parsed.drumNotes}`);
        let gzipResult="not configured";
        if(meta.midiGzip){
          const gr=await fetch(withProbe(meta.midiGzip,i),{cache:"no-store"});if(!gr.ok)throw Error(`MIDI gzip HTTP ${gr.status}: ${meta.midiGzip}`);
          if(typeof DecompressionStream==="function"){
            const gab=await new Response(gr.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer(),gh=await hashBuffer(gab);parseMidiForGame(gab);
            if(gh!==actualHash)throw Error(`chart.mid.gz decompressed SHA mismatch: midi=${actualHash}, gzip=${gh}`);gzipResult=`OK (${gab.byteLength} bytes)`;
          }else gzipResult=`HTTP OK (${gr.headers.get("content-length")||"size unknown"})`;
        }
        const diag=[
          `GAME LOAD CHECK: PASS`,
          `songId: ${tx.songId}`,
          `metadata: ${source}`,
          `midi URL: ${meta.midi}`,
          `bytes: ${ab.byteLength}`,
          `sha256: ${actualHash}`,
          `MIDI format/tracks/PPQ: ${parsed.format}/${parsed.tracks}/${parsed.division}`,
          `drum notes: ${parsed.drumNotes}`,
          `midiGzip: ${gzipResult}`
        ].join("\n");
        appendLog(tx,`GAME LOAD CHECK PASS: ${ab.byteLength} bytes / ${actualHash.slice(0,12)}… / ${parsed.drumNotes} drum notes`,d);
        return diag;
      }catch(e){lastError=e;attempts.push(`attempt ${i+1}: ${e?.message||String(e)}`);appendLog(tx,`GAME LOAD CHECK RETRY: ${e?.message||String(e)}`,d)}
    }
    const err=new Error(`ゲームロード検証に失敗しました: ${lastError?.message||"unknown error"}`);err.diagnostics=attempts.join("\n");throw err;
  }

  function setVerifyBusy(d,on){
    for(const el of [d.getElementById("publish"),d.getElementById("dmConfirmUpdate"),d.getElementById("dmExistingSong")])if(el)el.disabled=!!on;
    d.querySelectorAll(".dm-mode-switch button").forEach(b=>b.disabled=!!on);
  }
  function setMainUi(d,stageText,logText,kind=""){
    const stage=d.getElementById("stage"),log=d.getElementById("log"),bar=d.getElementById("bar"),pct=d.getElementById("percent");
    if(stage)stage.textContent=stageText;if(log){log.textContent=logText;log.className=kind}if(bar)bar.style.width=stageText.includes("エラー")?"0%":"100%";if(pct)pct.textContent=stageText.includes("エラー")?"0%":"100%";
  }

  function startTransaction(d,stageText){
    if(current?.status==="UPLOADING")return current;
    const changes=collectChanges(d),id=currentSongId(d),file=changes.midiFile;
    const tx={id:`upd-${Date.now()}-${Math.random().toString(36).slice(2,8)}`,startedAt:nowIso(),finishedAt:null,songId:id,songTitle:currentSongTitle(d),detail:changes.detail,status:"UPLOADING",stage:stageText,error:"",diagnostics:"",logs:[],includesMidi:changes.includesMidi};
    tx._midiFile=file;tx._midiHashPromise=file?file.arrayBuffer().then(hashBuffer):Promise.resolve(null);
    runtimeErrors=[];current=tx;appendLog(tx,`START: ${changes.detail}`,d);appendLog(tx,`STAGE: ${stageText}`,d);return tx;
  }
  function finalizeSuccess(d,message){
    if(!current)return;current.status="SUCCESS";current.finishedAt=nowIso();current.stage="GitHub更新完了";current.error="";appendLog(current,`SUCCESS: ${message||"更新完了"}`,d);upsertHistory(current,d);captureBaseline(d);current=null;
  }
  function finalizeError(d,message,diagnostics=""){
    if(!current){const id=currentSongId(d);current={id:`upd-${Date.now()}-${Math.random().toString(36).slice(2,8)}`,startedAt:nowIso(),songId:id,songTitle:currentSongTitle(d),detail:"更新処理",status:"UPLOADING",logs:[],includesMidi:false}}
    current.status="ERROR";current.finishedAt=nowIso();current.stage="GitHub更新エラー";current.error=message||"不明なエラー";if(diagnostics)current.diagnostics=diagnostics;
    if(runtimeErrors.length)current.logs.push(...runtimeErrors.map(x=>`RUNTIME: ${x}`));appendLog(current,`ERROR: ${current.error}`,d);upsertHistory(current,d);current=null;
  }
  async function interceptSuccessForMidi(d){
    if(!current||!current.includesMidi||current.verifying)return;
    current.verifying=true;current.stage="ゲームロード確認";appendLog(current,"GitHub保存完了。ゲーム実ロード検証を開始します。",d);upsertHistory(current,d);setVerifyBusy(d,true);setMainUi(d,"ゲームロード確認","MIDIをゲームと同じ公開URLから再ロードして検証しています…","warn");
    try{const diagnostics=await verifyGameLoad(current,d);current.diagnostics=diagnostics;setMainUi(d,"GitHub更新完了","MIDI更新とゲームロード検証が完了しました。","ok");finalizeSuccess(d,"MIDI更新 + GAME LOAD CHECK PASS")}
    catch(e){const diagnostics=[e?.diagnostics||"",e?.stack||""].filter(Boolean).join("\n");setMainUi(d,"GitHub更新エラー",e?.message||String(e),"bad");finalizeError(d,e?.message||String(e),diagnostics)}
    finally{setVerifyBusy(d,false)}
  }

  function onStageChange(d){
    const stage=safeText(d.getElementById("stage")?.textContent),log=safeText(d.getElementById("log")?.textContent),pct=safeText(d.getElementById("percent")?.textContent);
    if(!stage)return;
    if(FINAL_SUCCESS.has(stage)){
      if(!current)return;
      appendLog(current,`STAGE: ${stage} / ${log}`,d);
      if(current.includesMidi){void interceptSuccessForMidi(d);return}
      finalizeSuccess(d,log);return;
    }
    if(FINAL_ERROR.has(stage)){
      if(!current&&d.body.classList.contains("dm-publisher-update"))startTransaction(d,stage);
      if(current){appendLog(current,`STAGE: ${stage} / ${log}`,d);finalizeError(d,log||stage)}return;
    }
    if(stage==="ゲームロード確認")return;
    if(!IDLE.has(stage)&&stage!=="入力エラー"){
      const numeric=Number(pct.replace("%",""));if(!current&&(Number.isFinite(numeric)&&numeric>0||/確認|更新|UPLOAD|変換|保存|準備/.test(stage)))startTransaction(d,stage);
      else if(current&&current.stage!==stage){current.stage=stage;appendLog(current,`STAGE: ${stage}${log?` / ${log}`:""}`,d)}
    }
  }

  function bindRuntimeErrors(d){
    if(d.documentElement.dataset.dmHistoryErrorBound==="1")return;d.documentElement.dataset.dmHistoryErrorBound="1";
    const record=(prefix,value)=>{if(!current)return;const msg=value instanceof Error?(value.stack||value.message):String(value||"");runtimeErrors.push(`${prefix}: ${msg}`);if(runtimeErrors.length>30)runtimeErrors=runtimeErrors.slice(-30)};
    try{frame.contentWindow.addEventListener("error",e=>record("iframe error",e.error||e.message))}catch{}
    try{frame.contentWindow.addEventListener("unhandledrejection",e=>record("iframe unhandledrejection",e.reason))}catch{}
  }
  function bind(d){
    if(!d?.head||!d.body)return false;ensurePanel(d);bindRuntimeErrors(d);
    if(boundDoc===d)return true;boundDoc=d;captureBaseline(d);
    d.getElementById("dmExistingSong")?.addEventListener("change",()=>scheduleBaseline(d));
    stageObserver?.disconnect();stageObserver=new MutationObserver(()=>onStageChange(d));const stage=d.getElementById("stage"),log=d.getElementById("log"),pct=d.getElementById("percent");for(const el of [stage,log,pct])if(el)stageObserver.observe(el,{childList:true,subtree:true,characterData:true});
    modeObserver?.disconnect();modeObserver=new MutationObserver(()=>{ensurePanel(d);render(d);if(d.body.classList.contains("dm-publisher-update"))scheduleBaseline(d)});modeObserver.observe(d.body,{attributes:true,attributeFilter:["class"]});render(d);return true;
  }
  function install(){const d=doc();if(!d?.body||!d.getElementById("dmPublisherMode"))return false;return bind(d)}
  frame.addEventListener("load",()=>{boundDoc=null;current=null;stageObserver?.disconnect();modeObserver?.disconnect();const t=setInterval(()=>{if(install())clearInterval(t)},80);setTimeout(()=>clearInterval(t),12000)});
  const t=setInterval(()=>{if(install())clearInterval(t)},80);setTimeout(()=>clearInterval(t),12000);
})();
