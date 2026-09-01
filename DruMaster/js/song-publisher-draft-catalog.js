"use strict";

(()=>{
  if(globalThis.DruMasterDraftCatalog)return;

  const REPO="ld1kanae/ld1kanae.github.io",ROOT="DruMaster/songs",BRANCH="main";
  const nativeFetch=globalThis.fetch.bind(globalThis);
  let cache={at:0,value:{}};

  async function apiGet(path){
    const r=await nativeFetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}`,{
      headers:{"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},cache:"no-store"
    });
    if(r.status===404)return null;
    if(!r.ok)throw Error(`GitHub API ${r.status}: ${path}`);
    return r.json();
  }
  async function publicJson(path){
    const r=await nativeFetch(`${path}${path.includes("?")?"&":"?"}t=${Date.now()}`,{cache:"no-store"});
    if(r.status===404)return null;
    if(!r.ok)throw Error(`取得失敗: ${path} (${r.status})`);
    return r.json();
  }
  async function discover(registry={}){
    if(Date.now()-cache.at<30000)return {...cache.value};
    const found={};
    try{
      const list=await apiGet(ROOT);
      const dirs=Array.isArray(list)?list.filter(x=>x?.type==="dir"):[];
      await Promise.all(dirs.map(async item=>{
        const id=item.name;
        if(!id||registry?.[id])return;
        try{
          const [published,draft]=await Promise.all([
            publicJson(`songs/${id}/song.json`),
            publicJson(`songs/${id}/song-draft.json`)
          ]);
          const song=published||draft,draftOnly=!published&&!!draft;
          if(!song?.id||!song?.title||!song?.artist||!song?.stems)return;
          const hasAudio=Object.values(song.stems||{}).some(stem=>!!stem?.path);
          if(!hasAudio)return;
          /* MIDI is intentionally NOT required here. An audio-only draft must
             remain selectable so chart.mid can be added later from UPDATE. */
          found[id]={...song,midi:song.midi||null,midiGzip:song.midiGzip||null,__draftOnly:draftOnly};
        }catch(e){console.warn("DruMaster draft catalog skip",id,e)}
      }));
    }catch(e){console.warn("DruMaster draft catalog unavailable",e)}
    cache={at:Date.now(),value:found};
    return {...found};
  }

  globalThis.DruMasterDraftCatalog={discover};
})();
