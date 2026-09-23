import {analyzeSections} from './section-analysis.js';
import {loadGmdKstKnowledge,gmdKstEvidence,sectionAtTime} from './gmd-kst-prior.js';
import {inferSectionStyleMixtures} from './gmd-kst-genre.js';

function slot16(time,bpm,barPhaseSec,numerator=4,denominator=4){
  const beat=60/bpm*4/denominator,bar=beat*numerator;
  let x=(time-barPhaseSec)%bar;if(x<0)x+=bar;
  return Math.round(x/(beat/4))%Math.max(1,Math.round(numerator*16/denominator));
}

export async function buildSectionKstContext({
  offvocalDecoded,
  events,
  bpm,
  barPhaseSec,
  numerator=4,
  denominator=4,
  knowledge=null,
}={}){
  if(!offvocalDecoded||!(bpm>0)||!Number.isFinite(barPhaseSec)){
    return {enabled:false,reason:'missing-offvocal-or-grid',knowledge:null,sections:[]};
  }
  const kb=knowledge||await loadGmdKstKnowledge();
  const sectionAnalysis=analyzeSections(offvocalDecoded,{
    analysisSampleRate:8000,
    bpm,barPhaseSec,numerator,denominator,
    frameSec:.75,hopSec:.375,contextSec:4.5,
    minSectionSec:7,noveltyStd:.72,maxSections:18,
  });
  const strong=(events||[]).filter(e=>
    (e.group==='kick'||e.group==='snare'||e.group==='tom') &&
    Number(e.confidence||0)>=1
  );
  const sections=inferSectionStyleMixtures(kb,strong,sectionAnalysis,{
    bpm,barPhaseSec,numerator,denominator
  },{
    topK:8,temperature:.10,scoreFloor:0
  });
  return {
    enabled:true,
    method:'offvocal-sections+gmd-exact-style-mixture-v1',
    knowledge:kb,
    sectionAnalysis,
    sections,
  };
}

export function kstContextEvidence(context,candidate,{mode='style',maxInfluence=.18}={}){
  if(!context?.enabled||!context.knowledge)return {multiplier:1,raw:1,confidence:0};
  const bpm=Number(context.bpm||candidate.bpm);
  const barPhaseSec=Number(context.barPhaseSec??candidate.barPhaseSec);
  const numerator=Number(context.numerator)||4,denominator=Number(context.denominator)||4;
  if(!(bpm>0)||!Number.isFinite(barPhaseSec))return {multiplier:1,raw:1,confidence:0};
  const slots=Math.max(1,Math.round(numerator*16/denominator));
  const slot=slot16(candidate.time,bpm,barPhaseSec,numerator,denominator);
  const section=sectionAtTime({sections:context.sections},candidate.time);
  if(mode==='global'||!section){
    return {...gmdKstEvidence(context.knowledge,{
      group:candidate.group,slot,slotsPerBar:slots,maxInfluence
    }),slot,section:null};
  }
  const ev=gmdKstEvidence(context.knowledge,{
    group:candidate.group,slot,slotsPerBar:slots,
    expertFamily:'style',
    expertWeights:section.styleWeights,
    maxInfluence,
  });
  return {...ev,slot,section:{
    index:section.index,group:section.group,startSec:section.startSec,endSec:section.endSec,
    styleConfidence:section.styleConfidence,styleWeights:section.styleWeights
  }};
}

export function attachGridToContext(context,{bpm,barPhaseSec,numerator=4,denominator=4}={}){
  return {...context,bpm,barPhaseSec,numerator,denominator};
}
