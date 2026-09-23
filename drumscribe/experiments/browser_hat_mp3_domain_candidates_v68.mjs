import {chromium} from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));
const out={schema:1,date:'2026-09-24',experiment:'hat-raw-acoustic-candidates-v68',
  predictionReadsReferenceMidi:false,reviewSpecificInputsUsed:false,songs:{}};

for(const song of songs){
  console.log('START',song);
  out.songs[song]=await page.evaluate(async song=>{
    const [{transcribe},{extractHatAcousticFeaturesV63}]=await Promise.all([
      import('/drumscribe/transcribe.js?v=hat-mp3-domain-train-v68'),
      import('/drumscribe/hat-context-v57.js?v=hat-mp3-domain-train-v68')
    ]);
    const ac=new AudioContext(),r=await fetch('/DruMaster/songs/'+song+'/drums.mp3');
    if(!r.ok)throw Error(song+': '+r.status);
    const decoded=await ac.decodeAudioData(await r.arrayBuffer());
    const tr=await transcribe(decoded,()=>{},{hatSequenceVariant:'off',hatFusionVariant:'off'});
    const descriptors=await extractHatAcousticFeaturesV63(decoded,tr.events);
    return {
      bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,
      descriptors,
      events:tr.events.map(e=>({time:e.time,note:e.note,group:e.group})).sort((a,b)=>a.time-b.time||a.note-b.note)
    };
  },song);
  console.log('DONE',song,'desc',out.songs[song].descriptors.length);
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-hat-raw-acoustic-candidates-v68.json',JSON.stringify(out,null,2)+'\n');
