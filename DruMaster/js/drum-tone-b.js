"use strict";

(()=>{
  const baseStartDrumVoice=startDrumVoice;
  const toneKits={A:null,B:null};
  let bLoadPromise=null;

  function captureA(){
    if(!toneKits.A&&drumSampleBuffers&&Object.keys(drumSampleBuffers).length){
      toneKits.A={buffers:drumSampleBuffers,sourceVelocity:drumSourceVelocity};
    }
    return toneKits.A;
  }

  function songUsesB(song){
    const config=song?.midiDrumMix;
    return !!config?.individual&&["cymbal","hihatRide","snareTom","kick","other"].some(group=>config.tone?.[group]==="B");
  }

  function toneForType(type){
    const config=globalThis.DruMasterSongs?.current?.midiDrumMix;
    if(!config?.individual)return "A";
    return config.tone?.[midiDrumGroup(type)]==="B"?"B":"A";
  }

  async function ensureB(){
    captureA();
    if(toneKits.B)return toneKits.B;
    if(bLoadPromise)return bLoadPromise;
    bLoadPromise=(async()=>{
      const manifest=await fetch("assets/drumsoundB-manifest.json",{cache:"no-store"}).then(r=>{
        if(!r.ok)throw Error(`Bセットドラム音源設定を取得できません（HTTP ${r.status}）`);
        return r.json();
      });
      const savedBuffers=drumSampleBuffers,
            savedVelocity=drumSourceVelocity,
            savedRegions=drumRegions,
            savedBuffer=drumBuffer;
      try{
        await loadDrumSource(manifest);
        toneKits.B={buffers:drumSampleBuffers,sourceVelocity:drumSourceVelocity};
      }finally{
        drumSampleBuffers=savedBuffers;
        drumSourceVelocity=savedVelocity;
        drumRegions=savedRegions;
        drumBuffer=savedBuffer;
      }
      return toneKits.B;
    })().catch(e=>{bLoadPromise=null;throw e});
    return bLoadPromise;
  }

  startDrumVoice=function(type,v=.75,when){
    captureA();
    const tone=toneForType(type),kit=tone==="B"?toneKits.B:toneKits.A;
    if(!kit)return baseStartDrumVoice(type,v,when);
    const savedBuffers=drumSampleBuffers,savedVelocity=drumSourceVelocity;
    drumSampleBuffers=kit.buffers;
    drumSourceVelocity=kit.sourceVelocity;
    try{return baseStartDrumVoice(type,v,when)}
    finally{
      drumSampleBuffers=savedBuffers;
      drumSourceVelocity=savedVelocity;
    }
  };

  const startButton=$("#start"),baseStartHandler=startButton?.onclick;
  if(startButton&&baseStartHandler){
    startButton.onclick=async function(e){
      captureA();
      const scoreMode=document.querySelector("#performanceModeSelect")?.value==="score",
            songs=globalThis.DruMasterSongs?.songs||{},
            needsB=scoreMode?Object.values(songs).some(songUsesB):songUsesB(globalThis.DruMasterSongs?.current);
      if(needsB&&!toneKits.B){
        const state=$("#loadState");
        startButton.disabled=true;
        if(state)state.textContent="Bセットドラム音源を読み込み中…";
        try{await ensureB()}
        catch(err){
          console.error(err);
          if(state)state.textContent=err.message||"Bセットドラム音源の読み込みに失敗しました";
          startButton.disabled=false;
          return;
        }
      }
      return baseStartHandler.call(this,e);
    };
  }

  globalThis.DruMasterDrumTone={
    ensureB,
    toneForType,
    songUsesB,
    get loadedB(){return !!toneKits.B}
  };
})();
