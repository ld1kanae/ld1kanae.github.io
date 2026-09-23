from pathlib import Path

p = Path('drumscribe/open-hat.js')
s = p.read_text()

if 'function alternatingEighthRescore(' not in s:
    marker = 'function slot16(time,bpm,barPhaseSec){'
    if marker not in s:
        raise SystemExit('slot16 marker missing')
    fn = r'''
function alternatingEighthRescore(samples,hats,events,baseProb,bpm,barPhaseSec,threshold,policy={}){
  // Relative-decay detector for repeated 8th-note Closed/Open alternation.
  // It does not require an absolute high-confidence Open exemplar, so it can
  // recover kits whose whole Open probability distribution is shifted low.
  if(!Number.isFinite(barPhaseSec)||!(bpm>=50&&bpm<=240)||hats.length<4){
    return {probabilities:baseProb.slice(),info:{enabled:false,reason:'insufficient-context'}};
  }
  const step=30/bpm,tol=Math.min(.075,.34*step),rows=[];
  for(let i=0;i<hats.length;i++){
    const e=hats[i],slot=Math.round((e.time-barPhaseSec)/step);
    const target=barPhaseSec+slot*step,residual=Math.abs(e.time-target);
    if(residual>tol)continue;
    const onset=Math.max(rmsWindow(samples,e.time,0,.025),1e-8);
    const late=rmsWindow(samples,e.time,.120,.200)/onset;
    const preNext=rmsWindow(samples,e.time,Math.max(.030,step-.070),Math.max(.045,step-.025))/onset;
    const decay=.65*Math.log1p(late)+.35*Math.log1p(preNext);
    rows.push({event:e,index:i,slot,residual,decay,p:Number(baseProb[i])||0});
  }
  if(rows.length<4)return {probabilities:baseProb.slice(),info:{enabled:false,reason:'too-few-aligned-hats',aligned:rows.length}};
  const bySlot=new Map();
  for(const r of rows){const old=bySlot.get(r.slot);if(!old||r.residual<old.residual)bySlot.set(r.slot,r);}
  const reps=[...bySlot.values()].sort((a,b)=>a.slot-b.slot),segments=[];let cur=[];
  for(const r of reps){if(cur.length&&r.slot-cur[cur.length-1].slot>2){segments.push(cur);cur=[];}cur.push(r);}
  if(cur.length)segments.push(cur);
  const minItems=Number(policy.minItems??6),minOccupancy=Number(policy.minOccupancy??.65);
  const minSeparation=Number(policy.minSeparation??.10),localMargin=Number(policy.localMargin??.36),strong=[];
  for(const seg of segments){
    const span=seg[seg.length-1].slot-seg[0].slot+1,a=[[],[]];
    for(const r of seg)a[((r.slot%2)+2)%2].push(r.decay);
    if(seg.length<minItems||seg.length/span<minOccupancy||Math.min(a[0].length,a[1].length)<2)continue;
    const med=[median(a[0]),median(a[1])],separation=Math.abs(med[1]-med[0]);
    if(separation<minSeparation)continue;
    strong.push({seg,openParity:med[1]>med[0]?1:0,separation,span,occupancy:seg.length/span});
  }
  const votes=[0,0],counts=[0,0];
  for(const x of strong){votes[x.openParity]+=x.seg.length*x.separation;counts[x.openParity]++;}
  const totalStrong=strong.reduce((z,x)=>z+x.seg.length,0),strongCount=strong.length;
  const winner=votes[1]>votes[0]?1:0,loser=1-winner;
  const voteShare=(votes[winner]+votes[loser])?votes[winner]/(votes[winner]+votes[loser]):0;
  const globalEnabled=Boolean(policy.global)&&strongCount>=Number(policy.globalMinSegments??3)&&
    totalStrong>=Number(policy.globalMinRows??40)&&voteShare>=Number(policy.globalVoteShare??.75);
  const out=baseProb.slice(),applications=[];let changed=0,localChanged=0,globalChanged=0;
  const strongByStart=new Map(strong.map(x=>[x.seg[0].slot,x]));
  for(const seg of segments){
    const span=seg[seg.length-1].slot-seg[0].slot+1,occupancy=seg.length/span,local=strongByStart.get(seg[0].slot)||null;
    let openParity=null,margin=localMargin,mode=null,separation=0;
    if(local){openParity=local.openParity;mode='local';separation=local.separation;}
    else if(globalEnabled&&seg.length>=Number(policy.globalMinItems??2)&&occupancy>=Number(policy.globalMinOccupancy??.50)){
      const a=[[],[]];for(const r of seg)a[((r.slot%2)+2)%2].push(r.decay);
      if(a[0].length&&a[1].length){
        const med=[median(a[0]),median(a[1])],d=Math.abs(med[1]-med[0]),op=med[1]>med[0]?1:0;
        if(d>=minSeparation&&op!==winner)continue;
        separation=d;
      }
      openParity=winner;mode='global';margin=Number(policy.globalMargin??.28);
    }
    if(openParity==null)continue;
    const lo=seg[0].slot,hi=seg[seg.length-1].slot;let appChanged=0;
    for(const r of rows){
      if(r.slot<lo||r.slot>hi||Math.abs(r.p-threshold)>margin)continue;
      const targetOpen=((r.slot%2)+2)%2===openParity;
      const q=targetOpen?Math.max(r.p,threshold+.04):Math.min(r.p,threshold-.04);
      if((q>=threshold)!==(r.p>=threshold)){changed++;appChanged++;if(mode==='local')localChanged++;else globalChanged++;}
      out[r.index]=q;
    }
    applications.push({startSec:seg[0].event.time,endSec:seg[seg.length-1].event.time,
      items:seg.length,span,occupancy,separation,openParity,mode,changed:appChanged});
  }
  return {probabilities:out,info:{enabled:applications.length>0,aligned:rows.length,uniqueSlots:reps.length,
    strongSegments:strongCount,totalStrongRows:totalStrong,votes,counts,globalEnabled,
    globalOpenParity:globalEnabled?winner:null,globalVoteShare:voteShare,applications:applications.length,
    changed,localChanged,globalChanged,policy:policy.name||'alternating-eighth-relative-decay'}};
}

'''
    s = s.replace(marker, fn + marker)

