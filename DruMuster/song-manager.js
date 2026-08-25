"use strict";

(()=>{
  const songs={
    nanairo:{
      id:"nanairo",title:"なないろ",artist:"BUMP OF CHICKEN",duration:263.05,
      midi:"songs/nanairo/chart.mid",midiSha256:"7b8face996ec02aa1b525128d797ba163d6cd81d360b17ae393c1d36fd589819",
      stems:{
        base:{path:"songs/nanairo/offvocal.mp3",bytes:6314638,sha256:"4dd43973168efdc730112bec742e3dced51024080d222dbd43f7065ef713a8b1"},
        vocals:{path:"songs/nanairo/vocals.mp3",bytes:6314638,sha256:"73e6ba324ffa608fb74b7a33206c9189e2b885a43c48779bd4b0094729e75c2f"},
        drums:{path:"songs/nanairo/drums.mp3",bytes:6314638,sha256:"6d50cf5fe21ab4fb73588d3cda1c8bb8ace2ae5234db1eaaca571374ff8e9eeb"}
      }
    },
    ray:{
      id:"ray",title:"Ray",artist:"BUMP OF CHICKEN",duration:305.544,
      midi:"songs/ray/chart.mid",midiSha256:"227a68a185430e9a0e15b70a64b7ddca35c2ee29353d8ecb3dee24a6759b8891",
      stems:{
        base:{path:"songs/ray/offvocal.mp3",bytes:12221760,sha256:"b0f8b2b8930e054f7edfc71922a03b119771e54fc14f5dec6f4d94e6ff8e236c"},
        vocals:{path:"songs/ray/vocals.mp3",bytes:8735901,sha256:"b9225fa4869c56bd3a4009db88d9e86002b560083fb869f6183de29442dfde5d"},
        drums:{path:"songs/ray/drums.mp3",bytes:9806929,sha256:"526328461d8f5f4aea6d52bf2c5954d1b9a0d619da90d4348b95bb44fbaec960"}
      }
    }
  };

  const params=new URLSearchParams(location.search),requested=params.get("song"),current=songs[requested]||songs.nanairo;
  const nativeFetch=globalThis.fetch.bind(globalThis);
  globalThis.DruMasterSongs={songs,current,nativeFetch};

  function midiRequestId(url){
    if(typeof url!=="string")return null;
    const clean=url.replace(/^\.\//,"").split(/[?#]/)[0];
    if(clean.endsWith("songs/nanairo/chart.mid"))return current.id;
    if(clean.endsWith("songs/ray/chart.mid"))return "ray";
    return null;
  }

  /* Both app.js and the shared chart timing adapter keep using fetch(). Supply
     the newly uploaded charts from the same path so production timing/rendering cannot diverge. */
  globalThis.fetch=async function(input,init){
    const url=typeof input==="string"?input:input?.url,
          id=midiRequestId(url),embedded=globalThis.DruMasterEmbeddedMidi;
    if(id&&embedded?.has?.(id)){
      if(String(init?.method||"GET").toUpperCase()==="HEAD")return new Response(null,{status:200,headers:{"Content-Type":"audio/midi"}});
      const ab=await embedded.get(id);
      return new Response(ab,{status:200,headers:{"Content-Type":"audio/midi","Cache-Control":"no-store"}});
    }
    return nativeFetch(input,init);
  };

  function applyLabels(){
    document.querySelector(".song-card h1")?.replaceChildren(document.createTextNode(current.title));
    document.querySelector(".song-card p")?.replaceChildren(document.createTextNode(current.artist));
    document.querySelector(".song-hud b")?.replaceChildren(document.createTextNode(current.title));
    document.querySelector(".song-hud small")?.replaceChildren(document.createTextNode(current.artist));
  }

  const select=document.querySelector("#songSelect");
  if(select){
    select.replaceChildren();
    for(const song of Object.values(songs)){
      const opt=document.createElement("option");
      opt.value=song.id;
      opt.textContent=`${song.title} — ${song.artist}`;
      opt.selected=song.id===current.id;
      if(song.id==="ray")opt.disabled=true;
      select.appendChild(opt);
    }
    select.addEventListener("change",()=>{
      const url=new URL(location.href);
      url.searchParams.set("song",select.value);
      location.href=url.toString();
    });
  }
  applyLabels();

  async function assetExists(path){
    try{
      const r=await nativeFetch(path,{method:"HEAD",cache:"no-store"});
      return r.ok;
    }catch{return false}
  }
  async function unlockRayWhenReady(){
    if(!select)return;
    const ray=songs.ray;
    const ready=(await Promise.all([ray.stems.base.path,ray.stems.vocals.path,ray.stems.drums.path].map(assetExists))).every(Boolean);
    const opt=[...select.options].find(o=>o.value==="ray");
    if(opt){
      opt.disabled=!ready;
      opt.textContent=ready?`${ray.title} — ${ray.artist}`:`${ray.title} — ${ray.artist}（audio pending）`;
    }
  }
  unlockRayWhenReady();

  /* Chart notes end before the mastered audio on both songs. The result screen
     should appear after the audio tail, not after the last drum note. */
  const start=document.querySelector("#start");
  if(start){
    const syncDuration=()=>{
      if(start.disabled)return;
      try{duration=current.duration}catch{}
    };
    new MutationObserver(syncDuration).observe(start,{attributes:true,attributeFilter:["disabled"]});
    setTimeout(syncDuration,0);
  }
})();
