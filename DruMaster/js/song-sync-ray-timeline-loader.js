"use strict";

(async()=>{
  try{
    const r=await fetch("js/song-sync-ray-timeline.js?v=20260828-raytimeline1",{cache:"no-store"});
    if(!r.ok)throw Error(`Timeline load failed: HTTP ${r.status}`);
    let src=await r.text();
    const replace=(from,to,label)=>{
      if(!src.includes(from))throw Error(`Timeline MIDI safety patch target missing: ${label}`);
      src=src.replace(from,to);
    };

    replace(
      'const d=new DataView(ab);let p=0;const need=(n,end=d.byteLength)=>{if(p+n>end)throw Error("MIDIが途中で切れています")}',
      'const d=new DataView(ab);let p=0;const need=(n,end=d.byteLength)=>{const limit=Math.min(Number.isFinite(end)?end:d.byteLength,d.byteLength);if(!Number.isFinite(n)||n<0||p<0||p+n>limit)throw Error("MIDIが途中で切れています")}',
      "bounds guard"
    );
    replace(
      'p=8+hl;const raw=[],tempoRaw=[{tick:0,us:500000}],sigs=[];',
      'p=8+hl;if(hl<6||p>d.byteLength)throw Error("MIDIヘッダーが不正です");const raw=[],tempoRaw=[{tick:0,us:500000}],sigs=[];',
      "header length"
    );
    replace(
      'const len=u32(),end=p+len;let tick=0,run=0;while(p<end)',
      'const len=u32(),end=p+len;if(end>d.byteLength)throw Error("MIDIトラックが途中で切れています");let tick=0,run=0;while(p<end)',
      "track length"
    );

    (0,eval)(`${src}\n//# sourceURL=song-sync-ray-timeline.patched.js`);
  }catch(e){
    console.error(e);
    const m=document.getElementById("message");
    if(m){m.textContent=e?.message||String(e);m.className="bad";}
  }
})();