variants = [
    'ride-open-decay-rescue-alt-strict',
    'ride-open-decay-rescue-alt-local',
    'ride-open-decay-rescue-alt-global',
]

# Add accepted variant names immediately after the current production variant.
needle = "'ride-open-decay-rescue'"
if variants[0] not in s:
    replacement = needle + ',' + ','.join(repr(x) for x in variants)
    first = s.find(needle)
    if first < 0:
        raise SystemExit('production variant marker missing')
    s = s[:first] + s[first:].replace(needle, replacement, 1)

# Include the three variants wherever production ride/open decay logic is gated.
for suffix in [
    "||requestedVariant==='ride-selective70-decay-rescue'",
    "||requestedVariant==='ride-selective80-decay-rescue'",
    "||requestedVariant==='ride-selective90-decay-rescue'",
]:
    old = "requestedVariant==='ride-open-decay-rescue'" + suffix
    if old in s and variants[0] not in s[s.find(old):s.find(old)+500]:
        extra = "requestedVariant==='ride-open-decay-rescue'" + ''.join(f"||requestedVariant==='{x}'" for x in variants) + suffix
        s = s.replace(old, extra)

anchor = '    let probSum=0,maxProbability=0,basePromoted=0;'
if 'alt-strict-local' not in s:
    if anchor not in s:
        raise SystemExit('probability loop marker missing')
    block = r'''    if(requestedVariant==='ride-open-decay-rescue-alt-strict'||requestedVariant==='ride-open-decay-rescue-alt-local'||requestedVariant==='ride-open-decay-rescue-alt-global'){
      const policies={
        'ride-open-decay-rescue-alt-strict':{name:'alt-strict-local',minItems:8,minOccupancy:.70,minSeparation:.14,localMargin:.32,global:false},
        'ride-open-decay-rescue-alt-local':{name:'alt-balanced-local',minItems:6,minOccupancy:.65,minSeparation:.10,localMargin:.36,global:false},
        'ride-open-decay-rescue-alt-global':{name:'alt-global-calibrated',minItems:6,minOccupancy:.65,minSeparation:.10,localMargin:.36,
          global:true,globalMinSegments:3,globalMinRows:40,globalVoteShare:.75,globalMinItems:2,globalMinOccupancy:.50,globalMargin:.28}
      };
      const seq=alternatingEighthRescore(samples,hats,events,probabilities,bpm,Number(context?.barPhaseSec),threshold,policies[requestedVariant]);
      probabilities=seq.probabilities;sequenceInfo.alternating=seq.info;
    }else sequenceInfo.alternating={enabled:false};
'''
    s = s.replace(anchor, block + anchor)

p.write_text(s)
