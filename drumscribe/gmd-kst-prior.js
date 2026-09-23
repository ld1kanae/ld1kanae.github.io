// Genre/section-aware evidence adapter for GMD K/S/T knowledge.
//
// Important: this module returns bounded evidence multipliers only. It must not
// create notes on its own. Callers should apply it only to acoustically plausible
// kick/snare/tom candidates.

const DEFAULT_URL='./models/gmd-kst/knowledge-v1.json';
const GROUPS=new Set(['kick','snare','tom']);

function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
function normalizeWeights(weights){
  const rows=Object.entries(weights||{}).filter(([,v])=>Number(v)>0);
  const sum=rows.reduce((s,[,v])=>s+Number(v),0);
  if(!sum)return {};
  return Object.fromEntries(rows.map(([k,v])=>[k,Number(v)/sum]));
}
function phaseMultiplier(agg,group,slot,slotsPerBar){
  if(!agg||!GROUPS.has(group))return 1;
  const counts=agg.phase_16th_counts?.[group]||{};
  const slots=Math.max(1,Number(slotsPerBar)||16);
  let total=0;
  for(let i=0;i<slots;i++)total+=Number(counts[String(i)]||0);
  if(!total)return 1;
  const mean=total/slots;
  // Empirical-Bayes style additive smoothing. Sparse genres collapse toward 1.
  const alpha=Math.max(2,mean*.12);
  return (Number(counts[String(slot%slots)]||0)+alpha)/(mean+alpha);
}
function reliability(agg){
  if(!agg)return 0;
  const rows=Number(agg.rows)||0,duration=Number(agg.duration_sec)||0;
  // Deliberately conservative: small genre bins lean heavily on global GMD.
  const rowW=rows/(rows+40);
  const durationW=duration/(duration+1800);
  return Math.sqrt(rowW*durationW);
}
function blendLog(values){
  let log=0,sum=0;
  for(const [value,weight] of values){
    if(!(weight>0))continue;
    log+=Math.log(Math.max(.05,value))*weight;sum+=weight;
  }
  return sum?Math.exp(log/sum):1;
}

export async function loadGmdKstKnowledge(url=DEFAULT_URL){
  const r=await fetch(url);
  if(!r.ok)throw new Error(`GMD K/S/T knowledge HTTP ${r.status}`);
  const data=await r.json();
  if(!data?.aggregates?.global?.all)throw new Error('Invalid GMD K/S/T knowledge');
  return data;
}

export function gmdKstEvidence(knowledge,{
  group,
  slot,
  slotsPerBar=16,
  genreWeights={},
  beatType=null,
  maxInfluence=.18,
}={}){
  if(!GROUPS.has(group))return {multiplier:1,global:1,genres:[],confidence:0};
  const globalAgg=knowledge?.aggregates?.global?.all;
  if(!globalAgg)return {multiplier:1,global:1,genres:[],confidence:0};

  const normalized=normalizeWeights(genreWeights);
  const global=phaseMultiplier(globalAgg,group,slot,slotsPerBar);
  const genreRows=[];
  let weightedConfidence=0;

  for(const [genre,genreWeight] of Object.entries(normalized)){
    const genreAgg=knowledge.aggregates?.genre?.[genre];
    if(!genreAgg)continue;
    const rel=reliability(genreAgg);
    let local=phaseMultiplier(genreAgg,group,slot,slotsPerBar);

    if(beatType){
      const btAgg=knowledge.aggregates?.genre_beat_type?.[`${genre}|${beatType}`];
      if(btAgg){
        const btRel=reliability(btAgg);
        const bt=phaseMultiplier(btAgg,group,slot,slotsPerBar);
        local=blendLog([[local,1],[bt,btRel]]);
      }
    }
    // Shrink the genre expert toward the global distribution.
    const shrunk=blendLog([[global,1-rel],[local,rel]]);
    genreRows.push({genre,weight:genreWeight,reliability:rel,multiplier:shrunk});
    weightedConfidence+=genreWeight*rel;
  }

  const mixed=genreRows.length
    ? blendLog(genreRows.map(x=>[x.multiplier,x.weight]))
    : global;
  const raw=blendLog([[global,1-weightedConfidence],[mixed,weightedConfidence]]);

  // Prior evidence is intentionally bounded. It resolves ambiguous candidates;
  // it is not allowed to overpower the acoustic detector.
  const influence=clamp(Number(maxInfluence)||0,.02,.30);
  const multiplier=clamp(1+(raw-1)*influence,.82,1.18);
  return {multiplier,raw,global,genres:genreRows,confidence:weightedConfidence};
}

export function sectionAtTime(sectionAnalysis,timeSec){
  const sections=sectionAnalysis?.sections||[];
  return sections.find(s=>timeSec>=s.startSec&&timeSec<s.endSec)
    || sections[sections.length-1]
    || null;
}
