// Arrangement-aware K/S/T candidate rescoring.
//
// This module never copies a note from one section into another. It can only
// promote a low-threshold acoustic candidate that already exists at the target
// time, using repeated structural-family support (A/A'/...) and an optional
// GMD symbolic slot prior.
//
// Reference chart.mid must never be used here.

const DEFAULT_POLICY={
  name:'family-gmd-postfilter-v39d',
  minConfidence:.50,
  minSupportRate:.50,
  minFamilyQuality:.90,
  minGmdLift:.80,
  candidateToleranceSec:.055,
  supportToleranceSec:.075,
  dedupeToleranceSec:.05,
  handWindowSec:.035,
  rejectPostfilteredHandCandidate:true,
  enforceTwoHands:true,
  enableEgmdResidualSnare:false,
  residualSnareMinProbability:.93,
  residualSnareMinConfidence:.55,
  residualSnareMinGmdLift:1.65,
};

const NOTE_OF={kick:36,snare:38,tom:45};
const KST=new Set(Object.keys(NOTE_OF));
const HAND_GROUPS=new Set(['snare','tom','hat','open_hat','crash','ride']);

function familyQuality(sections,group){
  const family=sections.filter(s=>s.group===group);
  if(family.length<2)return 0;
  const repeats=family
    .filter(s=>(Number(s.occurrence)||1)>1)
    .map(s=>Number(s.repeatSimilarity))
    .filter(Number.isFinite);
  if(!repeats.length)return 1;
  return repeats.reduce((a,b)=>a+b,0)/repeats.length;
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
  return {barIndex,slot:Math.max(0,Math.min(15,slot))};
}

function nearGroup(events,time,group,tolerance){
  return events.some(e=>e.group===group&&Math.abs(Number(e.time)-time)<=tolerance);
}

function familySupport(time,group,section,sections,baselineKst,barSec,tolerance){
  const {barIndex,slot}=slotInfo(time,section,barSec);
  const otherOccurrences=sections.filter(s=>s.group===section.group&&s.index!==section.index);
  let eligible=0,support=0;
  for(const other of otherOccurrences){
    const target=Number(other.startSec)+barIndex*barSec+slot/16*barSec;
    if(target>=Number(other.endSec)-.03)continue;
    eligible++;
    if(nearGroup(baselineKst,target,group,tolerance))support++;
  }
  return {barIndex,slot,support,eligible,rate:eligible?support/eligible:0};
}

function candidateRank(candidate,support,gmdLift,quality){
  return (Number(candidate.confidence)||0)+.35*support.rate+.12*Math.min(2,gmdLift)+.08*quality;
}

function isHandSafe(events,candidate,windowSec){
  if(!HAND_GROUPS.has(candidate.group))return true;
  let hands=0;
  for(const e of events){
    if(!HAND_GROUPS.has(e.group))continue;
    if(Math.abs(Number(e.time)-candidate.time)<=windowSec)hands++;
    if(hands>=2)return false;
  }
  return true;
}

function dedupeAdditions(additions,tolerance){
  const out=[];
  for(const e of additions.slice().sort((a,b)=>a.time-b.time||String(a.group).localeCompare(String(b.group))||b.arrangementRank-a.arrangementRank)){
    const old=out.find(x=>x.group===e.group&&Math.abs(x.time-e.time)<=tolerance);
    if(!old){out.push(e);continue;}
    if(e.arrangementRank>old.arrangementRank){
      out.splice(out.indexOf(old),1,e);
    }
  }
  return out.sort((a,b)=>a.time-b.time||a.note-b.note);
}

