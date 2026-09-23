import {chromium} from 'playwright';
import fs from 'node:fs/promises';
const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const out={schema:1,date:'2026-09-23',experiment:'hat-context-heldout-v55',
  prediction_reads_reference_midi:false,note:'Each song uses a synchronized-corpus logistic model trained on the other four songs only.',songs:{}};
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));
for(const song of songs){
  console.log('START',song);
  const row=await page.evaluate(async(song)=>{
    const [{transcribe},{scoreHatContextV55}]=await Promise.all([
      import('/drumscribe/transcribe.js?v=hat-context-v55'),
      import('/drumscribe/hat-context-v55.js?v=hat-context-v55')
    ]);
    const ac=new AudioContext(),resp=await fetch('/DruMaster/songs/'+song+'/drums.mp3');
    if(!resp.ok)throw Error(song+': '+resp.status);
    const drums=await ac.decodeAudioData(await resp.arrayBuffer());
    const tr=await transcribe(drums,()=>{},{hatSequenceVariant:'off'});
    const rr=await scoreHatContextV55(drums,tr.events,song);
    return {bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,info:rr.info,
      events:rr.events.map(e=>({time:e.time,note:({kick:36,snare:38,hat:42,open_hat:46,pedal_hat:44,tom:45,crash:49,ride:51})[e.group]||e.note,
        group:e.group,hatContextProbability:e.hatContextProbability}))};
  },song);
  out.songs[song]=row;
  console.log('DONE',song,row.info);
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-hat-context-heldout-predictions-v55.json',JSON.stringify(out,null,2)+'\n');
