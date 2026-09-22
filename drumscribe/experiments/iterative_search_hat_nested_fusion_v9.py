"""Cycles 219-221: nested-LOO 44.1-kHz hi-hat fusion on the current best all-part MIDI.

Prediction for each held song uses only models trained on the other four songs.
The held chart is scoring-only. Inner threshold selection is also leave-one-song-out
inside those four training songs.

219: current best vs replace / intersection / union using the medium 44.1-kHz forest.
220: compare micro / medium / full forests with the safest winning fusion mode.
221: compare no repeat rescue / 0.75 / 1.00 repeat rescue and matching windows.

All candidates are materialized as MIDI, re-read, and scored with the canonical
80-ms all-part evaluator. No song-name rules or target-chart features are used
for prediction.
"""
from __future__ import annotations
import importlib.util, json
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
BASE=EXP/"generated-search-best-merge-v8/cycle216/c216_both"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

bm=loadmod("bm",EXP/"iterative_search_best_merge_v8.py")
bh=loadmod("bh_nested",EXP/"browser_hat_meta_nested_loo.py")
cf=loadmod("cf",EXP/"iterative_search_browser_component_fusion.py")

SONGS=bm.SONGS; GROUPS=bm.GROUPS
FORESTS={
    "micro":dict(n_estimators=32,max_depth=7,min_samples_leaf=8),
    "medium":dict(n_estimators=160,max_depth=12,min_samples_leaf=4),
    "full":dict(n_estimators=260,max_depth=12,min_samples_leaf=4),
}

def train(data,songs,variant):
    X=np.concatenate([data[s]["X"] for s in songs])
    y=np.concatenate([data[s]["y"] for s in songs])
    return ExtraTreesClassifier(**FORESTS[variant],class_weight="balanced",
        random_state=219,n_jobs=-1).fit(X,y)

def nested_predictions(data,variant):
    """Return held-song probabilities and inner-selected threshold/repeat."""
    out={}
    for held in SONGS:
        outer=[s for s in SONGS if s!=held]
        pcache={}
        for valid in outer:
            tr=[s for s in outer if s!=valid]
            model=train(data,tr,variant)
            pcache[valid]=model.predict_proba(data[valid]["X"])[:,1]

        base_outer=bh.aggregate({s:bh.score(s,data[s]["rows"]) for s in outer})
        ranked=[]
        for thr in (.35,.45,.55,.65):
            for rep in (.50,.75,1.00):
                cfg={"thr":thr,"rescue":"repeat","rep":rep}
                scores={s:bh.score(s,bh.build(data[s],pcache[s],cfg)) for s in outer}
                agg=bh.aggregate(scores)
                eligible=(agg["f1"]>=base_outer["f1"]-.003 and
                          agg["by_group"]["hat"]["f1"]>=base_outer["by_group"]["hat"]["f1"]-.010)
                ranked.append((eligible,bh.objective(agg),agg["f1"],thr,rep))
        ranked.sort(reverse=True)
        eligible,obj,_,thr,rep=ranked[0]

        model=train(data,outer,variant)
        p=model.predict_proba(data[held]["X"])[:,1]
        out[held]={"p":p,"threshold":thr,"repeat":rep,
                   "innerEligible":bool(eligible),"innerObjective":float(obj)}
        print("HELD_MODEL",variant,held,json.dumps(
            {"threshold":thr,"repeat":rep,"innerEligible":bool(eligible),
             "innerObjective":float(obj)},ensure_ascii=False),flush=True)
    return out

def accepted_hats(d,p,cfg,repeat_override=None,rescue=True):
    rep=cfg["repeat"] if repeat_override is None else repeat_override
    cc={"thr":cfg["threshold"],"rescue":"repeat" if rescue else "none","rep":rep}
    rows=bh.build(d,p,cc)
    return sorted(t for t,g in rows if g=="hat")

def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)

