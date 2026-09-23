import {chromium} from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const out='drumscribe/experiments/results-arrangement-kst-candidates-v44.json';

const modes={
  conservative:{frameSec:.75,hopSec:.375,contextSec:6,minSectionSec:10,noveltyStd:.90,maxSections:18},
  balanced:{frameSec:.75,hopSec:.375,contextSec:4.5,minSectionSec:7,noveltyStd:.72,maxSections:24},
  sensitive:{frameSec:.75,hopSec:.375,contextSec:3,minSectionSec:6,noveltyStd:.55,maxSections:28},
};

const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));

const result={
  schema:1,
  date:'2026-09-23',
  experiment:'arrangement-kst-candidates-v44',
  prediction_reads_reference_midi:false,
  note:'Reference chart.mid is not loaded in this browser stage. A/A-prime labels are structural families only. Diagnostic K/S/T candidates include frozen E-GMD v4 acoustic probabilities.',
  modes,
  songs:{}
};

for(const song of songs){
  console.log('START',song);
  const row=await page.evaluate(async({song,modes})=>{
    const [{transcribe},{analyzeSections}]=await Promise.all([
      import('/drumscribe/transcribe.js?v=arrangement-kst-v44'),
      import('/drumscribe/arrangement/index.js?v=arrangement-kst-v44')
    ]);
    const ac=new AudioContext();
    async function decode(url){
      const r=await fetch(url);
      if(!r.ok)throw Error(url+': HTTP '+r.status);
      return ac.decodeAudioData(await r.arrayBuffer());
    }
    const [drums,offvocal]=await Promise.all([
      decode('/DruMaster/songs/'+song+'/drums.mp3'),
      decode('/DruMaster/songs/'+song+'/offvocal.mp3')
    ]);
    const tr=await transcribe(drums,()=>{},{diagnosticKst:true});
    const analyses={};
    for(const [name,params] of Object.entries(modes)){
      const a=analyzeSections(offvocal,{
        analysisSampleRate:8000,
        bpm:tr.bpm,
        barPhaseSec:tr.barPhaseSec,
        numerator:tr.numerator||4,
        denominator:tr.denominator||4,
        ...params
      });
      analyses[name]={
        duration:a.duration,
        boundaries:a.boundaries,
        sections:a.sections.map(s=>({
          index:s.index,startSec:s.startSec,endSec:s.endSec,duration:s.duration,
          group:s.group,label:s.label,occurrence:s.occurrence,
          repeatSimilarity:s.repeatSimilarity
        }))
      };
    }
    const keepKst=(tr.events||[]).filter(e=>e.note===36||e.note===38||e.note===45).map(e=>({
      time:e.time,note:e.note,group:e.group,velocity:e.velocity
    }));
    const diagnostic=tr.diagnostics||{};
    return {
      bpm:tr.bpm,
      barPhaseSec:tr.barPhaseSec,
      numerator:tr.numerator||4,
      denominator:tr.denominator||4,
      tempoSource:tr.tempoInfo?.source||null,
      barPhaseSource:tr.barPhaseInfo?.source||null,
      finalKst:diagnostic.finalKst||keepKst,
      candidates:diagnostic.kstCandidates||null,
      egmdSnareSupport:diagnostic.egmdSnareSupport||[],
      analyses,
      adtofSummary:tr.adtofInfo?{
        enabled:tr.adtofInfo.enabled,
        counts:tr.adtofInfo.counts,
        structuralPriority:tr.adtofInfo.structuralPriority
      }:null
    };
  },{song,modes});
  result.songs[song]=row;
  console.log('DONE',song,
    'KST',row.finalKst.length,
    'candidates',Object.fromEntries(Object.entries(row.candidates||{}).map(([k,v])=>[k,v.length])),
    'families',Object.fromEntries(Object.entries(row.analyses).map(([k,v])=>[k,v.sections.map(s=>s.label).join(' ')]))
  );
}
await browser.close();
await fs.writeFile(out,JSON.stringify(result,null,2)+'\n');
console.log(out);
