// GMD train-only K/S/T bar-phase scorer.
// The learned model ranks 4/4 phase hypotheses only. It never creates,
// deletes, retimes, or reclassifies drum notes.

const MODEL_URL='./models/gmd-kst/bar-phase-discriminative-v1.json';
const GROUP_INDEX={kick:0,snare:1,tom:2};
let modelPromise=null;

function wrap(x,m){x%=m;return x<0?x+m:x;}
function circDistance(a,b,m){const d=Math.abs(a-b)%m;return Math.min(d,m-d);}
async function loadModel(){
  if(!modelPromise)modelPromise=fetch(MODEL_URL).then(async r=>{
    if(!r.ok)throw new Error(`GMD bar-phase model HTTP ${r.status}`);
    const m=await r.json();
    if(!Array.isArray(m.weights)||m.weights.length!==48)throw new Error('Invalid GMD bar-phase model');
    return m;
  });
  return modelPromise;
}
function scorePhase(events,bpm,phase,model){
  const beat=60/bpm,bar=4*beat,step=beat/4;
  const bars=new Map(),counts=new Map();
  for(const e of events){
    const gi=GROUP_INDEX[e.group];
    if(gi===undefined||!Number.isFinite(e.time))continue;
    const rel=e.time-phase;
    const bi=Math.floor(rel/bar);
    const pos=rel-bi*bar;
    const slot=Math.round(pos/step)%16;
    let x=bars.get(bi);
    if(!x){x=new Uint8Array(48);bars.set(bi,x);}
    x[gi*16+slot]=1;
    counts.set(bi,(counts.get(bi)||0)+1);
  }
  let total=0,used=0;
  for(const [bi,x] of bars){
    if((counts.get(bi)||0)<2)continue;
    let occupied=0,s=Number(model.intercept)||0;
    for(let i=0;i<48;i++)if(x[i]){occupied++;s+=Number(model.weights[i])||0;}
    if(occupied<2)continue;
    total+=s;used++;
  }
  return {score:used?total/used:-Infinity,windows:used};
}

export async function estimateGmdBarPhase(events,bpm,{searchSteps=512,minMargin=.55,minCoverage=.55}={}){
  if(!(bpm>=50&&bpm<=220))return {enabled:false,accepted:false,reason:'bpm-out-of-range'};
  const kst=(events||[]).filter(e=>GROUP_INDEX[e.group]!==undefined&&Number.isFinite(e.time));
  if(kst.length<24)return {enabled:false,accepted:false,reason:'too-few-kst-events'};
  let model;
  try{model=await loadModel();}catch(err){
    return {enabled:false,accepted:false,reason:'model-load-failed',error:String(err?.message||err)};
  }
  const beat=60/bpm,bar=4*beat;
  const start=Math.min(...kst.map(e=>e.time)),end=Math.max(...kst.map(e=>e.time));
  const expectedBars=Math.max(1,Math.floor((end-start)/bar)+1);
  const rows=[];
  const steps=Math.max(64,Math.min(1024,Math.round(searchSteps)||512));
  for(let i=0;i<steps;i++){
    const phase=bar*i/steps;
    const r=scorePhase(kst,bpm,phase,model);
    rows.push({phaseSec:phase,score:r.score,windows:r.windows});
  }
  rows.sort((a,b)=>b.score-a.score);
  const best=rows[0];
  if(!best||!Number.isFinite(best.score))return {enabled:true,accepted:false,reason:'no-score',model:model.version};
  const minSep=beat*.65;
  const runner=rows.find(r=>circDistance(r.phaseSec,best.phaseSec,bar)>=minSep)||rows[1]||best;
  const margin=best.score-runner.score;
  const coverage=Math.min(1,best.windows/expectedBars);
  const accepted=best.windows>=8&&coverage>=minCoverage&&margin>=minMargin;
  return {
    enabled:true,
    accepted,
    model:model.version,
    hypothesis:model.selected_hypothesis,
    phaseSec:wrap(best.phaseSec,bar),
    score:best.score,
    margin,
    coverage,
    windows:best.windows,
    minMargin,
    minCoverage,
    runnerUp:{phaseSec:wrap(runner.phaseSec,bar),score:runner.score},
    officialHeldout:model.official_heldout||null,
  };
}
