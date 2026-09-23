// Infer a section-local mixture of GMD drum-style experts from preliminary
// kick/snare/tom events. This is a context estimator only; it never moves or
// creates drum notes.
//
// Deliberate separation:
//   off-vocal -> section boundaries
//   strong preliminary drum events -> genre mixture within each section
//   GMD prior -> bounded evidence for ambiguous acoustic candidates
//
// Dataset frequency is NOT used as a genre prior because GMD is imbalanced.
// Genre support/reliability is returned separately and is applied later when
// weighting the genre expert against the global GMD prior.

const GROUPS=['kick','snare','tom'];
const TOM_NOTES=new Set([41,43,45,47,48,50,58]);

function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
function noteGroup(note){
  note=Number(note);
  if(note===35||note===36)return 'kick';
  if(note===37||note===38||note===39||note===40)return 'snare';
  if(TOM_NOTES.has(note))return 'tom';
  return null;
}
function cosine(a,b){
  let ab=0,aa=0,bb=0;
  for(let i=0;i<a.length;i++){
    const x=Number(a[i])||0,y=Number(b[i])||0;
    ab+=x*y;aa+=x*x;bb+=y*y;
  }
  if(aa<=1e-12||bb<=1e-12)return 0;
  return ab/Math.sqrt(aa*bb);
}
function normalized(values){
  const sum=values.reduce((a,b)=>a+b,0);
  return sum>0?values.map(v=>v/sum):values.map(()=>0);
}
function entropy01(weights){
  const vals=Object.values(weights).filter(x=>x>0);
  if(vals.length<=1)return 0;
  let h=0;for(const p of vals)h-=p*Math.log(p);
  return h/Math.log(vals.length);
}
function aggregateVector(agg,slotsPerBar=16){
  const phase={};
  for(const g of GROUPS){
    const counts=agg?.phase_16th_counts?.[g]||{};
    const row=[];
    for(let i=0;i<slotsPerBar;i++)row.push(Number(counts[String(i)]||0));
    phase[g]=normalized(row);
  }
  const hits=GROUPS.map(g=>Number(agg?.hits?.[g]||0));
  return {phase,composition:normalized(hits)};
}
function supportReliability(agg){
  const rows=Number(agg?.rows)||0,duration=Number(agg?.duration_sec)||0;
  const rowW=rows/(rows+40),durationW=duration/(duration+1800);
  return Math.sqrt(Math.max(0,rowW*durationW));
}
function softmax(rows,temperature){
  if(!rows.length)return {};
  const t=Math.max(.02,Number(temperature)||.12);
  const max=Math.max(...rows.map(r=>r.score));
  const ex=rows.map(r=>Math.exp((r.score-max)/t));
  const sum=ex.reduce((a,b)=>a+b,0)||1;
  return Object.fromEntries(rows.map((r,i)=>[r.genre,ex[i]/sum]));
}
function blendMixtures(a,b,t){
  const keys=new Set([...Object.keys(a||{}),...Object.keys(b||{})]);
  const out={};let total=0;
  for(const k of keys){
    const v=(1-t)*Number(a?.[k]||0)+t*Number(b?.[k]||0);
    if(v>0){out[k]=v;total+=v;}
  }
  if(total)for(const k of Object.keys(out))out[k]/=total;
  return out;
}

export function profileSectionEvents(events,{
  bpm,
  barPhaseSec=0,
  numerator=4,
  denominator=4,
  startSec=0,
  endSec=Infinity,
  scoreFloor=0,
  slotsPerBar=null,
}={}){
  bpm=Number(bpm);
  numerator=Number(numerator)||4;denominator=Number(denominator)||4;
  const beatSec=Number.isFinite(bpm)&&bpm>0?60/bpm*4/denominator:null;
  const barSec=beatSec?beatSec*numerator:null;
  const slots=Number(slotsPerBar)||Math.max(1,Math.round(numerator*16/denominator));
  const phase=Object.fromEntries(GROUPS.map(g=>[g,new Array(slots).fill(0)]));
  const hits=Object.fromEntries(GROUPS.map(g=>[g,0]));
  let total=0;

  for(const e of events||[]){
    const time=Number(e.time);
    if(!Number.isFinite(time)||time<startSec||time>=endSec)continue;
    if(Number(e.score||0)<scoreFloor)continue;
    const group=e.group&&GROUPS.includes(e.group)?e.group:noteGroup(e.note);
    if(!group)continue;
    let slot=0;
    if(barSec){
      let pos=(time-Number(barPhaseSec||0))%barSec;
      if(pos<0)pos+=barSec;
      slot=Math.round(pos/barSec*slots)%slots;
    }else{
      // Without a tempo grid we can still use K/S/T composition, but not phase.
      slot=0;
    }
    phase[group][slot]+=1;
    hits[group]+=1;total++;
  }

  const duration=Math.max(0,Math.min(Number(endSec)||0,Infinity)-Number(startSec||0));
  const approxBars=barSec&&Number.isFinite(duration)?duration/barSec:0;
  return {
    hits,total,
    phase:Object.fromEntries(GROUPS.map(g=>[g,normalized(phase[g])])),
    composition:normalized(GROUPS.map(g=>hits[g])),
    slotsPerBar:slots,
    approxBars,
    hasGrid:Boolean(barSec),
  };
}

