"use strict";

(()=>{
  const baseStartDrumVoice=startDrumVoice;
  const baseStartGame=startGame;
  const toneKits={A:null,B:null};
  let bLoadPromise=null;

  function captureA(){
    if(!toneKits.A&&drumSampleBuffers&&Object.keys(drumSampleBuffers).length){
      toneKits.A={buffers:drumSampleBuffers,sourceVelocity:drumSourceVelocity};
    }
    return toneKits.A;
  }

  function toneForType(type){
    const config=globalThis.DruMasterSongs?.current?.midiDrumMix;
    if(!config?.individual)return "A";
    return config.tone?.[midiDrumGroup(type)]==="B"?"B":"A";
  }

  function needsB(){
    const config=globalThis.DruMasterSongs?.current?.midiDrumMix;
    return !!config?.individual&&["cymbal","hihatRide","snareTom","kick","other"].some(group=>config.tone?.[group]==="B");
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

  startGame=async function(...args){
    captureA();
    if(needsB()){
      const state=$("#loadState");
      if(state)state.textContent="Bセットドラム音源を読み込み中…";
      try{await ensureB()}
      catch(e){
        console.error(e);
        if(state)state.textContent=e.message||"Bセットドラム音源の読み込みに失敗しました";
        const start=$("#start");
        if(start)start.disabled=false;
        return;
      }
    }
    return baseStartGame(...args);
  };

  const startButton=$("#start");
  if(startButton)startButton.onclick=startGame;

  globalThis.DruMasterDrumTone={
    ensureB,
    toneForType,
    get loadedB(){return !!toneKits.B}
  };
})();
