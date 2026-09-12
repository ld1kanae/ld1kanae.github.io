"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;

  let boundDoc=null,busy=false,monitorTimer=0,busyStartedAt=0;

  function doc(){try{return frame.contentDocument}catch{return null}}
  function setDisabled(el,on){if(el)el.disabled=!!on}
  function setBusy(d,on){
    busy=!!on;
    d.body?.classList.toggle("dm-update-transaction-busy",busy);
    const grid=d.querySelector(".grid");
    if(grid){try{grid.inert=busy}catch{}}
    setDisabled(d.getElementById("dmExistingSong"),busy);
    d.querySelectorAll(".dm-mode-switch button").forEach(b=>setDisabled(b,busy));
    d.querySelectorAll(".dm-update-delete").forEach(b=>setDisabled(b,busy));
    if(busy){
      busyStartedAt=Date.now();
      try{d.activeElement?.blur?.()}catch{}
    }
  }
  function ensureStyle(d){
    if(d.getElementById("dmUpdateIsolationStyle"))return;
    const s=d.createElement("style");
    s.id="dmUpdateIsolationStyle";
    s.textContent=`
      body.dm-update-transaction-busy .grid{pointer-events:none!important}
      body.dm-update-transaction-busy #dmExistingWrap{cursor:wait}
      body.dm-update-transaction-busy .dm-mode-switch button,
      body.dm-update-transaction-busy #dmExistingSong{cursor:wait!important}
    `;
    d.head.appendChild(s);
  }
  function unlock(d){
    clearInterval(monitorTimer);monitorTimer=0;
    setBusy(d,false);
  }
  function monitor(d){
    clearInterval(monitorTimer);
    monitorTimer=setInterval(()=>{
      if(!busy){clearInterval(monitorTimer);monitorTimer=0;return}
      const stage=String(d.getElementById("stage")?.textContent||"").trim();
      if(stage==="GitHub更新完了"||stage==="GitHub更新エラー"||stage==="エラー"){
        unlock(d);return;
      }
      if(stage==="編集準備完了"&&Date.now()-busyStartedAt>12000){
        unlock(d);return;
      }
      if(Date.now()-busyStartedAt>10*60*1000)unlock(d);
    },150);
  }
  function bind(d){
    if(boundDoc===d)return;
    boundDoc=d;ensureStyle(d);
    d.addEventListener("click",e=>{
      const target=e.target;
      if(target?.id!=="dmConfirmUpdate")return;
      if(!d.body.classList.contains("dm-publisher-update"))return;
      if(busy){e.preventDefault();e.stopImmediatePropagation();return}
      setBusy(d,true);
      setTimeout(()=>monitor(d),0);
    },true);
    d.addEventListener("change",e=>{
      if(!busy)return;
      if(e.target?.id==="dmExistingSong"){
        e.preventDefault();e.stopImmediatePropagation();
      }
    },true);
  }
  function install(){
    const d=doc();if(!d?.head||!d.body)return false;
    bind(d);return !!d.getElementById("dmConfirmUpdate");
  }

  frame.addEventListener("load",()=>{
    boundDoc=null;busy=false;clearInterval(monitorTimer);monitorTimer=0;
    const timer=setInterval(()=>{if(install())clearInterval(timer)},100);
    setTimeout(()=>clearInterval(timer),10000);
  });
  const timer=setInterval(()=>{if(install())clearInterval(timer)},100);
  setTimeout(()=>clearInterval(timer),10000);
})();

/* MIDI-only updates are committed through the Git database API as one atomic
   commit. This prevents chart.mid, chart.mid.gz, song.json and registry.json
   from creating four separate pushes and therefore four build queues. */
