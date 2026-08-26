"use strict";

(()=>{
  const songs={
    nanairo:{
      id:"nanairo",title:"なないろ",artist:"BUMP OF CHICKEN",duration:263.05,
      chart:{pixelsPerQuarter:80},
      playback:{stemOffsetSec:0},
      midi:"songs/nanairo/chart.mid",midiGzip:"songs/nanairo/chart.mid.gz",
      stems:{
        base:{path:"songs/nanairo/offvocal.mp3",bytes:6314638,sha256:"4dd43973168efdc730112bec742e3dced51024080d222dbd43f7065ef713a8b1"},
        vocals:{path:"songs/nanairo/vocals.mp3",bytes:6314638,sha256:"73e6ba324ffa608fb74b7a33206c9189e2b885a43c48779bd4b0094729e75c2f"},
        drums:{path:"songs/nanairo/drums.mp3",bytes:6314638,sha256:"6d50cf5fe21ab4fb73588d3cda1c8bb8ace2ae5234db1eaaca571374ff8e9eeb"}
      }
    },
    ray:{
      id:"ray",title:"Ray",artist:"BUMP OF CHICKEN",duration:305.544,
      chart:{pixelsPerQuarter:60,desktopPixelsPerQuarter:80},
      playback:{stemOffsetSec:.0215},
      midi:"songs/ray/chart.mid",midiGzip:"songs/ray/chart.mid.gz",
      mix:{base:.70,vocals:.60,drums:.70},
      stems:{
        base:{path:"songs/ray/offvocal.mp3",bytes:12221760,sha256:"b0f8b2b8930e054f7edfc71922a03b119771e54fc14f5dec6f4d94e6ff8e236c"},
        vocals:{path:"songs/ray/vocals.mp3",bytes:8735901,sha256:"b9225fa4869c56bd3a4009db88d9e86002b560083fb869f6183de29442dfde5d"},
        drums:{path:"songs/ray/drums.mp3",bytes:9806929,sha256:"526328461d8f5f4aea6d52bf2c5954d1b9a0d619da90d4348b95bb44fbaec960"}
      }
    }
  };

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
    if(url.endsWith("songs/ray/chart.mid"))return songs.ray;
    return null;
  }
  async function loadMidi(song){
    if(midiCache.has(song.id))return (await midiCache.get(song.id)).slice(0);
    const task=(async()=>{
      const r=await nativeFetch(song.midiGzip,{cache:"force-cache"});
      if(!r.ok)throw Error(`${song.title} MIDIを取得できません（HTTP ${r.status}）`);
      if(typeof DecompressionStream!=="function")throw Error("このブラウザではMIDI展開機能を利用できません");
      const stream=r.body.pipeThrough(new DecompressionStream("gzip"));
      const ab=await new Response(stream).arrayBuffer();
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
        const r=await nativeFetch(song.midiGzip,{method:"HEAD",cache:"no-store"});
        return new Response(null,{status:r.status,statusText:r.statusText,headers:{"Content-Type":"audio/midi"}});
      }
      const ab=await loadMidi(song);
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
      select.appendChild(opt);
    }
    select.addEventListener("change",()=>{
      const url=new URL(location.href);
      url.searchParams.set("song",select.value);
      location.href=url.toString();
    });
  }
  applyLabels();

  /* Asset availability is validated by the actual pre-game MIDI/stem loads.
     Do not launch separate background HEAD requests: on slower phones those
     requests can outlive setup and compete with real-time audio playback. */

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