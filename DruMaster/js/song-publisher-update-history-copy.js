"use strict";

(()=>{
  const frame=document.getElementById("registerView");if(!frame)return;
  let boundDoc=null,observer=null;
  function doc(){try{return frame.contentDocument}catch{return null}}
  function ensureStyle(d){if(d.getElementById("dmHistoryCopyStyle"))return;const s=d.createElement("style");s.id="dmHistoryCopyStyle";s.textContent=`
    .dm-history-diag summary{display:flex;align-items:center;gap:8px}
    .dm-history-copy{margin-left:auto;min-width:86px;height:25px;padding:0 9px;border:1px solid #3e5669;border-radius:6px;background:#0a151e;color:#b8cad7;font:800 8px/1 Inter,"Noto Sans JP",system-ui,sans-serif;letter-spacing:.06em;cursor:pointer}
    .dm-history-copy:hover{border-color:#69bddf;color:#effaff;background:#102330}
    .dm-history-item.error .dm-history-copy{border-color:rgba(255,125,141,.55);color:#ffadb7;background:rgba(150,38,55,.12)}
    .dm-history-copy.copied{border-color:#72d6a6!important;color:#72d6a6!important;background:rgba(54,178,120,.10)!important}
  `;d.head.appendChild(s)}
  async function copyText(text,d){
    if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);return}
    const ta=d.createElement("textarea");ta.value=text;ta.style.position="fixed";ta.style.opacity="0";d.body.appendChild(ta);ta.select();d.execCommand("copy");ta.remove();
  }
  function buildText(item){
    const status=item.querySelector(".dm-history-status")?.textContent?.trim()||"";
    const detail=item.querySelector(".dm-history-detail")?.innerText?.trim()||"";
    const log=item.querySelector(".dm-history-log")?.textContent?.trim()||"";
    return [status&&`STATUS: ${status}`,detail&&`DETAIL: ${detail}`,log].filter(Boolean).join("\n");
  }
  function decorate(d){
    ensureStyle(d);
    d.querySelectorAll(".dm-history-diag").forEach(diag=>{
      if(diag.querySelector(".dm-history-copy"))return;
      const summary=diag.querySelector("summary");if(!summary)return;
      const item=diag.closest(".dm-history-item"),isError=item?.classList.contains("error");
      const b=d.createElement("button");b.type="button";b.className="dm-history-copy";b.textContent=isError?"COPY ERROR":"COPY LOG";
      b.addEventListener("click",async e=>{e.preventDefault();e.stopPropagation();const text=buildText(item);try{await copyText(text,d);const before=b.textContent;b.textContent="COPIED";b.classList.add("copied");setTimeout(()=>{b.textContent=before;b.classList.remove("copied")},1200)}catch(err){console.error("History log copy failed",err);b.textContent="COPY ERROR"}});
      summary.appendChild(b);
    });
  }
  function bind(d){if(!d?.body)return false;if(boundDoc===d){decorate(d);return true}boundDoc=d;decorate(d);observer?.disconnect();observer=new MutationObserver(()=>decorate(d));observer.observe(d.body,{childList:true,subtree:true});return true}
  function install(){return bind(doc())}
  frame.addEventListener("load",()=>{boundDoc=null;observer?.disconnect();const t=setInterval(()=>{if(install())clearInterval(t)},80);setTimeout(()=>clearInterval(t),12000)});
  if(!install()){const t=setInterval(()=>{if(install())clearInterval(t)},80);setTimeout(()=>clearInterval(t),12000)}
})();
