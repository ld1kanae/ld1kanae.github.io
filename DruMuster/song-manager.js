"use strict";

(()=>{
  const songs={
    nanairo:{
      id:"nanairo",title:"なないろ",artist:"BUMP OF CHICKEN",duration:263.05,
      midi:"songs/nanairo/chart.mid",
      stems:{
        base:{path:"songs/nanairo/offvocal.mp3",bytes:6314638,sha256:"4dd43973168efdc730112bec742e3dced51024080d222dbd43f7065ef713a8b1"},
        vocals:{path:"songs/nanairo/vocals.mp3",bytes:6314638,sha256:"73e6ba324ffa608fb74b7a33206c9189e2b885a43c48779bd4b0094729e75c2f"},
        drums:{path:"songs/nanairo/drums.mp3",bytes:6314638,sha256:"6d50cf5fe21ab4fb73588d3cda1c8bb8ace2ae5234db1eaaca571374ff8e9eeb"}
      }
    },
    ray:{
      id:"ray",title:"Ray",artist:"BUMP OF CHICKEN",duration:305.544,
      midi:"songs/ray/chart.mid",
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

  globalThis.fetch=function(input,init){
    const url=typeof input==="string"?input:input?.url;
    if(current.id!=="nanairo"&&typeof url==="string"&&url.replace(/^\.\//,"").split(/[?#]/)[0].endsWith("songs/nanairo/chart.mid")){
      return nativeFetch(current.midi,init);
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
  async function validateSelectedSong(){
    if(!select)return;
    const s=current;
    const ready=(await Promise.all([s.midi,s.stems.base.path,s.stems.vocals.path,s.stems.drums.path].map(assetExists))).every(Boolean);
    if(!ready){
      const opt=[...select.options].find(o=>o.value===s.id);
      if(opt)opt.textContent=`${s.title} — ${s.artist}（assets pending）`;
    }
  }
  validateSelectedSong();

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
