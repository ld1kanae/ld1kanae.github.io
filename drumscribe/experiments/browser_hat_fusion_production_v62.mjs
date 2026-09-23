import {chromium} from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));
const out={schema:1,date:'2026-09-24',experiment:'hat-fusion-production-v62',predictionReadsReferenceMidi:false,songs:{}};
for(const song of songs){
  console.log('START',song);
  out.songs[song]=await page.evaluate(async song=>{
    const {transcribe}=await import('/drumscribe/transcribe.js?v=hat-fusion-production-v62');
    const ac=new AudioContext(),r=await fetch('/DruMaster/songs/'+song+'/drums.mp3');
    if(!r.ok)throw Error(song+': '+r.status);
    const decoded=await ac.decodeAudioData(await r.arrayBuffer());
    const pack=(tr)=>({
      bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,
      fusionInfo:tr.adtofInfo?.hatFusionV61||null,
      events:tr.events.map(e=>({time:e.time,note:e.note,group:e.group})).sort((a,b)=>a.time-b.time||a.note-b.note)
    });
    const off=await transcribe(decoded,()=>{},{hatSequenceVariant:'off',hatFusionVariant:'off'});
    const on=await transcribe(decoded,()=>{},{hatSequenceVariant:'off',hatFusionVariant:'acoustic-fusion-v61'});
    return {off:pack(off),on:pack(on)};
  },song);
  console.log('DONE',song,out.songs[song].on.fusionInfo);
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-hat-fusion-production-predictions-v62.json',JSON.stringify(out,null,2)+'\n');
