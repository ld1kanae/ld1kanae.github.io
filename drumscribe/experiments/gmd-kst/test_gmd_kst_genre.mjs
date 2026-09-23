import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {inferGenreMixture} from '../../gmd-kst-genre.js';

const knowledge=JSON.parse(await readFile(
  new URL('../../models/gmd-kst/knowledge-v1.json',import.meta.url),'utf8'
));
const genres=knowledge.aggregates.genre;
let correct=0,total=0;
for(const [genre,agg] of Object.entries(genres)){
  const slots=16,phase={},hits={};
  for(const group of ['kick','snare','tom']){
    const counts=agg.phase_16th_counts?.[group]||{};
    const row=Array.from({length:slots},(_,i)=>Number(counts[String(i)]||0));
    const sum=row.reduce((a,b)=>a+b,0)||1;
    phase[group]=row.map(x=>x/sum);
    hits[group]=Number(agg.hits?.[group]||0);
  }
  const h=[hits.kick,hits.snare,hits.tom],hs=h.reduce((a,b)=>a+b,0)||1;
  const profile={
    hits,
    total:Math.min(96,hs),
    phase,
    composition:h.map(x=>x/hs),
    slotsPerBar:slots,
    approxBars:16,
    hasGrid:true,
  };
  const out=inferGenreMixture(knowledge,profile,{topK:4,temperature:.08});
  total++;
  if(out.ranking[0]?.genre===genre)correct++;
  assert.equal(out.ranking[0]?.genre,genre,`self profile should rank ${genre} first`);
  const sum=Object.values(out.weights).reduce((a,b)=>a+b,0);
  assert.ok(Math.abs(sum-1)<1e-9);
}
assert.equal(correct,total);
console.log(JSON.stringify({selfProfileTop1:`${correct}/${total}`,genres:total},null,2));
