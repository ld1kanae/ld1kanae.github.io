// Arrangement-aware 42/46 articulation rescoring.
//
// This module never creates or removes a hit. It only changes an existing
// closed/open hi-hat articulation when repeated structural-family occurrences
// (A/A'/...) provide strong same-slot support. The acoustic probability comes
// from open-hat.js; chart.mid is never read at runtime.

const DEFAULT_POLICY={
  name:'family-hat-articulation-repeat-v1',
  threshold:.575,
  borderlineRadius:.17,
  strongOpen:.70,
  strongClosed:.40,
  supportToleranceSec:.075,
  minFamilyQuality:.90,
  singleSupportMinQuality:.94,
  singleSupportStrongOpen:.78,
  singleSupportStrongClosed:.30,
  logitWeight:.42,
};

function clamp(x,a,b){return Math.max(a,Math.min(b,x));}
function logit(p){
  const q=clamp(Number(p)||0,1e-5,1-1e-5);
  return Math.log(q/(1-q));
}
function sigmoid(x){return 1/(1+Math.exp(-x));}
function familyQuality(sections,group){
  const family=sections.filter(s=>s.group===group);
  if(family.length<2)return 0;
  const q=family.filter(s=>(Number(s.occurrence)||1)>1)
    .map(s=>Number(s.repeatSimilarity)).filter(Number.isFinite);
  return q.length?q.reduce((a,b)=>a+b,0)/q.length:1;
}
function sectionForTime(sections,time){
  return sections.find(s=>time>=Number(s.startSec)&&time<Number(s.endSec))||null;
}
function slotInfo(time,section,barSec){
  const rel=Math.max(0,time-Number(section.startSec));
  let barIndex=Math.floor(rel/barSec+1e-8);
  const inBar=rel-barIndex*barSec;
  let slot=Math.round(inBar/barSec*16);
  if(slot>=16){barIndex++;slot=0;}
  return {barIndex,slot:clamp(slot,0,15)};
}
function closestHat(events,time,tolerance){
  let best=null,bestD=Infinity;
  for(const e of events){
    if(e.group!=='hat'&&e.group!=='open_hat')continue;
    const d=Math.abs(Number(e.time)-time);
    if(d<=tolerance&&d<bestD){best=e;bestD=d;}
  }
  return best;
}

export function rescoreHatArticulationByArrangement(events,arrangement,options={}){
  const policy={...DEFAULT_POLICY,...(options.policy||{})};
  const sections=arrangement?.sections||[];
  const bpm=Number(options.bpm),numerator=Number(options.numerator)||4,denominator=Number(options.denominator)||4;
  if(!(bpm>0)||sections.length<2){
    return {events:events.slice(),info:{enabled:false,reason:'missing-context',policy}};
  }
  const beatSec=60/bpm*4/denominator,barSec=beatSec*numerator;
  const hats=events.filter(e=>(e.group==='hat'||e.group==='open_hat')&&Number.isFinite(Number(e.openHatProbability)));
  if(!hats.length)return {events:events.slice(),info:{enabled:false,reason:'missing-acoustic-probability',policy}};
  const replacement=new Map(),decisions=[];

  for(const e of hats){
    const p=Number(e.openHatProbability);
    if(Math.abs(p-policy.threshold)>policy.borderlineRadius)continue;
    const section=sectionForTime(sections,Number(e.time));if(!section)continue;
    const quality=familyQuality(sections,section.group);if(quality<policy.minFamilyQuality)continue;
    const {barIndex,slot}=slotInfo(Number(e.time),section,barSec);
    const others=sections.filter(s=>s.group===section.group&&s.index!==section.index);
    const support=[];
    for(const s of others){
      const target=Number(s.startSec)+barIndex*barSec+slot/16*barSec;
      if(target>=Number(s.endSec)-.03)continue;
      const h=closestHat(hats,target,policy.supportToleranceSec);
      if(!h)continue;
      const hp=Number(h.openHatProbability);
      if(hp>=policy.strongOpen)support.push({vote:1,p:hp,label:s.label||s.group});
      else if(hp<=policy.strongClosed)support.push({vote:0,p:hp,label:s.label||s.group});
    }
    if(!support.length)continue;
    let open=support.filter(x=>x.vote===1).length,closed=support.length-open;
    const desired=open>closed?1:closed>open?0:null;if(desired==null)continue;
    const rate=Math.max(open,closed)/support.length;
    if(rate<.75)continue;
    if(support.length===1){
      const sp=support[0].p;
      if(quality<policy.singleSupportMinQuality)continue;
      if(desired&&sp<policy.singleSupportStrongOpen)continue;
      if(!desired&&sp>policy.singleSupportStrongClosed)continue;
    }
    const sign=desired?1:-1;
    const q=sigmoid(logit(p)+sign*policy.logitWeight*rate*quality);
    if((q>=policy.threshold)===(p>=policy.threshold))continue;
    const next={...e,
      group:q>=policy.threshold?'open_hat':'hat',
      note:q>=policy.threshold?46:42,
      openHatProbability:q,
      arrangementHatRescored:true,
      arrangementHatFamily:section.group,
      arrangementHatLabel:section.label||section.group,
      arrangementHatSupport:support.length,
      arrangementHatSupportRate:rate,
      arrangementHatFamilyQuality:quality,
      arrangementHatSlot:slot,
    };
    replacement.set(e,next);
    decisions.push({time:e.time,from:e.group,to:next.group,baseProbability:p,probability:q,
      family:section.group,label:section.label||section.group,slot,support:support.length,supportRate:rate,quality});
  }
  return {
    events:events.map(e=>replacement.get(e)||e),
    info:{enabled:true,policy,candidates:hats.length,changed:decisions.length,decisions}
  };
}

export const arrangementHatPolicyV1={...DEFAULT_POLICY};
