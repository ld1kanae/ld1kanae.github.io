import {chromium} from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));
const out={schema:1,date:'2026-09-24',experiment:'hat-sync-candidate-promote-v67',
  predictionReadsReferenceMidi:false,preselectedFromSyncLoocv:{openThreshold:.55,allowDemotion:false},songs:{}};
for(const song of songs){
  console.log('START',song);
  out.songs[song]=await page.evaluate(async song=>{
    const [{transcribe},{rescoreHatSyncCandidateV66}]=await Promise.all([
      import('/drumscribe/transcribe.js?v=hat-sync-promote-v67'),
      import('/drumscribe/hat-context-v57.js?v=hat-sync-promote-v67')
    ]);
    const ac=new AudioContext(),r=await fetch('/DruMaster/songs/'+song+'/drums.mp3');
    if(!r.ok)throw Error(song+': '+r.status);
    const decoded=await ac.decodeAudioData(await r.arrayBuffer());
    const tr=await transcribe(decoded,()=>{},{hatSequenceVariant:'off',hatFusionVariant:'off',hatSyncCandidateVariant:'off'});
    const rr=await rescoreHatSyncCandidateV66(decoded,tr.events,{enabled:true,allowDemotion:false,openThreshold:.55});
    const slim=events=>events.map(e=>({time:e.time,note:e.note,group:e.group}))
      .sort((a,b)=>a.time-b.time||a.note-b.note);
    const result={off:{bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,events:slim(tr.events),info:{enabled:false}},
      on:{bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,events:slim(rr.events),info:rr.info}};
    await ac.close();return result;
  },song);
  console.log('DONE',song,out.songs[song].on.info);
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-hat-sync-candidate-promote-predictions-v67.json',JSON.stringify(out,null,2)+'\n');
