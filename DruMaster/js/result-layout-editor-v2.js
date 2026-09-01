"use strict";
(()=>{
  const M=globalThis.DruMasterResultLayout;if(!M)return;
  const KEY="drumasterResultLayoutEditorV2",MAX_HISTORY=100;
  const $=id=>document.getElementById(id);
  let data=load(),screen="normal",device="pc",selected=new Set(["title"]),scale=1,drag=null;
  let undoStack=[],redoStack=[],fieldEditStart=null;
  const shell=$("shell"),preview=$("preview"),stage=$("stage"),list=$("elementList"),screenSeg=$("screenSeg"),deviceSeg=$("deviceSeg"),selectedTitle=$("selectedTitle"),selectionNote=$("selectionNote"),cssOut=$("css");
  const inputs={x:$("x"),y:$("y"),w:$("w"),h:$("h"),font:$("font"),line:$("line"),letter:$("letter"),opacity:$("opacity")};
  const labels={x:$("xLabel"),y:$("yLabel")};
  function load(){try{const raw=JSON.parse(localStorage.getItem(KEY)||"null");if(raw)return M.normalizeData(raw)}catch{}return M.clone(M.base)}
  function save(){localStorage.setItem(KEY,JSON.stringify(data));toast("保存しました")}
  function snapshot(){return JSON.stringify(data)}
  function restoreSnapshot(s){try{data=M.normalizeData(JSON.parse(s));render()}catch{}}
  function pushUndo(s=snapshot()){if(undoStack[undoStack.length-1]===s)return;undoStack.push(s);if(undoStack.length>MAX_HISTORY)undoStack.shift();redoStack=[]}
  function undo(){if(!undoStack.length){toast("戻せる操作がありません");return}redoStack.push(snapshot());restoreSnapshot(undoStack.pop());toast("元に戻しました")}
  function redo(){if(!redoStack.length){toast("やり直せる操作がありません");return}undoStack.push(snapshot());restoreSnapshot(redoStack.pop());toast("やり直しました")}
  function keys(){return [...selected].filter(k=>M.defs[screen][k])}
  function values(){return keys().map(k=>({key:k,v:M.obj(data[device][screen][k])}))}
  function setValue(key,v){data[device][screen][key]=M.arr(v)}
  function render(){
    shell.className="shell "+device;shell.style.transform=`scale(${scale})`;preview.innerHTML="";
    if(screen==="normal")preview.insertAdjacentHTML("beforeend",'<i class="rl-guide v mid"></i><i class="rl-guide v left-center"></i><i class="rl-guide v right-center"></i>');
    const defs=M.defs[screen];
    for(const key of Object.keys(defs))preview.appendChild(M.makeElement(key,defs[key],M.obj(data[device][screen][key]),selected.has(key)));
    const mode=document.createElement("div");mode.className="rl-mode-switch";mode.innerHTML=`<span class="${screen==="normal"?"on":""}">NORMAL</span><span class="${screen==="auto"?"on":""}">AUTO PLAY</span>`;preview.appendChild(mode);
    buildList();fillInputs();generateCss();
  }
  function toggleSelection(key,additive){
    if(additive){
      if(selected.has(key)&&selected.size>1)selected.delete(key);else selected.add(key);
    }else selected=new Set([key]);
    if(!selected.size)selected.add(key);
  }
  function buildList(){
    list.innerHTML="";
    for(const [key,def] of Object.entries(M.defs[screen])){
      const b=document.createElement("button");b.textContent=def.label;b.classList.toggle("active",selected.has(key));
      b.onclick=e=>{toggleSelection(key,e.shiftKey);render()};
      list.appendChild(b);
    }
  }
  function mixed(prop){const vals=values().map(x=>x.v[prop]);return vals.length&&vals.every(v=>v===vals[0])?vals[0]:""}
  function fillInputs(){
    const ks=keys(),multi=ks.length>1;selectedTitle.textContent=multi?`${ks.length} ELEMENTS`:M.defs[screen][ks[0]]?.label||"SELECTED";
    selectionNote.textContent=multi?"複数選択中：Shift＋クリックで追加/解除、ドラッグ・矢印キーで一括移動。":"Shift＋クリックで複数選択できます。";
    labels.x.textContent=multi?"ΔX":"X";labels.y.textContent=multi?"ΔY":"Y";
    for(const [prop,input] of Object.entries(inputs)){input.disabled=!ks.length;input.classList.toggle("mixed",multi&&prop!=="x"&&prop!=="y"&&mixed(prop)==="");input.placeholder=multi&&prop!=="x"&&prop!=="y"?"MIXED":"";input.value=multi&&(prop==="x"||prop==="y")?0:mixed(prop)}
  }
  function applyAbsolute(prop,value,record=true){if(record)pushUndo();for(const {key,v} of values()){v[prop]=value;if(["w","h","font"].includes(prop))v[prop]=Math.max(1,v[prop]);if(prop==="opacity")v[prop]=Math.max(0,Math.min(1,v[prop]));setValue(key,v)}render()}
  function applyDelta(dx,dy,record=true){if(!dx&&!dy)return;if(record)pushUndo();for(const {key,v} of values()){v.x+=dx;v.y+=dy;setValue(key,v)}render()}
  for(const [prop,input] of Object.entries(inputs)){
    input.addEventListener("focus",()=>{fieldEditStart=snapshot()});
    input.addEventListener("blur",()=>{if(fieldEditStart&&fieldEditStart!==snapshot()){if(undoStack[undoStack.length-1]!==fieldEditStart){undoStack.push(fieldEditStart);if(undoStack.length>MAX_HISTORY)undoStack.shift();redoStack=[]}}fieldEditStart=null});
    if(!["x","y"].includes(prop))input.addEventListener("input",()=>{if(input.value==="")return;applyAbsolute(prop,Number(input.value),false)});
  }
  for(const prop of ["x","y"]){
    inputs[prop].addEventListener("input",()=>{if(keys().length!==1||inputs[prop].value==="")return;applyAbsolute(prop,Number(inputs[prop].value),false)});
    inputs[prop].addEventListener("change",()=>{if(keys().length<2)return;const d=Number(inputs[prop].value)||0;if(d){pushUndo(fieldEditStart||snapshot());applyDelta(prop==="x"?d:0,prop==="y"?d:0,false)}inputs[prop].value=0;fieldEditStart=null});
  }
  preview.addEventListener("pointerdown",e=>{
    const el=e.target.closest(".rl-el");if(!el)return;e.preventDefault();const key=el.dataset.key,additive=e.shiftKey;
    if(additive){toggleSelection(key,true);renderSelectionOnly();fillInputs();buildList();if(!selected.has(key))return}
    else if(!selected.has(key)){selected=new Set([key]);renderSelectionOnly();fillInputs();buildList()}
    const starts={};for(const k of keys())starts[k]=M.obj(data[device][screen][k]);
    drag={id:e.pointerId,startX:e.clientX,startY:e.clientY,starts,axis:null,before:snapshot(),moved:false};el.setPointerCapture(e.pointerId);
  });
  preview.addEventListener("pointermove",e=>{
    if(!drag||e.pointerId!==drag.id)return;let dx=(e.clientX-drag.startX)/scale,dy=(e.clientY-drag.startY)/scale;
    if(e.shiftKey){if(!drag.axis&&(Math.abs(dx)>2||Math.abs(dy)>2))drag.axis=Math.abs(dx)>=Math.abs(dy)?"x":"y";if(drag.axis==="x")dy=0;else if(drag.axis==="y")dx=0}else drag.axis=null;
    dx=Math.round(dx);dy=Math.round(dy);drag.moved=drag.moved||!!(dx||dy);
    for(const [key,start] of Object.entries(drag.starts)){const v={...start,x:start.x+dx,y:start.y+dy};setValue(key,v);const node=preview.querySelector(`.rl-el[data-key="${key}"]`);if(node)M.applyStyle(node,v)}
    fillInputs();generateCss();
  });
  function endDrag(e){if(!drag||e.pointerId!==drag.id)return;if(drag.moved&&drag.before!==snapshot()){if(undoStack[undoStack.length-1]!==drag.before){undoStack.push(drag.before);if(undoStack.length>MAX_HISTORY)undoStack.shift();redoStack=[]}}drag=null;render()}
  preview.addEventListener("pointerup",endDrag);preview.addEventListener("pointercancel",endDrag);
  function renderSelectionOnly(){preview.querySelectorAll(".rl-el").forEach(el=>el.classList.toggle("selected",selected.has(el.dataset.key)))}
  window.addEventListener("keydown",e=>{
    const mod=e.ctrlKey||e.metaKey;
    if(mod&&e.key.toLowerCase()==="z"){
      e.preventDefault();if(e.shiftKey)redo();else undo();return;
    }
    if(mod&&e.key.toLowerCase()==="y"){e.preventDefault();redo();return}
    if(["INPUT","TEXTAREA"].includes(document.activeElement?.tagName)||!["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(e.key))return;
    e.preventDefault();const n=e.shiftKey?10:1;applyDelta(e.key==="ArrowLeft"?-n:e.key==="ArrowRight"?n:0,e.key==="ArrowUp"?-n:e.key==="ArrowDown"?n:0,true)
  });
  function setSeg(root,key,value){root.querySelectorAll("button").forEach(b=>b.classList.toggle("active",b.dataset[key]===value))}
  screenSeg.onclick=e=>{const b=e.target.closest("button");if(!b)return;screen=b.dataset.screen;selected=new Set([Object.keys(M.defs[screen])[0]]);setSeg(screenSeg,"screen",screen);render()};
  deviceSeg.onclick=e=>{const b=e.target.closest("button");if(!b)return;device=b.dataset.device;selected=new Set([Object.keys(M.defs[screen])[0]]);setSeg(deviceSeg,"device",device);fit()};
  function fit(){const v=M.view[device],pad=52;scale=Math.min(1,Math.max(100,stage.clientWidth-pad)/v.w,Math.max(100,stage.clientHeight-pad)/v.h);render()}
  $("fit").onclick=fit;$("actual").onclick=()=>{scale=1;render()};$("save").onclick=save;
  $("resetView").onclick=()=>{pushUndo();data[device][screen]=M.clone(M.base[device][screen]);selected=new Set([Object.keys(M.defs[screen])[0]]);render();toast("現在のビューを初期化しました")};
  $("resetAll").onclick=()=>{if(!confirm("4レイアウトすべて初期化しますか？"))return;pushUndo();data=M.clone(M.base);localStorage.removeItem(KEY);render();toast("すべて初期化しました")};
  function centerGroup(group,x0,x1){const items=group.map(k=>({k,v:M.obj(data[device].normal[k])}));if(!items.length)return;const min=Math.min(...items.map(i=>i.v.x)),max=Math.max(...items.map(i=>i.v.x+i.v.w)),cx=(min+max)/2,target=(x0+x1)/2,dx=Math.round(target-cx);for(const i of items){i.v.x+=dx;data[device].normal[i.k]=M.arr(i.v)}}
  function centerNormalColumns(){
    if(screen!=="normal"){toast("NORMAL RESULTで使用してください");return}
    pushUndo();const width=M.view[device].w,half=width/2,left=["title","artist","scoreLabel","score","summary"];
    for(const k of left){const v=M.obj(data[device].normal[k]);v.x=Math.round((half-v.w)/2);data[device].normal[k]=M.arr(v)}
    const r=M.obj(data[device].normal.ranking);r.x=Math.round(half+(half-r.w)/2);data[device].normal.ranking=M.arr(r);
    centerGroup(["retry","home"],half,width);render();toast(`${device==="pc"?"PC":"スマホ"}左右カラムをセンタリングしました`)
  }
  $("centerColumns").onclick=centerNormalColumns;
  function selector(key){return{title:">h2",artist:">.result-song-sub",scoreLabel:">.result-score-label",score:">#finalScore",summary:">.result-summary",ranking:">.ranking-panel",retry:">.result-actions>#retry",home:">.result-actions>#home",autoText:">#finalScore"}[key]}
  function rulesFor(dev,mode){let out="",prefix=mode==="auto"?"#result.autoplay":"#result:not(.autoplay)";for(const key of Object.keys(M.defs[mode])){const v=M.obj(data[dev][mode][key]),sel=prefix+selector(key);out+=`${sel}{position:absolute!important;left:${v.x}px!important;top:${v.y}px!important;width:${v.w}px!important;height:${v.h}px!important;font-size:${v.font}px!important;line-height:${v.line}!important;letter-spacing:${v.letter}px!important;opacity:${v.opacity}!important;margin:0!important;}\n`}return out}
  function generateCss(){cssOut.value=`/* Generated by DruMaster Result Layout Editor v2 */\n@media (hover:hover) and (pointer:fine){\n${rulesFor("pc","normal")}${rulesFor("pc","auto")}}\n@media (hover:none) and (pointer:coarse) and (max-width:900px){\n${rulesFor("mobile","normal")}${rulesFor("mobile","auto")}}\n`}
  $("copyCss").onclick=()=>copyText(cssOut.value,"CSSをコピーしました");
  function encodeViewer(){const json=JSON.stringify({mobile:data.mobile});return btoa(json).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/g,"")}
  function viewerUrl(){const u=new URL("result-layout-viewer.html",location.href);u.searchParams.set("screen",screen);u.searchParams.set("d",encodeViewer());return u.toString()}
  $("copyViewer").onclick=()=>copyText(viewerUrl(),"スマホビューワURLをコピーしました");$("openViewer").onclick=()=>window.open(viewerUrl(),"_blank","noopener");
  async function copyText(text,msg){try{await navigator.clipboard.writeText(text);toast(msg)}catch{const t=document.createElement("textarea");t.value=text;document.body.appendChild(t);t.select();document.execCommand("copy");t.remove();toast(msg)}}
  function toast(text){const el=$("toast");el.textContent=text;el.classList.add("show");clearTimeout(el._t);el._t=setTimeout(()=>el.classList.remove("show"),1500)}
  window.addEventListener("resize",fit);fit();
})();