"""Cycles 160-162: song-adaptive pedal-hi-hat suppression.

Base: metal-reclass c159_crash_recall.
Prediction-time evidence:
- current pedal stream
- raw/strict/balanced/recall pedal component streams
- current hand-hat stream
- BPM

A song with strong current/recall agreement keeps the current pedal stream.
A detector-sparse song keeps the prior sparse-rescue result. Only the
middle-agreement regime is filtered, using independent detector votes,
periodicity, and hand-hat coincidence.

chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util, json
from collections import Counter
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

repair=loadmod("repair",EXP/"iterative_search_overtrigger_repair.py")
ev=repair.ev; sel=repair.sel; detail=repair.detail; base=repair.base

SONGS=repair.SONGS; GROUPS=repair.GROUPS
BASE=EXP/"generated-search-metal-reclass/cycle159/c159_crash_recall"
RAW=EXP/"generated-search-fusion-v5/cycle129/c129_balanced"
STRICT=EXP/"generated-search-best-fusion/cycle81/c81_pedal_strict"
BAL=EXP/"generated-search-best-fusion/cycle81/c81_pedal_balanced"
RECALL=EXP/"generated-search-pedal-component/cycle64/c64_recall"

def rows(path,song): return repair.rows(path,song)
def meta(song): return repair.meta(song)
def near(xs,t,w): return any(abs(x-t)<=w for x in xs)

def periodic_support(times,t,bpm):
    if len(times)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.065 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def votes(t,sources,w=.035):
    return sum(1 for xs in sources if near(xs,t,w))

def make_pedal(song,strong_ratio,per_thr,vote_thr,sparse_ratio=.08):
    e=rows(BASE,song)
    current=[t for t,g in e if g=="pedal_hat"]
    hats=[t for t,g in e if g=="hat"]
    raw=[t for t,g in rows(RAW,song) if g=="pedal_hat"]
    strict=[t for t,g in rows(STRICT,song) if g=="pedal_hat"]
    bal=[t for t,g in rows(BAL,song) if g=="pedal_hat"]
    rec=[t for t,g in rows(RECALL,song) if g=="pedal_hat"]
    ratio=len(raw)/max(1,len(rec))
    m=meta(song); bpm=float(m["bpm"])
    sources=[raw,strict,bal,rec]
    union=sorted(set(round(t,5) for src in sources for t in src))

    if ratio>=strong_ratio or ratio<sparse_ratio:
        chosen=list(current); regime="keep"
    else:
        chosen=[]; regime="filtered"
        for t in current:
            v=votes(t,sources)
            per=periodic_support(union,t,bpm)
            overlap=near(hats,t,.030)
            if overlap:
                keep=v>=vote_thr and per>=per_thr
            else:
                keep=v>=max(2,vote_thr-1) and per>=per_thr
            if keep:chosen.append(t)

    others=[x for x in e if x[1]!="pedal_hat"]
    return repair.enforce(others+[(t,"pedal_hat") for t in chosen]),{
      "raw":len(raw),"strict":len(strict),"balanced":len(bal),"recall":len(rec),
      "current":len(current),"hat":len(hats),"agreement_ratio":ratio,
      "regime":regime,"chosen":len(chosen)
    }

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,strong_ratio,per_thr,vote_thr,outdir):
    result={"strong_ratio":strong_ratio,"periodic_threshold":per_thr,"vote_threshold":vote_thr,"song_decisions":{},"songs":{}}
    tot=Counter()
    for song in SONGS:
        m=meta(song);events,diag=make_pedal(song,strong_ratio,per_thr,vote_thr)
        result["song_decisions"][song]=diag
        p=outdir/name/f"{song}.mid";write(p,events,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,ref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":ref,"precision":tp/n if n else 0,"recall":tp/ref if ref else 0,
       "f1":2*tp/(n+ref) if n+ref else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,"false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s);return result

def choose(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("pedal_hat",),max_part_drop=.035,target_tolerance=.012)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-pedal-song-adaptive";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline",0.0,0.0,1,root/"baseline")

    res={}
    for name,r in [("c160_gate40",.40),("c160_gate60",.60),("c160_gate80",.80)]:
        res[name]=evaluate(name,r,.50,3,root/"cycle160")
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],"pedal":res[name]["summary"]["by_group"]["pedal_hat"],"decisions":res[name]["song_decisions"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":160,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,p in [("c161_per25",.25),("c161_per50",.50),("c161_per75",.75)]:
        res[name]=evaluate(name,best["strong_ratio"],p,best["vote_threshold"],root/"cycle161")
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],"pedal":res[name]["summary"]["by_group"]["pedal_hat"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":161,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,v in [("c162_vote2",2),("c162_vote3",3),("c162_vote4",4)]:
        res[name]=evaluate(name,best["strong_ratio"],best["periodic_threshold"],v,root/"cycle162")
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],"pedal":res[name]["summary"]["by_group"]["pedal_hat"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":162,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "strong_ratio":best["strong_ratio"],"periodic_threshold":best["periodic_threshold"],"vote_threshold":best["vote_threshold"],
      "song_decisions":best["song_decisions"],"detailed":detail.compare_dir(root/"cycle162"/win,win)["aggregate"]}
    (EXP/"results-iterative-pedal-song-adaptive.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
