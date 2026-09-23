import {chromium} from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const variants=['off','closed-open-995','closed-open-990','closed-open-highgap','bidirectional-extreme'];
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));
const out={schema:1,date:'2026-09-24',experiment:'hat-context-general-v59',predictionReadsReferenceMidi:false,variants,songs:{}};

for(const song of songs){
  console.log('START',song);
  out.songs[song]=await page.evaluate(async({song,variants})=>{
    const [{transcribe},{rescoreHatContextGeneralV59}]=await Promise.all([
      import('/drumscribe/transcribe.js?v=hat-general-v59'),
      import('/drumscribe/hat-context-v57.js?v=hat-general-v59')
    ]);
    const ac=new AudioContext(),r=await fetch('/DruMaster/songs/'+song+'/drums.mp3');
    if(!r.ok)throw Error(song+': '+r.status);
    const decoded=await ac.decodeAudioData(await r.arrayBuffer());
    // Review-trained sequence repair is explicitly OFF. Existing generic v58
    // Ride rescue remains on because it is already production-validated.
    const tr=await transcribe(decoded,()=>{},{hatSequenceVariant:'off'});
    const rows={};
    for(const variant of variants){
      let events=tr.events,info={enabled:false,variant:'off'};
      if(variant!=='off'){
        const rr=await rescoreHatContextGeneralV59(decoded,tr.events,variant);
        events=rr.events;info=rr.info;
      }
      rows[variant]={
        info,
        events:events.map(e=>({time:e.time,note:e.note,group:e.group})).sort((a,b)=>a.time-b.time||a.note-b.note)
      };
    }
    return {bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,rows,
      kstCounts:Object.fromEntries(['kick','snare','tom'].map(g=>[g,tr.events.filter(e=>e.group===g).length]))};
  },{song,variants});
  console.log('DONE',song,Object.fromEntries(variants.map(v=>[v,out.songs[song].rows[v].info])));
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-hat-context-general-predictions-v59.json',JSON.stringify(out,null,2)+'\n');
