"use strict";

(()=>{
  const frame=document.getElementById("registerView");
  if(!frame)return;

  const REPO="ld1kanae/ld1kanae.github.io",ROOT="DruMaster/songs",BRANCH="main";
  const DB_NAME="drumasterSongPublishV1",STORE="sessions",DB_VERSION=1;
  const BUILTIN={
    nanairo:{id:"nanairo",title:"なないろ",artist:"BUMP OF CHICKEN",duration:263.05,bpm:125,chart:{pixelsPerQuarter:80},playback:{stemOffsetSec:0,midiOffsetSec:0},midi:"songs/nanairo/chart.mid",midiGzip:"songs/nanairo/chart.mid.gz?v=20260826-midi2",stems:{base:{path:"songs/nanairo/offvocal.mp3",bytes:6314638,sha256:"4dd43973168efdc730112bec742e3dced51024080d222dbd43f7065ef713a8b1"},vocals:{path:"songs/nanairo/vocals.mp3",bytes:6314638,sha256:"73e6ba324ffa608fb74b7a33206c9189e2b885a43c48779bd4b0094729e75c2f"},drums:{path:"songs/nanairo/drums.mp3",bytes:6314638,sha256:"6d50cf5fe21ab4fb73588d3cda1c8bb8ace2ae5234db1eaaca571374ff8e9eeb"}}},
    ray:{id:"ray",title:"Ray",artist:"BUMP OF CHICKEN",duration:305.544,bpm:132,chart:{pixelsPerQuarter:75,desktopPixelsPerQuarter:100},playback:{stemOffsetSec:.005,midiOffsetSec:0},midi:"songs/ray/chart.mid",midiGzip:"songs/ray/chart.mid.gz?v=20260826-midi2",mix:{base:.70,vocals:.60,drums:.70},stems:{base:{path:"songs/ray/offvocal.mp3",bytes:12221760,sha256:"b0f8b2b8930e054f7edfc71922a03b119771e54fc14f5dec6f4d94e6ff8e236c"},vocals:{path:"songs/ray/vocals.mp3",bytes:8735901,sha256:"b9225fa4869c56bd3a4009db88d9e86002b560083fb869f6183de29442dfde5d"},drums:{path:"songs/ray/drums.mp3",bytes:9806929,sha256:"526328461d8f5f4aea6d52bf2c5954d1b9a0d619da90d4348b95bb44fbaec960"}}}
  };
  const SOURCE=[
    {input:"fullmix",key:"fullmix",filename:"fullmix.mp3",label:"原曲"},
    {input:"offvocal",key:"base",filename:"offvocal.mp3",label:"オフボーカル"},
    {input:"drums",key:"drums",filename:"drums.mp3",label:"ドラムのみ"},
    {input:"vocals",key:"vocals",filename:"vocals.mp3",label:"ボーカルのみ"}
  ];

  let mode="new",catalog={},currentSong=null,audioContext=null,installing=false;
  const clone=v=>JSON.parse(JSON.stringify(v));
  function doc(){try{return frame.contentDocument}catch{return null}}
  function $(id,d=doc()){return d?.getElementById(id)||null}
  function headers(t){return {"Accept":"application/vnd.github+json","Authorization":`Bearer ${t}`,"X-GitHub-Api-Version":"2022-11-28"}}
  function token(d=doc()){return $("token",d)?.value.trim()||""}
  function setProgress(v,text,d=doc()){v=Math.max(0,Math.min(100,v));const bar=$("bar",d),percent=$("percent",d),stage=$("stage",d);if(bar)bar.style.width=v.toFixed(1)+"%";if(percent)percent.textContent=Math.round(v)+"%";if(text&&stage)stage.textContent=text}
  function say(s,cls="",d=doc()){const log=$("log",d);if(!log)return;log.textContent=s;log.className=cls}
  async function apiGet(path,t){const r=await fetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}`,{headers:headers(t),cache:"no-store"});if(r.status===404)return null;if(!r.ok)throw Error(`GitHub API ${r.status}: ${path}`);return r.json()}
  async function publicJson(path){const r=await fetch(`${path}${path.includes("?")?"&":"?"}t=${Date.now()}`,{cache:"no-store"});if(!r.ok)throw Error(`取得失敗: ${path} (${r.status})`);return r.json()}
  function openDb(){return new Promise((resolve,reject)=>{const r=indexedDB.open(DB_NAME,DB_VERSION);r.onupgradeneeded=()=>{const db=r.result;if(!db.objectStoreNames.contains(STORE))db.createObjectStore(STORE,{keyPath:"sessionId"})};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error||Error("ローカルセッションDBを開けませんでした"))})}
  async function storeSession(value){const db=await openDb();return new Promise((resolve,reject)=>{const tx=db.transaction(STORE,"readwrite");tx.objectStore(STORE).put(value);tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>{db.close();reject(tx.error||Error("ローカル素材を保存できませんでした"))}})}
  async function sha256(ab){const h=await crypto.subtle.digest("SHA-256",ab);return [...new Uint8Array(h)].map(v=>v.toString(16).padStart(2,"0")).join("")}
  async function gzip(ab){if(typeof CompressionStream!=="function")return null;const stream=new Blob([ab]).stream().pipeThrough(new CompressionStream("gzip"));return new Uint8Array(await new Response(stream).arrayBuffer())}
  function getAC(){return audioContext||(audioContext=new (window.AudioContext||window.webkitAudioContext)())}
  async function resample(buffer,targetDuration){const sr=44100,length=Math.max(1,Math.round(targetDuration*sr)),ctx=new OfflineAudioContext(2,length,sr),src=ctx.createBufferSource();src.buffer=buffer;src.connect(ctx.destination);src.start();return ctx.startRendering()}
  function floatTo16(src,start,count){const out=new Int16Array(count);for(let i=0;i<count;i++){const v=Math.max(-1,Math.min(1,src[start+i]||0));out[i]=v<0?v*32768:v*32767}return out}
  async function encodeMp3(file,targetDuration,progress){if(!globalThis.lamejs?.Mp3Encoder)throw Error("MP3変換ライブラリを読み込めませんでした");const ab=await file.arrayBuffer(),decoded=await getAC().decodeAudioData(ab.slice(0)),rendered=await resample(decoded,targetDuration||decoded.duration),left=rendered.getChannelData(0),right=rendered.numberOfChannels>1?rendered.getChannelData(1):left,enc=new lamejs.Mp3Encoder(2,44100,192),blocks=[],step=1152,total=Math.ceil(rendered.length/step);for(let at=0,i=0;at<rendered.length;at+=step,i++){const n=Math.min(step,rendered.length-at),l=floatTo16(left,at,n),r=floatTo16(right,at,n),buf=enc.encodeBuffer(l,r);if(buf.length)blocks.push(new Uint8Array(buf));if(i%96===0){progress?.(i/total);await new Promise(res=>setTimeout(res,0))}}const end=enc.flush();if(end.length)blocks.push(new Uint8Array(end));progress?.(1);return new Blob(blocks,{type:"audio/mpeg"})}
  function parseMidi(ab){const d=new DataView(ab);let p=0;const need=n=>{if(p+n>d.byteLength)throw Error("MIDIが途中で切れています")},str=n=>{need(n);let s="";while(n--)s+=String.fromCharCode(d.getUint8(p++));return s},u32=()=>{need(4);const v=d.getUint32(p);p+=4;return v},u16=()=>{need(2);const v=d.getUint16(p);p+=2;return v},vlq=end=>{let v=0,b,c=0;do{if(p>=end)throw Error("MIDI VLQ error");b=d.getUint8(p++);v=(v<<7)|(b&127);if(++c>4)throw Error("MIDI VLQ error")}while(b&128);return v};if(str(4)!=="MThd")throw Error("MIDIヘッダーが不正です");const header=u32();u16();const tracks=u16(),division=u16();if(division&0x8000)throw Error("SMPTE MIDIには未対応です");p=8+header;let notes=0;const tempos=[],sigs=[];for(let tr=0;tr<tracks;tr++){if(str(4)!=="MTrk")throw Error("MIDIトラックが不正です");const len=u32(),end=p+len;let tick=0,run=0;while(p<end){tick+=vlq(end);let first=d.getUint8(p++),status;if(first<128){if(!run)throw Error("MIDI running status error");status=run;p--}else{status=first;if(status<240)run=status}if(status===255){const type=d.getUint8(p++),n=vlq(end);if(type===81&&n===3)tempos.push({tick,us:(d.getUint8(p)<<16)|(d.getUint8(p+1)<<8)|d.getUint8(p+2)});if(type===88&&n>=2)sigs.push({tick,numerator:d.getUint8(p),denominator:2**d.getUint8(p+1)});p+=n;continue}if(status===240||status===247){run=0;p+=vlq(end);continue}const hi=status&240,ch=status&15,bytes=(hi===192||hi===208)?1:2;need(bytes);d.getUint8(p++);const b=bytes===2?d.getUint8(p++):0;if(hi===144&&b>0&&ch===9)notes++}p=end}tempos.sort((a,b)=>a.tick-b.tick);sigs.sort((a,b)=>a.tick-b.tick);const tempo=tempos.find(x=>x.tick===0)||tempos[0]||{us:500000},sig=sigs.find(x=>x.tick===0)||sigs[0]||{numerator:4,denominator:4};return {division,noteCount:notes,bpm:60000000/tempo.us,numerator:sig.numerator,denominator:sig.denominator}}

  function storedOrder(song){
    const raw=song?.order;
    if(raw===null||raw===undefined||String(raw).trim()==="")return null;
    const n=Number(raw);
    return Number.isInteger(n)&&n>=0?n:null;
  }
  function readOrder(d=doc()){
    const raw=$("order",d)?.value.trim()||"";
    if(raw==="")return null;
    const n=Number(raw);
    if(!Number.isInteger(n)||n<0)throw Error("表示順は0以上の整数で入力してください");
    return n;
  }

  function injectStyle(d){
    if(d.getElementById("dmUpdateModeStyle"))return;
    const s=d.createElement("style");s.id="dmUpdateModeStyle";s.textContent=`
      .dm-mode-panel{order:-10}.dm-mode-switch{display:grid;grid-template-columns:1fr 1fr;gap:8px}.dm-mode-switch button{height:38px;border:1px solid #35516a;border-radius:8px;background:#0a1823;color:#aebdca;font-weight:800;cursor:pointer}.dm-mode-switch button.active{color:#f3fdff;border-color:rgba(103,226,215,.82);background:linear-gradient(115deg,rgba(37,189,187,.26),rgba(126,95,230,.30));box-shadow:inset 0 1px 0 rgba(255,255,255,.06)}
      .dm-existing-wrap{margin-top:14px}.dm-existing-wrap[hidden]{display:none!important}.dm-existing-wrap label{display:grid;gap:6px}.dm-existing-wrap label>span{font-size:11px;color:#9fadc0;font-weight:700}.dm-current-note{margin:8px 0 0;text-align:center;color:#7f91a4;font-size:10px}
      .dm-update-control{display:grid;grid-template-columns:minmax(0,1fr) 118px;gap:7px 8px;align-items:center;min-width:0}.dm-update-control input[type=file]{grid-column:1/-1}.dm-update-meta{min-width:0;color:#7f91a4;font:10px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.dm-update-action{height:32px!important;min-width:0!important;padding:0 8px!important;font-size:10px!important}
      body.dm-publisher-new .dm-update-meta,body.dm-publisher-new .dm-update-action{display:none!important}body.dm-publisher-new .dm-update-control{display:block}body.dm-publisher-update .file-row{grid-template-columns:150px minmax(0,1fr)!important}body.dm-publisher-update #songId{opacity:.65;cursor:not-allowed}
      .dm-update-confirm{margin-top:14px;padding:14px;border:1px solid #385467;border-radius:9px;background:#0b121a}.dm-update-confirm[hidden]{display:none!important}.dm-update-confirm h3{margin:0 0 9px;text-align:center;font-size:12px;letter-spacing:.08em}.dm-update-confirm ul{margin:0;padding-left:20px;color:#9fb1c4;font-size:10px;line-height:1.7}.dm-update-confirm .warn{margin:9px 0 0;text-align:center;color:#ffd17a;font-size:10px}.dm-confirm-actions{display:flex;justify-content:center;gap:8px;margin-top:12px}.dm-confirm-actions button{min-width:132px;height:36px}
      @media(max-width:640px){.dm-update-control{grid-template-columns:1fr}.dm-update-action,.dm-update-control input[type=file]{grid-column:1}.dm-confirm-actions{flex-direction:column}.dm-confirm-actions button{width:100%}}
    `;d.head.appendChild(s);
  }

  async function loadCatalog(d){
    let reg={};try{reg=await publicJson("songs/registry.json")}catch(e){console.warn(e)}
    let drafts={};try{drafts=await globalThis.DruMasterDraftCatalog?.discover(reg)||{}}catch(e){console.warn(e)}
    catalog={...clone(BUILTIN),...drafts,...(reg&&typeof reg==="object"?reg:{})};
    const sel=$("dmExistingSong",d);if(!sel)return;
    const rank=s=>storedOrder(s)??999;
    const values=Object.values(catalog).sort((a,b)=>rank(a)-rank(b)||String(a.title).localeCompare(String(b.title),"ja"));
    sel.replaceChildren();for(const song of values){const o=d.createElement("option");o.value=song.id;o.textContent=`${song.title} — ${song.artist}`;sel.appendChild(o)}
    if(values.length){sel.value=values[0].id;loadSong(values[0].id,d)}
  }

  function actionFor(inputId,d=doc()){return d?.querySelector(`.dm-update-action[data-input="${inputId}"]`)?.value||"keep"}
  function setAction(inputId,value,d=doc()){const a=d?.querySelector(`.dm-update-action[data-input="${inputId}"]`);if(a){a.value=value;syncAction(a,d)}}
  function syncAction(select,d=doc()){const input=$(select.dataset.input,d);if(!input)return;const replacing=select.value==="replace";input.disabled=false;input.hidden=false;if(!replacing)input.value="";updateSummaryHint(d)}
  function currentPath(key){return currentSong?.stems?.[key]?.path||null}

  function decorateRows(d){
    for(const spec of [...SOURCE,{input:"midi",key:"midi",filename:"chart.mid",label:"MIDI"}]){
      const input=$(spec.input,d),row=input?.closest(".file-row");if(!input||!row||row.querySelector(".dm-update-control"))continue;
      const wrap=d.createElement("div");wrap.className="dm-update-control";const meta=d.createElement("span");meta.className="dm-update-meta";meta.dataset.key=spec.key;const select=d.createElement("select");select.className="dm-update-action";select.dataset.input=spec.input;select.dataset.key=spec.key;select.innerHTML=spec.input==="midi"?'<option value="keep">変更なし</option><option value="replace">差し替え</option>':'<option value="keep">変更なし</option><option value="replace">差し替え</option><option value="delete">削除</option>';select.addEventListener("change",()=>syncAction(select,d));input.replaceWith(wrap);wrap.append(meta,select,input);
    }
  }

  function loadSong(id,d=doc()){
    const song=catalog[id];if(!song)return;currentSong=clone(song);
    const order=storedOrder(song);
    $("title",d).value=song.title||"";$("artist",d).value=song.artist||"";$("songId",d).value=song.id||id;$("songId",d).readOnly=true;$("order",d).value=order===null?"":String(order);$("ppqVisual",d).value=String(song.chart?.pixelsPerQuarter||80);$("desktopPpqVisual",d).value=Number.isFinite(Number(song.chart?.desktopPixelsPerQuarter))?String(Number(song.chart.desktopPixelsPerQuarter)):"";
    for(const spec of SOURCE){const meta=d.querySelector(`.dm-update-meta[data-key="${spec.key}"]`),path=song.stems?.[spec.key]?.path||"";if(meta)meta.textContent=path?`現在: ${path.split("/").pop()}`:"現在: 未登録";const action=d.querySelector(`.dm-update-action[data-key="${spec.key}"]`),del=action?.querySelector('option[value="delete"]');if(del)del.disabled=!path;setAction(spec.input,"keep",d)}
    const midiMeta=d.querySelector('.dm-update-meta[data-key="midi"]');if(midiMeta)midiMeta.textContent=song.midi?`現在: ${song.midi.split("/").pop().split("?")[0]}`:"現在: 未登録";setAction("midi","keep",d);
    $("publish",d).textContent="UPDATE";const h=d.querySelector("header h1");if(h)h.textContent="楽曲データ更新";const sub=d.querySelector("header .sub");if(sub)sub.textContent="変更した素材だけ差し替え、既存のタイミング・音量設定を引き継ぎます。";say("更新する項目を選択してください。変更なしの素材はそのまま維持されます。","",d);updateSummaryHint(d);
  }

  function resetNew(d=doc()){
    currentSong=null;for(const id of ["title","artist","songId","order","desktopPpqVisual"]){const n=$(id,d);if(n)n.value=""}const sid=$("songId",d);if(sid)sid.readOnly=false;const ppq=$("ppqVisual",d);if(ppq)ppq.value="80";for(const spec of [...SOURCE,{input:"midi"}]){const input=$(spec.input,d);if(input){input.disabled=false;input.hidden=false;input.value=""}}$("publish",d).textContent="PUBLISH";const h=d.querySelector("header h1");if(h)h.textContent="楽曲データ登録";const sub=d.querySelector("header .sub");if(sub)sub.textContent="入力 → 音源変換 → タイミング補正とGitHub登録を並行して進めます。";say("ファイルを選択してPUBLISHしてください。","",d);const confirm=$("dmUpdateConfirm",d);if(confirm)confirm.hidden=true;
  }

  function setMode(next,d=doc()){
    mode=next;d.body.classList.toggle("dm-publisher-update",next==="update");d.body.classList.toggle("dm-publisher-new",next==="new");d.querySelectorAll(".dm-mode-switch button").forEach(b=>b.classList.toggle("active",b.dataset.mode===next));const chooser=$("dmExistingWrap",d);if(chooser)chooser.hidden=next!=="update";if(next==="update"){if(!$("dmExistingSong",d)?.options.length){void loadCatalog(d)}else loadSong($("dmExistingSong",d).value,d)}else resetNew(d)
  }

  function updateSummaryHint(d=doc()){if(mode!=="update"||!currentSong)return;const parts=[];for(const spec of SOURCE){const a=actionFor(spec.input,d);if(a!=="keep")parts.push(`${spec.label}: ${a==="replace"?"差し替え":"削除"}`)}const midiFile=$("midi",d)?.files?.[0];if(midiFile)parts.push(`MIDI: ${currentSong.midi?"差し替え":"追加"}`);const note=$("dmCurrentNote",d);if(note)note.textContent=parts.length?parts.join(" / "):"素材はすべて変更なし"}

  function validatePlan(d=doc()){
    if(!currentSong)throw Error("更新する楽曲を選択してください");
    if(!$("title",d).value.trim())throw Error("曲名を入力してください");
    if(!$("artist",d).value.trim())throw Error("アーティスト名を入力してください");
    readOrder(d);
    for(const spec of SOURCE){if(actionFor(spec.input,d)==="replace"&&!$(spec.input,d).files[0])throw Error(`${spec.label}の差し替えファイルを選択してください`)}
    const hasBase=actionFor("offvocal",d)==="delete"?false:actionFor("offvocal",d)==="replace"?true:!!currentSong.stems?.base;
    const hasFull=actionFor("fullmix",d)==="delete"?false:actionFor("fullmix",d)==="replace"?true:!!currentSong.stems?.fullmix;
    if(!hasBase&&!hasFull)throw Error("原曲またはオフボーカルのどちらか1つ以上を残してください");
  }

  function showConfirm(d=doc()){
    try{validatePlan(d)}catch(e){say(e.message||String(e),"bad",d);return}
    const list=$("dmUpdateConfirmList",d);list.replaceChildren();let count=0;
    for(const spec of SOURCE){const a=actionFor(spec.input,d);if(a==="keep")continue;const li=d.createElement("li");li.textContent=a==="replace"?`${spec.label}: ${currentPath(spec.key)?.split("/").pop()||"未登録"} → ${$(spec.input,d).files[0]?.name||""}`:`${spec.label}: ${currentPath(spec.key)?.split("/").pop()||"未登録"} → 削除`;list.appendChild(li);count++}
    const midiFile=$("midi",d)?.files?.[0];if(midiFile){const li=d.createElement("li");li.textContent=`MIDI: ${currentSong.midi?currentSong.midi.split("/").pop().split("?")[0]:"未登録"} → ${midiFile.name}`;list.appendChild(li);count++}
    const metadataChanged=$("title",d).value.trim()!==(currentSong.title||"")||$("artist",d).value.trim()!==(currentSong.artist||"")||readOrder(d)!==storedOrder(currentSong);if(metadataChanged){const li=d.createElement("li");li.textContent="曲名・アーティスト名・表示順の変更を反映";list.appendChild(li);count++}
    if(!count){const li=d.createElement("li");li.textContent="素材・メタデータ変更なし";list.appendChild(li)}
    $("dmMidiWarning",d).hidden=!midiFile;$("dmUpdateConfirm",d).hidden=false;$("dmUpdateConfirm",d).scrollIntoView({behavior:"smooth",block:"center"});
  }

  async function runUpdate(d=doc()){
    validatePlan(d);const t=token(d);if(!t)throw Error("GitHub tokenを入力してください");const btn=$("dmConfirmUpdate",d),mainBtn=$("publish",d);btn.disabled=true;mainBtn.disabled=true;
    try{
      $("dmUpdateConfirm",d).hidden=true;setProgress(1,"既存データ確認",d);say("既存ファイルを確認しています…","",d);
      const id=currentSong.id,title=$("title",d).value.trim(),artist=$("artist",d).value.trim(),duration=Number(currentSong.duration)||0,draft=clone(currentSong),stems=clone(currentSong.stems||{}),uploadItems=[],originals={};
      const midiInputFile=$("midi",d)?.files?.[0]||null,changedMidi=!!midiInputFile;
      for(let i=0;i<SOURCE.length;i++){
        const spec=SOURCE[i],action=actionFor(spec.input,d),old=stems[spec.key],repoPath=old?.path?`DruMaster/${old.path.split(/[?#]/)[0]}`:`${ROOT}/${id}/${spec.filename}`;if(action==="keep")continue;const meta=await apiGet(repoPath,t);
        if(action==="delete"){if(meta?.sha)uploadItems.push({op:"delete",path:repoPath,sha:meta.sha,label:`${spec.filename} を削除`});delete stems[spec.key];continue}
        const file=$(spec.input,d).files[0],base=5+(i/SOURCE.length)*55,span=55/SOURCE.length,mp3=await encodeMp3(file,duration||null,p=>setProgress(base+p*span,`変換: ${spec.filename}`,d)),bytes=new Uint8Array(await mp3.arrayBuffer());stems[spec.key]={path:`songs/${id}/${spec.filename}`,bytes:bytes.byteLength,sha256:await sha256(bytes.buffer)};originals[spec.key]=file;uploadItems.push({path:`${ROOT}/${id}/${spec.filename}`,blob:mp3,sha:meta?.sha||null,label:`${spec.filename} を更新`})
      }

      let midiAb=null,midiGzip=currentSong.midiGzip||null,midiPatch=null;
      if(changedMidi){
        midiAb=await midiInputFile.arrayBuffer();
        const midiPath=`${ROOT}/${id}/chart.mid`,midiMeta=await apiGet(midiPath,t);
        uploadItems.push({path:midiPath,blob:new Blob([midiAb],{type:"audio/midi"}),sha:midiMeta?.sha||null,label:currentSong.midi?"chart.mid を更新":"chart.mid を追加"});
        const gz=await gzip(midiAb),gzipPath=`${ROOT}/${id}/chart.mid.gz`,gzipMeta=await apiGet(gzipPath,t);
        if(gz){uploadItems.push({path:gzipPath,blob:new Blob([gz],{type:"application/gzip"}),sha:gzipMeta?.sha||null,label:gzipMeta?.sha?"chart.mid.gz を更新":"chart.mid.gz を追加"});midiGzip=`songs/${id}/chart.mid.gz?v=${Date.now()}`}
        else{if(gzipMeta?.sha)uploadItems.push({op:"delete",path:gzipPath,sha:gzipMeta.sha,label:"chart.mid.gz を削除"});midiGzip=null}
        const midiInfo=parseMidi(midiAb),midiHash=await sha256(midiAb);
        midiPatch={bpm:Number(midiInfo.bpm.toFixed(6)),timeSignature:{numerator:midiInfo.numerator,denominator:midiInfo.denominator},division:midiInfo.division,noteCount:midiInfo.noteCount,midi:`songs/${id}/chart.mid`,midiGzip,midiBytes:midiAb.byteLength,midiSha256:midiHash};
      }

      const order=readOrder(d),chart={...(currentSong.chart||{}),pixelsPerQuarter:Number($("ppqVisual",d).value)||80},desktopRaw=$("desktopPpqVisual",d).value.trim();
      if(desktopRaw)chart.desktopPixelsPerQuarter=Number(desktopRaw);else delete chart.desktopPixelsPerQuarter;
      const fullMixOnly=!!stems.fullmix&&!stems.base,sourceMode=fullMixOnly?"fullmix":"base";
      Object.assign(draft,{schemaVersion:Math.max(3,Number(draft.schemaVersion)||0),state:"updating",id,title,artist,order,duration,chart,sourceMode,fullMixOnly,playback:{stemOffsetSec:Number(currentSong.playback?.stemOffsetSec)||0,midiMeasureOffset:Number(currentSong.playback?.midiMeasureOffset)||0,midiOffsetSec:Number(currentSong.playback?.midiOffsetSec)||0},stems});
      if(midiPatch)Object.assign(draft,midiPatch);
      else if(!currentSong.midi){draft.midi=null;draft.midiGzip=null;delete draft.midiBytes;delete draft.midiSha256}
      if(draft.mix){draft.mix={...draft.mix};if(!stems.vocals)draft.mix.vocals=0;if(!stems.drums)draft.mix.drums=0}

      const sessionId=`${id}-update-${Date.now()}-${Math.random().toString(36).slice(2,8)}`;
      setProgress(96,"編集準備",d);say("更新内容を編集セッションへ引き継いでいます…","",d);
      await storeSession({sessionId,id,createdAt:Date.now(),mode:"update",draft,originals,midiBlob:changedMidi?new Blob([midiAb],{type:"audio/midi"}):null,uploadItems});
      setProgress(100,"編集準備完了",d);
      say(changedMidi?`${currentSong.midi?"MIDIを差し替え":"MIDIを追加"}しました。Timing Correctionでタイミングを再確認してください。`:"更新内容を準備しました。","ok",d);
      parent.postMessage({type:"dm-song-editor-ready",token:t,repo:REPO,branch:BRANCH,id,sessionId,at:Date.now(),mode:"update"},location.origin)
    }finally{btn.disabled=false;mainBtn.disabled=false}
  }

  function install(){
    if(installing)return;const d=doc();if(!d?.head||!d.body||!$("publish",d)||$("dmPublisherMode",d))return;installing=true;
    try{
      injectStyle(d);decorateRows(d);const grid=d.querySelector(".grid");if(!grid)return;const panel=d.createElement("section");panel.id="dmPublisherMode";panel.className="panel full dm-mode-panel";panel.innerHTML='<h2>MODE</h2><div class="dm-mode-switch"><button type="button" data-mode="new" class="active">新規登録</button><button type="button" data-mode="update">既存曲を更新</button></div><div id="dmExistingWrap" class="dm-existing-wrap" hidden><label><span>更新する楽曲</span><select id="dmExistingSong"></select></label><p id="dmCurrentNote" class="dm-current-note">登録済み楽曲を読み込み中…</p></div>';grid.insertBefore(panel,grid.firstChild);panel.querySelectorAll("[data-mode]").forEach(b=>b.addEventListener("click",()=>setMode(b.dataset.mode,d)));$("dmExistingSong",d).addEventListener("change",e=>loadSong(e.target.value,d));
      const confirm=d.createElement("section");confirm.id="dmUpdateConfirm";confirm.className="dm-update-confirm";confirm.hidden=true;confirm.innerHTML='<h3>更新内容の確認</h3><ul id="dmUpdateConfirmList"></ul><p id="dmMidiWarning" class="warn" hidden>MIDI変更のため、Timing Correctionを必ず再確認してください。</p><div class="dm-confirm-actions"><button id="dmCancelUpdate" type="button">キャンセル</button><button id="dmConfirmUpdate" type="button" class="primary">この内容で更新</button></div>';const log=$("log",d);log.parentNode.insertBefore(confirm,log);$("dmCancelUpdate",d).addEventListener("click",()=>{confirm.hidden=true});$("dmConfirmUpdate",d).addEventListener("click",()=>{runUpdate(d).catch(e=>{console.error(e);say(e.message||String(e),"bad",d);setProgress(0,"エラー",d)})});$("publish",d).addEventListener("click",e=>{if(mode!=="update")return;e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();showConfirm(d)},true);d.body.classList.add("dm-publisher-new");void loadCatalog(d)
    }finally{installing=false}
  }

  frame.addEventListener("load",()=>setTimeout(install,0));setTimeout(install,350);
})();
