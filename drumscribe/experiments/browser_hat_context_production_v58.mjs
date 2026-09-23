import {chromium} from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const variants=['off','production'];
const out={schema:1,date:'2026-09-24',experiment:'hat-context-production-v58',
  prediction_reads_reference_midi:false,
  note:'Direct fresh Chromium comparison of production wiring vs identical runtime with hatContextVariant=off.',
  variants,songs:{}};

const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));

for(const song of songs){
  console.log('START',song);
  const row=await page.evaluate(async({song,variants})=>{
    const {transcribe}=await import('/drumscribe/transcribe.js?v=hat-context-production-v58');
    const ac=new AudioContext();
    const resp=await fetch('/DruMaster/songs/'+song+'/drums.mp3');
    if(!resp.ok)throw Error(song+': '+resp.status);
    const drums=await ac.decodeAudioData(await resp.arrayBuffer());
    const result={};
    for(const name of variants){
      const tr=await transcribe(drums,()=>{}, name==='off'?{hatContextVariant:'off'}:{});
      result[name]={
        bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,
        info:tr.info?.hatContextV57||tr.adtofInfo?.hatContextV57||null,
        events:tr.events.map(e=>({time:e.time,note:e.note,group:e.group}))
      };
      console.log(song,name,result[name].info);
    }
    return result;
  },{song,variants});
  out.songs[song]=row;
  console.log('DONE',song,Object.fromEntries(Object.entries(row).map(([k,v])=>[k,{
    closed:v.events.filter(e=>e.note===42).length,
    open:v.events.filter(e=>e.note===46).length,
    ride:v.events.filter(e=>e.note===51).length
  }])));
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-hat-context-production-predictions-v58.json',JSON.stringify(out,null,2)+'\n');
