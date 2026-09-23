import {chromium} from 'playwright';
import fs from 'node:fs/promises';
const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));
const output={schema:1,date:'2026-09-23',experiment:'hat-sequence-runtime-v52',predictionReadsReferenceMidi:false,songs:{}};
for(const song of songs){
  console.log('START',song);
  output.songs[song]=await page.evaluate(async song=>{
    const {transcribe}=await import('/drumscribe/transcribe.js?v=hat-sequence-runtime-v52');
    const ac=new AudioContext(),r=await fetch('/DruMaster/songs/'+song+'/drums.mp3');
    if(!r.ok)throw Error(song+': '+r.status);
    const decoded=await ac.decodeAudioData(await r.arrayBuffer());
    const tr=await transcribe(decoded,()=>{},{});
    return {bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,numerator:tr.numerator||4,denominator:tr.denominator||4,
      hatSequence:tr.adtofInfo?.hatSequence||null,
      events:tr.events.map(e=>({time:e.time,note:e.note,group:e.group})).sort((a,b)=>a.time-b.time||a.note-b.note)};
  },song);
  console.log('DONE',song,output.songs[song].hatSequence);
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-hat-sequence-runtime-predictions-v52.json',JSON.stringify(output,null,2)+'\n');