export function inferGenreMixture(knowledge,profile,{
  topK=4,
  temperature=.10,
  phaseWeight=.82,
  compositionWeight=.18,
  minHitsForFullConfidence=48,
}={}){
  const genres=knowledge?.aggregates?.genre||{};
  const rows=[];
  for(const [genre,agg] of Object.entries(genres)){
    const ref=aggregateVector(agg,profile.slotsPerBar||16);
    let phaseScore=0,phaseWeightSum=0;
    for(const g of GROUPS){
      const observed=Number(profile.hits?.[g]||0);
      if(!observed)continue;
      const w=Math.sqrt(observed);
      phaseScore+=w*cosine(profile.phase[g]||[],ref.phase[g]);
      phaseWeightSum+=w;
    }
    phaseScore=phaseWeightSum?phaseScore/phaseWeightSum:0;
    const compositionScore=cosine(profile.composition||[],ref.composition);
    const pw=profile.hasGrid?clamp(Number(phaseWeight)||.82,0,1):0;
    const cw=profile.hasGrid?1-pw:1;
    const score=pw*phaseScore+cw*compositionScore;
    rows.push({
      genre,
      score,
      phaseScore,
      compositionScore,
      supportReliability:supportReliability(agg),
      trainRows:Number(agg.rows)||0,
    });
  }
  rows.sort((a,b)=>b.score-a.score);

  // Equal prior over genre labels. Do not inject GMD row frequency.
  const allWeights=softmax(rows,temperature);
  const top=rows.slice(0,Math.max(1,Number(topK)||4));
  let topMass=top.reduce((s,r)=>s+Number(allWeights[r.genre]||0),0)||1;
  const weights={};
  for(const r of top)weights[r.genre]=Number(allWeights[r.genre]||0)/topMass;

  const hitConfidence=clamp((Number(profile.total)||0)/Math.max(1,minHitsForFullConfidence),0,1);
  const gridConfidence=profile.hasGrid?clamp((Number(profile.approxBars)||0)/8,0.35,1):.45;
  const separation=top.length>1?clamp((top[0].score-top[1].score)/.12,0,1):1;
  const uncertainty=entropy01(weights);
  const confidence=clamp(
    hitConfidence*gridConfidence*(.55+.45*separation)*(1-.35*uncertainty),
    0,1
  );

  return {weights,confidence,ranking:rows,top};
}

export function inferSectionGenreMixtures(knowledge,events,sectionAnalysis,timing,options={}){
  const sections=sectionAnalysis?.sections||[];
  const raw=sections.map(section=>{
    const profile=profileSectionEvents(events,{
      ...timing,
      startSec:section.startSec,
      endSec:section.endSec,
      scoreFloor:options.scoreFloor||0,
    });
    const inferred=inferGenreMixture(knowledge,profile,options);
    return {...section,profile,genreWeights:inferred.weights,genreConfidence:inferred.confidence,genreRanking:inferred.ranking};
  });

  // Repeated arrangement groups can share evidence, but only softly. This helps
  // short A/B sections while still allowing later occurrences to change style.
  const byGroup=new Map();
  for(const s of raw){
    if(!s.group)continue;
    const arr=byGroup.get(s.group)||[];arr.push(s);byGroup.set(s.group,arr);
  }
  for(const arr of byGroup.values()){
    if(arr.length<2)continue;
    const pooled={};
    let denom=0;
    for(const s of arr){
      const w=Math.max(.1,s.genreConfidence);
      denom+=w;
      for(const [g,p] of Object.entries(s.genreWeights))pooled[g]=(pooled[g]||0)+w*p;
    }
    if(denom)for(const g of Object.keys(pooled))pooled[g]/=denom;
    for(const s of arr){
      const share=clamp(.15+.35*(1-s.genreConfidence),.15,.45);
      s.genreWeights=blendMixtures(s.genreWeights,pooled,share);
    }
  }
  return raw;
}
