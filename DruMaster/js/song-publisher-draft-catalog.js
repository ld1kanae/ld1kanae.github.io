"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame||globalThis.__dmDraftCatalogInstalled)return;
  globalThis.__dmDraftCatalogInstalled=true;

  const REPO="ld1kanae/ld1kanae.github.io",ROOT="DruMaster/songs",BRANCH="main";
  const nativeFetch=globalThis.fetch.bind(globalThis);
  let cache={at:0,value:{}};

  function isRegistryRequest(input){
    const url=typeof input==="string"?input:String(input?.url||"");
    if(/api\.github\.com/i.test(url))return false;
    return /(?:^|\/)songs\/registry\.json(?:[?#]|$)/.test(url);
  }
  function decodeContent(value){
    const bin=atob(String(value||"").replace(/\n/g,"")),u=new Uint8Array(bin.length);
    for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);
    return new TextDecoder().decode(u);
  }
  async function apiGet(path){
    const r=await nativeFetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}`,{
      headers:{"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},cache:"no-store"
    });
    if(r.status===404)return null;
    if(!r.ok)throw Error(`GitHub API ${r.status}: ${path}`);
    return r.json();
  }
  async function discover(registry){
    if(Date.now()-cache.at<30000)return {...cache.value};
    const found={};
    try{
      const list=await apiGet(ROOT);
      const dirs=Array.isArray(list)?list.filter(x=>x?.type==="dir"):[];
      await Promise.all(dirs.map(async item=>{
        const id=item.name;
        if(!id||registry?.[id]||id==="nanairo"||id==="ray")return;
        try{
          let meta=await apiGet(`${ROOT}/${id}/song.json`),draftOnly=false;
          if(!meta){meta=await apiGet(`${ROOT}/${id}/song-draft.json`);draftOnly=!!meta}
          if(!meta?.content)return;
          const song=JSON.parse(decodeContent(meta.content));
          if(!song?.id||!song?.title||!song?.artist||!song?.midi||!song?.stems)return;
          found[id]={...song,__draftOnly:draftOnly};
        }catch(e){console.warn("DruMaster draft catalog skip",id,e)}
      }));
    }catch(e){console.warn("DruMaster draft catalog unavailable",e)}
    cache={at:Date.now(),value:found};
    return {...found};
  }

  globalThis.fetch=async(input,init)=>{
    if(!isRegistryRequest(input))return nativeFetch(input,init);
    const response=await nativeFetch(input,init);
    if(!response.ok)return response;
    try{
      const registry=await response.clone().json(),drafts=await discover(registry);
      const headers=new Headers(response.headers);headers.set("content-type","application/json; charset=utf-8");
      return new Response(JSON.stringify({...drafts,...registry}),{status:response.status,statusText:response.statusText,headers});
    }catch(e){console.warn("DruMaster catalog merge failed",e);return response}
  };

  /* update-mode has already performed its first catalog read before this helper
     is loaded. Reload only the registration iframe once so its existing load
     handler rebuilds the catalog through the patched fetch. */
  if(!globalThis.__dmDraftCatalogFrameReloaded){
    globalThis.__dmDraftCatalogFrameReloaded=true;
    setTimeout(()=>{try{frame.contentWindow.location.reload()}catch{}},0);
  }
})();
