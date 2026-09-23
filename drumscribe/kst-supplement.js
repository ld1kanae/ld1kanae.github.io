import {buildSectionKstContext,attachGridToContext,kstContextEvidence} from './kst-section-context.js';

const NEAR_SEC=.035;

function nearGroup(events,candidate){
  return events.some(e=>e.group===candidate.group&&Math.abs(e.time-candidate.time)<=NEAR_SEC);
}

function policySpec(policy){
  switch(policy){
    case 'egmd-kick':
      return {groups:['kick'],prior:'none'};
    case 'egmd-tom':
      return {groups:['tom'],prior:'none'};
    case 'egmd-kicktom':
      return {groups:['kick','tom'],prior:'none'};
    case 'egmd-global-kicktom':
      return {groups:['kick','tom'],prior:'global'};
    case 'egmd-style-kicktom':
      return {groups:['kick','tom'],prior:'style'};
    default:
      return {groups:[],prior:'none'};
  }
}

export async function applyKstSupplementPolicy({
  structural,
  egmdKstSupport,
  offvocalDecoded=null,
  bpm,
  barPhaseSec,
  numerator=4,
  denominator=4,
  policy='baseline',
}={}){
  const spec=policySpec(policy);
  if(!spec.groups.length){
    return {events:structural,info:{policy:'baseline',added:0,byGroup:{kick:0,tom:0}}};
  }

  let context={enabled:false,reason:'prior-not-requested'};
  if(spec.prior==='style'){
    context=await buildSectionKstContext({
      offvocalDecoded,events:structural,bpm,barPhaseSec,numerator,denominator
    });
    context=attachGridToContext(context,{bpm,barPhaseSec,numerator,denominator});
  }else if(spec.prior==='global'){
    // Global prior still needs the knowledge file but not off-vocal sections.
    const styleContext=await buildSectionKstContext({
      offvocalDecoded,events:structural,bpm,barPhaseSec,numerator,denominator
    });
    if(styleContext.knowledge){
      context=attachGridToContext({...styleContext,enabled:true,sections:[]},{
        bpm,barPhaseSec,numerator,denominator
      });
    }
  }

  const out=structural.slice();
  const detail=[];
  const byGroup={kick:0,tom:0};
  for(const group of spec.groups){
    for(const e of egmdKstSupport?.[group]||[]){
      const threshold=Number(e.modelThreshold)||1;
      if((Number(e.probability)||0)<threshold)continue;
      if(nearGroup(out,e))continue;

      let evidence={raw:1,multiplier:1,confidence:0};
      if(spec.prior!=='none'){
        if(!context?.enabled){
          detail.push({group,time:e.time,probability:e.probability,accepted:false,reason:'context-unavailable'});
          continue;
        }
        evidence=kstContextEvidence(context,e,{mode:spec.prior,maxInfluence:.18});
        // Neutral-or-positive rhythmic evidence only. 1.0 is not tuned on
        // DruMaster; it is the mathematical neutral point of the GMD prior.
        if(!(Number(evidence.raw)>=1)){
          detail.push({group,time:e.time,probability:e.probability,priorRaw:evidence.raw,accepted:false,reason:'negative-gmd-evidence'});
          continue;
        }
      }

      const confidence=Math.max(1,(Number(e.probability)||0)/Math.max(.01,threshold));
      out.push({...e,group,confidence,egmdSupplement:true,gmdPriorRaw:evidence.raw,gmdPriorMultiplier:evidence.multiplier});
      byGroup[group]=(byGroup[group]||0)+1;
      detail.push({group,time:e.time,probability:e.probability,priorRaw:evidence.raw,priorMultiplier:evidence.multiplier,accepted:true});
    }
  }
  out.sort((a,b)=>a.time-b.time||String(a.group).localeCompare(String(b.group)));
  return {
    events:out,
    info:{
      policy,
      prior:spec.prior,
      added:byGroup.kick+byGroup.tom,
      byGroup,
      contextEnabled:Boolean(context?.enabled),
      contextMethod:context?.method||null,
      sections:(context?.sections||[]).map(s=>({
        index:s.index,group:s.group,startSec:s.startSec,endSec:s.endSec,
        styleConfidence:s.styleConfidence,styleWeights:s.styleWeights
      })),
      detail,
    }
  };
}
