"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;

  const LABEL={fullmix:"原曲",base:"オフボーカル",drums:"ドラムのみ",vocals:"ボーカルのみ",midi:"MIDI"};
  let observer=null,refreshing=false;

  function doc(){try{return frame.contentDocument}catch{return null}}
  function forceFileVisible(input){
    if(!input)return;
    if(input.hidden)input.hidden=false;
    if(input.disabled)input.disabled=false;
    input.removeAttribute("hidden");
    input.removeAttribute("disabled");
  }
  function registered(meta){return !!meta&&!String(meta.textContent||"").includes("未登録")}

  function setInternalAction(select,input,value){
    if(!select)return;
    select.value=value;
    select.dispatchEvent(new Event("change",{bubbles:true}));
    requestAnimationFrame(()=>{
      forceFileVisible(input);
      syncAll();
    });
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
    if(note)note.textContent=parts.length?parts.join(" / "):"素材はすべて変更なし";
  }

  function syncWrap(wrap,d){
    const select=wrap.querySelector(".dm-update-action"),input=wrap.querySelector('input[type="file"]'),meta=wrap.querySelector(".dm-update-meta");
    if(!select||!input)return;
    const key=select.dataset.key||"";
    select.classList.add("dm-update-action-internal");
    select.tabIndex=-1;
    select.setAttribute("aria-hidden","true");
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
      del.hidden=!canDelete;
      del.classList.toggle("active",select.value==="delete");
      del.textContent=select.value==="delete"?"削除を取消":"削除";
    }

    if(input.dataset.dmUpdateFileBound!=="1"){
      input.dataset.dmUpdateFileBound="1";
      input.addEventListener("change",()=>{
        if(input.files?.length)setInternalAction(select,input,"replace");
        else if(select.value==="replace")setInternalAction(select,input,"keep");
      });
      select.addEventListener("change",()=>requestAnimationFrame(()=>{
        forceFileVisible(input);
        syncAll();
      }));
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

  function syncAll(){
    if(refreshing)return;
    refreshing=true;
    try{
      const d=doc();if(!d?.head||!d.body)return;
      injectStyle(d);
      d.querySelectorAll(".dm-update-control").forEach(w=>syncWrap(w,d));
      syncSummary(d);
    }finally{refreshing=false}
  }

  function install(){
    observer?.disconnect();observer=null;
    const d=doc();if(!d?.documentElement)return;
    syncAll();
    observer=new MutationObserver(()=>syncAll());
    observer.observe(d.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:["class","hidden","disabled"]});
    d.addEventListener("change",e=>{
      if(e.target?.id==="dmExistingSong")setTimeout(syncAll,0);
    },true);
    d.addEventListener("click",e=>{
      if(e.target?.matches?.(".dm-mode-switch button"))setTimeout(syncAll,0);
    },true);
    setTimeout(syncAll,250);
    setTimeout(syncAll,800);
  }

  frame.addEventListener("load",()=>setTimeout(install,0));
  setTimeout(install,450);
})();
