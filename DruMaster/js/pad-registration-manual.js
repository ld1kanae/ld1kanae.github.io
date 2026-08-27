"use strict";

(()=>{
  /* Restore the original 8-hit registration flow: after room-noise capture,
     pad registration does not listen until the user explicitly starts it. */
  const Port=globalThis.MessagePort;
  if(!Port?.prototype?.postMessage)return;

  const nativePost=Port.prototype.postMessage;
  let waitingForManual=false;
  let manualStarted=false;
  let registrationPort=null;
  let pendingRawMessage=null;
  let uiTimer=0;

  function screen(){return document.querySelector("#micCalibration")}
  function action(){return screen()?.querySelector("#micCalAction")}
  function samplePane(){return screen()?.querySelector('[data-fp-step="sample"]')}
  function sampleState(){return screen()?.querySelector("#fpSampleState")}
  function instruction(){return screen()?.querySelector("#micCalInstruction")}
  function detail(){return screen()?.querySelector("#micCalDetail")}

  function showManualStart(){
    uiTimer=0;
    const s=screen(),b=action(),pane=samplePane();
    if(!waitingForManual||manualStarted||!s||s.classList.contains("hidden")||!b||!pane)return;
    if(pane.dataset.state!=="active")return;

    b.classList.remove("hidden");
    b.disabled=false;
    b.style.pointerEvents="";
    b.removeAttribute("aria-disabled");
    b.textContent="パッド音の登録を開始";
    const state=sampleState();if(state)state.textContent="0 / 8";
    const ins=instruction();if(ins)ins.textContent="次にパッドを8回ほど叩いて音色を登録します";
    const d=detail();if(d)d.textContent="「パッド音の登録を開始」を押すまでは打音を登録しません。開始後、検出した打音を1 / 8から順に登録します。";
  }

  function scheduleManualUi(){
    if(uiTimer)return;
    uiTimer=setTimeout(showManualStart,0);
  }

  Port.prototype.postMessage=function(message,...rest){
    if(message&&typeof message==="object"){
      if(message.type==="beginCapture"&&Number(message.seconds)>=7.5){
        waitingForManual=true;
        manualStarted=false;
        registrationPort=this;
        pendingRawMessage=null;
      }else if(message.type==="candidateMode"&&message.mode==="raw"&&waitingForManual&&!manualStarted){
        registrationPort=this;
        pendingRawMessage={...message};
        scheduleManualUi();
        return;
      }
    }
    return nativePost.call(this,message,...rest);
  };

  document.addEventListener("click",e=>{
    const b=e.target?.closest?.("#micCalibration #micCalAction");
    if(!b||!waitingForManual||manualStarted||samplePane()?.dataset.state!=="active")return;
    if(b.textContent.trim()!=="パッド音の登録を開始")return;

    e.preventDefault();
    e.stopImmediatePropagation();
    manualStarted=true;
    waitingForManual=false;

    b.classList.add("hidden");
    const state=sampleState();if(state)state.textContent="0 / 8";
    const ins=instruction();if(ins)ins.textContent="パッドを続けて叩いてください";
    const d=detail();if(d)d.textContent="現在 0 / 8。検出した打音を1打ずつ音色登録します。強弱を少し混ぜてください。";

    /* Flush all pre-start proposal state, then start RAW registration using the
       original one-candidate / 145 ms / refractory detector. */
    if(registrationPort&&pendingRawMessage){
      const noiseRms=Number(pendingRawMessage.noiseRms)||0.0005;
      nativePost.call(registrationPort,{type:"candidateMode",mode:"off",noiseRms});
      nativePost.call(registrationPort,{...pendingRawMessage,registration:true});
    }
    pendingRawMessage=null;
  },true);

  const observer=new MutationObserver(()=>{if(waitingForManual&&!manualStarted)scheduleManualUi()});
  observer.observe(document.documentElement,{subtree:true,attributes:true,childList:true,characterData:true});
  setInterval(()=>{if(waitingForManual&&!manualStarted)showManualStart()},120);
})();
