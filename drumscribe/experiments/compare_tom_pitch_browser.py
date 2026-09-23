"""Fine-grained tom-pitch score for fresh browser output.

Tom onset matching is one-to-one at +/-80 ms, exactly like the main evaluator.
Reference chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter
from itertools import combinations
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
SONGS=("arcaround","diamondvirgin","kaiju","nanairo","ray")
TOL=.080

ANCHOR_HZ={41:math.sqrt(55*110),45:math.sqrt(110*145),47:math.sqrt(145*190),50:math.sqrt(190*360)}
K3_FIXED={
    "k3_41_45_47":[41,45,47],
    "k3_41_45_50":[41,45,50],
    "k3_41_47_50":[41,47,50],
    "k3_45_47_50":[45,47,50],
}

def k3_absolute_map(centers):
    """Audio-only mapping: choose the ordered 3-note subset whose anchor Hz best matches cluster centers."""
    if len(centers)!=3:return [41,45,50]
    best=None
    for subset in combinations((41,45,47,50),3):
        cost=sum((math.log(max(40,float(h)))-math.log(ANCHOR_HZ[n]))**2 for h,n in zip(centers,subset))
        row=(cost,list(subset))
        if best is None or row[0]<best[0]:best=row
    return best[1]

def candidate_map(info,name):
    k=int(info.get("clusters") or 0)
    if k!=3:return None
    if name in K3_FIXED:return K3_FIXED[name]
    if name=="k3_absolute_anchor_v1":
        return k3_absolute_map(info.get("centersHz") or [])
    return None

def decision_pairs(info,ref,shift,name):
    decisions=info.get("decisions") or []
    mapping=candidate_map(info,name)
    pred=[]
    for d in decisions:
        note=int(d.get("note") or 45)
        rank=d.get("clusterRank")
        if mapping is not None and isinstance(rank,int) and 0<=rank<len(mapping):
            note=mapping[rank]
        pred.append((float(d.get("time") or 0),note))
    rr=[(t+shift,int(note)) for t,g,note in ref if g=="tom"]
    used=set();pairs=[]
    for pt,pn in sorted(pred):
        choices=[i for i,(rt,rn) in enumerate(rr) if i not in used and abs(rt-pt)<=TOL]
        if not choices:continue
        j=min(choices,key=lambda i:abs(rr[i][0]-pt));used.add(j)
        rt,rn=rr[j];pairs.append((pt,pn,rt,rn))
    return pred,rr,pairs


def tier(n):
    n=int(n)
    if n in (41,43):return 41
    if n==45:return 45
    if n in (47,48):return 47
    if n==50:return 50
    return n

def match(pred,ref,shift):
    # pred times are already converted back to audio-local coordinates.
    rr=[(t+shift,int(note)) for t,g,note in ref if g=="tom"]
    pp=[(t,int(note)) for t,g,note in pred if g=="tom"]
    used=set();pairs=[]
    for pt,pn in sorted(pp):
        choices=[i for i,(rt,rn) in enumerate(rr) if i not in used and abs(rt-pt)<=TOL]
        if not choices:continue
        j=min(choices,key=lambda i:abs(rr[i][0]-pt));used.add(j)
        rt,rn=rr[j];pairs.append((pt,pn,rt,rn))
    return pp,rr,pairs

def metrics(pairs):
    if not pairs:return {"matched":0,"exact":None,"tier4":None}
    exact=sum(pn==rn for _,pn,_,rn in pairs)/len(pairs)
    t4=sum(tier(pn)==tier(rn) for _,pn,_,rn in pairs)/len(pairs)
    conf=Counter((tier(rn),tier(pn)) for _,pn,_,rn in pairs)
    return {"matched":len(pairs),"exact":exact,"tier4":t4,
            "confusion":{f"{a}->{b}":v for (a,b),v in sorted(conf.items())}}

def main():
    out={"schema":2,"toleranceSec":TOL,"songs":{},"decisionCandidates":{}}
    allpairs=[]
    candidate_names=["k3_41_45_47","k3_41_45_50","k3_41_47_50","k3_45_47_50","k3_absolute_anchor_v1"]
    candidate_all={name:[] for name in candidate_names}
    for song in SONGS:
        folder=ROOT/"DruMaster/songs"/song
        meta=json.loads((folder/"song.json").read_text())
        side=json.loads((EXP/"generated-v2-browser"/f"{song}.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        export=float(side.get("exportOffsetSec",0) or 0)
        pred0=ev.midi_events(EXP/"generated-v2-browser"/f"{song}.mid")
        pred=[(t-export,g,n) for t,g,n in pred0]
        ref=ev.midi_events(folder/"chart.mid")
        pp,rr,pairs=match(pred,ref,shift);allpairs.extend(pairs)
        m=metrics(pairs);m.update({"predictedTom":len(pp),"referenceTom":len(rr)})
        info=((side.get("adtofInfo") or {}).get("tomPitch") or {})
        m["tomPitchInfo"]={k:info.get(k) for k in ("method","tomCount","clusters","silhouette","centersHz","clusterNoteByRank")}
        m["candidateMaps"]={}
        m["candidateMetrics"]={}
        for name in candidate_names:
            dp,dr,cp=decision_pairs(info,ref,shift,name)
            candidate_all[name].extend(cp)
            m["candidateMaps"][name]=candidate_map(info,name)
            cm=metrics(cp);cm.update({"predictedTom":len(dp),"referenceTom":len(dr)})
            m["candidateMetrics"][name]=cm
        out["songs"][song]=m
    out["summary"]=metrics(allpairs)
    out["summary"]["note45BaselineOnMatched"]=(
      sum(tier(rn)==45 for _,_,_,rn in allpairs)/len(allpairs) if allpairs else None
    )
    out["decisionCandidates"]={name:metrics(pairs) for name,pairs in candidate_all.items()}
    (EXP/"results-tom-pitch-browser.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("CURRENT_MIDI",json.dumps(out["summary"],ensure_ascii=False))
    print("DECISION_CANDIDATES",json.dumps(out["decisionCandidates"],ensure_ascii=False))
    for song,row in out["songs"].items():
        print("TOM_MAP",song,json.dumps({
            "info":row["tomPitchInfo"],
            "maps":row["candidateMaps"],
            "metrics":{k:v.get("tier4") for k,v in row["candidateMetrics"].items()}
        },ensure_ascii=False))

if __name__=="__main__":main()
