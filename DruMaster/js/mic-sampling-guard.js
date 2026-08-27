"use strict";

(()=>{
  const MIN_SAMPLE_SEC=10;

  /* performance-mode-v5 was already deployed with a fixed worklet query.
     Rewrite only this module request so the updated processor is fetched
     immediately instead of waiting for the previous browser/CDN cache entry. */
  try{
    if(typeof ac!=="undefined"&&ac?.audioWorklet){
      const worklet=ac.audioWorklet,nativeAdd=worklet.addModule.bind(worklet);
      worklet.addModule=(url,options)=>{
        const text=String(url||"");
        if(text.includes("js/acoustic-cancel-processor.js")){
          const clean=text.split("?")[0];
          return nativeAdd(`${clean}?v=20260827-min10`,options);
        }
        return nativeAdd(url,options);
      };
    }
  }catch(e){console.warn("DruMaster worklet cache guard unavailable",e)}

  let samplingStartedAt=0,lastPane=null;
  function tick(){
    const screen=document.querySelector("#micCalibration");
    if(!screen||screen.classList.contains("hidden")){samplingStartedAt=0;lastPane=null;return}
    const pane=screen.querySelector('[data-fp-step="sample"]');
    const active=pane?.dataset.state==="active";
    if(!active){samplingStartedAt=0;lastPane=pane||null;return}
    if(!samplingStartedAt||lastPane!==pane){samplingStartedAt=performance.now();lastPane=pane}

    const elapsed=Math.min(MIN_SAMPLE_SEC,(performance.now()-samplingStartedAt)/1000);
    const state=screen.querySelector("#fpSampleState"),detail=screen.querySelector("#micCalDetail");
    if(elapsed<MIN_SAMPLE_SEC){
      if(state)state.textContent=`収集中 ${elapsed.toFixed(1)} / ${MIN_SAMPLE_SEC.toFixed(1)}秒`;
      if(detail)detail.textContent=`パッド音をサンプリングしています。最低${MIN_SAMPLE_SEC}秒間は終了しません。強弱を混ぜて何度か叩いてください。`;
    }else if(state&&/^収集中/.test(state.textContent)){
      state.textContent="サンプルを解析中…";
      if(detail)detail.textContent="10秒分の候補音を解析しています。必要な打音数が足りない場合は、そのまま叩き続けてください。";
    }
  }

  setInterval(tick,80);
})();
