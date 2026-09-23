import {execFileSync} from 'node:child_process';
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {analyzeSections} from '../arrangement/index.js';

const HERE=dirname(fileURLToPath(import.meta.url));
const ROOT=resolve(HERE,'../..');
const SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const OUT=resolve(HERE,'results-arrangement-structure-v37.json');

const MODES={
  conservative:{frameSec:.75,hopSec:.375,contextSec:6,minSectionSec:10,noveltyStd:.90,maxSections:18},
  balanced:{frameSec:.75,hopSec:.375,contextSec:4.5,minSectionSec:7,noveltyStd:.72,maxSections:24},
  sensitive:{frameSec:.75,hopSec:.375,contextSec:3,minSectionSec:6,noveltyStd:.55,maxSections:28},
};

function decodeMono(path,sampleRate=8000){
  const raw=execFileSync('ffmpeg',[
    '-v','error','-i',path,'-ac','1','-ar',String(sampleRate),
    '-f','f32le','-acodec','pcm_f32le','-'
  ],{maxBuffer:96*1024*1024});
  return new Float32Array(raw.buffer,raw.byteOffset,Math.floor(raw.byteLength/4));
}

function strip(result){
  return {
    duration:result.duration,
    boundaries:result.boundaries,
    method:result.method,
    featureSchema:result.featureSchema,
    sections:result.sections.map(s=>({
      index:s.index,
      startSec:s.startSec,
      endSec:s.endSec,
      duration:s.duration,
      group:s.group,
      label:s.label,
      occurrence:s.occurrence,
      repeatSimilarity:s.repeatSimilarity,
    })),
  };
}

const output={
  schema:1,
  date:'2026-09-23',
  experiment:'arrangement-structure-v37',
  source:'DruMaster/songs/<song>/offvocal.mp3',
  semantic_labels:false,
  note:'A/B/C are structural families only; A-prime means a repeated occurrence of family A.',
  modes:MODES,
  songs:{},
};

for(const id of SONGS){
  const folder=resolve(ROOT,'DruMaster','songs',id);
  const meta=JSON.parse(readFileSync(resolve(folder,'song.json'),'utf8'));
  const source=resolve(folder,'offvocal.mp3');
  const sampleRate=8000;
  const samples=decodeMono(source,sampleRate);
  const numerator=Number(meta?.timeSignature?.numerator)||4;
  const denominator=Number(meta?.timeSignature?.denominator)||4;
  const bpm=Number(meta?.bpm)||120;
  output.songs[id]={
    bpm,numerator,denominator,
    audio:'offvocal.mp3',
    analyses:{},
  };
  for(const [mode,params] of Object.entries(MODES)){
    const result=analyzeSections(samples,{
      sampleRate,bpm,numerator,denominator,...params,
    });
    output.songs[id].analyses[mode]=strip(result);
  }
  const b=output.songs[id].analyses.balanced;
  console.log(id,'balanced sections',b.sections.length,'labels',b.sections.map(x=>x.label).join(' '));
}

mkdirSync(dirname(OUT),{recursive:true});
writeFileSync(OUT,JSON.stringify(output,null,2)+'\n');
console.log(OUT);
