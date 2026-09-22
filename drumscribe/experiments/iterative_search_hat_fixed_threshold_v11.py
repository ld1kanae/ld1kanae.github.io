"""Cycles 225-227: deployable fixed-threshold 44.1-kHz hat filter.

Previous nested-LOO work (219-224) selected a probability threshold separately for
each held song using the other four labeled songs. That is valid for model
selection, but a production browser cannot select a new threshold per unseen
song. This experiment removes that degree of freedom:

- each held song is predicted by an ExtraTrees model trained on the other four;
- ONE fixed probability threshold is used across all held songs;
- repeat rescue, intersection window, and density guard are also fixed globally;
- the held song's chart is never read until final scoring.

Prediction features are the same 44.1-kHz browser-native spectral/rhythm features
from browser_hat_meta_nested_loo.py. Every candidate is written as a real MIDI,
re-read, then scored against chart.mid.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
BASE=EXP/"generated-search-best-merge-v8/cycle216/c216_both"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

bh=loadmod("bh_fixed",EXP/"browser_hat_meta_nested_loo.py")
bm=loadmod("bm_fixed",EXP/"iterative_search_best_merge_v8.py")
cf=loadmod("cf_fixed",EXP/"iterative_search_browser_component_fusion.py")

SONGS=bm.SONGS; GROUPS=bm.GROUPS
FORESTS={
    "micro":dict(n_estimators=32,max_depth=7,min_samples_leaf=8),
    "small":dict(n_estimators=96,max_depth=10,min_samples_leaf=5),
    "medium":dict(n_estimators=160,max_depth=12,min_samples_leaf=4),
    "full":dict(n_estimators=260,max_depth=12,min_samples_leaf=4),
}

def train(data,songs,variant):
    X=np.concatenate([data[s]["X"] for s in songs])
    y=np.concatenate([data[s]["y"] for s in songs])
    return ExtraTreesClassifier(**FORESTS[variant],class_weight="balanced",
        random_state=225,n_jobs=-1).fit(X,y)

def held_probabilities(data,variant):
    out={}
    for held in SONGS:
        outer=[s for s in SONGS if s!=held]
        model=train(data,outer,variant)
        # Only X is consumed for held prediction. data[held]["y"] is not touched.
        p=model.predict_proba(data[held]["X"])[:,1]
        out[held]=p
        print("HELD_MODEL",variant,held,json.dumps({
            "trainSongs":outer,"candidates":int(len(p))},ensure_ascii=False),flush=True)
    return out

def base_rows(song):
    return bm.rows(BASE,song)

def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)

def accepted_hats(d,p,prob_thr,repeat_rescue):
    hats=d["hats"]; bpm=float(d["side"]["bpm"]); keep=[]
    for i,t in enumerate(hats):
        ok=float(p[i])>=prob_thr
        if not ok and repeat_rescue is not None:
            ok=bh.periodic(hats,t,bpm)>=repeat_rescue
        if ok: keep.append(t)
    return keep

def build(song,data,preds,prob_thr,repeat_rescue,window,density_guard):
    rr=base_rows(song)
    base_hat=sorted(t for t,g in rr if g=="hat")
    kicks=sorted(t for t,g in rr if g=="kick")
    ratio=len(base_hat)/max(1,len(kicks))
    active=ratio>=density_guard
    if not active:
        hats=base_hat
        accepted=[]
    else:
        accepted=accepted_hats(data[song],preds[song],prob_thr,repeat_rescue)
        hats=[t for t in base_hat if near(accepted,t,window)]
    rows=cf.enforce([x for x in rr if x[1]!="hat"]+[(t,"hat") for t in hats])
    return rows,{
        "hatKickRatio":ratio,"filterActive":active,
        "baseHat":len(base_hat),"acceptedBrowserHat":len(accepted),"outputHat":len(hats)
    }

def evaluate(name,data,preds,variant,prob_thr,repeat_rescue,window,density_guard,outdir):
    result={
        "model_variant":variant,"prob_threshold":prob_thr,
        "repeat_rescue":repeat_rescue,"window":window,
        "density_guard":density_guard,"songs":{},"diagnostic":{}
    }
    tot=Counter()
    for song in SONGS:
        rr,diag=build(song,data,preds,prob_thr,repeat_rescue,window,density_guard)
        result["diagnostic"][song]=diag
        m=bm.meta(song); p=outdir/name/f"{song}.mid"
        bm.write(p,rr,float(m["bpm"]))
        pe=bm.ev.midi_events(p)
        tr=bm.ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
        sc=bm.ev.score(pe,tr,shift); conf=bm.ev.confusion(pe,tr,shift)
        sc["confusion"]=conf; sc["count_ratio"]=bm.ev.count_ratios(sc)
        result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=conf["kick_to_snare"],snare_to_kick=conf["snare_to_kick"])
        for g,z in sc["by_group"].items():
            tot[f"{g}_tp"]+=z["tp"];tot[f"{g}_pred"]+=z["predicted"];tot[f"{g}_ref"]+=z["reference"]

    tp,n,r=tot["tp"],tot["predicted"],tot["reference"]
    sm={"tp":tp,"predicted":n,"reference":r,
        "precision":tp/n if n else 0,"recall":tp/r if r else 0,
        "f1":2*tp/(n+r) if n+r else 0,
        "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
        "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]; sf=[]
        for s in SONGS:
            z=result["songs"][s]["by_group"].get(g,{})
            if z.get("reference",0):
                sf.append(2*z.get("tp",0)/(z.get("predicted",0)+z["reference"])
                          if z.get("predicted",0)+z["reference"] else 0)
        sm["by_group"][g]={
            "tp":a,"predicted":b,"reference":c,
            "precision":a/b if b else 0,"recall":a/c if c else 0,
            "f1":2*a/(b+c) if b+c else 0,
            "false_discovery_rate":(b-a)/b if b else 0,
            "miss_rate":(c-a)/c if c else 0,
            "count_ratio":b/c if c else None,
            "mean_song_f1":sum(sf)/len(sf) if sf else None,
            "worst_song_f1":min(sf) if sf else None}
    result["summary"]=sm
    result["canonical_score"]=bm.sel.score(sm)
    result["detailed"]=bm.detail.compare_dir(outdir/name,name)["aggregate"]
    return result

def baseline(data,preds,outdir):
    # A probability threshold >1 disables filtering while preserving the exact
    # same writer/evaluator path used by candidates.
    return evaluate("baseline",data,preds,"medium",2.0,None,.060,999,outdir)

def choose(candidates,base):
    d=bm.sel.select(candidates,base["summary"],target_parts=("hat",),
                    max_part_drop=.006,target_tolerance=.004)
    for n in candidates:candidates[n]["guard"]=d["guards"][n]
    return d

def brief(x):
    h=x["summary"]["by_group"]["hat"]
    return {"f1":x["summary"]["f1"],"precision":x["summary"]["precision"],
            "hat_f1":h["f1"],"hat_p":h["precision"],"hat_r":h["recall"],
            "hat_fdr":h["false_discovery_rate"],"hat_worst":h["worst_song_f1"],
            "score":x["canonical_score"]["score"]}

def main():
    data=bh.prepare()
    preds={v:held_probabilities(data,v) for v in FORESTS}
    root=EXP/"generated-search-hat-fixed-threshold-v11"
    report={"schema":1,
      "description":"Cycles 225-227: globally fixed 44.1k hat probability threshold and production-observable density guard; held chart scoring-only.",
      "cycles":[]}

    base=baseline(data,preds,root/"baseline")
    print("BASE",json.dumps(brief(base),ensure_ascii=False),flush=True)

    # Cycle 225: fixed global probability threshold, medium forest.
    c225={"c225_base":base}
    for n,t in [("c225_p35",.35),("c225_p45",.45),("c225_p55",.55),("c225_p65",.65)]:
        c225[n]=evaluate(n,data,preds["medium"],"medium",t,1.0,.060,.55,root/"cycle225")
        print("SUMMARY",n,json.dumps({"metrics":brief(c225[n]),"diag":c225[n]["diagnostic"]},ensure_ascii=False),flush=True)
    d225=choose(c225,base); w225=d225["winner"] or "c225_base"; b225=c225[w225]
    report["cycles"].append({"cycle":225,"candidates":c225,"winner":w225,
                             "ranking":d225["ranking"],"guards":d225["guards"]})
    thr=b225["prob_threshold"] if b225["prob_threshold"]<=1 else .45

    # Cycle 226: model capacity with one global threshold.
    c226={"c226_base":base}
    for var in ("micro","small","medium","full"):
        n=f"c226_{var}"
        c226[n]=evaluate(n,data,preds[var],var,thr,1.0,.060,.55,root/"cycle226")
        print("SUMMARY",n,json.dumps(brief(c226[n]),ensure_ascii=False),flush=True)
    d226=choose(c226,b225); w226=d226["winner"] or "c226_base"; b226=c226[w226]
    report["cycles"].append({"cycle":226,"candidates":c226,"winner":w226,
                             "ranking":d226["ranking"],"guards":d226["guards"]})
    var=b226["model_variant"] if b226["prob_threshold"]<=1 else "medium"

    # Cycle 227: fixed temporal rescue/window alternatives.
    c227={"c227_prev":b226}
    settings=[
        ("c227_rep75_w35",.75,.035),
        ("c227_rep100_w60",1.0,.060),
        ("c227_rep100_w80",1.0,.080),
        ("c227_norescue_w60",None,.060),
    ]
    for n,rep,w in settings:
        c227[n]=evaluate(n,data,preds[var],var,thr,rep,w,.55,root/"cycle227")
        print("SUMMARY",n,json.dumps(brief(c227[n]),ensure_ascii=False),flush=True)
    d227=choose(c227,b226); w227=d227["winner"] or "c227_prev"; b227=c227[w227]
    report["cycles"].append({"cycle":227,"candidates":c227,"winner":w227,
                             "ranking":d227["ranking"],"guards":d227["guards"]})

    pool=[base,b225,b226,b227]
    best=max(pool,key=lambda x:x["canonical_score"]["score"])
    report["baseline"]=base
    report["final"]={
        "summary":best["summary"],"canonical_score":best["canonical_score"],
        "model_variant":best["model_variant"],"prob_threshold":best["prob_threshold"],
        "repeat_rescue":best["repeat_rescue"],"window":best["window"],
        "density_guard":best["density_guard"],"diagnostic":best["diagnostic"],
        "detailed":best["detailed"]
    }
    (EXP/"results-iterative-hat-fixed-threshold-v11.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps({"config":{k:report["final"][k] for k in
        ("model_variant","prob_threshold","repeat_rescue","window","density_guard")},
        "metrics":brief(best)},ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__": main()
