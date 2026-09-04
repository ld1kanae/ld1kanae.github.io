"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;

  const REPO="ld1kanae/ld1kanae.github.io",BRANCH="main",ROOT="DruMaster/songs";
  let boundDoc=null,stageObserver=null,intent=null,busy=false;

  function doc(){try{return frame.contentDocument}catch{return null}}
  function headers(token){return {"Accept":"application/vnd.github+json","Authorization":`Bearer ${token}`,"X-GitHub-Api-Version":"2022-11-28"}}
  function encodeText(text){const u=new TextEncoder().encode(text);let b="";for(let i=0;i<u.length;i+=0x8000)b+=String.fromCharCode(...u.subarray(i,i+0x8000));return btoa(b)}
  function decodeText(s){const b=atob(String(s||"").replace(/\n/g,"")),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return new TextDecoder().decode(u)}
  function base64Bytes(s){const b=atob(String(s||"").replace(/\n/g,"")),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u}
  async function hashBytes(u){const h=await crypto.subtle.digest("SHA-256",u);return [...new Uint8Array(h)].map(v=>v.toString(16).padStart(2,"0")).join("")}
  async function hashFile(file){return hashBytes(new Uint8Array(await file.arrayBuffer()))}
  async function apiGet(path,token){const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}&t=${Date.now()}`,{headers:headers(token),cache:"no-store"});if(r.status===404)return null;if(!r.ok)throw Error(`GitHub API ${r.status}: ${path}`);return r.json()}
  async function putBase64(path,content,sha,token,message){const body={message,content,branch:BRANCH};if(sha)body.sha=sha;const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`,{method:"PUT",headers:{...headers(token),"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r.ok)throw Error(`GitHub upload ${r.status}: ${await r.text()}`);return r.json()}
  async function putText(path,text,sha,token,message){return putBase64(path,encodeText(text),sha,token,message)}
  function parseJson(meta,path){try{return JSON.parse(decodeText(meta?.content)||"{}")||{}}catch{throw Error(`${path} を解析できませんでした`)}}
  function setUi(d,stageText,message,kind="warn",percent=96){const stage=d.getElementById("stage"),log=d.getElementById("log"),bar=d.getElementById("bar"),pct=d.getElementById("percent");if(stage)stage.textContent=stageText;if(log){log.textContent=message;log.className=kind}if(bar)bar.style.width=`${percent}%`;if(pct)pct.textContent=`${percent}%`}
  function getToken(d){return String(d.getElementById("token")?.value||"").trim()}
  function currentId(d){return String(d.getElementById("dmExistingSong")?.value||"").trim()}

  function captureIntent(d){
    if(!d.body.classList.contains("dm-publisher-update"))return;
    const file=d.getElementById("midi")?.files?.[0];if(!file)return;
    const id=currentId(d);if(!id)return;
    intent={id,fileName:file.name,size:file.size,hashPromise:hashFile(file),capturedAt:Date.now()};
  }

  async function ensureImmutablePublication(d,successStage){
    if(!intent||busy)return;busy=true;
    const localIntent=intent;
    try{
      const token=getToken(d);if(!token)throw Error("MIDI公開URL作成用のGitHub tokenを取得できませんでした");
      if(currentId(d)!==localIntent.id)throw Error(`更新対象が途中で変わりました: ${localIntent.id} -> ${currentId(d)}`);
      setUi(d,"MIDI公開準備",`${localIntent.id} のMIDIをキャッシュ衝突しない固有URLへ配置しています…","warn",96);

      const expectedHash=await localIntent.hashPromise,tag=expectedHash.slice(0,16);
      const canonicalPath=`${ROOT}/${localIntent.id}/chart.mid`,canonical=await apiGet(canonicalPath,token);
      if(!canonical)throw Error(`${canonicalPath} がGitHub上にありません`);
      if(Number(canonical.size)!==Number(localIntent.size))throw Error(`GitHub canonical MIDI bytes mismatch: upload=${localIntent.size}, repository=${canonical.size}`);
      const canonicalB64=String(canonical.content||"").replace(/\n/g,"");if(!canonicalB64)throw Error("GitHub APIからchart.mid本体を取得できませんでした");
      const repositoryHash=await hashBytes(base64Bytes(canonicalB64));
      if(repositoryHash!==expectedHash)throw Error(`GitHub canonical MIDI SHA mismatch: upload=${expectedHash}, repository=${repositoryHash}`);

      const immutableName=`chart.mid-${tag}.mid`,immutablePath=`${ROOT}/${localIntent.id}/${immutableName}`;
      let immutable=await apiGet(immutablePath,token);
      if(!immutable){await putBase64(immutablePath,canonicalB64,null,token,`Publish immutable MIDI ${localIntent.id}: ${immutableName}`);immutable=await apiGet(immutablePath,token)}
      if(!immutable||Number(immutable.size)!==Number(localIntent.size))throw Error(`Immutable MIDI save verification failed: ${immutablePath}`);

      const canonicalGzipPath=`${ROOT}/${localIntent.id}/chart.mid.gz`,canonicalGzip=await apiGet(canonicalGzipPath,token);
      let immutableGzipUrl=null;
      if(canonicalGzip?.content){
        const immutableGzipName=`chart.mid-${tag}.mid.gz`,immutableGzipPath=`${ROOT}/${localIntent.id}/${immutableGzipName}`;
        let immutableGzip=await apiGet(immutableGzipPath,token);
        if(!immutableGzip){await putBase64(immutableGzipPath,String(canonicalGzip.content).replace(/\n/g,""),null,token,`Publish immutable MIDI gzip ${localIntent.id}: ${immutableGzipName}`);immutableGzip=await apiGet(immutableGzipPath,token)}
        if(!immutableGzip)throw Error(`Immutable MIDI gzip save verification failed: ${immutableGzipPath}`);
        immutableGzipUrl=`songs/${localIntent.id}/${immutableGzipName}`;
      }

      const songPath=`${ROOT}/${localIntent.id}/song.json`,draftPath=`${ROOT}/${localIntent.id}/song-draft.json`;
      let songMeta=await apiGet(songPath,token),path=songPath,draftOnly=false;if(!songMeta){songMeta=await apiGet(draftPath,token);path=draftPath;draftOnly=true}if(!songMeta)throw Error(`${localIntent.id} の楽曲設定が見つかりません`);
      const song=parseJson(songMeta,path),midiUrl=`songs/${localIntent.id}/${immutableName}`;
      song.midi=midiUrl;song.midiGzip=immutableGzipUrl;song.midiBytes=localIntent.size;song.midiSha256=expectedHash;
      await putText(path,JSON.stringify(song,null,2)+"\n",songMeta.sha,token,`Use immutable MIDI URL: ${localIntent.id}`);

      if(!draftOnly){
        const regPath=`${ROOT}/registry.json`,regMeta=await apiGet(regPath,token);if(!regMeta)throw Error("registry.json が見つかりません");
        const registry=parseJson(regMeta,regPath);registry[localIntent.id]={...(registry[localIntent.id]||{}),...song};
        await putText(regPath,JSON.stringify(registry,null,2)+"\n",regMeta.sha,token,`Use immutable MIDI registry URL: ${localIntent.id}`);
      }

      const verifySong=parseJson(await apiGet(path,token),path);
      if(verifySong.midi!==midiUrl||verifySong.midiSha256!==expectedHash||Number(verifySong.midiBytes)!==Number(localIntent.size))throw Error("固有MIDI URLのsong.json保存確認に失敗しました");
      if(!draftOnly){const reg=parseJson(await apiGet(`${ROOT}/registry.json`,token),`${ROOT}/registry.json`);if(reg[localIntent.id]?.midi!==midiUrl||reg[localIntent.id]?.midiSha256!==expectedHash)throw Error("固有MIDI URLのregistry.json保存確認に失敗しました")}

      setUi(d,"MIDI公開反映待ち",`公開MIDIを ${midiUrl} に固定しました。ゲームロード検証へ進みます…","warn",98);
      intent=null;
      setTimeout(()=>setUi(d,successStage,`MIDIを ${midiUrl} へ公開しました。ゲームロード検証を開始します。","ok",100),50);
    }catch(e){
      console.error("Immutable MIDI publication failed",e);intent=null;setUi(d,"GitHub更新エラー",e?.message||String(e),"bad",0);
    }finally{busy=false}
  }

  function onStage(d){
    const stage=String(d.getElementById("stage")?.textContent||"").trim();
    if(!intent)return;
    if(stage==="GitHub更新エラー"||stage==="エラー"){intent=null;return}
    if((stage==="GitHub更新完了"||stage==="登録データ更新完了")&&!busy)void ensureImmutablePublication(d,stage);
  }

  function bind(d){
    if(!d?.body||!d.getElementById("dmPublisherMode"))return false;
    if(boundDoc===d)return true;boundDoc=d;
    d.addEventListener("click",e=>{if(e.target?.id==="dmConfirmUpdate")captureIntent(d)},true);
    const stage=d.getElementById("stage");if(stage){stageObserver?.disconnect();stageObserver=new MutationObserver(()=>onStage(d));stageObserver.observe(stage,{childList:true,subtree:true,characterData:true})}
    return true;
  }
  function install(){return bind(doc())}
  frame.addEventListener("load",()=>{boundDoc=null;intent=null;stageObserver?.disconnect();const t=setInterval(()=>{if(install())clearInterval(t)},20);setTimeout(()=>clearInterval(t),12000)});
  if(!install()){const t=setInterval(()=>{if(install())clearInterval(t)},20);setTimeout(()=>clearInterval(t),12000)}
})();
