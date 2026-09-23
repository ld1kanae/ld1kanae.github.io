import {chromium} from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const configs=[
  {name:'base',openHatVariant:'base',arrangement:false},
  {name:'decay',openHatVariant:'decay',arrangement:false},
  {name:'arrangement',openHatVariant:'base',arrangement:true},
  {name:'decay-arrangement',openHatVariant:'decay',arrangement:true},
  {name:'ride-acoustic-arrangement',openHatVariant:'ride-acoustic',arrangement:true},
  {name:'ride-decay-arrangement',openHatVariant:'ride-decay',arrangement:true},
];

const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));

const out={schema:1,date:'2026-09-23',experiment:'openhat-arrangement-v43',
  prediction_reads_reference_midi:false,
  note:"A/A' are structural-family labels from offvocal; chart.mid is not fetched here.",
  configs:{},songs:{}};
for(const c of configs)out.configs[c.name]=c;

for(const song of songs){
  console.log('START',song);
  const row=await page.evaluate(async({song,configs})=>{
    const [{transcribe},{analyzeSections,rescoreHatArticulationByArrangement,arrangementHatPolicyV1}]=await Promise.all([
      import('/drumscribe/transcribe.js?v=openhat-arrangement-v43'),
      import('/drumscribe/arrangement/index.js?v=openhat-arrangement-v43')
    ]);
    const ac=new AudioContext();
    async function decode(url){
      const r=await fetch(url); if(!r.ok)throw Error(url+': HTTP '+r.status);
      return ac.decodeAudioData(await r.arrayBuffer());
    }
    const [drums,offvocal]=await Promise.all([
      decode('/DruMaster/songs/'+song+'/drums.mp3'),
      decode('/DruMaster/songs/'+song+'/offvocal.mp3')
    ]);
    const result={};
    for(const cfg of configs){
      const tr=await transcribe(drums,()=>{},{openHatVariant:cfg.openHatVariant});
      const numerator=Number(tr.numerator)||4,denominator=Number(tr.denominator)||4;
      const arrangement=analyzeSections(offvocal,{
        analysisSampleRate:8000,bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,
        numerator,denominator,frameSec:.75,hopSec:.375,contextSec:3,minSectionSec:6,
        noveltyStd:.55,maxSections:28
      });
      let events=tr.events,arrInfo={enabled:false};
      if(cfg.arrangement){
        const rr=rescoreHatArticulationByArrangement(events,arrangement,{
          bpm:tr.bpm,numerator,denominator,policy:arrangementHatPolicyV1
        });
        events=rr.events; arrInfo=rr.info;
      }
      result[cfg.name]={
        bpm:tr.bpm,barPhaseSec:tr.barPhaseSec,numerator,denominator,
        openHatInfo:tr.adtofInfo?.openHat||null,arrangementHatInfo:arrInfo,
        sections:arrangement.sections.map(s=>({startSec:s.startSec,endSec:s.endSec,group:s.group,label:s.label,occurrence:s.occurrence,repeatSimilarity:s.repeatSimilarity})),
        events:events.map(e=>({time:e.time,note:e.note,group:e.group,
          openHatProbability:e.openHatProbability,openHatBaseProbability:e.openHatBaseProbability,
          rideRoundedToHat:Boolean(e.rideRoundedToHat),arrangementHatRescored:Boolean(e.arrangementHatRescored)}))
      };
    }
    return result;
  },{song,configs});
  out.songs[song]=row;
  console.log('DONE',song,Object.fromEntries(Object.entries(row).map(([k,v])=>[k,{
    hats:v.events.filter(e=>e.note===42||e.note===46).length,
    open:v.events.filter(e=>e.note===46).length,
    ride:v.events.filter(e=>e.note===51).length,
    arrChanged:v.arrangementHatInfo?.changed||0
  }])));
}
await browser.close();
await fs.writeFile('drumscribe/experiments/results-openhat-arrangement-predictions-v43.json',JSON.stringify(out,null,2)+'\n');
