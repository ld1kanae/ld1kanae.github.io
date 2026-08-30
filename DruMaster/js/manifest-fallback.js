"use strict";

// Keep the tiny drum manifest embedded so startup does not depend on a separate JSON request.
(function(){
  const embeddedDrumManifest={
    sourceVelocity:100,
    wav:{
      pathPrefix:"assets/drumsound-v2-",
      parts:22,
      digits:3,
      bytes:17243836,
      sha256:"5936599edbefc2485e6dd682784fd275e64e39dc10b7b74968722ddba82853bf",
      sourceSampleRate:44100,
      channels:2,
      bitsPerSample:16
    },
    midi:{
      path:"assets/drumsound.mid",
      bytes:6366,
      sha256:"6fe934d11bf77704d51686ad520dab601f6cf7f46d32d3cb69086c1dc678d5a3"
    }
  };

  const nativeFetch=window.fetch.bind(window);
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));

  async function fetchWithRetry(url,attempts=3,timeoutMs=5000){
    let lastError=null;
    for(let attempt=0;attempt<attempts;attempt++){
      const controller=new AbortController();
      const timer=setTimeout(()=>controller.abort(),timeoutMs);
      try{
        const response=await nativeFetch(url,{cache:"no-store",signal:controller.signal});
        clearTimeout(timer);
        if(response.ok)return response;
        lastError=new Error(`HTTP ${response.status}`);
        if(response.status!==429&&response.status<500)return response;
      }catch(error){
        clearTimeout(timer);
        lastError=error;
      }
      if(attempt+1<attempts)await wait(200*(attempt+1));
    }
    throw lastError||new Error(`Failed to fetch ${url}`);
  }

  window.fetch=async function(input,init){
    const url=typeof input==="string"?input:(input&&input.url)||"";
    if(/(?:^|\/)assets\/drumsound-manifest\.json(?:[?#].*)?$/.test(url)){
      return new Response(JSON.stringify(embeddedDrumManifest),{
        status:200,
        headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"}
      });
    }
    return nativeFetch(input,init);
  };

  // app.js registers startup after scripts have loaded. Register this first so the
  // audio.js drum loader is replaced before init() begins. We intentionally avoid
  // the 22-part source WAV here: the already-exported per-note WAVs are much smaller
  // and make startup independent of any single large/chunk request stalling.
  addEventListener("load",()=>{
    if(typeof loadDrumSource!=="function"||typeof DEFAULT_NOTE==="undefined")return;
    loadDrumSource=async function(manifest){
      const state=document.querySelector("#loadState");
      const entries=[...new Set(Object.values(DEFAULT_NOTE).map(Number))];
      const loaded=new Map();
      let next=0,done=0;
      if(state)state.textContent=`ゲーム内ドラム音源を読み込み中… 0/${entries.length}`;

      const worker=async()=>{
        while(true){
          const i=next++;
          if(i>=entries.length)return;
          const note=entries[i];
          const response=await fetchWithRetry(`assets/drums/${note}.wav?v=20260830-individual1`);
          if(!response.ok)throw Error(`ゲーム内ドラム音源を取得できません（MIDI ${note} / HTTP ${response.status}）`);
          const encoded=await response.arrayBuffer();
          loaded.set(note,await ac.decodeAudioData(encoded.slice(0)));
          done++;
          if(state)state.textContent=`ゲーム内ドラム音源を読み込み中… ${done}/${entries.length}`;
        }
      };

      await Promise.all(Array.from({length:Math.min(4,entries.length)},worker));
      drumSampleBuffers={};
      for(const [note,buffer] of loaded)drumSampleBuffers[String(note)]=buffer;
      drumSourceVelocity=manifest?.sourceVelocity||100;
      drumBuffer=null;
      drumRegions={};
      if(state)state.textContent="ゲーム内ドラム音源を準備しました";
    };
  },{once:true});
})();
