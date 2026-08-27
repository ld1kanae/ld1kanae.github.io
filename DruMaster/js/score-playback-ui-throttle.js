"use strict";

(()=>{
  const seek=document.querySelector("#scoreSeek"),label=document.querySelector("#scoreSeekTime");
  if(!seek||!label)return;
  let dragging=false,lastValueWrite=0,lastLabelWrite=0;
  seek.addEventListener("pointerdown",()=>{dragging=true});
  const release=()=>{dragging=false;lastValueWrite=0;lastLabelWrite=0};
  seek.addEventListener("pointerup",release);seek.addEventListener("pointercancel",release);seek.addEventListener("change",release);

  const valueDesc=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value");
  if(valueDesc?.get&&valueDesc?.set){
    Object.defineProperty(seek,"value",{
      configurable:true,
      get(){return valueDesc.get.call(this)},
      set(v){
        const now=performance.now();
        if(dragging||now-lastValueWrite>=100){lastValueWrite=now;valueDesc.set.call(this,v)}
      }
    });
  }

  const textDesc=Object.getOwnPropertyDescriptor(Node.prototype,"textContent");
  if(textDesc?.get&&textDesc?.set){
    Object.defineProperty(label,"textContent",{
      configurable:true,
      get(){return textDesc.get.call(this)},
      set(v){
        const now=performance.now();
        if(dragging||now-lastLabelWrite>=100){lastLabelWrite=now;textDesc.set.call(this,v)}
      }
    });
  }
})();
