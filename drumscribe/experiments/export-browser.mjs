// Run the actual Web transcription module against the untouched MP3 files.
// Node has no AudioBuffer, so ffmpeg supplies the same 11,025 Hz mono samples.
// MIDI/chart files are never accessed by this exporter.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {transcribe} from '../transcribe.js';
import {midiFile} from '../midi.js';

const project=path.dirname(fileURLToPath(import.meta.url));
const data=process.argv[2]||'data',out=process.argv[3]||path.join(project,'generated-v2');
fs.mkdirSync(out,{recursive:true});
const reference=JSON.parse(fs.readFileSync(path.join(project,'..','templates.json'),'utf8'));
globalThis.fetch=async()=>({ok:true,json:async()=>reference});
for(const entry of fs.readdirSync(data,{withFileTypes:true})){
  if(!entry.isDirectory()||!fs.existsSync(path.join(data,entry.name,'song.json')))continue;
  const audio=path.join(data,entry.name,'drums.mp3');
  const result=spawnSync('ffmpeg',['-v','error','-i',audio,'-ac','1','-ar','11025','-f','f32le','-acodec','pcm_f32le','-'],{maxBuffer:100*1024*1024});
  if(result.status!==0)throw Error(result.stderr.toString());
  const raw=result.stdout,values=new Float32Array(raw.buffer,raw.byteOffset,raw.length/4);
  const decoded={duration:values.length/11025,sampleRate:11025,numberOfChannels:1,getChannelData:()=>values};
  const start=Date.now(),events=await transcribe(decoded,()=>{},{});
  fs.writeFileSync(path.join(out,entry.name+'.mid'),midiFile(events));
  console.log(entry.name,events.length,Object.fromEntries(['kick','snare','hat','tom','cymbal','other'].map(g=>[g,events.filter(e=>e.group===g).length])),((Date.now()-start)/1000).toFixed(1)+'s');
}
