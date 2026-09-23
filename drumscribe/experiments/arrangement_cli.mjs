import {spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {analyzeSections} from '../arrangement/index.js';

const [,,inputPath,optionsPath] = process.argv;
if(!inputPath) throw new Error('usage: node arrangement_cli.mjs <audio> [options.json]');
const options=optionsPath?JSON.parse(readFileSync(optionsPath,'utf8')):{};
const rate=Math.max(2000,Math.min(44100,Number(options.analysisSampleRate)||8000));
const p=spawnSync('ffmpeg',['-v','error','-i',inputPath,'-ac','1','-ar',String(rate),'-f','f32le','-acodec','pcm_f32le','-'],{maxBuffer:64*1024*1024});
if(p.status!==0) throw new Error(`ffmpeg failed: ${p.stderr?.toString()||p.status}`);
const buf=p.stdout;
const samples=new Float32Array(buf.buffer,buf.byteOffset,Math.floor(buf.byteLength/4));
const result=analyzeSections(samples,{...options,sampleRate:rate});
const compact={
  duration:result.duration,
  boundaries:result.boundaries,
  sections:result.sections.map(({index,startSec,endSec,duration,group,label,occurrence,repeatSimilarity,vector})=>({index,startSec,endSec,duration,group,label,occurrence,repeatSimilarity,vector})),
  featureSchema:result.featureSchema,
  method:result.method,
};
process.stdout.write(JSON.stringify(compact));
