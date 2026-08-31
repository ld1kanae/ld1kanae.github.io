"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;
  let retry=0,timer=0;
  function check(){
    clearTimeout(timer);
    let d=null;try{d=frame.contentDocument}catch{}
    if(!d?.body)return;
    if(d.getElementById("dmPublisherMode"))return;
    if(retry>=2){console.error("DruMaster update mode UI failed to install");return}
    retry++;
    const s=document.createElement("script");
    s.src=`js/song-publisher-update-mode.js?v=20260829-update2&retry=${retry}-${Date.now()}`;
    document.head.appendChild(s);
    timer=setTimeout(check,900);
  }
  frame.addEventListener("load",()=>{retry=0;timer=setTimeout(check,900)});
  timer=setTimeout(check,1200);
})();
