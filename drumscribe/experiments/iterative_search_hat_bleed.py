"""Cycles 160-162: adaptive suppression of kick/snare bleed into hi-hat.

Base: generated-search-metal-reclass/cycle159/c159_crash_recall.

The current dominant metal error is kick/snare -> hat. We only reconsider hat
events within a small kick/snare window. A conflicting hat survives when
independent hat detectors and/or repeated rhythmic support agree strongly
enough. chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util, json, math
from collections import Counter
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

repair=loadmod("repair",EXP/"iterative_search_overtrigger_repair.py")
ev=repair.ev; sel=repair.sel; detail=repair.detail; base=repair.base
SONGS=repair.SONGS; GROUPS=repair.GROUPS
BASE=EXP/"generated-search-metal-reclass/cycle159/c159_crash_recall"

HAT_SOURCES=[
    EXP/"generated-search-crossstem-hat/cycle85/c85_strict",
    EXP/"generated-search-hat-precision/cycle75/c75_repeat5",
    EXP/"generated-search-pattern-consensus/cycle56/c56_window2",
]

def rows(path,song): return repair.rows(path,song)
def meta(song): return repair.meta(song)

def hat_votes(song,t):
    src=repair.source_times(HAT_SOURCES,song,"hat")
    return repair.source_votes(src,t,.045)

def conflict_features(song,events,t):
    hats=[x for x,g in events if g=="hat"]
    kicks=[x for x,g in events if g=="kick"]
    snares=[x for x,g in events if g=="snare"]
    _,ph,_,bar=repair.timing(song,events)
    return {
      "kick":repair.near(kicks,t,.032),
      "snare":repair.near(snares,t,.032),
      "votes":hat_votes(song,t),
      "rep":repair.rep_support(hats,t,ph,bar),
    }

def keep_conflicting(f,mode):
    v,r=f["votes"],f["rep"]
    if mode=="base": return True
    if mode=="balanced":
        return v>=2 or (v>=1 and r>=4)
    if mode=="strict":
        return v>=3 or (v>=2 and r>=3)
    if mode=="consensus_repeat":
        return v>=2 and r>=2
    if mode=="kick_strict":
        if f["kick"]:
            return v>=3 or (v>=2 and r>=3)
        return v>=2 or (v>=1 and r>=4)
    if mode=="kick_very_strict":
        if f["kick"]:
            return v>=3 or (v>=2 and r>=4)
        return v>=2 or (v>=1 and r>=4)
    return True

def filter_hat(song,events,mode,adaptive_thr=None):
    hats=[t for t,g in events if g=="hat"]
    feats=[(t,conflict_features(song,events,t)) for t in hats]
    conflict_n=sum(1 for _,f in feats if f["kick"] or f["snare"])
    frac=conflict_n/max(1,len(hats))

    local_mode=mode
    if mode=="adaptive":
        # Song-level aggressiveness is inferred from prediction structure only.
        # High conflict fractions get a stricter gate; lower-conflict songs keep
        # the balanced gate to preserve legitimate simultaneous hat patterns.
        local_mode="strict" if frac >= adaptive_thr else "balanced"

    keep=[]
    for t,f in feats:
        if not(f["kick"] or f["snare"]):
            keep.append(t); continue
        if keep_conflicting(f,local_mode):
            keep.append(t)

    out=[e for e in events if e[1]!="hat"]+[(t,"hat") for t in keep]
    return repair.enforce(out),frac,local_mode

def build(song,mode,adaptive_thr=None):
    e=rows(BASE,song)
    return filter_hat(song,e,mode,adaptive_thr)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,adaptive_thr,outdir):
    result={"mode":mode,"adaptive_thr":adaptive_thr,"songs":{}}; tot=Counter()
    for song in SONGS:
        m=meta(song); events,frac,local_mode=build(song,mode,adaptive_thr)
        p=outdir/name/f"{song}.mid"; write(p,events,float(m["bpm"]))
        pred=ev.midi_events(p); truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift); cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf; sc["count_ratio"]=ev.count_ratios(sc)
        sc["hat_conflict_fraction"]=frac; sc["hat_gate_mode"]=local_mode
        result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],
                   kick_to_hat=cf["class_errors"].get("kick_to_hat",0),
                   snare_to_hat=cf["class_errors"].get("snare_to_hat",0))
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"]; tot[f"{g}_pred"]+=x["predicted"]; tot[f"{g}_ref"]+=x["reference"]

    tp,n,ref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":ref,"precision":tp/n if n else 0,
       "recall":tp/ref if ref else 0,"f1":2*tp/(n+ref) if n+ref else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "kick_to_hat":tot["kick_to_hat"],"snare_to_hat":tot["snare_to_hat"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]; sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{}); rr=x.get("reference",0)
            if rr: sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,
          "false_discovery_rate":(b-a)/b if b else 0,
          "miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,
          "mean_song_f1":sum(sf)/len(sf) if sf else None,
          "worst_song_f1":min(sf) if sf else None}
    can=sel.score(s)
    # Directly penalize the specific failure mode being repaired.
    href=max(1,s["by_group"]["hat"]["reference"])
    bleed=(s["kick_to_hat"]+s["snare_to_hat"])/href
    result["summary"]=s; result["canonical_score"]=can
    result["selection_score"]=round(can["score"]-.06*bleed,6)
    return result

def choose(candidates,baseline):
    ranking=[]; guards={}
    for name,obj in candidates.items():
        guard=sel.eligibility(obj["summary"],baseline["summary"],target_parts=("hat",),
                              max_part_drop=.025,target_tolerance=.012)
        obj["guard"]=guard; guards[name]=guard
        ranking.append((guard["eligible"],obj["selection_score"],obj["summary"]["f1"],name))
    ranking.sort(reverse=True)
    winner=next((n for ok,_,_,n in ranking if ok),None)
    return {"winner":winner,"ranking":[x[3] for x in ranking],"guards":guards}

def main():
    root=EXP/"generated-search-hat-bleed"; report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","base",None,root/"baseline")

    res={}
    for name,mode in [
      ("c160_base","base"),
      ("c160_balanced","balanced"),
      ("c160_strict","strict"),
      ("c160_consensus_repeat","consensus_repeat"),
    ]:
        res[name]=evaluate(name,mode,None,root/"cycle160")
        print("SUMMARY",name,json.dumps({
          "f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],
          "kick_to_hat":res[name]["summary"]["kick_to_hat"],
          "snare_to_hat":res[name]["summary"]["snare_to_hat"],
          "score":res[name]["selection_score"]
        },ensure_ascii=False),flush=True)
    d=choose(res,baseline); win=d["winner"] or "c160_base"; best=res[win]
    report["cycles"].append({"cycle":160,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,mode in [
      ("c161_base","base"),
      ("c161_kick_strict","kick_strict"),
      ("c161_kick_very_strict","kick_very_strict"),
      ("c161_balanced","balanced"),
    ]:
        # Apply this round directly on the fixed BASE so each rule is interpretable;
        # the winning rule becomes the carried policy for cycle 162.
        res[name]=evaluate(name,mode,None,root/"cycle161")
        print("SUMMARY",name,json.dumps({
          "f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],
          "kick_to_hat":res[name]["summary"]["kick_to_hat"],
          "snare_to_hat":res[name]["summary"]["snare_to_hat"],
          "score":res[name]["selection_score"]
        },ensure_ascii=False),flush=True)
    d=choose(res,best); win=d["winner"] or "c161_base"; best=res[win]
    report["cycles"].append({"cycle":161,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,thr in [
      ("c162_thr20",.20),("c162_thr30",.30),("c162_thr40",.40),("c162_thr50",.50)
    ]:
        res[name]=evaluate(name,"adaptive",thr,root/"cycle162")
        print("SUMMARY",name,json.dumps({
          "f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],
          "kick_to_hat":res[name]["summary"]["kick_to_hat"],
          "snare_to_hat":res[name]["summary"]["snare_to_hat"],
          "modes":{s:x["hat_gate_mode"] for s,x in res[name]["songs"].items()},
          "fractions":{s:round(x["hat_conflict_fraction"],3) for s,x in res[name]["songs"].items()},
          "score":res[name]["selection_score"]
        },ensure_ascii=False),flush=True)
    d=choose(res,best); win=d["winner"] or d["ranking"][0]; best=res[win]
    report["cycles"].append({"cycle":162,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    final_dir=root/"cycle162"/win
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],
      "selection_score":best["selection_score"],"mode":best["mode"],"adaptive_thr":best["adaptive_thr"],
      "detailed":detail.compare_dir(final_dir,win)["aggregate"]}
    (EXP/"results-iterative-hat-bleed.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__": main()
