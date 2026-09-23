// rerun after transcribe syntax fix
import {chromium} from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const variants=[
  {name:'baseline'},
  {name:'v57-min24-p99',threshold:.99,minRideCandidates:24},
  {name:'v57-min16-p99',threshold:.99,minRideCandidates:16},
  {name:'v57-min24-p98',threshold:.98,minRideCandidates:24},
];
const out={schema:1,date:'2026-09-23',experiment:'hat-context-global-v57',
  prediction_reads_reference_midi:false,
  note:'Portable global synchronized-corpus model. No song identity or reference MIDI is used by runtime rescue.',
  variants,songs:{}};

const browser=await chromium.launch({headless:true});
const page=await browser.newPage();page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));

for(const song of songs){
  console.log('START',song);
  const row=await page.evaluate(async({song,variants})=>{
    const [{transcribe},{rescueRideOpenV57}]=await Promise.all([
      import('/drumscribe/transcribe.js?v=hat-context-global-v57'),
      import('/drumscribe/hat-context-v57.js?v=hat-context-global-v57')
    ]);
    const ac=new AudioContext(),resp=await fetch('/DruMaster/songs/'+song+'/drums.mp3');
    if(!resp.ok)throw Error(song+': '+resp.status);
    const drums=await ac.decodeAudioData(await resp.arrayBuffer());
    const tr=await transcribe(drums,()=>{});
    const result={};
    for(const cfg of variants){
      let events=tr.events,info={enabled:false,variant:'baseline'};
      if(cfg.name!=='baseline'){
        const rr=await rescueRideOpenV57(drums,tr.events,cfg);
        events=rr.events;info=rr.info;
      }
      result[cfg.name]={
        bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,info,
        events:events.map(e=>({
          time:e.time,note:e.note,group:e.group,
          hatContextProbability:e.hatContextProbability,
          hatContextRideRescue:Boolean(e.hatContextRideRescue)
        }))
      };
    }
    return result;
  },{song,variants});
  out.songs[song]=row;
  console.log('DONE',song,Object.fromEntries(Object.entries(row).map(([k,v])=>[k,{
    ride:v.events.filter(e=>e.group==='ride').length,
    open:v.events.filter(e=>e.group==='open_hat').length,
    changed:v.info?.changed||0,
    enabled:v.info?.enabled||false
  }])));
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-hat-context-global-predictions-v57.json',JSON.stringify(out,null,2)+'\n');