(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;
  const REPO="ld1kanae/ld1kanae.github.io",BRANCH="main",ROOT="DruMaster/songs";
  let busy=false,boundDoc=null;

  function headers(token){return {"Accept":"application/vnd.github+json","Authorization":`Bearer ${token}`,"X-GitHub-Api-Version":"2022-11-28"}}
  function decodeText(s){const b=atob(String(s||"").replace(/\n/g,"")),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return new TextDecoder().decode(u)}
  function arrayBufferBase64(ab){const u=new Uint8Array(ab);let b="";for(let i=0;i<u.length;i+=0x8000)b+=String.fromCharCode(...u.subarray(i,i+0x8000));return btoa(b)}
  async function request(url,token,method="GET",body){
    const r=await fetch(url,{method,headers:{...headers(token),...(body?{"Content-Type":"application/json"}:{})},body:body?JSON.stringify(body):undefined,cache:"no-store"});
    if(!r.ok){const text=await r.text();const e=Error(`GitHub API ${r.status}: ${text}`);e.status=r.status;throw e}
    return r.status===204?null:r.json();
  }
  async function apiGet(path,token){
    const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}&t=${Date.now()}`,{headers:headers(token),cache:"no-store"});
    if(r.status===404)return null;
    if(!r.ok)throw Error(`GitHub API ${r.status}: ${path}`);
    return r.json();
  }
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
  async function makeBlob(token,content,encoding){return request(`https://api.github.com/repos/${REPO}/git/blobs`,token,"POST",{content,encoding})}

  async function commitMidiAtomic(d){
    if(busy)return;busy=true;
    const confirm=d.getElementById("dmConfirmUpdate"),publish=d.getElementById("publish");
    try{
      const token=String(d.getElementById("token")?.value||"").trim();if(!token)throw Error("GitHub tokenを入力してください");
      const id=String(d.getElementById("dmExistingSong")?.value||"").trim();if(!id)throw Error("更新する楽曲を選択してください");
      const file=d.getElementById("midi")?.files?.[0];if(!file)throw Error("更新するMIDIファイルを選択してください");
      const title=String(d.getElementById("title")?.value||"").trim(),artist=String(d.getElementById("artist")?.value||"").trim(),order=readOrder(d);if(!title)throw Error("曲名を入力してください");if(!artist)throw Error("アーティスト名を入力してください");
      if(confirm)confirm.disabled=true;if(publish)publish.disabled=true;const box=d.getElementById("dmUpdateConfirm");if(box)box.hidden=true;

      setUi(d,3,"MIDI確認","選択したMIDIを検証しています…");
      const ab=await file.arrayBuffer(),info=parseMidi(ab),hash=await sha256(ab),gz=await gzip(ab),version=Date.now();
      const midiPath=`${ROOT}/${id}/chart.mid`,gzPath=`${ROOT}/${id}/chart.mid.gz`,songPath=`${ROOT}/${id}/song.json`,draftPath=`${ROOT}/${id}/song-draft.json`,regPath=`${ROOT}/registry.json`;
      const [gzMeta,liveSong,draftSong]=await Promise.all([apiGet(gzPath,token),apiGet(songPath,token),apiGet(draftPath,token)]);
      let songMeta=liveSong,path=songPath,draftOnly=false;if(!songMeta){songMeta=draftSong;path=draftPath;draftOnly=true}if(!songMeta)throw Error(`${id} の楽曲設定が見つかりません`);
      const current=parseJson(songMeta,path),midiGzip=gz?`songs/${id}/chart.mid.gz?v=${version}`:null,updated={...current,title,artist,order,bpm:Number(info.bpm.toFixed(6)),timeSignature:{numerator:info.numerator,denominator:info.denominator},division:info.division,noteCount:info.noteCount,midi:`songs/${id}/chart.mid?v=${version}`,midiGzip,midiBytes:ab.byteLength,midiSha256:hash};

      let registryText=null;
      if(!draftOnly){
        const regMeta=await apiGet(regPath,token);if(!regMeta)throw Error("registry.json が見つかりません");
        const registry=parseJson(regMeta,regPath);registry[id]={...(registry[id]||{}),...updated};registryText=JSON.stringify(registry,null,2)+"\n";
      }

      setUi(d,24,"1コミット準備","MIDI・圧縮MIDI・設定を1つのコミットにまとめています…");
      const ref=await request(`https://api.github.com/repos/${REPO}/git/ref/heads/${BRANCH}`,token);
      const headSha=ref?.object?.sha;if(!headSha)throw Error("main の現在位置を取得できませんでした");
      const headCommit=await request(`https://api.github.com/repos/${REPO}/git/commits/${headSha}`,token);
      const baseTree=headCommit?.tree?.sha;if(!baseTree)throw Error("main のツリーを取得できませんでした");

      const blobTasks=[makeBlob(token,arrayBufferBase64(ab),"base64"),makeBlob(token,JSON.stringify(updated,null,2)+"\n","utf-8")];
      if(gz)blobTasks.push(makeBlob(token,arrayBufferBase64(gz.buffer),"base64"));
      if(registryText!==null)blobTasks.push(makeBlob(token,registryText,"utf-8"));
      const blobs=await Promise.all(blobTasks);
      const midiBlob=blobs[0],songBlob=blobs[1];let i=2,gzBlob=null,regBlob=null;if(gz)gzBlob=blobs[i++];if(registryText!==null)regBlob=blobs[i++];

      const treeEntries=[{path:midiPath,mode:"100644",type:"blob",sha:midiBlob.sha},{path,mode:"100644",type:"blob",sha:songBlob.sha}];
      if(gzBlob)treeEntries.push({path:gzPath,mode:"100644",type:"blob",sha:gzBlob.sha});
      else if(gzMeta?.sha)treeEntries.push({path:gzPath,mode:"100644",type:"blob",sha:null});
      if(regBlob)treeEntries.push({path:regPath,mode:"100644",type:"blob",sha:regBlob.sha});

      setUi(d,62,"GitHub更新","1回のコミットとして main に保存しています…");
      const tree=await request(`https://api.github.com/repos/${REPO}/git/trees`,token,"POST",{base_tree:baseTree,tree:treeEntries});
      const commit=await request(`https://api.github.com/repos/${REPO}/git/commits`,token,"POST",{message:`Update MIDI: ${id}`,tree:tree.sha,parents:[headSha]});
      try{await request(`https://api.github.com/repos/${REPO}/git/refs/heads/${BRANCH}`,token,"PATCH",{sha:commit.sha,force:false})}
      catch(e){if(e?.status===409||e?.status===422)throw Error("更新中にmainが変更されました。ページを再読み込みしてもう一度MIDI更新してください。");throw e}

      setUi(d,88,"保存確認","GitHub上のMIDIとメタデータを再確認しています…");
      const verifyMidi=await apiGet(midiPath,token);if(!verifyMidi||verifyMidi.size!==ab.byteLength||verifyMidi.sha!==midiBlob.sha)throw Error("chart.mid の保存確認に失敗しました");
      const verifySong=parseJson(await apiGet(path,token),path);if(verifySong.midiSha256!==hash||Number(verifySong.midiBytes)!==ab.byteLength)throw Error("楽曲設定のMIDI情報が一致しませんでした");
      if(!draftOnly){const registry=parseJson(await apiGet(regPath,token),regPath);if(registry[id]?.midiSha256!==hash||Number(registry[id]?.midiBytes)!==ab.byteLength)throw Error("registry.json のMIDI情報が一致しませんでした")}

      const midiInput=d.getElementById("midi");if(midiInput)midiInput.value="";const action=d.querySelector('.dm-update-action[data-key="midi"]');if(action)action.value="keep";const meta=d.querySelector('.dm-update-meta[data-key="midi"]');if(meta)meta.textContent="現在: chart.mid";
      setUi(d,100,draftOnly?"登録データ更新完了":"GitHub更新完了",`MIDI一式を1コミットで更新しました。${ab.byteLength.toLocaleString()} bytes / SHA-256 ${hash.slice(0,12)}… を再確認済みです。`,"ok");
    }catch(e){console.error("Atomic MIDI update failed",e);setUi(d,0,"GitHub更新エラー",e?.message||String(e),"bad")}
    finally{if(confirm)confirm.disabled=false;if(publish)publish.disabled=false;busy=false}
  }

  function bind(d){
    if(!d||boundDoc===d)return;boundDoc=d;
    d.addEventListener("click",e=>{
      const target=e.target;if(target?.id!=="dmConfirmUpdate"||!d.body.classList.contains("dm-publisher-update"))return;
      const midi=d.getElementById("midi")?.files?.[0];if(!midi||hasNonMidiAssetChanges(d))return;
      e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();void commitMidiAtomic(d);
    },true);
  }
  function install(){let d;try{d=frame.contentDocument}catch{return}if(d?.documentElement)bind(d)}
  frame.addEventListener("load",()=>setTimeout(install,0));
  setTimeout(install,0);setTimeout(install,250);setTimeout(install,1000);
})();
