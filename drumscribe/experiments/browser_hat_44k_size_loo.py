"""Size sweep for the validated 44.1-kHz hat ExtraTrees classifier.

Uses the same fully nested LOO protocol/features as browser_hat_meta_nested_loo,
but compares smaller forests. Each variant gets its own inner threshold/repeat
selection. Goal: identify the smallest browser-exportable model that still
beats the true browser baseline out-of-sample.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
spec=importlib.util.spec_from_file_location("bh",EXP/"browser_hat_meta_nested_loo.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

VARIANTS={
 "micro":dict(n_estimators=32,max_depth=7,min_samples_leaf=8),
 "tiny":dict(n_estimators=64,max_depth=8,min_samples_leaf=6),
 "small":dict(n_estimators=96,max_depth=10,min_samples_leaf=5),
 "medium":dict(n_estimators=160,max_depth=12,min_samples_leaf=4),
 "full":dict(n_estimators=260,max_depth=12,min_samples_leaf=4),
}

def train(data,songs,var):
    X=np.concatenate([data[s]["X"] for s in songs]);y=np.concatenate([data[s]["y"] for s in songs])
    return ExtraTreesClassifier(**VARIANTS[var],class_weight="balanced",random_state=198,n_jobs=-1).fit(X,y)

def main():
    data=b.prepare();base={s:b.score(s,data[s]["rows"]) for s in b.SONGS};bag=b.aggregate(base)
    results={}
    for var in VARIANTS:
        held={};det={}
        for h in b.SONGS:
            outer=[s for s in b.SONGS if s!=h];pcache={}
            for v in outer:
                tr=[s for s in outer if s!=v];m=train(data,tr,var);pcache[v]=m.predict_proba(data[v]["X"])[:,1]
            rank=[];bouter=b.aggregate({s:base[s] for s in outer})
            for thr in (.35,.45,.55,.65):
              for rep in (.50,.75,1.0):
                cfg={"thr":thr,"rescue":"repeat","rep":rep}
                sc={v:b.score(v,b.build(data[v],pcache[v],cfg)) for v in outer};a=b.aggregate(sc)
                valid=a["f1"]>=bouter["f1"]-.003 and a["by_group"]["hat"]["f1"]>=bouter["by_group"]["hat"]["f1"]-.010
                rank.append((valid,b.objective(a),a["f1"],thr,rep,a))
            rank.sort(reverse=True);valid,objv,_,thr,rep,inner=rank[0]
            m=train(data,outer,var);p=m.predict_proba(data[h]["X"])[:,1]
            cfg={"thr":thr,"rescue":"repeat","rep":rep};sc=b.score(h,b.build(data[h],p,cfg));held[h]=sc
            det[h]={"threshold":thr,"repeat":rep,"innerEligible":bool(valid),"heldF1":float(sc["f1"]),"hat":sc["by_group"]["hat"]}
        a=b.aggregate(held);results[var]={"params":VARIANTS[var],"aggregate":a,"objective":float(b.objective(a)),"songs":det}
        print("VARIANT",var,json.dumps(results[var],ensure_ascii=False),flush=True)
    out={"schema":1,"description":"44.1k hat ExtraTrees size sweep with fully nested LOO.","baseline":bag,"variants":results}
    (EXP/"results-browser-hat-44k-size-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(bag,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
