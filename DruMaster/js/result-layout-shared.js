"use strict";
(()=>{
  const clone=o=>JSON.parse(JSON.stringify(o));
  const view={pc:{w:1280,h:720},mobile:{w:844,h:390}};
  const defs={
    normal:{
      title:{label:"曲名",cls:"song-title",text:"Ray",region:"left"},
      artist:{label:"アーティスト",cls:"artist",text:"BUMP OF CHICKEN",region:"left"},
      scoreLabel:{label:"SCORE",cls:"score-label",text:"SCORE",region:"left"},
      score:{label:"スコア値",cls:"final-score",text:"985,420",region:"left"},
      summary:{label:"判定",cls:"summary",region:"left"},
      ranking:{label:"ランキング",cls:"ranking",region:"right"},
      retry:{label:"RETRY",cls:"result-btn",text:"RETRY",region:"full"},
      home:{label:"HOME",cls:"result-btn",text:"HOME",region:"full"}
    },
    auto:{
      title:{label:"曲名",cls:"song-title",text:"Ray",region:"full"},
      artist:{label:"アーティスト",cls:"artist",text:"BUMP OF CHICKEN",region:"full"},
      scoreLabel:{label:"SCORE",cls:"score-label",text:"SCORE",region:"full"},
      autoText:{label:"AUTO PLAY",cls:"autoplay-text",text:"AUTO PLAY",region:"full"},
      retry:{label:"RETRY",cls:"result-btn",text:"RETRY",region:"full"},
      home:{label:"HOME",cls:"result-btn",text:"HOME",region:"full"}
    }
  };
  const base={
    pc:{
      normal:{
        title:[180,76,280,58,48,1.05,1,1],artist:[160,145,320,34,24,1.15,1,1],scoreLabel:[230,208,180,28,21,1,7,1],score:[60,236,520,110,92,.9,1,1],summary:[85,348,470,78,16,1.1,1,1],ranking:[665,100,590,390,20,1.1,1,1],retry:[441,550,190,48,15,1.2,1,1],home:[649,550,190,48,15,1.2,1,1]
      },
      auto:{
        title:[500,70,280,58,48,1.05,1,1],artist:[500,165,300,36,24,1.15,1,1],scoreLabel:[560,235,160,30,21,1,7,1],autoText:[395,285,490,120,92,.9,1,1],retry:[438,455,190,48,15,1.2,1,1],home:[652,455,190,48,15,1.2,1,1]
      }
    },
    mobile:{
      normal:{
        title:[96,47,230,40,30,1,1,1],artist:[86,92,250,26,16,1.05,1,1],scoreLabel:[141,130,140,22,14,1,2,1],score:[41,150,340,72,58,.84,0,1],summary:[51,226,320,52,11,1,0,1],ranking:[458,22,350,274,16,1,0,1],retry:[290,320,126,42,13,1.2,1,1],home:[428,320,126,42,13,1.2,1,1]
      },
      auto:{
        title:[292,47,260,42,36,1,1,1],artist:[297,105,250,26,21,1.05,1,1],scoreLabel:[367,154,110,22,18,1,3,1],autoText:[264,183,315,80,58,.9,1,1],retry:[283,286,126,42,13,1.2,1,1],home:[435,286,126,42,13,1.2,1,1]
      }
    }
  };
  function obj(a){return{x:+a[0],y:+a[1],w:+a[2],h:+a[3],font:+a[4],line:+a[5],letter:+a[6],opacity:+a[7]}}
  function arr(o){return[+o.x,+o.y,+o.w,+o.h,+o.font,+o.line,+o.letter,+o.opacity]}
  function innerFor(key,text){
    if(key==="summary")return '<div class="sum-cell"><small>PERFECT</small><b>428</b></div><div class="sum-cell"><small>GREAT</small><b>37</b></div><div class="sum-cell"><small>GOOD</small><b>9</b></div><div class="sum-cell"><small>MISS</small><b>2</b></div>';
    if(key==="ranking")return '<div class="rtitle">RECORD RANKING</div><div class="rhead"><span>RANK</span><span>SCORE</span><span class="right">DATE</span></div><div class="rrow best"><span>1</span><b>985,420</b><span class="right">2026.09.01</span></div><div class="rrow"><span>2</span><b>973,180</b><span class="right">2026.08.31</span></div><div class="rrow"><span>3</span><b>961,730</b><span class="right">2026.08.30</span></div>';
    return text||"";
  }
  function applyStyle(el,v){
    el.style.left=v.x+"px";el.style.top=v.y+"px";el.style.width=v.w+"px";el.style.height=v.h+"px";el.style.fontSize=v.font+"px";el.style.lineHeight=String(v.line);el.style.letterSpacing=v.letter+"px";el.style.opacity=String(v.opacity);
  }
  function makeElement(key,def,value,selected=false){
    const el=document.createElement("div");
    el.className=`rl-el ${def.cls||""}${selected?" selected":""}`;
    el.dataset.key=key;
    applyStyle(el,value);
    const content=document.createElement("div");content.className="rl-content";content.innerHTML=innerFor(key,def.text);el.appendChild(content);
    return el;
  }
  function normalizeData(raw){
    const out=clone(base);
    if(!raw||typeof raw!=="object")return out;
    for(const device of ["pc","mobile"])for(const screen of ["normal","auto"]){
      const src=raw?.[device]?.[screen];if(!src)continue;
      for(const key of Object.keys(defs[screen]))if(Array.isArray(src[key])&&src[key].length>=8)out[device][screen][key]=src[key].slice(0,8).map(Number);
    }
    return out;
  }
  globalThis.DruMasterResultLayout={clone,view,defs,base,obj,arr,innerFor,applyStyle,makeElement,normalizeData};
})();