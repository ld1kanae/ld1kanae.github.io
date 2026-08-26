"use strict";

(()=>{
  const STORAGE_KEY="drumasterSettingsV1";
  const ids={
    vocal:"vocalToggle",
    guide:"guideToggle",
    hidden:"hiddenToggle",
    auto:"autoToggle",
    tempo:"tempo",
    volume:"masterVolume",
    performanceMode:"performanceModeSelect"
  };

  function read(){
    try{
      const data=JSON.parse(localStorage.getItem(STORAGE_KEY)||"{}");
      return data&&typeof data==="object"?data:{};
    }catch{return {}}
  }

  function current(){
    const out={};
    for(const [key,id] of Object.entries(ids)){
      const el=document.getElementById(id);
      if(!el)continue;
      out[key]=el.type==="checkbox"?!!el.checked:String(el.value);
    }
    return out;
  }

  function save(){
    try{
      const previous=read();
      localStorage.setItem(STORAGE_KEY,JSON.stringify({...previous,...current()}));
    }catch{}
  }

  function restore(){
    const saved=read();
    for(const [key,id] of Object.entries(ids)){
      if(!(key in saved))continue;
      const el=document.getElementById(id);
      if(!el)continue;
      if(el.type==="checkbox"){
        el.checked=!!saved[key];
        el.dispatchEvent(new Event("change",{bubbles:true}));
      }else{
        const value=String(saved[key]);
        if([...el.options||[]].length&&![...el.options].some(o=>o.value===value))continue;
        el.value=value;
        el.dispatchEvent(new Event(el.type==="range"?"input":"change",{bubbles:true}));
      }
    }
  }

  restore();

  for(const id of Object.values(ids)){
    const el=document.getElementById(id);
    if(!el)continue;
    el.addEventListener(el.type==="range"?"input":"change",save);
  }
  addEventListener("pagehide",save);

  globalThis.DruMasterSettings={save,restore,read};
})();
