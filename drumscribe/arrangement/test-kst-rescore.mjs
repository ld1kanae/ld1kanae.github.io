import assert from 'node:assert/strict';
import {rescoreKstByArrangement,arrangementKstPolicyV46R1} from './index.js';

const sections=[
  {index:0,startSec:0,endSec:8,duration:8,group:'A',label:'A',occurrence:1,repeatSimilarity:1},
  {index:1,startSec:8,endSec:16,duration:8,group:'A',label:"A'",occurrence:2,repeatSimilarity:.96},
];
const slotPrior={lift:{
  kick:new Array(16).fill(1),
  snare:new Array(16).fill(1),
  tom:new Array(16).fill(1),
}};
slotPrior.lift.snare[8]=1.7;

const baseline=[
  {time:9,note:38,group:'snare',velocity:90},
  {time:1.01,note:42,group:'hat',velocity:80},
];
const diagnostics={kstCandidates:{
  kick:[],
  snare:[
    {time:1,group:'snare',score:.8,confidence:.8},
    {time:3,group:'snare',score:1.3,confidence:1.2},
  ],
  tom:[],
}};

const accepted=rescoreKstByArrangement(baseline,diagnostics,{sections},{
  bpm:120,numerator:4,denominator:4,slotPrior,
});
assert.equal(accepted.additions.length,1);
assert.equal(accepted.additions[0].group,'snare');
assert(Math.abs(accepted.additions[0].time-1)<1e-9);
assert.equal(accepted.additions[0].arrangementFamily,'A');
assert.equal(accepted.info.rejectedHand,0);

// Two existing hand hits at the target time must block a third hand event.
const blocked=rescoreKstByArrangement(
  [...baseline,{time:1.02,note:51,group:'ride',velocity:80}],
  diagnostics,{sections},
  {bpm:120,numerator:4,denominator:4,slotPrior}
);
assert.equal(blocked.additions.length,0);
assert.equal(blocked.info.rejectedHand,1);

const residualDiagnostics={kstCandidates:{
  kick:[],
  snare:[{time:5,group:'snare',score:.22,confidence:.70,egmdProbability:.96,egmdModelThreshold:.67}],
  tom:[],
}};
const fixedResidual=rescoreKstByArrangement(baseline,residualDiagnostics,{sections},{
  bpm:120,numerator:4,denominator:4,slotPrior,
});
assert.equal(fixedResidual.additions.length,0);

const residualAccepted=rescoreKstByArrangement(baseline,residualDiagnostics,{sections},{
  bpm:120,numerator:4,denominator:4,slotPrior,policy:arrangementKstPolicyV46R1,
});
assert.equal(residualAccepted.additions.length,1);
assert.equal(residualAccepted.additions[0].egmdResidualRescued,true);
assert.equal(residualAccepted.info.acceptedEgmdResidual,1);

const residualLowProbability=rescoreKstByArrangement(baseline,{kstCandidates:{
  kick:[],snare:[{time:5,group:'snare',score:.22,confidence:.70,egmdProbability:.90,egmdModelThreshold:.67}],tom:[]
}},{sections},{
  bpm:120,numerator:4,denominator:4,slotPrior,policy:arrangementKstPolicyV46R1,
});
assert.equal(residualLowProbability.additions.length,0);

console.log(JSON.stringify({
  accepted:accepted.additions.map(e=>({time:e.time,group:e.group,label:e.arrangementLabel})),
  residualAccepted:residualAccepted.additions.map(e=>({time:e.time,group:e.group,p:e.egmdProbability,lift:e.gmdSlotLift})),
  rejectedHand:blocked.info.rejectedHand,
}));