def dedupe_times(xs,w=.035):
    out=[]
    for t in sorted(xs):
        if not out or t-out[-1]>=w: out.append(t)
    return out

def base_rows(song):
    return bm.rows(BASE,song)

def fuse(song,data,pred,mode,window=.045,repeat_override=None,rescue=True):
    rr=base_rows(song)
    base_hat=sorted(t for t,g in rr if g=="hat")
    accepted=accepted_hats(data[song],pred[song]["p"],pred[song],
                           repeat_override=repeat_override,rescue=rescue)
    if mode=="base":
        hats=base_hat
    elif mode=="replace":
        hats=accepted
    elif mode=="intersection":
        hats=[t for t in base_hat if near(accepted,t,window)]
    elif mode=="union":
        # Preserve base timing when the model already supports a nearby event;
        # add only genuinely new accepted events.
        hats=list(base_hat)
        hats += [t for t in accepted if not near(base_hat,t,window)]
        hats=dedupe_times(hats)
    else:
        raise ValueError(mode)
    return cf.enforce([x for x in rr if x[1]!="hat"]+[(t,"hat") for t in hats])

def evaluate(name,data,pred,variant,mode,outdir,window=.045,repeat_override=None,rescue=True):
    result={"model_variant":variant,"mode":mode,"window":window,
            "repeat_override":repeat_override,"rescue":rescue,"songs":{}}
    tot=Counter()
    for song in SONGS:
        rr=fuse(song,data,pred,mode,window,repeat_override,rescue)
        m=bm.meta(song); path=outdir/name/f"{song}.mid"
        bm.write(path,rr,float(m["bpm"]))
        pe=bm.ev.midi_events(path)
        tr=bm.ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
        sc=bm.ev.score(pe,tr,shift); cfusion=bm.ev.confusion(pe,tr,shift)
        sc["confusion"]=cfusion; sc["count_ratio"]=bm.ev.count_ratios(sc)
        result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=cfusion["kick_to_snare"],snare_to_kick=cfusion["snare_to_kick"])
        for g,z in sc["by_group"].items():
            tot[f"{g}_tp"]+=z["tp"]; tot[f"{g}_pred"]+=z["predicted"]; tot[f"{g}_ref"]+=z["reference"]

    tp,n,r=tot["tp"],tot["predicted"],tot["reference"]
    sm={"tp":tp,"predicted":n,"reference":r,
        "precision":tp/n if n else 0,"recall":tp/r if r else 0,
        "f1":2*tp/(n+r) if n+r else 0,
        "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
        "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]; song_f=[]
        for s in SONGS:
            z=result["songs"][s]["by_group"].get(g,{})
            if z.get("reference",0):
                song_f.append(2*z.get("tp",0)/(z.get("predicted",0)+z["reference"])
                              if z.get("predicted",0)+z["reference"] else 0)
        sm["by_group"][g]={
            "tp":a,"predicted":b,"reference":c,
            "precision":a/b if b else 0,"recall":a/c if c else 0,
            "f1":2*a/(b+c) if b+c else 0,
            "false_discovery_rate":(b-a)/b if b else 0,
            "miss_rate":(c-a)/c if c else 0,
            "count_ratio":b/c if c else None,
            "mean_song_f1":sum(song_f)/len(song_f) if song_f else None,
            "worst_song_f1":min(song_f) if song_f else None}
    result["summary"]=sm
    result["canonical_score"]=bm.sel.score(sm)
    result["detailed"]=bm.detail.compare_dir(outdir/name,name)["aggregate"]
    return result

def choose(candidates,baseline):
    d=bm.sel.select(candidates,baseline["summary"],target_parts=("hat",),
                    max_part_drop=.006,target_tolerance=.004)
    for n in candidates: candidates[n]["guard"]=d["guards"][n]
    return d

def brief(x):
    h=x["summary"]["by_group"]["hat"]
    return {"f1":x["summary"]["f1"],"hat_f1":h["f1"],"hat_p":h["precision"],
            "hat_r":h["recall"],"hat_fdr":h["false_discovery_rate"],
            "hat_worst":h["worst_song_f1"],"score":x["canonical_score"]["score"]}

def main():
    data=bh.prepare()
    preds={v:nested_predictions(data,v) for v in ("micro","medium","full")}
    root=EXP/"generated-search-hat-nested-fusion-v9"
    report={"schema":1,
            "description":"Cycles 219-221: nested-LOO 44.1k hat classifier fused into c216_both; held chart scoring-only.",
            "cycles":[]}

    baseline=evaluate("baseline",data,preds["medium"],"medium","base",root/"baseline")
    print("BASE",json.dumps(brief(baseline),ensure_ascii=False),flush=True)

    # Cycle 219: three distinct fusion hypotheses plus unchanged baseline.
    c219={"c219_base":baseline}
    for mode in ("replace","intersection","union"):
        n=f"c219_{mode}"
        c219[n]=evaluate(n,data,preds["medium"],"medium",mode,root/"cycle219")
        print("SUMMARY",n,json.dumps(brief(c219[n]),ensure_ascii=False),flush=True)
    d219=choose(c219,baseline); w219=d219["winner"] or "c219_base"
    report["cycles"].append({"cycle":219,"candidates":c219,"winner":w219,
                             "ranking":d219["ranking"],"guards":d219["guards"]})
    b219=c219[w219]

    # If the guard retains baseline, use the conservative intersection as the
    # next test mode rather than turning subsequent cycles into no-ops.
    mode220=b219["mode"] if b219["mode"]!="base" else "intersection"

    # Cycle 220: model capacity. All are fully nested LOO.
    c220={"c220_base":baseline}
    for var in ("micro","medium","full"):
        n=f"c220_{var}"
        c220[n]=evaluate(n,data,preds[var],var,mode220,root/"cycle220")
        print("SUMMARY",n,json.dumps(brief(c220[n]),ensure_ascii=False),flush=True)
    d220=choose(c220,baseline); w220=d220["winner"] or "c220_base"
    report["cycles"].append({"cycle":220,"candidates":c220,"winner":w220,
                             "ranking":d220["ranking"],"guards":d220["guards"]})
    b220=c220[w220]
    var221=b220["model_variant"] if b220["mode"]!="base" else "medium"
    mode221=b220["mode"] if b220["mode"]!="base" else mode220

    # Cycle 221: repeat rescue and temporal matching tolerance.
    c221={"c221_base":baseline}
    settings=[
        ("c221_no_rescue",.045,None,False),
        ("c221_rep75_w35",.035,.75,True),
        ("c221_rep100_w60",.060,1.00,True),
    ]
    for n,w,rep,rescue in settings:
        c221[n]=evaluate(n,data,preds[var221],var221,mode221,root/"cycle221",
                         window=w,repeat_override=rep,rescue=rescue)
        print("SUMMARY",n,json.dumps(brief(c221[n]),ensure_ascii=False),flush=True)
    d221=choose(c221,baseline); w221=d221["winner"] or "c221_base"
    report["cycles"].append({"cycle":221,"candidates":c221,"winner":w221,
                             "ranking":d221["ranking"],"guards":d221["guards"]})

    pool=[baseline,c219[w219],c220[w220],c221[w221]]
    best=max(pool,key=lambda x:x["canonical_score"]["score"])
    report["baseline"]=baseline
    report["final"]={"summary":best["summary"],"canonical_score":best["canonical_score"],
                     "model_variant":best["model_variant"],"mode":best["mode"],
                     "window":best["window"],"repeat_override":best["repeat_override"],
                     "rescue":best["rescue"],"detailed":best["detailed"]}
    (EXP/"results-iterative-hat-nested-fusion-v9.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps({"config":{k:report["final"][k] for k in
        ("model_variant","mode","window","repeat_override","rescue")},
        "metrics":brief(best)},ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    main()
