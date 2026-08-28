"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;

  const CREDENTIAL_ID="drumaster-github-pat";

  function tokenInput(){
    try{return frame.contentDocument?.getElementById("token")||null}catch{return null}
  }

  async function preparePasswordManager(){
    const input=tokenInput();
    if(!input)return;
    const doc=input.ownerDocument;

    input.name="password";
    input.autocomplete="current-password";
    input.setAttribute("data-form-type","password");

    if(!doc.getElementById("dmTokenCredentialUser")){
      const user=doc.createElement("input");
      user.id="dmTokenCredentialUser";
      user.type="text";
      user.name="username";
      user.autocomplete="username";
      user.value=CREDENTIAL_ID;
      user.tabIndex=-1;
      user.setAttribute("aria-hidden","true");
      user.style.cssText="position:fixed;left:-10000px;top:-10000px;width:1px;height:1px;opacity:0;pointer-events:none";
      input.parentNode?.insertBefore(user,input);
    }

    const panel=input.closest(".panel");
    if(panel&&!doc.getElementById("dmTokenMemoryNote")){
      const note=doc.createElement("p");
      note.id="dmTokenMemoryNote";
      note.style.cssText="margin:10px 0 0;text-align:center;color:#7f91a4;font-size:9px;line-height:1.55";
      note.textContent="Tokenは対応ブラウザのパスワードマネージャーに保存し、次回以降の自動入力を試みます。GitHubデータやLocalStorageには保存しません。";
      panel.appendChild(note);
    }

    if(input.value||!navigator.credentials?.get||typeof PasswordCredential!=="function")return;
    try{
      const credential=await navigator.credentials.get({password:true,mediation:"optional"});
      const password=credential?.password||"";
      if(/^github_pat_/.test(password)){
        input.value=password;
        input.dispatchEvent(new Event("input",{bubbles:true}));
        input.dispatchEvent(new Event("change",{bubbles:true}));
      }
    }catch(e){
      console.debug("DruMaster token autofill unavailable",e);
    }
  }

  async function storeToken(value){
    const password=String(value||"").trim();
    if(!/^github_pat_/.test(password))return;
    if(!navigator.credentials?.store||typeof PasswordCredential!=="function")return;
    try{
      const credential=new PasswordCredential({
        id:CREDENTIAL_ID,
        name:"DruMaster GitHub PAT",
        password
      });
      await navigator.credentials.store(credential);
    }catch(e){
      console.debug("DruMaster token save unavailable",e);
    }
  }

  frame.addEventListener("load",()=>{void preparePasswordManager()});
  setTimeout(()=>{void preparePasswordManager()},300);

  addEventListener("message",e=>{
    if(e.origin!==location.origin||e.source!==frame.contentWindow)return;
    const d=e.data;
    if(d?.type!=="dm-song-editor-ready"||!d.token)return;
    void storeToken(d.token);
  });
})();
