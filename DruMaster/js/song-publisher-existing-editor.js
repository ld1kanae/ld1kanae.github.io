"use strict";

(()=>{
  const registerTab=document.getElementById("registerTab"),editorTab=document.getElementById("editorTab"),volumeTab=document.getElementById("volumeTab");
  const registerView=document.getElementById("registerView"),editorView=document.getElementById("editorView"),volumeView=document.getElementById("volumeView");
  if(!registerTab||!editorTab||!volumeTab||!registerView||!editorView||!volumeView)return;

  const tabs={register:registerTab,editor:editorTab,volume:volumeTab},views={register:registerView,editor:editorView,volume:volumeView};
  const launcher=tool=>`song-existing-edit.html?tool=${tool}&v=20260829-lazy1`;
  const TOKEN_SENTINEL="__dm_existing_edit__";
  let session=null,sessionToken="",rememberedToken="";
  const launched={editor:false,volume:false},loaded={editor:false,volume:false};

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
  function enableDirectTabs(){makeDirectTab(editorTab);makeDirectTab(volumeTab)}
  function inherited(d,token){return {dmSongPublisher:{token:token||TOKEN_SENTINEL,repo:d.repo||"ld1kanae/ld1kanae.github.io",branch:d.branch||"main",id:d.id,sessionId:d.sessionId,at:d.at||Date.now()}}}
  function timingUrl(){return `song-sync-editor.html?song=${encodeURIComponent(session.id)}&session=${encodeURIComponent(session.sessionId)}&embedded=1&v=20260829-timingfix2`}
  function loadTool(which){
    if(!session?.id||!session?.sessionId)return false;
    const view=views[which];if(!view)return false;
    try{view.contentWindow.name=JSON.stringify(inherited(session,sessionToken||rememberedToken))}catch{}
    view.src=which==="editor"
      ?timingUrl()
      :`song-volume-editor.html?song=${encodeURIComponent(session.id)}&session=${encodeURIComponent(session.sessionId)}&embedded=1&v=20260829-lazy1`;
    loaded[which]=true;launched[which]=true;return true;
  }
  function openTool(which){
    if(session?.id&&session?.sessionId){if(!loaded[which])loadTool(which)}
    else if(!launched[which]){views[which].src=launcher(which==="editor"?"timing":"volume");launched[which]=true}
    activate(which);
  }

  enableDirectTabs();
  editorTab.addEventListener("click",e=>{e.stopImmediatePropagation();openTool("editor")},true);
  volumeTab.addEventListener("click",e=>{e.stopImmediatePropagation();openTool("volume")},true);

  addEventListener("message",async e=>{
    if(e.origin!==location.origin)return;
    const d=e.data;
    if(d?.type==="dm-existing-editor-ready"&&(e.source===editorView.contentWindow||e.source===volumeView.contentWindow)&&d.id&&d.sessionId){
      session=d;sessionToken="";loaded.editor=false;loaded.volume=false;
      if(!rememberedToken)rememberedToken=await readRememberedToken();
      const which=d.tool==="volume"?"volume":"editor";
      loadTool(which);
      for(const tab of [editorTab,volumeTab]){const s=tab.querySelector(".tab-state");if(s)s.textContent="READY"}
      activate(which);return;
    }
    if(d?.type==="dm-song-editor-ready"&&e.source===registerView.contentWindow&&d.id&&d.sessionId){
      session=d;sessionToken=d.token||"";loaded.editor=false;loaded.volume=false;
      if(d.mode==="update"){
        editorView.src="about:blank";volumeView.src="about:blank";launched.editor=false;launched.volume=false;
        queueMicrotask(()=>activate("register"));
      }else{
        /* Replace the publisher's legacy Timing cache key immediately, while
           keeping Volume lazy so no hidden audio assets are loaded. */
        try{editorView.contentWindow.name=JSON.stringify(inherited(session,sessionToken||rememberedToken))}catch{}
        editorView.src=timingUrl();
        volumeView.src="about:blank";launched.volume=false;loaded.editor=true;launched.editor=true;
      }
    }
  });

  globalThis.DruMasterExistingEditor={activate,openTool,get session(){return session}};
})();
