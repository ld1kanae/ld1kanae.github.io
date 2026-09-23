import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const variants={
  baseline:null,
  V39_A_runtime:{
    minConfidence:.72,minSupportRate:.50,minFamilyQuality:.90,minGmdLift:0,
    rejectPostfilteredHandCandidate:true,enforceTwoHands:true,
  },
  V39_D_runtime:{
    minConfidence:.50,minSupportRate:.50,minFamilyQuality:.90,minGmdLift:.80,
    rejectPostfilteredHandCandidate:true,enforceTwoHands:true,
  },
  V39_D_no_hand_guard:{
    minConfidence:.50,minSupportRate:.50,minFamilyQuality:.90,minGmdLift:.80,
    rejectPostfilteredHandCandidate:true,enforceTwoHands:false,
  },
};
const outDir='drumscribe/experiments/generated-arrangement-kst-v40';
await fs.mkdir(outDir,{recursive:true});
for(const name of Object.keys(variants))await fs.mkdir(path.join(outDir,name),{recursive:true});

const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));

for(const song of songs){
  console.log('START',song);
  const row=await page.evaluate(async({song,variants})=>{
    const [
      {transcribe},
      {analyzeSections,rescoreKstByArrangement},
      {buildRhythmGrid},
      {midiFile},
      {inferBars,parseBeatThis},
    ]=await Promise.all([
      import('/drumscribe/transcribe.js?v=arrangement-runtime-v40'),
      import('/drumscribe/arrangement/index.js?v=arrangement-runtime-v40'),
      import('/drumscribe/rhythm-grid.js?v=arrangement-runtime-v40'),
      import('/drumscribe/midi.js?v=arrangement-runtime-v40'),
      import('/drumscribe/meter.js?v=arrangement-runtime-v40'),
    ]);
    const priorResponse=await fetch('/drumscribe/models/gmd-kst/slot-prior-v1.json?v=arrangement-runtime-v40');
    if(!priorResponse.ok)throw Error('GMD slot prior HTTP '+priorResponse.status);
    const slotPrior=await priorResponse.json();

    const ac=new AudioContext();
    async function decode(url){
      const r=await fetch(url);
      if(!r.ok)throw Error(url+': HTTP '+r.status);
      return ac.decodeAudioData(await r.arrayBuffer());
    }
    const [drums,offvocal]=await Promise.all([
      decode('/DruMaster/songs/'+song+'/drums.mp3'),
      decode('/DruMaster/songs/'+song+'/offvocal.mp3'),
    ]);
    const tr=await transcribe(drums,()=>{},{diagnosticKst:true});
    const numerator=Number(tr.numerator)||4,denominator=Number(tr.denominator)||4;
    const arrangement=analyzeSections(offvocal,{
      analysisSampleRate:8000,
      bpm:tr.bpm,
      barPhaseSec:tr.barPhaseSec,
      numerator,
      denominator,
      frameSec:.75,
      hopSec:.375,
      contextSec:3,
      minSectionSec:6,
      noveltyStd:.55,
      maxSections:28,
    });

    let beatData=[];
    if(['arcaround','diamondvirgin','kaiju'].includes(song)){
      const beatFile=song==='arcaround'
        ?'/drumscribe/experiments/beatthis-v17/'+song+'-fullmix.beats'
        :'/drumscribe/experiments/beatthis-v18/'+song+'-fullmix.beats';
      const r=await fetch(beatFile);
      if(r.ok)beatData=parseBeatThis(await r.text());
    }

    const output={
      bpm:tr.bpm,
      barPhaseSec:tr.barPhaseSec,
      numerator,
      denominator,
      tempoInfo:tr.tempoInfo,
      barPhaseInfo:tr.barPhaseInfo,
      arrangement:{
        boundaries:arrangement.boundaries,
        sections:arrangement.sections.map(s=>({
          index:s.index,startSec:s.startSec,endSec:s.endSec,duration:s.duration,
          group:s.group,label:s.label,occurrence:s.occurrence,repeatSimilarity:s.repeatSimilarity
        }))
      },
      variants:{}
    };

    for(const [name,policy] of Object.entries(variants)){
      const rescored=policy
        ?rescoreKstByArrangement(tr.events,tr.diagnostics,arrangement,{
            bpm:tr.bpm,numerator,denominator,slotPrior,policy
          })
        :{events:tr.events.slice(),additions:[],info:{enabled:false,policy:null}};
      const events=rescored.events;
      let meter={bars:[],variableMeterEnabled:false,externalDownbeats:0};
      const beatSec=60/tr.bpm*4/denominator;
      const barSec=beatSec*numerator;
      const rawPhase=Number(tr.barPhaseSec);
      const barPhaseSec=Number.isFinite(rawPhase)?((rawPhase%barSec)+barSec)%barSec:null;
      if(beatData?.downbeats?.length&&Number.isFinite(barPhaseSec)){
        meter=inferBars(events,tr.bpm,barPhaseSec,drums.duration,beatData);
      }
      const grid=buildRhythmGrid(events,tr.bpm,{
        barPhaseSec,numerator,denominator,bars:meter.bars
      });
      const midi=midiFile(events,tr.bpm,{
        barPhaseSec,numerator,denominator,bars:meter.bars,rhythmGrid:grid
      });
      let binary='';
      for(let i=0;i<midi.length;i+=0x4000){
        binary+=String.fromCharCode(...midi.subarray(i,i+0x4000));
      }
      output.variants[name]={
        midiBase64:btoa(binary),
        side:{
          bpm:tr.bpm,
          barPhaseSec,
          beatPhaseSec:tr.beatPhaseSec,
          numerator,denominator,
          exportOffsetSec:grid.exportOffsetSec,
          exportBarPad:grid.barPad,
          barSec,
          rhythmGridInfo:grid.info,
          meterInfo:{
            variableMeterEnabled:meter.variableMeterEnabled,
            externalDownbeats:meter.externalDownbeats,
            threeFourBars:meter.bars.filter(b=>b.numerator===3).length,
          },
          arrangementRescore:rescored.info,
          counts:{
            total:events.length,
            kick:events.filter(e=>e.note===36).length,
            snare:events.filter(e=>e.note===38).length,
            tom:events.filter(e=>e.note===45).length,
          }
        }
      };
    }
    return output;
  },{song,variants});

  for(const [name,v] of Object.entries(row.variants)){
    const dir=path.join(outDir,name);
    await fs.writeFile(path.join(dir,song+'.mid'),Buffer.from(v.midiBase64,'base64'));
    await fs.writeFile(path.join(dir,song+'.json'),JSON.stringify(v.side,null,2)+'\n');
    console.log('VARIANT',song,name,v.side.counts,'rescued',v.side.arrangementRescore?.accepted||0,'handReject',v.side.arrangementRescore?.rejectedHand||0);
  }
  const structure={...row,variants:undefined};
  await fs.writeFile(path.join(outDir,song+'-arrangement.json'),JSON.stringify(structure,null,2)+'\n');
  console.log('DONE',song,row.arrangement.sections.map(s=>s.label).join(' '));
}
await browser.close();
