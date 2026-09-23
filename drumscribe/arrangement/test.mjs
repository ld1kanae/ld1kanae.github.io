import assert from 'node:assert/strict';
import {analyzeSections,extractSectionFeatures} from './index.js';

const sampleRate=4000;
const duration=24;
const samples=new Float32Array(sampleRate*duration);
for(let i=0;i<samples.length;i++){
  const t=i/sampleRate;
  const block=Math.floor(t/6)%4;
  const freq=(block===0||block===2)?120:900;
  const amp=(block===0||block===2)?.22:.48;
  samples[i]=amp*Math.sin(2*Math.PI*freq*t);
}

const features=extractSectionFeatures(samples,sampleRate,{frameSec:.75,hopSec:.375});
assert(features.rows.length>10);
assert.equal(features.rows.length,features.normalized.length);

const result=analyzeSections(samples,{
  sampleRate,
  frameSec:.75,
  hopSec:.375,
  contextSec:2,
  minSectionSec:4,
  noveltyStd:.5,
  maxSections:8,
});
assert.equal(result.boundaries[0],0);
assert(Math.abs(result.boundaries.at(-1)-duration)<1e-6);
assert.equal(result.sections.length,result.boundaries.length-1);
assert(result.sections.length>=1);
for(const section of result.sections){
  assert(section.endSec>=section.startSec);
  assert(typeof section.group==='string'&&section.group.length>0);
  assert(typeof section.label==='string'&&section.label.length>0);
  assert(Number.isInteger(section.occurrence)&&section.occurrence>=1);
}
assert.deepEqual(result.sections.map(s=>s.group),['A','B','A','B']);
assert.deepEqual(result.sections.map(s=>s.label),['A','B',"A'","B'"]);
assert.deepEqual(result.sections.map(s=>s.occurrence),[1,1,2,2]);
console.log(JSON.stringify({
  method:result.method,
  boundaries:result.boundaries,
  groups:result.sections.map(s=>s.group),
  labels:result.sections.map(s=>s.label),
  occurrences:result.sections.map(s=>s.occurrence),
  featureSchema:result.featureSchema,
}));
