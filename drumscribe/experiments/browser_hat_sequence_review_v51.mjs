import {chromium} from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const variants=['off','inversion-articulation','inversion-metal-grid','inversion-guarded-rescue'];
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));
const output={schema:1,date:'2026-09-23',experiment:'hat-sequence-review-v51',predictionReadsReferenceMidi:false,variants,songs:{}};
for(const song of songs){
  console.log('START',song);
  output.songs[song]=await page.evaluate(async({song,variants})=>{
    const [{transcribe},{repairAlternatingHiHats}]=await Promise.all([
      import('/drumscribe/transcribe.js?v=hat-sequence-review-v51'),
      import('/drumscribe/hat-sequence.js?v=hat-sequence-review-v51')
    ]);
    const ac=new AudioContext();
    const response=await fetch('/DruMaster/songs/'+song+'/drums.mp3');
    if(!response.ok)throw Error(song+': drums '+response.status);
    const decoded=await ac.decodeAudioData(await response.arrayBuffer());
    const tr=await transcribe(decoded,()=>{},{hatSequenceVariant:'off',diagnosticHatSequence:true});
    if(!tr.hatSequenceDebug)throw Error(song+': diagnostic payload missing');
    const internal=tr.hatSequenceDebug.events,broad=tr.hatSequenceDebug.broadMetal;
    const noteOf={kick:36,snare:38,hat:42,open_hat:46,pedal_hat:44,tom:45,crash:49,ride:51};
    const serialize=xs=>xs.filter(e=>noteOf[e.group]).map(e=>({time:e.time,note:noteOf[e.group],group:e.group})).sort((a,b)=>a.time-b.time||a.note-b.note);
    const rows={off:{events:serialize(internal),info:{enabled:false,variant:'off'}}};
    for(const variant of variants.slice(1)){
      const rr=await repairAlternatingHiHats(decoded,internal,broad,tr.bpm,tr.barPhaseSec,variant);
      rows[variant]={events:serialize(rr.events),info:rr.info};
    }
    return {bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,numerator:tr.numerator||4,denominator:tr.denominator||4,
      openHatInfo:tr.adtofInfo?.openHat||null,rows};
  },{song,variants});
  console.log('DONE',song,Object.fromEntries(Object.entries(output.songs[song].rows).map(([k,v])=>[k,v.info])));
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-hat-sequence-predictions-v51.json',JSON.stringify(output,null,2)+'\n');
