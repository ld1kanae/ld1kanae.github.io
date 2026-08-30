"use strict";

(()=>{
  const LOG_KEY="dmBootDebugLogV1";
  const PREV_KEY="dmBootDebugPrevV1";
  const HEARTBEAT_KEY="dmBootDebugHeartbeatV1";
  const SESSION=`${Date.now().toString(36)}-${Math.random().toString(36).slice(2,7)}`;
  const started=performance.now();
  let log=[];
  try{
    const old=localStorage.getItem(LOG_KEY);
    if(old)localStorage.setItem(PREV_KEY,old);
  }catch{}

  const safe=v=>{
    try{
      if(v instanceof Error)return `${v.name}: ${v.message}${v.stack?`\n${v.stack}`:""}`;
      if(typeof v==="string")return v;
      return JSON.stringify(v);
    }catch{return String(v)}
  };
  function persist(){
    try{localStorage.setItem(LOG_KEY,JSON.stringify({session:SESSION,startedAt:new Date().toISOString(),entries:log.slice(-240)}))}catch{}
  }
  function add(kind,detail=""){
    const entry={t:+(performance.now()-started).toFixed(1),kind,detail:safe(detail)};
    log.push(entry);
    if(log.length>240)log=log.slice(-240);
    persist();
    return entry;
  }
  function loadNode(){return document.getElementById("loadState")}
  function stage(text){
    const n=loadNode();
    if(n&&n.textContent!==text)n.textContent=text;
    add("STAGE",text);
  }
  function uiState(){
    const g=id=>document.getElementById(id);
    const check=id=>{const e=g(id);return e?{checked:!!e.checked,disabled:!!e.disabled}:null};
    return {
      readyState:document.readyState,
      loadState:loadNode()?.textContent||null,
      startDisabled:g("start")?!!g("start").disabled:null,
      songOptions:g("songSelect")?.options?.length??null,
      songValue:g("songSelect")?.value??null,
      vocal:check("vocalToggle"),guide:check("guideToggle"),auto:check("autoToggle"),hidden:check("hiddenToggle"),
      tempo:g("tempo")?.value??null,volume:g("masterVolume")?.value??null,
      performanceMode:g("performanceModeSelect")?.value??null,
      globals:{songs:!!globalThis.DruMasterSongs,loadDrumSource:typeof globalThis.loadDrumSource,playDrum:typeof globalThis.playDrum,audioControl:!!globalThis.DruMasterAudioControl}
    };
  }
  function snapshot(reason){add("SNAPSHOT",{reason,...uiState()})}

  globalThis.DruMasterBootDebug={add,stage,snapshot,getLog:()=>({session:SESSION,entries:[...log],state:uiState()})};

  add("BOOT","boot-debug.js entered");
  stage("起動 1/12 · 診断開始 / song-manager待機");

  addEventListener("error",e=>add("ERROR",{message:e.message,source:e.filename,line:e.lineno,col:e.colno,error:safe(e.error)}));
  addEventListener("unhandledrejection",e=>add("UNHANDLED_REJECTION",safe(e.reason)));

  const NativeXHR=globalThis.XMLHttpRequest;
  if(NativeXHR?.prototype){
    const open=NativeXHR.prototype.open,send=NativeXHR.prototype.send;
    NativeXHR.prototype.open=function(method,url,async=true,...rest){
      this.__dmdbg={method:String(method),url:String(url),async:async!==false,t0:0};
      return open.call(this,method,url,async,...rest);
    };
    NativeXHR.prototype.send=function(body){
      const d=this.__dmdbg||{method:"?",url:"?",async:true};d.t0=performance.now();
      add("XHR_START",d);
      if(d.url.includes("songs/registry.json"))stage("起動 2/12 · registry.json 応答待ち…");
      if(d.async){
        this.addEventListener("loadend",()=>add("XHR_END",{...d,status:this.status,ms:+(performance.now()-d.t0).toFixed(1)}),{once:true});
      }
      try{
        const r=send.call(this,body);
        if(!d.async){
          add("XHR_END",{...d,status:this.status,ms:+(performance.now()-d.t0).toFixed(1)});
          if(d.url.includes("songs/registry.json"))stage(`起動 3/12 · registry.json 取得完了 · HTTP ${this.status}`);
        }
        return r;
      }catch(e){add("XHR_THROW",{...d,error:safe(e)});throw e}
    };
  }

  const boot={midi:"未開始",song:"未開始",drums:"未開始"};
  let drumFetchStarted=0,drumFetchDone=0,chunkStarted=0,chunkDone=0,decodeStarted=0,decodeDone=0,lastAudioAsset="";
  function bootText(){return `起動 6/12 · 起動データ取得 [MIDI:${boot.midi} / 楽曲設定:${boot.song} / ドラム設定:${boot.drums}]`}
  function classify(url){
    const u=String(url||"").split("#")[0];
    if(/songs\/[^/]+\/chart\.mid(?:\.gz)?(?:[?]|$)/.test(u))return "midi";
    if(u.includes("audio-manifest-v2.json"))return "songManifest";
    if(u.includes("assets/drumsound-manifest.json"))return "drumManifest";
    if(/assets\/drums\/\d+\.wav/.test(u))return "drumSample";
    if(/assets\/drumsound(?:-v2)?-\d{3}/.test(u))return "drumChunk";
    if(/\.(?:mp3|wav)(?:[?]|$)/.test(u))return "audio";
    return "other";
  }
  const nativeFetch=globalThis.fetch?.bind(globalThis);
  if(nativeFetch){
    globalThis.fetch=async function(input,init){
      const url=typeof input==="string"?input:input?.url||String(input),kind=classify(url),t0=performance.now();
      add("FETCH_START",{url,kind,cache:init?.cache||null,method:init?.method||"GET"});
      if(kind==="midi"){boot.midi="取得中";stage(bootText())}
      else if(kind==="songManifest"){boot.song="取得中";stage(bootText())}
      else if(kind==="drumManifest"){boot.drums="取得中";stage(bootText())}
      else if(kind==="drumSample"){
        drumFetchStarted++;lastAudioAsset=url;stage(`起動 10/12 · 個別ドラムWAV取得中 ${drumFetchDone}/${Math.max(12,drumFetchStarted)} · ${url.split("/").pop()}`);
      }else if(kind==="drumChunk"){
        chunkStarted++;lastAudioAsset=url;stage(`起動 10/12 · 分割ドラム取得中 ${chunkDone}/${Math.max(22,chunkStarted)} · ${url.split("/").pop()}`);
      }else if(kind==="audio")lastAudioAsset=url;
      try{
        const r=await nativeFetch(input,init);
        add("FETCH_HEADERS",{url,kind,status:r.status,ok:r.ok,ms:+(performance.now()-t0).toFixed(1)});
        if(kind==="midi"){boot.midi=r.ok?"応答済":`HTTP${r.status}`;stage(bootText())}
        else if(kind==="songManifest"){boot.song=r.ok?"応答済":`HTTP${r.status}`;stage(bootText())}
        else if(kind==="drumManifest"){boot.drums=r.ok?"応答済":`HTTP${r.status}`;stage(bootText())}
        else if(kind==="drumSample"&&r.ok){drumFetchDone++;stage(`起動 10/12 · 個別ドラムWAV応答 ${drumFetchDone}/12 · ${url.split("/").pop()}`)}
        else if(kind==="drumChunk"&&r.ok){chunkDone++;stage(`起動 10/12 · 分割ドラム応答 ${chunkDone}/22 · ${url.split("/").pop()}`)}
        return r;
      }catch(e){add("FETCH_THROW",{url,kind,ms:+(performance.now()-t0).toFixed(1),error:safe(e)});throw e}
    };
  }

  const Resp=globalThis.Response?.prototype;
  if(Resp){
    for(const method of ["arrayBuffer","json"]){
      const original=Resp[method];
      if(typeof original!=="function")continue;
      Resp[method]=async function(...args){
        const url=this.url||"(synthetic response)",t0=performance.now();
        add("BODY_START",{method,url});
        try{const v=await original.apply(this,args);add("BODY_END",{method,url,ms:+(performance.now()-t0).toFixed(1),bytes:v?.byteLength??null});return v}
        catch(e){add("BODY_THROW",{method,url,error:safe(e)});throw e}
      };
    }
  }

  const patched=new Set();
  function patchAudio(Ctor){
    const p=Ctor?.prototype;if(!p||patched.has(p)||typeof p.decodeAudioData!=="function")return;patched.add(p);
    const original=p.decodeAudioData;
    p.decodeAudioData=function(data,...rest){
      const n=++decodeStarted,t0=performance.now(),bytes=data?.byteLength??null;
      add("DECODE_START",{n,bytes,lastAudioAsset});
      stage(`起動 11/12 · 音声デコード中 ${decodeDone}/${n} · ${lastAudioAsset.split("/").pop()||"audio"}`);
      let result;
      try{result=original.call(this,data,...rest)}catch(e){add("DECODE_THROW",{n,error:safe(e)});throw e}
      if(result&&typeof result.then==="function")return result.then(v=>{decodeDone++;add("DECODE_END",{n,ms:+(performance.now()-t0).toFixed(1),duration:v?.duration??null});stage(`起動 11/12 · 音声デコード完了 ${decodeDone}/${decodeStarted}`);return v},e=>{add("DECODE_REJECT",{n,error:safe(e)});throw e});
      return result;
    };
  }
  patchAudio(globalThis.AudioContext);patchAudio(globalThis.webkitAudioContext);

  function installDomWatch(){
    const state=loadNode(),start=document.getElementById("start"),select=document.getElementById("songSelect");
    if(state)new MutationObserver(()=>add("LOADSTATE",state.textContent)).observe(state,{childList:true,characterData:true,subtree:true});
    if(start)new MutationObserver(()=>{
      add("START_STATE",{disabled:start.disabled});
      if(!start.disabled){stage("起動 12/12 · 準備完了 / START有効");snapshot("start-enabled")}
    }).observe(start,{attributes:true,attributeFilter:["disabled"]});
    if(select)new MutationObserver(()=>add("SONG_SELECT",{count:select.options.length,value:select.value})).observe(select,{childList:true,subtree:true});
    document.addEventListener("change",e=>{const el=e.target;if(el?.matches?.("input,select"))add("CONTROL_CHANGE",{id:el.id,value:el.value,checked:el.checked,disabled:el.disabled})},true);
    document.addEventListener("input",e=>{const el=e.target;if(el?.matches?.('input[type="range"]'))add("RANGE_INPUT",{id:el.id,value:el.value})},true);
  }
  installDomWatch();

  try{
    new PerformanceObserver(list=>{for(const e of list.getEntries())add("LONGTASK",{ms:+e.duration.toFixed(1),name:e.name})}).observe({type:"longtask",buffered:true});
  }catch{}

  addEventListener("DOMContentLoaded",()=>{add("DOM","DOMContentLoaded");snapshot("DOMContentLoaded")},{once:true});
  addEventListener("load",()=>{add("DOM","window.load");snapshot("window.load")},{once:true});
  addEventListener("pageshow",e=>add("DOM",{event:"pageshow",persisted:e.persisted}),{once:true});
  setInterval(()=>{try{localStorage.setItem(HEARTBEAT_KEY,JSON.stringify({session:SESSION,at:new Date().toISOString(),ms:+(performance.now()-started).toFixed(0),state:uiState()}))}catch{}},1000);

  function reportText(){
    let previous=null,heartbeat=null;
    try{previous=JSON.parse(localStorage.getItem(PREV_KEY)||"null");heartbeat=JSON.parse(localStorage.getItem(HEARTBEAT_KEY)||"null")}catch{}
    const lines=["DruMaster BOOT DEBUG",`generated: ${new Date().toISOString()}`,`session: ${SESSION}`,`userAgent: ${navigator.userAgent}`,`currentState: ${safe(uiState())}`,`heartbeat: ${safe(heartbeat)}`,"","CURRENT LOG:"];
    for(const e of log)lines.push(`${String(e.t).padStart(8)}ms  ${e.kind}  ${e.detail}`);
    if(previous){lines.push("","PREVIOUS SESSION:");for(const e of previous.entries||[])lines.push(`${String(e.t).padStart(8)}ms  ${e.kind}  ${e.detail}`)}
    return lines.join("\n");
  }
  function showPanel(){
    document.getElementById("dmBootDebugPanel")?.remove();
    const panel=document.createElement("div");panel.id="dmBootDebugPanel";panel.style.cssText="position:fixed;inset:4%;z-index:2147483647;background:#090d13;color:#e9f1fa;border:1px solid #637083;border-radius:12px;padding:12px;display:flex;flex-direction:column;gap:8px;font:12px/1.45 monospace;box-shadow:0 20px 80px #000";
    const bar=document.createElement("div");bar.style.cssText="display:flex;gap:8px;align-items:center";
    const title=document.createElement("strong");title.textContent="DruMaster Boot Debug";title.style.marginRight="auto";
    const copy=document.createElement("button");copy.textContent="コピー";const open=document.createElement("button");open.textContent="別ページで開く";const close=document.createElement("button");close.textContent="閉じる";
    for(const b of [copy,open,close])b.style.cssText="padding:7px 10px;background:#182231;color:#fff;border:1px solid #667386;border-radius:6px";
    const pre=document.createElement("textarea");pre.value=reportText();pre.readOnly=true;pre.style.cssText="width:100%;flex:1;min-height:0;resize:none;background:#05080d;color:#dbe8f5;border:1px solid #394554;padding:10px;font:11px/1.45 monospace";
    copy.onclick=async()=>{try{await navigator.clipboard.writeText(pre.value);copy.textContent="コピー済み"}catch{pre.select();document.execCommand("copy")}};
    open.onclick=()=>window.open("debug.html","_blank");close.onclick=()=>panel.remove();
    bar.append(title,copy,open,close);panel.append(bar,pre);document.body.appendChild(panel);
  }
  let clicks=[];
  document.addEventListener("click",()=>{const now=performance.now();clicks=clicks.filter(t=>now-t<1800);clicks.push(now);if(clicks.length>=5){clicks=[];showPanel()}},true);
  globalThis.DruMasterBootDebug.show=showPanel;
})();
