"use strict";

// The drum-source manifest is tiny and versioned with the app. Keep an embedded copy so
// a transient GitHub Pages/cache failure for the JSON file can never block the START button.
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

  async function fetchDrumChunk(input,init,url){
    let lastError=null;
    for(let attempt=0;attempt<3;attempt++){
      const controller=new AbortController();
      const timer=setTimeout(()=>controller.abort(),6000);
      try{
        const response=await nativeFetch(input,{...(init||{}),cache:"no-store",signal:controller.signal});
        clearTimeout(timer);
        if(response.ok)return response;
        lastError=new Error(`HTTP ${response.status}`);
        if(response.status!==429&&response.status<500)return response;
      }catch(error){
        clearTimeout(timer);
        lastError=error;
      }
      if(attempt<2)await wait(250*(attempt+1));
    }
    throw lastError||new Error(`Failed to fetch ${url}`);
  }

  window.fetch=async function(input,init){
    const url=typeof input==="string"?input:(input&&input.url)||"";
    if(/(?:^|\/)assets\/drumsound-manifest\.json(?:[?#].*)?$/.test(url)){
      // Do not depend on a separate Pages request for this static metadata.
      return new Response(JSON.stringify(embeddedDrumManifest),{
        status:200,
        headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"}
      });
    }
    if(/(?:^|\/)assets\/drumsound-v2-\d{3}(?:[?#].*)?$/.test(url)){
      return fetchDrumChunk(input,init,url);
    }
    return nativeFetch(input,init);
  };
})();
