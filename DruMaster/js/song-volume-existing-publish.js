"use strict";

(()=>{
  const DB_NAME="drumasterSongPublishV1",STORE="sessions",DB_VERSION=1,REPO="ld1kanae/ld1kanae.github.io",ROOT="DruMaster/songs",BRANCH="main";
  const params=new URLSearchParams(location.search),sessionId=params.get("session"),songId=params.get("song");
  if(!sessionId||!songId)return;
  const CREDENTIAL_ID="drumaster-github-pat";
  const $=id=>document.getElementById(id);

  function openDb(){return new Promise((resolve,reject)=>{const r=indexedDB.open(DB_NAME,DB_VERSION);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error||Error("編集セッションDBを開けませんでした"))})}
  async function getSession(){const db=await openDb();return new Promise((resolve,reject)=>{const tx=db.transaction(STORE,"readonly"),r=tx.objectStore(STORE).get(sessionId);r.onsuccess=()=>resolve(r.result||null);r.onerror=()=>reject(r.error);tx.oncomplete=()=>db.close()})}
  function headers(t){return {"Accept":"application/vnd.github+json","Authorization":`Bearer ${t}`,"X-GitHub-Api-Version":"2022-11-28"}}
  function encodeText(s){const u=new TextEncoder().encode(s);let bin="";for(let i=0;i<u.length;i+=0x8000)bin+=String.fromCharCode(...u.subarray(i,i+0x8000));return btoa(bin)}
  function decodeText(s){const bin=atob(String(s||"").replace(/\n/g,"")),u=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);return new TextDecoder().decode(u)}
  async function apiMaybeGet(path,t){const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}`,{headers:headers(t),cache:"no-store"});if(r.status===404)return null;if(!r.ok)throw Error(`GitHub API ${r.status}: ${path}`);return r.json()}
  async function putText(path,text,message,t,sha=null){const body={message,content:encodeText(text),branch:BRANCH};if(sha)body.sha=sha;const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`,{method:"PUT",headers:{...headers(t),"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r.ok)throw Error(`GitHub PUT ${r.status}: ${await r.text()}`);return r.json()}
  function registryEntry(d){const out={id:d.id,title:d.title,artist:d.artist,duration:d.duration,bpm:d.bpm,chart:d.chart||{pixelsPerQuarter:80},playback:d.playback||{stemOffsetSec:0,midiOffsetSec:0},midi:d.midi,midiGzip:d.midiGzip||null,sourceMode:d.sourceMode||null,fullMixOnly:!!d.fullMixOnly,stems:d.stems||{},mix:d.mix||{},midiDrumMix:d.midiDrumMix||{}};if(d.order!==null&&d.order!==""&&Number.isFinite(Number(d.order)))out.order=Number(d.order);return out}

  async function maybeAutofill(input){input.name="password";input.autocomplete="current-password";if(!navigator.credentials?.get||typeof PasswordCredential!=="function")return;try{const c=await navigator.credentials.get({password:true,mediation:"optional"});if(/^github_pat_/.test(c?.password||""))input.value=c.password}catch{}}
  async function rememberToken(value){if(!/^github_pat_/.test(value)||!navigator.credentials?.store||typeof PasswordCredential!=="function")return;try{await navigator.credentials.store(new PasswordCredential({id:CREDENTIAL_ID,name:"DruMaster GitHub PAT",password:value}))}catch{}}

  async function install(){
    const session=await getSession();if(!session||session.id!==songId||session.mode!=="existing-edit")return;
    if($("existingVolumePublish"))return;
    const main=document.querySelector("main");if(!main)return;
    const section=document.createElement("section");section.id="existingVolumePublish";section.className="panel";section.style.marginTop="14px";section.innerHTML='<h2>PUBLISH</h2><label style="display:grid;gap:6px"><span style="font-size:10px;color:#8697a9">GitHub Token</span><input id="existingVolumeToken" type="password" placeholder="github_pat_…" style="width:100%;height:38px;border:1px solid #34485d;border-radius:7px;background:#070d13;color:#edf4fb;padding:0 9px;outline:none"></label><div style="display:flex;justify-content:center;margin-top:12px"><button id="existingVolumePublishButton" class="primary" type="button" style="height:42px;min-width:190px;font-weight:800;letter-spacing:.06em">PUBLISH</button></div><div id="existingVolumePublishMessage" class="status" style="margin-top:10px">変更内容をGitHubへ反映します。</div>';
    main.appendChild(section);
    const input=$("existingVolumeToken"),button=$("existingVolumePublishButton"),message=$("existingVolumePublishMessage");void maybeAutofill(input);
    button.addEventListener("click",async()=>{button.disabled=true;message.className="status";message.textContent="保存中…";try{const latest=await getSession();if(!latest||latest.id!==songId)throw Error("編集セッションが見つかりません");const t=input.value.trim();if(!t)throw Error("GitHub Tokenを入力してください");const draft={...latest.draft,state:"published"};const songMeta=await apiMaybeGet(`${ROOT}/${songId}/song.json`,t);await putText(`${ROOT}/${songId}/song.json`,JSON.stringify(draft,null,2)+"\n",`Publish volume settings: ${songId}`,t,songMeta?.sha||null);const regMeta=await apiMaybeGet(`${ROOT}/registry.json`,t);if(!regMeta)throw Error("registry.jsonが見つかりません");const registry=JSON.parse(decodeText(regMeta.content)||"{}");registry[songId]={...(registry[songId]||{}),...registryEntry(draft)};await putText(`${ROOT}/registry.json`,JSON.stringify(registry,null,2)+"\n",`Publish volume balance: ${songId}`,t,regMeta.sha);await rememberToken(t);message.className="status ok";message.textContent="音量バランスを保存しました。"}catch(e){console.error(e);message.className="status";message.style.color="#ff7d8d";message.textContent=e.message||String(e)}finally{button.disabled=false}});
  }
  setTimeout(()=>install().catch(console.error),0);
})();
