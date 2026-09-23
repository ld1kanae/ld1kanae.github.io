import {chromium} from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const variants=['baseline','hats50','hats55','selective55','binary55'];
const out={schema:1,date:'2026-09-23',experiment:'hat-context-runtime-v54',
  prediction_reads_reference_midi:false,variants,songs:{}};

const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));

for(const song of songs){
  console.log('START',song);
  const row=await page.evaluate(async({song,variants})=>{
    const [{transcribe},{rescoreHatContextV54}]=await Promise.all([
      import('/drumscribe/transcribe.js?v=hat-context-v54'),
      import('/drumscribe/hat-context-v54.js?v=hat-context-v54')
    ]);
    const ac=new AudioContext();
    const resp=await fetch('/DruMaster/songs/'+song+'/drums.mp3');
    if(!resp.ok)throw Error(song+': '+resp.status);
    const drums=await ac.decodeAudioData(await resp.arrayBuffer());
    const tr=await transcribe(drums,()=>{},{hatSequenceVariant:'off'});
    const result={};
    for(const name of variants){
      let events=tr.events,info={enabled:false,variant:'baseline'};
      if(name!=='baseline'){
        const rr=await rescoreHatContextV54(drums,tr.events,name);
        events=rr.events;info=rr.info;
      }
      result[name]={
        bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,info,
        events:events.map(e=>({time:e.time,note:({kick:36,snare:38,hat:42,open_hat:46,pedal_hat:44,tom:45,crash:49,ride:51})[e.group]||e.note,group:e.group,
          hatContextProbability:e.hatContextProbability}))
      };
    }
    return result;
  },{song,variants});
  out.songs[song]=row;
  console.log('DONE',song,Object.fromEntries(Object.entries(row).map(([k,v])=>[k,{
    c:v.events.filter(e=>e.note===42).length,o:v.events.filter(e=>e.note===46).length,r:v.events.filter(e=>e.note===51).length,changed:v.info?.changed||0
  }])));
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-hat-context-runtime-predictions-v54.json',JSON.stringify(out,null,2)+'\n');
