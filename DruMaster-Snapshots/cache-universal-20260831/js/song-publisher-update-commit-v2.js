"use strict";

(()=>{
  const registerView=document.getElementById("registerView");
  if(!registerView)return;

  const REPO="ld1kanae/ld1kanae.github.io",BRANCH="main",ROOT="DruMaster/songs";
  const DB_NAME="drumasterSongPublishV1",STORE="sessions",DB_VERSION=1;
  const active=new Set();

  function openDb(){return new Promise((resolve,reject)=>{const r=indexedDB.open(DB_NAME,DB_VERSION);r.onupgradeneeded=()=>{const db=r.result;if(!db.objectStoreNames.contains(STORE))db.createObjectStore(STORE,{keyPath:"sessionId"})};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error||Error("更新セッションDBを開けませんでした"))})}
  async function getSession(id){const db=await openDb();return new Promise((resolve,reject)=>{const tx=db.transaction(STORE,"readonly"),r=tx.objectStore(STORE).get(id);r.onsuccess=()=>resolve(r.result||null);r.onerror=()=>reject(r.error);tx.oncomplete=()=>db.close()})}
  async function putSession(value){const db=await openDb();return new Promise((resolve,reject)=>{const tx=db.transaction(STORE,"readwrite");tx.objectStore(STORE).put(value);tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>{db.close();reject(tx.error||Error("更新セッションを保存できませんでした"))}})}

  function headers(token){return {"Accept":"application/vnd.github+json","Authorization":`Bearer ${token}`,"X-GitHub-Api-Version":"2022-11-28"}}
  function encodeText(text){const u=new TextEncoder().encode(text);let b="";for(let i=0;i<u.length;i+=0x8000)b+=String.fromCharCode(...u.subarray(i,i+0x8000));return btoa(b)}
  function decodeText(s){const b=atob(String(s||"").replace(/\n/g,"")),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return new TextDecoder().decode(u)}
  function readBlob(blob){return new Promise((resolve,reject)=>{const f=new FileReader();f.onerror=()=>reject(f.error||Error("ファイル変換に失敗しました"));f.onload=()=>resolve(String(f.result).split(",")[1]||"");f.readAsDataURL(blob)})}
  async function apiGet(path,token){const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}`,{headers:headers(token),cache:"no-store"});if(r.status===404)return null;if(!r.ok)throw Error(`GitHub API ${r.status}: ${path}`);return r.json()}
  async function putBlob(path,blob,sha,token,message){const body={message,content:await readBlob(blob),branch:BRANCH};if(sha)body.sha=sha;const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`,{method:"PUT",headers:{...headers(token),"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r.ok)throw Error(`GitHub upload ${r.status}: ${await r.text()}`);return r.json()}
  async function putText(path,text,sha,token,message){const body={message,content:encodeText(text),branch:BRANCH};if(sha)body.sha=sha;const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`,{method:"PUT",headers:{...headers(token),"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r.ok)throw Error(`GitHub update ${r.status}: ${await r.text()}`);return r.json()}
  async function deleteFile(path,sha,token,message){if(!sha)return;const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`,{method:"DELETE",headers:{...headers(token),"Content-Type":"application/json"},body:JSON.stringify({message,sha,branch:BRANCH})});if(!r.ok)throw Error(`GitHub delete ${r.status}: ${await r.text()}`)}

  function regDoc(){try{return registerView.contentDocument}catch{return null}}
  function setUi(percent,stage,message,kind=""){const d=regDoc();if(!d)return;const bar=d.getElementById("bar"),pct=d.getElementById("percent"),st=d.getElementById("stage"),log=d.getElementById("log");if(bar)bar.style.width=`${Math.max(0,Math.min(100,percent))}%`;if(pct)pct.textContent=`${Math.round(percent)}%`;if(st)st.textContent=stage;if(log&&message){log.textContent=message;log.className=kind}}
  function clean(path){return String(path||"").replace(/^DruMaster\//,"").split(/[?#]/)[0]}
  function applyVersions(draft,items,version){const changed=new Set(items.filter(x=>x.op!=="delete").map(x=>clean(x.path)));for(const stem of Object.values(draft.stems||{})){if(!stem?.path)continue;const p=clean(stem.path);if(changed.has(p))stem.path=`${p}?v=${version}`}if(draft.midi){const p=clean(draft.midi);if(changed.has(p))draft.midi=`${p}?v=${version}`}if(draft.midiGzip){const p=clean(draft.midiGzip);if(changed.has(p))draft.midiGzip=`${p}?v=${version}`}}

  async function commitUpdate(msg){
    if(active.has(msg.sessionId))return;active.add(msg.sessionId);
    try{
      const token=String(msg.token||"").trim();if(!token)throw Error("GitHub Tokenを取得できませんでした");
      const session=await getSession(msg.sessionId);if(!session||session.id!==msg.id||session.mode!=="update")throw Error("更新セッションが見つかりません");
      const items=session.uploadItems||[],writes=items.filter(x=>x.op!=="delete"),deletes=items.filter(x=>x.op==="delete"&&x.sha);
      const draft=structuredClone(session.draft||{}),draftOnly=!!draft.__draftOnly;delete draft.__draftOnly;
      setUi(2,"GitHub更新開始",draftOnly?"公開前の登録データを更新しています…":"GitHubへ変更ファイルを反映しています…");

      for(let i=0;i<writes.length;i++){
        const it=writes[i],base=5+(i/Math.max(1,writes.length))*65;
        setUi(base,`UPLOAD ${i+1}/${writes.length}`,it.label||it.path);
        await putBlob(it.path,it.blob,it.sha||null,token,`Update song ${msg.id}: ${it.label||it.path}`);
        setUi(5+((i+1)/Math.max(1,writes.length))*65,`UPLOAD ${i+1}/${writes.length}`,it.label||it.path);
      }

      const version=Number(session.createdAt)||Date.now();applyVersions(draft,items,version);

      if(draftOnly){
        draft.state="uploading";
        setUi(78,"登録データ更新","song-draft.json を更新しています…");
        const path=`${ROOT}/${msg.id}/song-draft.json`,meta=await apiGet(path,token);
        await putText(path,JSON.stringify(draft,null,2)+"\n",meta?.sha||null,token,`Update draft song: ${msg.id}`);
        for(let i=0;i<deletes.length;i++){
          const it=deletes[i];setUi(88+(i/Math.max(1,deletes.length))*9,"旧素材整理",it.label||it.path);
          await deleteFile(it.path,it.sha,token,`Remove draft song asset ${msg.id}: ${it.label||it.path}`);
        }
        session.draft=draft;session.mode="existing-edit";session.uploadItems=[];session.assetsCommittedAt=Date.now();await putSession(session);
        setUi(100,"登録データ更新完了",items.some(x=>clean(x.path).endsWith("chart.mid"))?"MIDIを更新しました。公開前の状態を維持しています。Timing Correctionで確認してください。":"公開前の登録データを更新しました。まだゲーム本編には公開されていません。","ok");
        return;
      }

      draft.state="published";
      setUi(76,"楽曲設定更新","song.json を更新しています…");
      const songPath=`${ROOT}/${msg.id}/song.json`,songMeta=await apiGet(songPath,token);
      await putText(songPath,JSON.stringify(draft,null,2)+"\n",songMeta?.sha||null,token,`Update song settings: ${msg.id}`);

      setUi(86,"楽曲一覧更新","registry.json を更新しています…");
      const regPath=`${ROOT}/registry.json`,regMeta=await apiGet(regPath,token);if(!regMeta)throw Error("registry.json が見つかりません");
      let registry={};try{registry=JSON.parse(decodeText(regMeta.content)||"{}")||{}}catch{throw Error("registry.json を解析できませんでした")}
      registry[msg.id]={...(registry[msg.id]||{}),...draft};
      await putText(regPath,JSON.stringify(registry,null,2)+"\n",regMeta.sha,token,`Update song registry: ${msg.id}`);

      for(let i=0;i<deletes.length;i++){const it=deletes[i];setUi(92+(i/Math.max(1,deletes.length))*6,"旧素材整理",it.label||it.path);await deleteFile(it.path,it.sha,token,`Remove song asset ${msg.id}: ${it.label||it.path}`)}

      session.draft=draft;session.mode="existing-edit";session.uploadItems=[];session.assetsCommittedAt=Date.now();await putSession(session);
      setUi(100,"GitHub更新完了",items.some(x=>clean(x.path).endsWith("chart.mid"))?"MIDIを更新しました。必要に応じてTiming Correctionでタイミングを再確認してください。":"更新内容をGitHubへ反映しました。","ok");
    }catch(e){console.error("Existing song update commit failed",e);setUi(0,"GitHub更新エラー",e?.message||String(e),"bad")}
    finally{active.delete(msg.sessionId)}
  }

  addEventListener("message",e=>{if(e.origin!==location.origin||e.source!==registerView.contentWindow)return;const d=e.data;if(d?.type!=="dm-song-editor-ready"||d.mode!=="update"||!d.id||!d.sessionId)return;void commitUpdate(d)});
})();
