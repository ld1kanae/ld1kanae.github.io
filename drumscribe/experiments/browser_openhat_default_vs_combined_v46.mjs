import {chromium} from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const configs=[
  {name:'default',variant:'decay-rescue'},
  {name:'combined',variant:'ride-open-decay-rescue'},
];
const out={schema:1,date:'2026-09-23',experiment:'openhat-default-vs-combined-v46',
  prediction_reads_reference_midi:false,configs,songs:{}};

const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));

for(const song of songs){
  console.log('START',song);
  const row=await page.evaluate(async({song,configs})=>{
    const {transcribe}=await import('/drumscribe/transcribe.js?v=openhat-v46');
    const ac=new AudioContext();
    const resp=await fetch('/DruMaster/songs/'+song+'/drums.mp3');
    if(!resp.ok)throw Error(song+': '+resp.status);
    const drums=await ac.decodeAudioData(await resp.arrayBuffer());
    const result={};
    for(const cfg of configs){
      const tr=await transcribe(drums,()=>{},{openHatVariant:cfg.variant});
      result[cfg.name]={
        bpm:tr.bpm,
        barPhaseSec:tr.barPhaseSec,
        openHatInfo:tr.adtofInfo?.openHat||null,
        events:(tr.events||[]).map(e=>({time:e.time,note:e.note,group:e.group}))
      };
    }
    return result;
  },{song,configs});
  out.songs[song]=row;
  console.log('DONE',song,Object.fromEntries(Object.entries(row).map(([k,v])=>[k,{
    closed:v.events.filter(e=>e.note===42).length,
    open:v.events.filter(e=>e.note===46).length,
    ride:v.events.filter(e=>e.note===51).length
  }])));
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-openhat-default-vs-combined-predictions-v46.json',JSON.stringify(out,null,2)+'\n');