export function rescoreKstByArrangement(baselineEvents,diagnostics,arrangement,options={}){
  const policy={...DEFAULT_POLICY,...(options.policy||{})};
  const sections=arrangement?.sections||[];
  const candidates=diagnostics?.kstCandidates||{};
  const bpm=Number(options.bpm);
  const numerator=Number(options.numerator)||4;
  const denominator=Number(options.denominator)||4;
  const slotPrior=options.slotPrior||null;
  if(!(bpm>0)||sections.length<2||!candidates){
    return {events:baselineEvents.slice(),additions:[],info:{enabled:false,reason:'missing-context',policy}};
  }
  const beatSec=60/bpm*4/denominator;
  const barSec=beatSec*numerator;
  const baselineKst=baselineEvents.filter(e=>KST.has(e.group));
  const proposed=[];

  for(const group of ['kick','snare','tom']){
    const rows=Array.isArray(candidates[group])?candidates[group]:[];
    for(const candidate of rows){
      const time=Number(candidate.time);
      if(!Number.isFinite(time))continue;
      if(nearGroup(baselineKst,time,group,policy.candidateToleranceSec))continue;

      const section=sectionForTime(sections,time);
      if(!section)continue;
      const quality=familyQuality(sections,section.group);
      if(quality<policy.minFamilyQuality)continue;

      const support=familySupport(time,group,section,sections,baselineKst,barSec,policy.supportToleranceSec);
      if(support.eligible<1||support.support<1||support.rate<policy.minSupportRate)continue;

      const confidence=Number(candidate.confidence)||0;
      if(confidence<policy.minConfidence)continue;

      // v39 finding: a Snare/Tom candidate already above the production
      // threshold but absent from final output was a downstream-veto case, not
      // a threshold miss. Arrangement evidence must not silently override it.
      if(policy.rejectPostfilteredHandCandidate&&group!=='kick'&&confidence>=1)continue;

      const lifts=slotPrior?.lift?.[group];
      const gmdLift=Array.isArray(lifts)&&Number.isFinite(Number(lifts[support.slot]))
        ?Number(lifts[support.slot]):1;
      if(gmdLift<policy.minGmdLift)continue;

      proposed.push({
        time,
        note:NOTE_OF[group],
        group,
        velocity:Math.max(40,Math.min(120,Math.round(80+15*Math.log1p(Math.max(0,Number(candidate.score)||0))))),
        score:Number(candidate.score)||0,
        confidence,
        arrangementRescued:true,
        arrangementFamily:section.group,
        arrangementLabel:section.label||section.group,
        arrangementFamilyQuality:quality,
        arrangementSupport:support.support,
        arrangementEligible:support.eligible,
        arrangementSupportRate:support.rate,
        arrangementBarIndex:support.barIndex,
        arrangementSlot:support.slot,
        gmdSlotLift:gmdLift,
        arrangementRank:candidateRank(candidate,support,gmdLift,quality),
      });
    }
  }

  const residualProposed=[];
  if(policy.enableEgmdResidualSnare){
    const rows=Array.isArray(candidates.snare)?candidates.snare:[];
    for(const candidate of rows){
      const time=Number(candidate.time);
      if(!Number.isFinite(time))continue;
      if(nearGroup(baselineKst,time,'snare',policy.candidateToleranceSec))continue;

      const confidence=Number(candidate.confidence)||0;
      if(confidence<policy.residualSnareMinConfidence)continue;
      // Preserve the v39 downstream-veto guard: this residual rescue is only
      // for genuinely sub-threshold acoustic candidates.
      if(policy.rejectPostfilteredHandCandidate&&confidence>=1)continue;

      const egmdProbability=Number(candidate.egmdProbability);
      if(!Number.isFinite(egmdProbability)||egmdProbability<policy.residualSnareMinProbability)continue;

      const section=sectionForTime(sections,time);
      if(!section)continue;
      const {barIndex,slot}=slotInfo(time,section,barSec);
      const lifts=slotPrior?.lift?.snare;
      const gmdLift=Array.isArray(lifts)&&Number.isFinite(Number(lifts[slot]))?Number(lifts[slot]):1;
      if(gmdLift<policy.residualSnareMinGmdLift)continue;

      residualProposed.push({
        time,
        note:NOTE_OF.snare,
        group:'snare',
        velocity:Math.max(40,Math.min(120,Math.round(80+15*Math.log1p(Math.max(0,Number(candidate.score)||0))))),
        score:Number(candidate.score)||0,
        confidence,
        arrangementRescued:false,
        egmdResidualRescued:true,
        egmdProbability,
        egmdModelThreshold:Number(candidate.egmdModelThreshold)||null,
        arrangementFamily:section.group,
        arrangementLabel:section.label||section.group,
        arrangementFamilyQuality:familyQuality(sections,section.group),
        arrangementSupport:0,
        arrangementEligible:0,
        arrangementSupportRate:0,
        arrangementBarIndex:barIndex,
        arrangementSlot:slot,
        gmdSlotLift:gmdLift,
        arrangementRank:2+egmdProbability+.10*confidence+.05*Math.min(2,gmdLift),
      });
    }
  }

  const deduped=dedupeAdditions([...proposed,...residualProposed],policy.dedupeToleranceSec);
  const accepted=[];
  const rejectedHand=[];
  for(const candidate of deduped){
    const current=[...baselineEvents,...accepted];
    if(policy.enforceTwoHands&&!isHandSafe(current,candidate,policy.handWindowSec)){
      rejectedHand.push(candidate);
      continue;
    }
    accepted.push(candidate);
  }

  const events=[...baselineEvents,...accepted].sort((a,b)=>a.time-b.time||a.note-b.note);
  return {
    events,
    additions:accepted,
    info:{
      enabled:true,
      policy,
      sections:sections.length,
      repeatedSections:sections.filter(s=>(Number(s.occurrence)||1)>1).length,
      proposed:proposed.length,
      residualProposed:residualProposed.length,
      accepted:accepted.length,
      acceptedArrangement:accepted.filter(e=>e.arrangementRescued).length,
      acceptedEgmdResidual:accepted.filter(e=>e.egmdResidualRescued).length,
      rejectedHand:rejectedHand.length,
      additions:accepted.map(e=>({
        time:e.time,group:e.group,confidence:e.confidence,
        rescueType:e.egmdResidualRescued?'egmd-residual':'arrangement-family',
        egmdProbability:Number.isFinite(Number(e.egmdProbability))?Number(e.egmdProbability):null,
        family:e.arrangementFamily,label:e.arrangementLabel,
        support:e.arrangementSupport,eligible:e.arrangementEligible,
        supportRate:e.arrangementSupportRate,slot:e.arrangementSlot,
        gmdSlotLift:e.gmdSlotLift
      }))
    }
  };
}

export const arrangementKstPolicyV39D={...DEFAULT_POLICY};

export const arrangementKstPolicyV46R1={
  ...DEFAULT_POLICY,
  name:'family-gmd-plus-egmd-residual-v46r1',
  enableEgmdResidualSnare:true,
  residualSnareMinProbability:.93,
  residualSnareMinConfidence:.55,
  residualSnareMinGmdLift:1.65,
};

// Current production selection. Keep the explicit versioned exports above so
// historical experiments remain reproducible.
export const arrangementKstPolicyCurrent={...arrangementKstPolicyV46R1};
