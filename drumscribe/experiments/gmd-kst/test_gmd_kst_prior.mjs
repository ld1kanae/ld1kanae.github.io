import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {gmdKstEvidence} from '../../gmd-kst-prior.js';

const knowledge=JSON.parse(await readFile(
  new URL('../../models/gmd-kst/knowledge-v1.json',import.meta.url),
  'utf8'
));

for(const group of ['kick','snare','tom']){
  const globalOnly=gmdKstEvidence(knowledge,{group,slot:0,slotsPerBar:16});
  assert.ok(globalOnly.multiplier>=.82&&globalOnly.multiplier<=1.18);
  const mixed=gmdKstEvidence(knowledge,{
    group,
    slot:4,
    slotsPerBar:16,
    genreWeights:{rock:.55,pop:.25,funk:.20},
    beatType:'beat',
  });
  assert.ok(mixed.multiplier>=.82&&mixed.multiplier<=1.18);
  assert.ok(mixed.confidence>=0&&mixed.confidence<=1);
  assert.ok(mixed.genres.length>=2);
  console.log(group,JSON.stringify(mixed));
}
