"use strict";
(()=>{
  const root=document.querySelector("#editorWrap"),btn=document.querySelector("#editorButton"),halo=document.querySelector("#editorHalo"),sizeSel=document.querySelector("#editorSize"),copy=document.querySelector("#copyGlowSettings"),status=document.querySelector("#copyStatus");
  if(!root||!btn||!halo)return;
  const controls=[...root.querySelectorAll("[data-var]")];
  const fmt=(el,v)=>`${v}${el.dataset.unit||""}`;
  function apply(){
    for(const el of controls){
      const v=fmt(el,el.value);
      const target=el.dataset.target==="halo"?halo:btn;
      target.style.setProperty(el.dataset.var,v);
      const out=root.querySelector(`[data-output="${el.id}"]`);if(out)out.textContent=v;
    }
  }
  function icon(kind){
    if(kind==="pause")return '<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="4" width="4" height="16" rx="1.3"/><rect x="15" y="4" width="4" height="16" rx="1.3"/></svg>';
    if(kind==="score")return '<svg class="transport-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.2c0-.9 1-1.45 1.78-.98l8.35 5.03a3.2 3.2 0 0 1 0 5.5l-8.35 5.03A1.15 1.15 0 0 1 8 18.8V5.2Z"/></svg>';
    return `<span>${kind==="start"?"START":"ホーム"}</span>`;
  }
  function applySize(){
    btn.classList.remove("size-result","size-pause","size-score","size-start");
    btn.classList.add(`size-${sizeSel.value}`);
    btn.innerHTML=icon(sizeSel.value);
  }
  function payload(){
    const data={size:sizeSel.value,inner:{},outer:{}};
    for(const el of controls){const key=el.dataset.var.replace(/^--/,"");(el.dataset.target==="halo"?data.outer:data.inner)[key]=fmt(el,el.value)}
    return `DruMaster glass hover settings\n${JSON.stringify(data,null,2)}`;
  }
  controls.forEach(el=>el.addEventListener("input",apply));sizeSel.addEventListener("change",applySize);
  copy.addEventListener("click",async()=>{
    const text=payload();
    try{await navigator.clipboard.writeText(text);status.textContent="コピーしました"}
    catch{const ta=document.createElement("textarea");ta.value=text;document.body.appendChild(ta);ta.select();document.execCommand("copy");ta.remove();status.textContent="コピーしました"}
    setTimeout(()=>status.textContent="",1800);
  });
  applySize();apply();
})();