"use strict";

(()=>{
  const transport=document.querySelector(".transport"),play=document.getElementById("mixPlay"),oldStop=document.getElementById("mixStop")||document.getElementById("mixPause");
  if(!transport||!play||!oldStop)return;

  oldStop.id="mixPause";
  oldStop.textContent="Ⅱ 一時停止";
  play.textContent="▶ MIX再生";

  if(!document.getElementById("mixSeek")){
    const wrap=document.createElement("div");
    wrap.id="mixSeekWrap";
    wrap.innerHTML='<input id="mixSeek" type="range" min="0" max="1" step="0.05" value="0" disabled aria-label="再生位置"><span id="mixSeekTime">0:00 / 0:00</span>';
    transport.insertAdjacentElement("afterend",wrap);
  }

  if(!document.getElementById("dmVolumeTransportStyle")){
    const style=document.createElement("style");
    style.id="dmVolumeTransportStyle";
    style.textContent=`
      #mixSeekWrap{display:flex;align-items:center;gap:8px;width:100%;margin:-5px 0 14px;padding:3px 10px;border-radius:999px;background:#06101ac2;border:1px solid #64788b55}
      #mixSeekWrap #mixSeek{flex:1;min-width:0;margin:0}
      #mixSeekTime{min-width:72px;text-align:right;color:#b9c7d7;font:800 9px/1 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:nowrap}
      @media(max-width:560px){#mixSeekTime{min-width:64px;font-size:8px}}
    `;
    document.head.appendChild(style);
  }
})();
