"use strict";

(()=>{
  const DB_NAME="drumasterSongPublishV1",STORE="sessions",DB_VERSION=1;
  const params=new URLSearchParams(location.search),sessionId=params.get("session"),songId=params.get("song");
  if(!sessionId||!songId)return;

  const nativeFetch=globalThis.fetch.bind(globalThis);
  let session=null,uploadPromise=null,uploadError=null,uploadPercent=0,uploadLabel="準備中",uploadDeferred=false,updateAssetsPromise=null,updateDeletesDone=false;

  function openDb(){
    return new Promise((resolve,reject)=>{
      const r=indexedDB.open(DB_NAME,DB_VERSION);
      r.onupgradeneeded=()=>{const db=r.result;if(!db.objectStoreNames.contains(STORE))db.createObjectStore(STORE,{keyPath:"sessionId"})};
      r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error||Error("ローカルセッションDBを開けませんでした"));
    });
  }
  async function getSession(id){const db=await openDb();return new Promise((resolve,reject)=>{const tx=db.transaction(STORE,"readonly"),r=tx.objectStore(STORE).get(id);r.onsuccess=()=>resolve(r.result||null);r.onerror=()=>reject(r.error);tx.oncomplete=()=>db.close()})}
  async function refreshSession(){const latest=await getSession(sessionId);if(latest&&latest.id===songId)session=latest;return session}
  async function deleteSession(id){try{const db=await openDb();await new Promise((resolve,reject)=>{const tx=db.transaction(STORE,"readwrite");tx.objectStore(STORE).delete(id);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)});db.close()}catch{}}
  function encodeText(s){const u=new TextEncoder().encode(s);let bin="";for(let i=0;i<u.length;i+=0x8000)bin+=String.fromCharCode(...u.subarray(i,i+0x8000));return btoa(bin)}
  function decodeText(s){const bin=atob(String(s||"").replace(/\n/g,"")),u=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);return new TextDecoder().decode(u)}
  function tokenFromWindow(){try{const w=JSON.parse(window.name||"{}").dmSongPublisher;return w?.token&&w?.sessionId===sessionId?w.token:""}catch{return ""}}
  function headers(t){return {"Accept":"application/vnd.github+json","Authorization":`Bearer ${t}`,"X-GitHub-Api-Version":"2022-11-28"}}
  function readDataUrl(blob){return new Promise((resolve,reject)=>{const fr=new FileReader();fr.onerror=()=>reject(fr.error||Error("base64変換失敗"));fr.onload=()=>resolve(String(fr.result).split(",")[1]||"");fr.readAsDataURL(blob)})}
  async function putFile(path,blob,message,t,onProgress,sha=null){const content=await readDataUrl(blob);return new Promise((resolve,reject)=>{const x=new XMLHttpRequest();x.open("PUT",`https://api.github.com/repos/ld1kanae/ld1kanae.github.io/contents/${path}`);for(const [k,v] of Object.entries(headers(t)))x.setRequestHeader(k,v);x.setRequestHeader("Content-Type","application/json");x.upload.onprogress=e=>{if(e.lengthComputable)onProgress?.(e.loaded/e.total)};x.onerror=()=>reject(Error("GitHubへのアップロード通信に失敗しました"));x.onload=()=>x.status>=200&&x.status<300?resolve():reject(Error(`GitHub upload ${x.status}: ${x.responseText}`));const body={message,content,branch:"main"};if(sha)body.sha=sha;x.send(JSON.stringify(body))})}
  async function deleteFile(path,sha,message,t){if(!sha)return;const r=await nativeFetch(`https://api.github.com/repos/ld1kanae/ld1kanae.github.io/contents/${path}`,{method:"DELETE",headers:{...headers(t),"Content-Type":"application/json"},body:JSON.stringify({message,sha,branch:"main"})});if(!r.ok)throw Error(`GitHub delete ${r.status}: ${await r.text()}`)}

  function updateUploadUi(){
    const bar=document.getElementById("localUploadBar"),percent=document.getElementById("localUploadPercent"),label=document.getElementById("localUploadLabel");
    if(bar)bar.style.width=`${Math.max(0,Math.min(100,uploadPercent))}%`;
    if(percent)percent.textContent=uploadDeferred?"WAIT":`${Math.round(uploadPercent)}%`;
    if(label)label.textContent=uploadError?`UPLOAD ERROR · ${uploadError.message||uploadError}`:uploadDeferred?uploadLabel:uploadPercent>=100?"素材アップロード完了":`素材アップロード中 · ${uploadLabel}`;
  }
  function installUploadUi(){
    if(document.getElementById("localUploadStatus"))return;
    const publish=document.querySelector(".publish");if(!publish)return;
    const box=document.createElement("section");box.id="localUploadStatus";box.className="panel";box.style.marginTop="12px";
    box.innerHTML='<span class="label">BACKGROUND UPLOAD</span><div class="track"><div id="localUploadBar" class="bar" style="width:0"></div></div><div class="meta"><span id="localUploadLabel">素材アップロード準備中</span><b id="localUploadPercent">0%</b></div>';
    publish.parentNode.insertBefore(box,publish);updateUploadUi();
  }

  function pathKey(url){
    if(!session)return null;
    const clean=String(url).split(/[?#]/)[0];
    for(const [key,s] of Object.entries(session.draft?.stems||{}))if(s?.path&&clean.endsWith(`/DruMaster/${String(s.path).split(/[?#]/)[0]}`))return key;
    return null;
  }
  function fakeApiDraft(){
    const text=JSON.stringify(session.draft,null,2)+"\n";
    return new Response(JSON.stringify({content:encodeText(text),encoding:"base64",sha:"local-session"}),{status:200,headers:{"Content-Type":"application/json"}});
  }
  async function waitForUpload(){
    if(!uploadPromise)throw Error("素材アップロードを開始できませんでした");
    await uploadPromise;
    if(uploadError)throw uploadError;
  }
  function applyUpdatedAssetVersions(song){
    if(session?.mode!=="update"||!song)return;
    const changed=new Set((session.uploadItems||[]).filter(it=>it.op!=="delete").map(it=>String(it.path||"").replace(/^DruMaster\//,"").split(/[?#]/)[0]));
    const version=Number(session.createdAt)||Date.now();
    for(const stem of Object.values(song.stems||{})){
      if(!stem?.path)continue;
      const clean=String(stem.path).split(/[?#]/)[0];
      if(changed.has(clean))stem.path=`${clean}?v=${version}`;
    }
    if(song.midi){const clean=String(song.midi).split(/[?#]/)[0];if(changed.has(clean))song.midi=`${clean}?v=${version}`}
    if(song.midiGzip){const clean=String(song.midiGzip).split(/[?#]/)[0];if(changed.has(clean))song.midiGzip=`${clean}?v=${version}`}
  }
  async function withLatestVolumeSettings(url,init){
    await refreshSession();
    const mix=session?.draft?.mix,midiDrumMix=session?.draft?.midiDrumMix;
    if(!init?.body)return init;
    try{
      const body=JSON.parse(init.body);if(!body?.content)return init;
      const data=JSON.parse(decodeText(body.content));
      if(url.includes("DruMaster/songs/registry.json")){
        if(data?.[songId]){if(mix)data[songId].mix=mix;if(midiDrumMix)data[songId].midiDrumMix=midiDrumMix;applyUpdatedAssetVersions(data[songId])}
      }else{
        if(mix)data.mix=mix;if(midiDrumMix)data.midiDrumMix=midiDrumMix;applyUpdatedAssetVersions(data);
      }
      body.content=encodeText(JSON.stringify(data,null,2)+"\n");
      return {...init,body:JSON.stringify(body)};
    }catch(e){console.warn("Session setting injection skipped",e);return init}
  }

  const sessionReady=getSession(sessionId).then(v=>{if(!v||v.id!==songId)throw Error("ローカル編集セッションが見つかりません");session=v;return v});

  async function applyUpdateAssets(){
    if(updateAssetsPromise)return updateAssetsPromise;
    updateAssetsPromise=(async()=>{
      const s=await refreshSession(),t=tokenFromWindow();
      if(!t)throw Error("GitHub tokenを引き継げませんでした。最終PUBLISH欄へ再入力してください");
      const items=(s?.uploadItems||[]).filter(it=>it.op!=="delete");
      uploadDeferred=false;uploadPercent=0;
      if(!items.length){uploadPercent=100;uploadLabel="変更ファイルなし";updateUploadUi();return}
      for(let i=0;i<items.length;i++){
        const it=items[i];uploadLabel=it.label||it.path;updateUploadUi();
        await putFile(it.path,it.blob,`Update song ${songId}: ${it.label||it.path}`,t,p=>{uploadPercent=(i+p)/items.length*100;updateUploadUi()},it.sha||null);
        uploadPercent=(i+1)/items.length*100;updateUploadUi();
      }
    })().catch(e=>{uploadError=e;updateUploadUi();throw e});
    return updateAssetsPromise;
  }

  async function applyUpdateDeletes(){
    if(updateDeletesDone)return;
    const s=await refreshSession(),t=tokenFromWindow();
    if(!t)throw Error("GitHub tokenを引き継げませんでした");
    const items=(s?.uploadItems||[]).filter(it=>it.op==="delete"&&it.sha);
    for(const it of items){uploadLabel=it.label||it.path;updateUploadUi();await deleteFile(it.path,it.sha,`Remove song asset ${songId}: ${it.label||it.path}`,t)}
    updateDeletesDone=true;
  }

  globalThis.fetch=async function(input,init){
    const url=typeof input==="string"?input:input?.url||"",method=String(init?.method||"GET").toUpperCase();
    await sessionReady;

    if(method==="GET"&&url.includes("api.github.com/repos/ld1kanae/ld1kanae.github.io/contents/DruMaster/songs/")&&url.includes(`/${songId}/song-draft.json`))return fakeApiDraft();

    if(method==="GET"&&url.includes("raw.githubusercontent.com/ld1kanae/ld1kanae.github.io/main/DruMaster/")){
      const clean=url.split(/[?#]/)[0];
      if(session.midiBlob&&clean.endsWith(`/DruMaster/${String(session.draft.midi||"").split(/[?#]/)[0]}`))return new Response(session.midiBlob,{status:200,headers:{"Content-Type":"audio/midi","X-DruMaster-Local":"1"}});
      const key=pathKey(url),blob=key&&session.originals?.[key];
      if(blob)return new Response(blob,{status:200,headers:{"Content-Type":blob.type||"application/octet-stream","X-DruMaster-Local":"1"}});
    }

    if(method==="PUT"&&url.includes("api.github.com/repos/ld1kanae/ld1kanae.github.io/contents/")&&(url.includes(`DruMaster/songs/${songId}/song.json`)||url.includes("DruMaster/songs/registry.json"))){
      if(session.mode==="update"&&url.includes(`DruMaster/songs/${songId}/song.json`))await applyUpdateAssets();
      else await waitForUpload();
      const nextInit=await withLatestVolumeSettings(url,init);
      const response=await nativeFetch(input,nextInit);
      if(response.ok&&url.includes("DruMaster/songs/registry.json")){
        if(session.mode==="update"){
          try{await applyUpdateDeletes()}catch(e){console.warn("Unused old asset cleanup failed",e);uploadError=e;updateUploadUi()}
        }
        void deleteSession(sessionId);
      }
      return response;
    }
    return nativeFetch(input,init);
  };

  async function startUpload(){
    const s=await sessionReady,t=tokenFromWindow();
    if(!t)throw Error("GitHub tokenを引き継げませんでした。最終PUBLISH欄へ再入力してください");
    const items=s.uploadItems||[];
    if(s.mode==="update"){
      uploadDeferred=true;uploadPercent=0;uploadLabel=items.length?"変更素材は最終PUBLISH時に本番へ反映します":"素材変更なし。設定だけ最終PUBLISHで反映します";updateUploadUi();return;
    }
    if(!items.length){uploadPercent=100;updateUploadUi();return}
    for(let i=0;i<items.length;i++){
      const it=items[i];uploadLabel=it.label||it.path;updateUploadUi();
      if(it.op==="delete"){
        await deleteFile(it.path,it.sha,`Remove song asset ${songId}: ${it.label||it.path}`,t);
        uploadPercent=(i+1)/items.length*100;updateUploadUi();continue;
      }
      await putFile(it.path,it.blob,`Stage song ${songId}: ${it.label||it.path}`,t,p=>{uploadPercent=(i+p)/items.length*100;updateUploadUi()},it.sha||null);
      uploadPercent=(i+1)/items.length*100;updateUploadUi();
    }
  }

  uploadPromise=sessionReady.then(()=>startUpload()).catch(e=>{uploadError=e;updateUploadUi();throw e});
  uploadPromise.catch(()=>{});

  addEventListener("DOMContentLoaded",()=>{installUploadUi();updateUploadUi()},{once:true});
  globalThis.DruMasterLocalPublishSession={sessionReady,waitForUpload,refreshSession,get uploadPercent(){return uploadPercent},get uploadError(){return uploadError}};
})();
