import {chromium} from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));
const out={schema:1,date:'2026-09-24',experiment:'hat-fusion-candidates-v60',
  predictionReadsReferenceMidi:false,reviewSpecificInputsUsed:false,songs:{}};

for(const song of songs){
  console.log('START',song);
  out.songs[song]=await page.evaluate(async song=>{
    const [{transcribe},{rescoreHatContextGeneralV59}]=await Promise.all([
      import('/drumscribe/transcribe.js?v=hat-fusion-v60'),
      import('/drumscribe/hat-context-v57.js?v=hat-fusion-v60')
    ]);
    const ac=new AudioContext(),r=await fetch('/DruMaster/songs/'+song+'/drums.mp3');
    if(!r.ok)throw Error(song+': '+r.status);
    const decoded=await ac.decodeAudioData(await r.arrayBuffer());
    const tr=await transcribe(decoded,()=>{},{hatSequenceVariant:'off'});
    const rr=await rescoreHatContextGeneralV59(decoded,tr.events,'score-only');
    return {
      bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,
      events:rr.events.map(e=>({
        time:e.time,note:e.note,group:e.group,
        score:Number(e.score)||0,confidence:Number(e.confidence)||0,
        openHatProbability:Number.isFinite(Number(e.openHatProbability))?Number(e.openHatProbability):null,
        openHatBaseProbability:Number.isFinite(Number(e.openHatBaseProbability))?Number(e.openHatBaseProbability):null,
        hatContextProbability:Number.isFinite(Number(e.hatContextProbability))?Number(e.hatContextProbability):null,
        rideRoundedToHat:Boolean(e.rideRoundedToHat),
        hatContextRideRescue:Boolean(e.hatContextRideRescue)
      })).sort((a,b)=>a.time-b.time||a.note-b.note)
    };
  },song);
  console.log('DONE',song,out.songs[song].events.length);
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-hat-fusion-candidates-v60.json',JSON.stringify(out,null,2)+'\n');
