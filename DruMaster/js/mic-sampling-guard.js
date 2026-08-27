"use strict";

(()=>{
  let workletPatched=false;
  function patchWorklet(){
    if(workletPatched)return true;
    try{
      if(typeof ac==="undefined"||!ac?.audioWorklet)return false;
      const worklet=ac.audioWorklet,nativeAdd=worklet.addModule.bind(worklet);
      worklet.addModule=(url,options)=>{
        const text=String(url||"");
        if(text.includes("js/acoustic-cancel-processor.js")){
          const clean=text.split("?")[0];
          return nativeAdd(`${clean}?v=20260827-registerrestore2`,options);
        }
        return nativeAdd(url,options);
      };
      workletPatched=true;
      return true;
    }catch(e){console.warn("DruMaster worklet cache guard unavailable",e);return false}
  }
  const patchTimer=setInterval(()=>{if(patchWorklet())clearInterval(patchTimer)},100);
  setTimeout(()=>{if(patchWorklet())clearInterval(patchTimer)},0);

  const screen=()=>document.querySelector("#micCalibration");
  const noisePane=()=>screen()?.querySelector('[data-fp-step="noise"]');

  /* Environment-noise capture must run for its full 8 seconds. */
  document.addEventListener("click",e=>{
    const b=e.target?.closest?.("#micCalibration #micCalAction");
    if(!b)return;
    const state=screen()?.querySelector("#fpNoiseState")?.textContent||"";
    if(noisePane()?.dataset.state==="active"&&/^収録中/.test(state)){
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  },true);

  function tickNoise(){
    const s=screen(),b=s?.querySelector("#micCalAction"),state=s?.querySelector("#fpNoiseState")?.textContent||"",detail=s?.querySelector("#micCalDetail");
    if(!s||s.classList.contains("hidden")||!b)return;
    if(noisePane()?.dataset.state==="active"&&/^収録中/.test(state)){
      b.disabled=true;
      b.textContent="収録中…";
      b.style.pointerEvents="none";
      b.setAttribute("aria-disabled","true");
      if(detail)detail.textContent="環境ノイズを8秒間取得しています。取得と解析が完了するまで次の工程には進みません。";
    }else{
      b.style.pointerEvents="";
      b.removeAttribute("aria-disabled");
    }
  }
  setInterval(tickNoise,35);
})();
