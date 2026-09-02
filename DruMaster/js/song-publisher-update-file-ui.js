"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;

  const REPO="ld1kanae/ld1kanae.github.io",BRANCH="main",ROOT="DruMaster/songs";
  const LABEL={fullmix:"原曲",base:"オフボーカル",drums:"ドラムのみ",vocals:"ボーカルのみ",midi:"MIDI"};
  let pollTimer=0,pollCount=0,boundDoc=null,fallbackLoaded=false,metadataBusy=false;

  function doc(){try{return frame.contentDocument}catch{return null}}
  function forceFileVisible(input){
    if(!input)return;
    input.hidden=false;
    input.disabled=false;
    if(input.hasAttribute("hidden"))input.removeAttribute("hidden");
    if(input.hasAttribute("disabled"))input.removeAttribute("disabled");
  }
  function registered(meta){return !!meta&&!String(meta.textContent||"").includes("未登録")}
  function setText(node,text){if(node&&node.textContent!==text)node.textContent=text}
  function headers(token){return {"Accept":"application/vnd.github+json","Authorization":`Bearer ${token}`,"X-GitHub-Api-Version":"2022-11-28"}}
  function encodeText(text){const u=new TextEncoder().encode(text);let b="";for(let i=0;i<u.length;i+=0x8000)b+=String.fromCharCode(...u.subarray(i,i+0x8000));return btoa(b)}
  function decodeText(s){const b=atob(String(s||"").replace(/\n/g,"")),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return new TextDecoder().decode(u)}
  async function apiGet(path,token){const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}&t=${Date.now()}`,{headers:headers(token),cache:"no-store"});if(r.status===404)return null;if(!r.ok)throw Error(`GitHub API ${r.status}: ${path}`);return r.json()}
  async function putText(path,text,sha,token,message){const body={message,content:encodeText(text),branch:BRANCH};if(sha)body.sha=sha;const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`,{method:"PUT",headers:{...headers(token),"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r.ok)throw Error(`GitHub update ${r.status}: ${await r.text()}`);return r.json()}
  function parseJson(meta,path){try{return JSON.parse(decodeText(meta?.content)||"{}")||{}}catch{throw Error(`${path} を解析できませんでした`)}}
  function parseOrder(raw){
    const text=String(raw??"").trim();
    if(text==="")return null;
    const n=Number(text);
    if(!Number.isInteger(n)||n<1)throw Error("表示順は1以上の整数で入力してください");
    return n;
  }
  function normalizedStoredOrder(raw){
    const n=Number(raw);
    return Number.isInteger(n)&&n>=1?n:null;
  }
  function setUi(d,percent,stage,message,kind=""){
    const bar=d.getElementById("bar"),pct=d.getElementById("percent"),st=d.getElementById("stage"),log=d.getElementById("log");
    if(bar)bar.style.width=`${Math.max(0,Math.min(100,percent))}%`;
    if(pct)pct.textContent=`${Math.round(percent)}%`;
    if(st)st.textContent=stage;
    if(log&&message){log.textContent=message;log.className=kind}
  }
  function syncOrderField(d){
    const input=d.getElementById("order");if(!input)return;
    input.min="1";input.step="1";input.placeholder="1 = 先頭 / 未指定は末尾";
    if(d.body.classList.contains("dm-publisher-update")&&String(input.value).trim()==="0")input.value="";
  }

  function setInternalAction(select,input,value){
    if(!select)return;
    if(select.value!==value){
      select.value=value;
      select.dispatchEvent(new Event("change",{bubbles:true}));
    }
    forceFileVisible(input);
    requestAnimationFrame(()=>{
      forceFileVisible(input);
      syncAll();
    });
  }

  function syncRequirementLabels(d){
    const midi=d.getElementById("midi"),badge=midi?.closest(".file-row")?.querySelector("i");
    if(!badge)return;
    const updating=d.body.classList.contains("dm-publisher-update");
    setText(badge,updating?"任意":"必須");
    badge.classList.toggle("req",!updating);
    badge.classList.toggle("optional",updating);
  }

  function syncSummary(d){
    if(!d?.body.classList.contains("dm-publisher-update"))return;
    const parts=[];
    for(const wrap of d.querySelectorAll(".dm-update-control")){
      const select=wrap.querySelector(".dm-update-action"),meta=wrap.querySelector(".dm-update-meta");
      if(!select)continue;
      const key=select.dataset.key||"",label=LABEL[key]||key;
      if(select.value==="delete")parts.push(`${label}: 削除`);
      else if(select.value==="replace")parts.push(`${label}: ${registered(meta)?"差し替え":"追加"}`);
    }
    const note=d.getElementById("dmCurrentNote");
    setText(note,parts.length?parts.join(" / "):"素材はすべて変更なし");
  }

  function syncWrap(wrap,d){
    const select=wrap.querySelector(".dm-update-action"),input=wrap.querySelector('input[type="file"]'),meta=wrap.querySelector(".dm-update-meta");
    if(!select||!input)return;
    const key=select.dataset.key||"";

    select.classList.add("dm-update-action-internal");
    if(select.tabIndex!==-1)select.tabIndex=-1;
    if(select.getAttribute("aria-hidden")!=="true")select.setAttribute("aria-hidden","true");
    forceFileVisible(input);

    let del=wrap.querySelector(".dm-update-delete");
    if(key!=="midi"&&!del){
      del=d.createElement("button");
      del.type="button";
      del.className="dm-update-delete";
      del.textContent="削除";
      del.addEventListener("click",()=>{
        if(select.value==="delete")setInternalAction(select,input,"keep");
        else{
          input.value="";
          setInternalAction(select,input,"delete");
        }
      });
      wrap.appendChild(del);
    }

    wrap.classList.toggle("dm-update-no-delete",key==="midi");
    if(del){
      const canDelete=d.body.classList.contains("dm-publisher-update")&&registered(meta);
      if(del.hidden===canDelete)del.hidden=!canDelete;
      del.classList.toggle("active",select.value==="delete");
      setText(del,select.value==="delete"?"削除を取消":"削除");
    }

    if(input.dataset.dmUpdateFileBound!=="1"){
      input.dataset.dmUpdateFileBound="1";
      const onFile=()=>setInternalAction(select,input,input.files?.length?"replace":"keep");
      input.addEventListener("change",onFile);
      input.addEventListener("input",onFile);
    }
  }

  function injectStyle(d){
    if(d.getElementById("dmUpdateSimpleFileStyle"))return;
    const s=d.createElement("style");
    s.id="dmUpdateSimpleFileStyle";
    s.textContent=`
      .dm-update-action-internal{display:none!important}
      body.dm-publisher-update .dm-update-control{display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;gap:7px 8px!important;align-items:center!important}
      body.dm-publisher-update .dm-update-meta{grid-column:1/-1!important}
      body.dm-publisher-update .dm-update-control input[type=file]{display:block!important;grid-column:1/2!important;width:100%!important;min-width:0!important}
      body.dm-publisher-update .dm-update-control.dm-update-no-delete input[type=file]{grid-column:1/-1!important}
      .dm-update-delete{grid-column:2;height:34px;min-width:70px;padding:0 10px;border:1px solid #39566e;border-radius:7px;background:#0a1721;color:#aab9c7;font:750 10px/1 Inter,"Noto Sans JP",system-ui,sans-serif;cursor:pointer}
      .dm-update-delete:hover{border-color:#58bfc9;color:#edfaff;background:#0d202b}
      .dm-update-delete.active{border-color:#d17b93;color:#ffdbe5;background:#2a121a}
      .dm-update-delete[hidden],body.dm-publisher-new .dm-update-delete{display:none!important}
      @media(max-width:640px){body.dm-publisher-update .dm-update-control{grid-template-columns:minmax(0,1fr) auto!important}.dm-update-delete{min-width:62px}}
    `;
    d.head.appendChild(s);
  }

  function syncAll(d=doc()){
    if(!d?.head||!d.body)return false;
    injectStyle(d);
    d.querySelectorAll(".dm-update-control").forEach(w=>syncWrap(w,d));
    syncRequirementLabels(d);
    syncOrderField(d);
    syncSummary(d);
    return !!d.getElementById("dmPublisherMode");
  }

  function hasAssetChanges(d){
    for(const wrap of d.querySelectorAll(".dm-update-control")){
      const select=wrap.querySelector(".dm-update-action"),input=wrap.querySelector('input[type="file"]');
      if(select?.value&&select.value!=="keep")return true;
      if(input?.files?.length)return true;
    }
    return false;
  }

  function validateMetadata(d){
    const title=d.getElementById("title")?.value.trim()||"",artist=d.getElementById("artist")?.value.trim()||"";
    if(!title)throw Error("曲名を入力してください");
    if(!artist)throw Error("アーティスト名を入力してください");
    return {title,artist,order:parseOrder(d.getElementById("order")?.value)};
  }

  async function runMetadataOnlyUpdate(d){
    if(metadataBusy)return;
    metadataBusy=true;
    const confirm=d.getElementById("dmConfirmUpdate"),publish=d.getElementById("publish");
    try{
      const token=String(d.getElementById("token")?.value||"").trim();if(!token)throw Error("GitHub tokenを入力してください");
      const id=String(d.getElementById("dmExistingSong")?.value||"").trim();if(!id)throw Error("更新する楽曲を選択してください");
      const values=validateMetadata(d);
      if(confirm)confirm.disabled=true;if(publish)publish.disabled=true;
      const box=d.getElementById("dmUpdateConfirm");if(box)box.hidden=true;
      setUi(d,4,"既存データ確認","GitHub上の楽曲設定を確認しています…");

      const songPath=`${ROOT}/${id}/song.json`,draftPath=`${ROOT}/${id}/song-draft.json`;
      let meta=await apiGet(songPath,token),path=songPath,draftOnly=false;
      if(!meta){meta=await apiGet(draftPath,token);path=draftPath;draftOnly=true}
      if(!meta)throw Error(`${id} の楽曲設定が見つかりません`);
      const current=parseJson(meta,path),updated={...current,title:values.title,artist:values.artist,order:values.order};
      setUi(d,42,draftOnly?"登録データ更新":"楽曲設定更新",`${path.split("/").pop()} を更新しています…`);
      await putText(path,JSON.stringify(updated,null,2)+"\n",meta.sha,token,`Update song metadata: ${id}`);

      if(!draftOnly){
        setUi(d,70,"楽曲一覧更新","registry.json を更新しています…");
        const regPath=`${ROOT}/registry.json`,regMeta=await apiGet(regPath,token);if(!regMeta)throw Error("registry.json が見つかりません");
        const registry=parseJson(regMeta,regPath);registry[id]={...(registry[id]||{}),...updated};
        await putText(regPath,JSON.stringify(registry,null,2)+"\n",regMeta.sha,token,`Update song registry: ${id}`);
      }

      setUi(d,90,"保存確認","GitHubへ保存された表示順を再確認しています…");
      const verifyMeta=await apiGet(path,token),verified=parseJson(verifyMeta,path);
      if(normalizedStoredOrder(verified.order)!==values.order)throw Error(`表示順の保存確認に失敗しました（期待値: ${values.order??"未指定"} / GitHub: ${normalizedStoredOrder(verified.order)??"未指定"}）`);
      if(!draftOnly){
        const verifyReg=await apiGet(`${ROOT}/registry.json`,token),registry=parseJson(verifyReg,`${ROOT}/registry.json`);
        if(normalizedStoredOrder(registry[id]?.order)!==values.order)throw Error("registry.json の表示順が一致しませんでした");
      }

      const selected=d.getElementById("dmExistingSong")?.selectedOptions?.[0];if(selected)selected.textContent=`${values.title} — ${values.artist}`;
      const orderInput=d.getElementById("order");if(orderInput)orderInput.value=values.order==null?"":String(values.order);
      setUi(d,100,draftOnly?"登録データ更新完了":"GitHub更新完了",values.order==null?"表示順を未指定（末尾）として保存しました。":`表示順 ${values.order} をGitHubへ保存し、再確認しました。`,"ok");
    }catch(e){console.error("Metadata-only update failed",e);setUi(d,0,"GitHub更新エラー",e?.message||String(e),"bad")}
    finally{if(confirm)confirm.disabled=false;if(publish)publish.disabled=false;metadataBusy=false}
  }

  function buildUpdateConfirmation(d){
    const confirm=d.getElementById("dmUpdateConfirm"),list=d.getElementById("dmUpdateConfirmList");
    if(!confirm||!list)return false;
    let values;try{values=validateMetadata(d)}catch(e){setUi(d,0,"入力エラー",e.message||String(e),"bad");return false}
    list.replaceChildren();
    let count=0;
    for(const wrap of d.querySelectorAll(".dm-update-control")){
      const select=wrap.querySelector(".dm-update-action"),input=wrap.querySelector('input[type="file"]'),meta=wrap.querySelector(".dm-update-meta");
      if(!select)continue;
      const key=select.dataset.key||"",label=LABEL[key]||key;
      if(select.value==="delete"){
        const li=d.createElement("li");li.textContent=`${label}: 削除`;list.appendChild(li);count++;
      }else if(select.value==="replace"&&input?.files?.[0]){
        const li=d.createElement("li");li.textContent=`${label}: ${registered(meta)?"差し替え":"追加"} → ${input.files[0].name}`;list.appendChild(li);count++;
      }
    }
    const li=d.createElement("li");
    li.textContent=`表示順: ${values.order==null?"未指定（末尾）":values.order}`;
    list.appendChild(li);count++;
    const warn=d.getElementById("dmMidiWarning");if(warn)warn.hidden=!d.getElementById("midi")?.files?.length;
    confirm.hidden=false;
    confirm.scrollIntoView({behavior:"smooth",block:"center"});
    const log=d.getElementById("log");if(log){log.textContent=hasAssetChanges(d)?"更新内容を確認し、「この内容で更新」を押してください。":"メタデータのみをGitHubへ直接更新します。「この内容で更新」を押してください。";log.className=""}
    return count>0;
  }

  function bindDocument(d){
    if(boundDoc===d)return;
    boundDoc=d;
    d.addEventListener("change",e=>{
      if(e.target?.id==="dmExistingSong")setTimeout(()=>syncAll(d),0);
    },true);
    d.addEventListener("click",e=>{
      const target=e.target;
      if(target?.id==="publish"){
        syncOrderField(d);
        if(!d.body.classList.contains("dm-publisher-update")){
          try{parseOrder(d.getElementById("order")?.value)}catch(err){e.preventDefault();e.stopImmediatePropagation();setUi(d,0,"入力エラー",err.message||String(err),"bad")}
          return;
        }
        e.preventDefault();
        e.stopImmediatePropagation();
        syncAll(d);
        if(!buildUpdateConfirmation(d))return;
        return;
      }
      if(target?.id==="dmConfirmUpdate"&&d.body.classList.contains("dm-publisher-update")&&!hasAssetChanges(d)){
        e.preventDefault();e.stopImmediatePropagation();void runMetadataOnlyUpdate(d);return;
      }
      if(target?.matches?.(".dm-mode-switch button"))setTimeout(()=>syncAll(d),0);
    },true);
  }

  function loadUpdateModeFallback(){
    if(fallbackLoaded)return;
    fallbackLoaded=true;
    const s=document.createElement("script");
    s.src="js/song-publisher-update-mode.js?v=20260902-updatefix2";
    s.dataset.dmUpdateFallback="1";
    document.head.appendChild(s);
  }

  function startPolling(){
    clearInterval(pollTimer);pollTimer=0;pollCount=0;boundDoc=null;
    const tick=()=>{
      const d=doc();
      if(d?.head&&d.body){
        bindDocument(d);
        const ready=syncAll(d);
        if(!ready&&d.getElementById("publish")&&pollCount===4)loadUpdateModeFallback();

        const chooser=d.getElementById("dmExistingSong");
        const controls=[...d.querySelectorAll('.dm-update-control input[type="file"]')];
        const catalogReady=!!chooser?.options?.length;
        const controlsReady=controls.length>=5&&controls.every(input=>!input.disabled&&!input.hidden);
        if(ready&&catalogReady&&controlsReady&&pollCount>=8){
          clearInterval(pollTimer);pollTimer=0;
          setTimeout(()=>syncAll(d),500);
          setTimeout(()=>syncAll(d),1500);
          return;
        }
      }
      if(++pollCount>=40){clearInterval(pollTimer);pollTimer=0}
    };
    tick();
    if(!pollTimer)pollTimer=setInterval(tick,250);
  }

  frame.addEventListener("load",()=>setTimeout(startPolling,0));
  setTimeout(startPolling,250);
})();