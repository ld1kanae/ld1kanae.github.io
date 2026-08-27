"use strict";

(()=>{
  const FIRST_STRIKE_WAIT_SEC=10;
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
          return nativeAdd(`${clean}?v=20260827-firststrike1`,options);
        }
        return nativeAdd(url,options);
      };
      workletPatched=true;
      return true;
    }catch(e){console.warn("DruMaster worklet cache guard unavailable",e);return false}
  }

  const patchTimer=setInterval(()=>{if(patchWorklet())clearInterval(patchTimer)},100);
  setTimeout(()=>{if(patchWorklet())clearInterval(patchTimer)},0);

  let sampleActive=false,firstWaitStartedAt=0,firstStrikeSeen=false;
  const screen=()=>document.querySelector("#micCalibration");
  const noisePane=()=>screen()?.querySelector('[data-fp-step="noise"]');
  const samplePane=()=>screen()?.querySelector('[data-fp-step="sample"]');
  const action=()=>screen()?.querySelector("#micCalAction");
  const sampleState=()=>screen()?.querySelector("#fpSampleState");
  const detail=()=>screen()?.querySelector("#micCalDetail");

  /* The 8-second environment capture must finish in full. Block the older
     early-completion path even if performance-mode-v5 briefly exposes it. */
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
    const s=screen(),b=action(),state=s?.querySelector("#fpNoiseState")?.textContent||"",d=detail();
    if(!s||s.classList.contains("hidden")||!b)return;
    if(noisePane()?.dataset.state==="active"&&/^収録中/.test(state)){
      b.disabled=true;
      b.textContent="収録中…";
      b.style.pointerEvents="none";
      b.setAttribute("aria-disabled","true");
      if(d)d.textContent="環境ノイズを8秒間取得しています。取得と解析が完了するまで次の工程には進みません。";
    }else{
      b.style.pointerEvents="";
      b.removeAttribute("aria-disabled");
    }
  }

  function tickSampling(){
    const s=screen(),pane=samplePane(),state=sampleState(),d=detail();
    if(!s||s.classList.contains("hidden")||!pane||pane.dataset.state!=="active"){
      sampleActive=false;firstWaitStartedAt=0;firstStrikeSeen=false;return;
    }
    if(!sampleActive){sampleActive=true;firstWaitStartedAt=performance.now();firstStrikeSeen=false}

    const text=state?.textContent||"";
    const match=text.match(/(\d+)\s*\/\s*8/),count=match?Number(match[1]):0;
    if(count>=1)firstStrikeSeen=true;

    if(!firstStrikeSeen){
      const elapsed=(performance.now()-firstWaitStartedAt)/1000;
      if(state)state.textContent="0 / 8";
      if(d)d.textContent=elapsed<FIRST_STRIKE_WAIT_SEC
        ?`一打目を待っています。あと${Math.max(0,FIRST_STRIKE_WAIT_SEC-elapsed).toFixed(1)}秒は無音でも待機します。叩いた瞬間から8打登録を開始します。`
        :"一打目を待っています。パッドを叩くまで次には進みません。";
    }
  }

  setInterval(()=>{tickNoise();tickSampling()},35);
})();
