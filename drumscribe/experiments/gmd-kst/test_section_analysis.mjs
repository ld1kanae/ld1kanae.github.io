import assert from 'node:assert/strict';
import {analyzeSections} from '../../section-analysis.js';

const sr=8000,duration=30,samples=new Float32Array(sr*duration);
for(let i=0;i<samples.length;i++){
  const t=i/sr;
  let f=120,amp=.25;
  if(t>=10&&t<20){f=1200;amp=.42;}
  // A -> B -> A, with a weak second harmonic so timbre is not a pure-level cue.
  samples[i]=amp*Math.sin(2*Math.PI*f*t)+.06*Math.sin(2*Math.PI*f*2*t);
}
const result=analyzeSections(samples,{
  sampleRate:sr,
  frameSec:.5,
  hopSec:.25,
  contextSec:2,
  minSectionSec:5,
  noveltyStd:.25,
  maxSections:6,
});

const near=(target,tol=2.0)=>result.boundaries.some(x=>Math.abs(x-target)<=tol);
assert.ok(near(10),`expected section boundary near 10s, got ${result.boundaries}`);
assert.ok(near(20),`expected section boundary near 20s, got ${result.boundaries}`);
assert.ok(result.sections.length>=3,`expected >=3 sections, got ${result.sections.length}`);

const first=result.sections.find(s=>s.startSec<2);
const last=result.sections[result.sections.length-1];
assert.ok(first&&last);
assert.equal(first.group,last.group,'repeated A sections should share a structural group');

console.log(JSON.stringify({
  boundaries:result.boundaries,
  groups:result.sections.map(s=>s.group),
  method:result.method,
},null,2));
