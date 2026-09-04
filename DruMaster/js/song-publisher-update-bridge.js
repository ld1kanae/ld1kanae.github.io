"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;
  const REPO="ld1kanae/ld1kanae.github.io",BRANCH="main",ROOT="DruMaster/songs";
  let observer=null,initialResetDone=false,midiDirectBusy=false,midiBoundDoc=null;

  if(!document.querySelector('script[data-dm-draft-catalog]')){
    const s=document.createElement("script");
    s.src="js/song-publisher-draft-catalog.js?v=20260902-midiupload2";
    s.dataset.dmDraftCatalog="1";
    document.head.appendChild(s);
  }

  if(!document.querySelector('script[data-dm-update-commit]')){
    const s=document.createElement("script");
    s.src="js/song-publisher-update-commit-v2.js?v=20260902-commitfix1";
    s.dataset.dmUpdateCommit="1";
    document.head.appendChild(s);
  }

  function iframeDoc(){try{return frame.contentDocument}catch{return null}}
  function syncLame(){
    try{
      const lib=frame.contentWindow?.lamejs;
      if(lib?.Mp3Encoder)globalThis.lamejs=lib;
    }catch{}
  }
  function fixInitialNewMode(){
    if(initialResetDone)return;
    const d=iframeDoc();if(!d)return;
    const panel=d.getElementById("dmPublisherMode"),select=d.getElementById("dmExistingSong"),newButton=panel?.querySelector('[data-mode="new"]');
    if(!panel||!select||!select.options.length||!newButton)return;
    if(newButton.classList.contains("active")&&d.body.classList.contains("dm-publisher-new")){
      initialResetDone=true;
      newButton.click();
    }
  }

  function headers(token){return {"Accept":"application/vnd.github+json","Authorization":`Bearer ${token}`,"X-GitHub-Api-Version":"2022-11-28"}}
  function encodeText(text){const u=new TextEncoder().encode(text);let b="";for(let i=0;i<u.length;i+=0x8000)b+=String.fromCharCode(...u.subarray(i,i+0x8000));return btoa(b)}
  function decodeText(s){const b=atob(String(s||"").replace(/\n/g,"")),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return new TextDecoder().decode(u)}
  function arrayBufferBase64(ab){const u=new Uint8Array(ab);let b="";for(let i=0;i<u.length;i+=0x8000)b+=String.fromCharCode(...u.subarray(i,i+0x8000));return btoa(b)}
  async function apiGet(path,token){const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}&t=${Date.now()}`,{headers:headers(token),cache:"no-store"});if(r.status===404)return null;if(!r.ok)throw Error(`GitHub API ${r.status}: ${path}`);return r.json()}
  async function putBase64(path,content,sha,token,message){const body={message,content,branch:BRANCH};if(sha)body.sha=sha;const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`,{method:"PUT",headers:{...headers(token),"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r.ok)throw Error(`GitHub upload ${r.status}: ${await r.text()}`);return r.json()}
  async function putText(path,text,sha,token,message){return putBase64(path,encodeText(text),sha,token,message)}
  async function deleteFile(path,sha,token,message){if(!sha)return;const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`,{method:"DELETE",headers:{...headers(token),"Content-Type":"application/json"},body:JSON.stringify({message,sha,branch:BRANCH})});if(!r.ok)throw Error(`GitHub delete ${r.status}: ${await r.text()}`)}
  function parseJson(meta,path){try{return JSON.parse(decodeText(meta?.content)||"{}")||{}}catch{throw Error(`${path} を解析できませんでした`)}}
  async function sha256(ab){const h=await crypto.subtle.digest("SHA-256",ab);return [...new Uint8Array(h)].map(v=>v.toString(16).padStart(2,"0")).join("")}
  async function gzip(ab){if(typeof CompressionStream!=="function")return null;const stream=new Blob([ab]).stream().pipeThrough(new CompressionStream("gzip"));return new Uint8Array(await new Response(stream).arrayBuffer())}
  function parseMidi(ab){
    const d=new DataView(ab);let p=0;
    const need=n=>{if(p+n>d.byteLength)throw Error("MIDIが途中で切れています")},str=n=>{need(n);let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s},u32=()=>{need(4);const v=d.getUint32(p);p+=4;return v},u16=()=>{need(2);const v=d.getUint16(p);p+=2;return v},vlq=end=>{let v=0,b,c=0;do{if(p>=end)throw Error("MIDI VLQ error");b=d.getUint8(p++);v=(v<<7)|(b&127);if(++c>4)throw Error("MIDI VLQ error")}while(b&128);return v};
    if(str(4)!=="MThd")throw Error("MIDIヘッダーが不正です");const header=u32();u16();const tracks=u16(),division=u16();if(division&0x8000)throw Error("SMPTE MIDIには未対応です");p=8+header;let notes=0;const tempos=[],sigs=[];
    for(let tr=0;tr<tracks;tr++){if(str(4)!=="MTrk")throw Error("MIDIトラックが不正です");const len=u32(),end=p+len;let tick=0,run=0;while(p<end){tick+=vlq(end);let first=d.getUint8(p++),status;if(first<128){if(!run)throw Error("MIDI running status error");status=run;p--}else{status=first;if(status<240)run=status}if(status===255){const type=d.getUint8(p++),n=vlq(end);if(type===81&&n===3)tempos.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});if(type===88&&n>=2)sigs.push({tick,numerator:d.getUint8(p),denominator:2**d.getUint8(p+1)});p+=n;continue}if(status===240||status===247){run=0;p+=vlq(end);continue}const hi=status&240,ch=status&15,bytes=(hi===192||hi===208)?1:2;need(bytes);d.getUint8(p++);const b=bytes===2?d.getUint8(p++):0;if(hi===144&&b>0&&ch===9)notes++}p=end}
    tempos.sort((a,b)=>a.tick-b.tick);sigs.sort((a,b)=>a.tick-b.tick);const tempo=tempos.find(x=>x.tick===0)||tempos[0]||{us:500000},sig=sigs.find(x=>x.tick===0)||sigs[0]||{numerator:4,denominator:4};return {division,noteCount:notes,bpm:60000000/tempo.us,numerator:sig.numerator,denominator:sig.denominator}
  }
  function readOrder(d){const raw=String(d.getElementById("order")?.value||"").trim();if(raw==="")return null;const n=Number(raw);if(!Number.isInteger(n)||n<1)throw Error("表示順は1以上の整数で入力してください");return n}
  function setUi(d,percent,stage,message,kind=""){const bar=d.getElementById("bar"),pct=d.getElementById("percent"),st=d.getElementById("stage"),log=d.getElementById("log");if(bar)bar.style.width=`${Math.max(0,Math.min(100,percent))}%`;if(pct)pct.textContent=`${Math.round(percent)}%`;if(st)st.textContent=stage;if(log&&message){log.textContent=message;log.className=kind}}
  function hasNonMidiAssetChanges(d){for(const wrap of d.querySelectorAll(".dm-update-control")){const select=wrap.querySelector(".dm-update-action"),input=wrap.querySelector('input[type="file"]'),key=select?.dataset.key||"";if(key==="midi")continue;if((select?.value&&select.value!=="keep")||input?.files?.length)return true}return false}

  async function commitMidiDirect(d){
    if(midiDirectBusy)return;midiDirectBusy=true;
    const confirm=d.getElementById("dmConfirmUpdate"),publish=d.getElementById("publish");
    try{
      const token=String(d.getElementById("token")?.value||"").trim();if(!token)throw Error("GitHub tokenを入力してください");
      const id=String(d.getElementById("dmExistingSong")?.value||"").trim();if(!id)throw Error("更新する楽曲を選択してください");
      const file=d.getElementById("midi")?.files?.[0];if(!file)throw Error("更新するMIDIファイルを選択してください");
      const title=String(d.getElementById("title")?.value||"").trim(),artist=String(d.getElementById("artist")?.value||"").trim(),order=readOrder(d);if(!title)throw Error("曲名を入力してください");if(!artist)throw Error("アーティスト名を入力してください");
      if(confirm)confirm.disabled=true;if(publish)publish.disabled=true;const box=d.getElementById("dmUpdateConfirm");if(box)box.hidden=true;
      setUi(d,3,"MIDI確認","選択したMIDIを検証しています…");
      const ab=await file.arrayBuffer(),info=parseMidi(ab),hash=await sha256(ab),gz=await gzip(ab),version=Date.now();
      const midiPath=`${ROOT}/${id}/chart.mid`,gzPath=`${ROOT}/${id}/chart.mid.gz`;
      const midiMeta=await apiGet(midiPath,token),gzMeta=await apiGet(gzPath,token);
      setUi(d,22,"MIDI更新","chart.mid をGitHubへ保存しています…");
      const midiPut=await putBase64(midiPath,arrayBufferBase64(ab),midiMeta?.sha||null,token,`Update song ${id}: chart.mid`);
      let midiGzip=null;
      if(gz){setUi(d,42,"MIDI圧縮版更新","chart.mid.gz をGitHubへ保存しています…");await putBase64(gzPath,arrayBufferBase64(gz.buffer),gzMeta?.sha||null,token,`Update song ${id}: chart.mid.gz`);midiGzip=`songs/${id}/chart.mid.gz?v=${version}`}
      else if(gzMeta?.sha){setUi(d,42,"旧MIDI圧縮版削除","古い chart.mid.gz を削除しています…");await deleteFile(gzPath,gzMeta.sha,token,`Remove stale MIDI gzip: ${id}`)}

      const songPath=`${ROOT}/${id}/song.json`,draftPath=`${ROOT}/${id}/song-draft.json`;
      let songMeta=await apiGet(songPath,token),path=songPath,draftOnly=false;if(!songMeta){songMeta=await apiGet(draftPath,token);path=draftPath;draftOnly=true}if(!songMeta)throw Error(`${id} の楽曲設定が見つかりません`);
      const current=parseJson(songMeta,path),updated={...current,title,artist,order,bpm:Number(info.bpm.toFixed(6)),timeSignature:{numerator:info.numerator,denominator:info.denominator},division:info.division,noteCount:info.noteCount,midi:`songs/${id}/chart.mid?v=${version}`,midiGzip,midiBytes:ab.byteLength,midiSha256:hash};
      setUi(d,62,draftOnly?"登録データ更新":"楽曲設定更新",`${path.split("/").pop()} を更新しています…`);
      await putText(path,JSON.stringify(updated,null,2)+"\n",songMeta.sha,token,`Update MIDI metadata: ${id}`);
      if(!draftOnly){setUi(d,78,"楽曲一覧更新","registry.json を更新しています…");const regPath=`${ROOT}/registry.json`,regMeta=await apiGet(regPath,token);if(!regMeta)throw Error("registry.json が見つかりません");const registry=parseJson(regMeta,regPath);registry[id]={...(registry[id]||{}),...updated};await putText(regPath,JSON.stringify(registry,null,2)+"\n",regMeta.sha,token,`Update MIDI registry: ${id}`)}

      setUi(d,91,"保存確認","GitHub上のMIDIを再確認しています…");
      const verifyMidi=await apiGet(midiPath,token);if(!verifyMidi||verifyMidi.size!==ab.byteLength||verifyMidi.sha!==midiPut?.content?.sha)throw Error("chart.mid の保存確認に失敗しました");
      const verifySong=parseJson(await apiGet(path,token),path);if(verifySong.midiSha256!==hash||Number(verifySong.midiBytes)!==ab.byteLength)throw Error("楽曲設定のMIDI情報が一致しませんでした");
      if(!draftOnly){const regPath=`${ROOT}/registry.json`,registry=parseJson(await apiGet(regPath,token),regPath);if(registry[id]?.midiSha256!==hash||Number(registry[id]?.midiBytes)!==ab.byteLength)throw Error("registry.json のMIDI情報が一致しませんでした")}
      const midiInput=d.getElementById("midi");if(midiInput)midiInput.value="";const action=d.querySelector('.dm-update-action[data-key="midi"]');if(action)action.value="keep";const meta=d.querySelector('.dm-update-meta[data-key="midi"]');if(meta)meta.textContent="現在: chart.mid";
      setUi(d,100,draftOnly?"登録データ更新完了":"GitHub更新完了",`MIDIを更新し、GitHub上の ${ab.byteLength.toLocaleString()} bytes / SHA-256 ${hash.slice(0,12)}… を再確認しました。Timing Correctionでタイミングを確認してください。`,"ok");
    }catch(e){console.error("Direct MIDI update failed",e);setUi(d,0,"GitHub更新エラー",e?.message||String(e),"bad")}
    finally{if(confirm)confirm.disabled=false;if(publish)publish.disabled=false;midiDirectBusy=false}
  }

  function bindMidiDirect(d){
    if(!d||midiBoundDoc===d)return;midiBoundDoc=d;
    d.addEventListener("click",e=>{
      const target=e.target;if(target?.id!=="dmConfirmUpdate"||!d.body.classList.contains("dm-publisher-update"))return;
      const midi=d.getElementById("midi")?.files?.[0];if(!midi||hasNonMidiAssetChanges(d))return;
      e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();void commitMidiDirect(d);
    },true);
  }

  function installObserver(){
    observer?.disconnect();observer=null;initialResetDone=false;
    const d=iframeDoc();if(!d?.documentElement)return;
    syncLame();fixInitialNewMode();bindMidiDirect(d);
    observer=new MutationObserver(()=>{syncLame();fixInitialNewMode();bindMidiDirect(d)});
    observer.observe(d.documentElement,{childList:true,subtree:true});
    setTimeout(()=>{observer?.disconnect();observer=null},12000);
  }

  async function deliverUpdate(d){
    const started=Date.now();
    while(typeof globalThis.DruMasterUpdateCommit!=="function"&&Date.now()-started<10000){
      await new Promise(resolve=>setTimeout(resolve,50));
    }
    if(typeof globalThis.DruMasterUpdateCommit==="function"){
      await globalThis.DruMasterUpdateCommit(d);
      return;
    }
    const rd=iframeDoc(),log=rd?.getElementById("log"),stage=rd?.getElementById("stage"),bar=rd?.getElementById("bar"),pct=rd?.getElementById("percent");
    if(stage)stage.textContent="GitHub更新エラー";
    if(bar)bar.style.width="0%";
    if(pct)pct.textContent="0%";
    if(log){log.textContent="GitHub更新処理を読み込めませんでした。ページを再読み込みしてください。";log.className="bad"}
  }

  frame.addEventListener("load",()=>setTimeout(installObserver,0));
  setTimeout(installObserver,400);

  addEventListener("message",e=>{
    if(e.source!==window||e.origin!==location.origin)return;
    const d=e.data;if(!d||d.type!=="dm-song-editor-ready"||d.mode!=="update"||!d.id||!d.sessionId)return;
    void deliverUpdate(d);
    dispatchEvent(new MessageEvent("message",{data:d,origin:location.origin,source:frame.contentWindow}));
  });
})();