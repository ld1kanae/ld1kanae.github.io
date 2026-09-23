import {readFile,writeFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {analyzeSections} from '../../section-analysis.js';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const sampleRate=8000;
const output={version:'offvocal-sections-v1',sampleRate,songs:{}};

function decode(path){
  const p=spawnSync('ffmpeg',[
    '-v','error','-i',path,
    '-f','f32le','-ac','1','-ar',String(sampleRate),'pipe:1'
  ],{maxBuffer:256*1024*1024});
  if(p.status!==0)throw new Error(`ffmpeg failed for ${path}: ${p.stderr.toString()}`);
  const b=p.stdout;
  return new Float32Array(b.buffer,b.byteOffset,Math.floor(b.byteLength/4));
}

for(const song of songs){
  const path=`DruMaster/songs/${song}/offvocal.mp3`;
  const samples=decode(path);
  const result=analyzeSections(samples,{
    sampleRate,
    frameSec:.75,
    hopSec:.375,
    contextSec:4.5,
    minSectionSec:7,
    noveltyStd:.72,
    maxSections:18,
  });
  output.songs[song]={
    durationSec:result.duration,
    boundaries:result.boundaries,
    sections:result.sections.map(s=>({
      index:s.index,
      startSec:s.startSec,
      endSec:s.endSec,
      duration:s.duration,
      group:s.group,
      repeatSimilarity:s.repeatSimilarity,
    })),
    method:result.method,
  };
  console.log(song,JSON.stringify(output.songs[song]));
}

await writeFile(
  'drumscribe/experiments/gmd-kst/results-offvocal-sections-v1.json',
  JSON.stringify(output,null,2)+'\n'
);
