"use strict";

(()=>{
  function loadRegistry(){
    try{
      const x=new XMLHttpRequest();
      x.open("GET",`songs/registry.json?t=${Date.now()}`,false);
      x.send();
      if(x.status>=200&&x.status<300){
        const v=JSON.parse(x.responseText||"{}");
        if(v&&typeof v==="object")return v;
      }
    }catch(e){console.warn("Song registry load failed",e)}
    return {};
  }
  if(!document.querySelector('link[data-song-source-mode]')){
    const l=document.createElement("link");
    l.rel="stylesheet";l.href="css/song-source-mode.css?v=20260828-fullmix1";l.dataset.songSourceMode="1";
    document.head.appendChild(l);
  }

  const builtInSongs={
    nanairo:{
      id:"nanairo",title:"なないろ",artist:"BUMP OF CHICKEN",duration:263.05,bpm:125,
      chart:{pixelsPerQuarter:80},
      playback:{stemOffsetSec:0,midiOffsetSec:0},
      midi:"songs/nanairo/chart.mid",midiGzip:"songs/nanairo/chart.mid.gz?v=20260826-midi2",
      stems:{
        base:{path:"songs/nanairo/offvocal.mp3",bytes:6314638,sha256:"4dd43973168efdc730112bec742e3dced51024080d222dbd43f7065ef713a8b1"},
        vocals:{path:"songs/nanairo/vocals.mp3",bytes:6314638,sha256:"73e6ba324ffa608fb74b7a33206c9189e2b885a43c48779bd4b0094729e75c2f"},
        drums:{path:"songs/nanairo/drums.mp3",bytes:6314638,sha256:"6d50cf5fe21ab4fb73588d3cda1c8bb8ace2ae5234db1eaaca571374ff8e9eeb"}
      }
    },
    ray:{
      id:"ray",title:"Ray",artist:"BUMP OF CHICKEN",duration:305.544,bpm:132,
      chart:{pixelsPerQuarter:75,desktopPixelsPerQuarter:100},
      playback:{stemOffsetSec:0.002,midiOffsetSec:0},
      midi:"songs/ray/chart.mid",midiGzip:"songs/ray/chart.mid.gz?v=20260826-midi2",
      mix:{base:.70,vocals:.60,drums:.70},
      stems:{
        base:{path:"songs/ray/offvocal.mp3",bytes:12221760,sha256:"b0f8b2b8930e054f7edfc71922a03b119771e54fc14f5dec6f4d94e6ff8e236c"},
        vocals:{path:"songs/ray/vocals.mp3",bytes:8735901,sha256:"b9225fa4869c56bd3a4009db88d9e86002b560083fb869f6183de29442dfde5d"},
        drums:{path:"songs/ray/drums.mp3",bytes:9806929,sha256:"526328461d8f5f4aea6d52bf2c5954d1b9a0d619da90d4348b95bb44fbaec960"}
      }
    }
  };

  const songs={...builtInSongs,...loadRegistry()};
  const params=new URLSearchParams(location.search),requested=params.get("song"),current=songs[requested]||songs.nanairo;
  const nativeFetch=globalThis.fetch.bind(globalThis),midiCache=new Map();
  globalThis.DruMasterSongs={songs,current,nativeFetch};

  function cleanUrl(input){
    const url=typeof input==="string"?input:input?.url;
    return typeof url==="string"?url.replace(/^\.\//,"").split(/[?#]/)[0]:"";
  }
  function requestedMidiSong(input){
    const url=cleanUrl(input);
    if(url.endsWith("songs/nanairo/chart.mid"))return current;
    for(const song of Object.values(songs))if(cleanUrl(song.midi)===url)return song;
    return null;
  }
  async function loadMidi(song){
    if(midiCache.has(song.id))return (await midiCache.get(song.id)).slice(0);
    const task=(async()=>{
      if(song.midiGzip&&typeof DecompressionStream==="function"){
        const r=await nativeFetch(song.midiGzip,{cache:"force-cache"});
        if(r.ok){
          const ab=await new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
          if(ab.byteLength>=14&&String.fromCharCode(...new Uint8Array(ab.slice(0,4)))==="MThd")return ab;
        }
      }
      const r=await nativeFetch(song.midi,{cache:"force-cache"});
      if(!r.ok)throw Error(`${song.title} MIDIを取得できません（HTTP ${r.status}）`);
      const ab=await r.arrayBuffer();
      if(ab.byteLength<14||String.fromCharCode(...new Uint8Array(ab.slice(0,4)))!=="MThd")throw Error(`${song.title} MIDIが破損しています`);
      return ab;
    })();
    midiCache.set(song.id,task);
    try{return (await task).slice(0)}catch(e){midiCache.delete(song.id);throw e}
  }

  globalThis.fetch=async function(input,init){
    const song=requestedMidiSong(input);
    if(song){
      const method=String(init?.method||"GET").toUpperCase();
      if(method==="HEAD"){
        const target=song.midiGzip||song.midi;
        const r=await nativeFetch(target,{method:"HEAD",cache:"no-store"});
        return new Response(null,{status:r.status,statusText:r.statusText,headers:{"Content-Type":"audio/midi"}});
      }
      const ab=await loadMidi(song);
      return new Response(ab,{status:200,headers:{"Content-Type":"audio/midi","Cache-Control":"no-store"}});
    }
    return nativeFetch(input,init);
  };

  function isFullMixOnly(song){
    if(song?.fullMixOnly===true)return true;
    const s=song?.stems||{};
    return !!s.fullmix&&!(s.base&&s.vocals&&s.drums);
  }
  function applySourceAvailability(song=globalThis.DruMasterSongs?.current||current){
    const locked=isFullMixOnly(song);
    for(const id of ["vocalToggle","guideToggle"]){
      const input=document.getElementById(id);
      if(!input)continue;
      const row=input.closest(".option");
      input.disabled=locked;
      if(locked)input.checked=true;
      row?.classList.toggle("source-locked",locked);
      row?.setAttribute("aria-disabled",locked?"true":"false");
      const value=row?.querySelector("b");
      if(locked&&value)value.textContent="ON";
    }
    document.documentElement.classList.toggle("dm-fullmix-only",locked);
  }

  function bpmText(){
    const tempo=document.querySelector("#tempo"),percent=Number(tempo?.value||100),base=Number(current.bpm)||0;
    return `♪＝${Math.round(base*(Number.isFinite(percent)?percent/100:1))}`;
  }
  function ensureSetupBpm(){
    const card=document.querySelector(".song-card");
    if(!card)return null;
    let node=card.querySelector(".setup-bpm");
    if(!node){node=document.createElement("span");node.className="setup-bpm";card.appendChild(node)}
    return node;
  }
  function positionSetupBpm(){
    const card=document.querySelector(".song-card"),title=card?.querySelector("h1"),artist=card?.querySelector("p"),node=card?.querySelector(".setup-bpm");
    if(!card||!title||!artist||!node)return;
    node.style.top=`${(title.offsetTop+artist.offsetTop+artist.offsetHeight)/2}px`;
  }
  function syncBpmLabels(){
    const hud=document.querySelector(".song-hud");
    if(hud){
      let node=hud.querySelector(".hud-bpm");
      if(!node){node=document.createElement("span");node.className="hud-bpm";hud.appendChild(node)}
      node.textContent=bpmText();
    }
    const setupBpm=ensureSetupBpm();
    if(setupBpm)setupBpm.textContent=bpmText();
    requestAnimationFrame(positionSetupBpm);
  }

  function applyLabels(){
    document.querySelector(".song-card h1")?.replaceChildren(document.createTextNode(current.title));
    document.querySelector(".song-card p")?.replaceChildren(document.createTextNode(current.artist));
    document.querySelector(".song-hud b")?.replaceChildren(document.createTextNode(current.title));
    document.querySelector(".song-hud small")?.replaceChildren(document.createTextNode(current.artist));
    document.querySelector(".result h2")?.replaceChildren(document.createTextNode(current.title));
    syncBpmLabels();
  }

  const select=document.querySelector("#songSelect");
  if(select){
    select.replaceChildren();
    const rank=s=>Number.isFinite(Number(s.order))?Number(s.order):999;
    const ordered=Object.values(songs).sort((a,b)=>rank(a)-rank(b));
    for(const song of ordered){
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
  document.querySelector("#tempo")?.addEventListener("input",syncBpmLabels);
  addEventListener("resize",()=>requestAnimationFrame(positionSetupBpm));
  applyLabels();
  applySourceAvailability(current);

  const start=document.querySelector("#start");
  if(start){
    const syncDuration=()=>{
      if(start.disabled)return;
      try{duration=current.duration}catch{}
      applySourceAvailability(globalThis.DruMasterSongs?.current||current);
    };
    new MutationObserver(syncDuration).observe(start,{attributes:true,attributeFilter:["disabled"]});
    setTimeout(syncDuration,0);
  }

  addEventListener("DOMContentLoaded",()=>{
    const baseCurrent=globalThis.current;
    if(typeof baseCurrent!=="function"||baseCurrent.__dmSongOffsetWrapped)return;
    const wrapped=function(){
      const activeSong=globalThis.DruMasterSongs?.current||current;
      const offset=Number(activeSong.playback?.midiOffsetSec)||0;
      return baseCurrent()-offset;
    };
    wrapped.__dmSongOffsetWrapped=true;
    globalThis.current=wrapped;
  },{once:true});

  globalThis.DruMasterSongSource={
    isFullMixOnly:(song=globalThis.DruMasterSongs?.current||current)=>isFullMixOnly(song),
    applySourceAvailability
  };
})();