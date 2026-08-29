"use strict";

(()=>{
  const registerTab=document.getElementById("registerTab"),editorTab=document.getElementById("editorTab"),volumeTab=document.getElementById("volumeTab");
  const registerView=document.getElementById("registerView"),editorView=document.getElementById("editorView"),volumeView=document.getElementById("volumeView");
  if(!registerTab||!editorTab||!volumeTab||!registerView||!editorView||!volumeView)return;

  const tabs={register:registerTab,editor:editorTab,volume:volumeTab},views={register:registerView,editor:editorView,volume:volumeView};
  const launcher=(tool)=>`song-existing-edit.html?tool=${tool}&v=20260829-restore1`;
  const TOKEN_SENTINEL="__dm_existing_edit__";
  let session=null,rememberedToken="";

  async function readRememberedToken(){
    if(!navigator.credentials?.get||typeof PasswordCredential!=="function")return "";
    try{const c=await navigator.credentials.get({password:true,mediation:"optional"});const p=c?.password||"";return /^github_pat_/.test(p)?p:""}catch{return ""}
  }
  void readRememberedToken().then(v=>{rememberedToken=v});

  function activate(which){
    for(const [key,tab] of Object.entries(tabs)){
      const active=key===which;
      tab.classList.toggle("active",active);
      tab.setAttribute("aria-selected",String(active));
      views[key].classList.toggle("active",active);
    }
  }
  function makeDirectTab(tab){
    tab.disabled=false;
    tab.classList.remove("locked");
    tab.classList.add("ready");
    tab.setAttribute("aria-disabled","false");
    const state=tab.querySelector(".tab-state");if(state)state.textContent="EDIT";
  }
  function ensureLaunchers(){
    makeDirectTab(editorTab);makeDirectTab(volumeTab);
    if(!editorView.src||editorView.src==="about:blank")editorView.src=launcher("timing");
    if(!volumeView.src||volumeView.src==="about:blank")volumeView.src=launcher("volume");
  }

  editorTab.addEventListener("click",e=>{e.stopImmediatePropagation();activate("editor")},true);
  volumeTab.addEventListener("click",e=>{e.stopImmediatePropagation();activate("volume")},true);

  addEventListener("message",async e=>{
    if(e.origin!==location.origin)return;
    const d=e.data;
    if(d?.type==="dm-existing-editor-ready"&&(e.source===editorView.contentWindow||e.source===volumeView.contentWindow)&&d.id&&d.sessionId){
      session=d;
      if(!rememberedToken)rememberedToken=await readRememberedToken();
      const inherited={dmSongPublisher:{token:rememberedToken||TOKEN_SENTINEL,repo:"ld1kanae/ld1kanae.github.io",branch:"main",id:d.id,sessionId:d.sessionId,at:d.at||Date.now()}};
      try{editorView.contentWindow.name=JSON.stringify(inherited)}catch{}
      try{volumeView.contentWindow.name=JSON.stringify(inherited)}catch{}
      editorView.src=`song-sync-editor.html?song=${encodeURIComponent(d.id)}&session=${encodeURIComponent(d.sessionId)}&embedded=1&v=20260829-restore1`;
      volumeView.src=`song-volume-editor.html?song=${encodeURIComponent(d.id)}&session=${encodeURIComponent(d.sessionId)}&embedded=1&v=20260829-restore1`;
      for(const tab of [editorTab,volumeTab]){const s=tab.querySelector(".tab-state");if(s)s.textContent="READY"}
      activate(d.tool==="volume"?"volume":"editor");
      return;
    }
    if(d?.type==="dm-song-editor-ready"&&e.source===registerView.contentWindow&&d.mode==="update"){
      queueMicrotask(()=>activate("register"));
    }
  });

  ensureLaunchers();
  setTimeout(ensureLaunchers,250);
  globalThis.DruMasterExistingEditor={activate,get session(){return session}};
})();
