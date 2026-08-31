"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;

  const CREDENTIAL_ID="drumaster-github-pat";

  function tokenInput(){
    try{return frame.contentDocument?.getElementById("token")||null}catch{return null}
  }

  function applyDruMasterTheme(){
    let doc;try{doc=frame.contentDocument}catch{return}
    if(!doc?.head)return;

    if(!doc.getElementById("dmSongToolTheme")){
      const link=doc.createElement("link");
      link.id="dmSongToolTheme";
      link.rel="stylesheet";
      link.href="css/song-tool-cyan-violet-theme.css?v=20260829-theme3";
      doc.head.appendChild(link);
    }
    if(!doc.getElementById("dmSongToolRangeTheme")){
      const script=doc.createElement("script");
      script.id="dmSongToolRangeTheme";
      script.src="js/song-tool-range-theme.js?v=20260829-range1";
      doc.head.appendChild(script);
    }

    const order=doc.getElementById("order");
    if(order)order.autocomplete="off";

    if(doc.getElementById("dmPublisherDruMasterTheme"))return;
    const style=doc.createElement("style");
    style.id="dmPublisherDruMasterTheme";
    style.textContent=`
      :root{--dm-publisher-cyan:#52dfcf;--dm-publisher-cyan2:#49c7dc;--dm-publisher-blue:#5e9ee8;--dm-publisher-violet:#8875ff;--dm-publisher-violet2:#a36cff}
      .req{color:var(--dm-publisher-cyan)!important}
      input[type=text]:focus,input[type=password]:focus,input[type=number]:focus,select:focus{
        border-color:var(--dm-publisher-cyan)!important;
        box-shadow:0 0 0 1px rgba(82,223,207,.22),0 0 0 3px rgba(136,117,255,.10)!important
      }
      #order,#order:hover,#order:focus{
        background:#080e15!important;
        color:#edf4fb!important
      }
      #order:-webkit-autofill,
      #order:-webkit-autofill:hover,
      #order:-webkit-autofill:focus,
      #order:-webkit-autofill:active{
        -webkit-text-fill-color:#edf4fb!important;
        caret-color:#edf4fb!important;
        -webkit-box-shadow:0 0 0 1000px #080e15 inset!important;
        box-shadow:0 0 0 1000px #080e15 inset!important;
        transition:background-color 999999s ease-out 0s!important
      }
      input[type=file]::file-selector-button{
        border:1px solid rgba(93,183,216,.55)!important;
        border-radius:7px!important;
        background:linear-gradient(115deg,rgba(38,183,190,.22),rgba(104,91,211,.25))!important;
        color:#eafcff!important;
        min-height:30px!important;
        padding:0 12px!important;
        cursor:pointer!important
      }
      input[type=file]::file-selector-button:hover{
        border-color:rgba(105,229,216,.78)!important;
        background:linear-gradient(115deg,rgba(42,206,202,.30),rgba(126,103,238,.34))!important
      }
      .publish button{
        border-color:rgba(100,199,218,.72)!important;
        background:linear-gradient(115deg,rgba(31,165,177,.34) 0%,rgba(72,132,211,.34) 52%,rgba(113,83,218,.38) 100%)!important;
        box-shadow:inset 0 1px 0 rgba(205,249,246,.09),0 0 18px rgba(99,108,228,.08)!important
      }
      .publish button:not(:disabled):hover{
        border-color:rgba(111,231,218,.92)!important;
        background:linear-gradient(115deg,rgba(35,196,194,.42) 0%,rgba(80,145,225,.43) 52%,rgba(132,96,239,.46) 100%)!important
      }
      .progress-bar{background:linear-gradient(90deg,var(--dm-publisher-cyan) 0%,var(--dm-publisher-blue) 52%,var(--dm-publisher-violet) 100%)!important}
      .token-link{
        border-color:rgba(90,186,213,.58)!important;
        background:linear-gradient(115deg,rgba(32,157,170,.22),rgba(101,78,202,.25))!important
      }
      .token-link:hover{
        border-color:rgba(103,226,215,.82)!important;
        background:linear-gradient(115deg,rgba(37,189,187,.31),rgba(126,95,230,.34))!important
      }
      .advanced summary:hover{color:#d9d4ff!important}
    `;
    doc.head.appendChild(style);
  }

  async function preparePasswordManager(){
    applyDruMasterTheme();
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
