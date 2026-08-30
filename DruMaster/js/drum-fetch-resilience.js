"use strict";
(()=>{
  const originalFetchJoined=globalThis.fetchJoined;
  if(typeof originalFetchJoined!=="function")return;

  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  async function fetchPart(path,attempt=0){
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),6000);
    try{
      const sep=path.includes("?")?"&":"?";
      const url=attempt?`${path}${sep}retry=${Date.now()}-${attempt}`:path;
      const r=await fetch(url,{cache:"no-store",signal:controller.signal});
      if(!r.ok)throw Error(`HTTP ${r.status}`);
      return await r.arrayBuffer();
    }catch(e){
      if(attempt<2){
        await sleep(250*(attempt+1));
        return fetchPart(path,attempt+1);
      }
      const reason=e?.name==="AbortError"?"タイムアウト":(e?.message||"通信エラー");
      throw Error(`ゲーム内ドラム音源を取得できません（${reason}）`);
    }finally{
      clearTimeout(timer);
    }
  }

  globalThis.fetchJoined=async function(spec,label){
    if(label!=="ゲーム内ドラム")return originalFetchJoined(spec,label);
    const paths=Array.isArray(spec.paths)?spec.paths:(spec.parts?Array.from({length:spec.parts},(_,i)=>`${spec.pathPrefix}${String(i).padStart(spec.digits||3,"0")}`):[]);
    if(!paths.length)throw Error("ゲーム内ドラム音源の分割ファイル設定がありません");
    const parts=new Array(paths.length);
    let next=0,done=0;
    const worker=async()=>{
      while(true){
        const i=next++;
        if(i>=paths.length)return;
        parts[i]=await fetchPart(paths[i]);
        done++;
        const el=document.querySelector("#loadState");
        if(el)el.textContent=`ゲーム内ドラム音源を読み込み中… ${done}/${paths.length}`;
      }
    };
    await Promise.all(Array.from({length:Math.min(3,paths.length)},worker));
    const size=parts.reduce((n,b)=>n+b.byteLength,0),out=new Uint8Array(size);
    let at=0;
    for(const b of parts){out.set(new Uint8Array(b),at);at+=b.byteLength}
    if(spec.bytes&&out.byteLength!==spec.bytes)throw Error(`ゲーム内ドラム音源が不完全です（${out.byteLength.toLocaleString()} / ${spec.bytes.toLocaleString()} bytes）`);
    return out.buffer;
  };
})();
