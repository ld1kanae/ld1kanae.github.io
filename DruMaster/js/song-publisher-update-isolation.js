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
      /* Local preparation succeeded but the GitHub committer failed to start.
         Do not leave the editor permanently locked. */
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
