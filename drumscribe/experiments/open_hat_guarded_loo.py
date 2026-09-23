"""Cycle 4: guarded song-adaptive open-hi-hat promotion.

Use the Cycle-3 robust-normalized timbre ExtraTrees, but default every candidate
to closed unless the song itself contains enough high-confidence open-hat
evidence. The gate uses predicted probabilities only (no song identity/chart).

Nested LOO selects a fixed probability threshold + predicted-open-density guard
from the four training songs. Held-out chart is scoring only.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";OUT=EXP/"generated-search-open-hat-guarded-loo"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
PROB=[.40,.45,.50,.55,.60]
GATES=[.10,.15,.20,.25,.30]

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
sn=loadmod("openhat_norm_guard",EXP/"open_hat_songnorm_loo.py");oh=sn.oh

def train(d,songs):
    X=np.concatenate([d[s]["X"]["timbre_norm"] for s in songs])
    y=np.concatenate([(d[s]["y"]==1).astype(np.int8) for s in songs])
    return ExtraTreesClassifier(n_estimators=320,max_depth=13,min_samples_leaf=4,
        class_weight="balanced",random_state=560,n_jobs=-1).fit(X,y)

def prob(model,X):
    p=model.predict_proba(X);return p[:,list(model.classes_).index(1)]

def decode(d,s,p,th,gate):
    raw=p>=th;ratio=float(np.mean(raw)) if len(raw) else 0.
    active=ratio>=gate
    op=[t for t,v in zip(d[s]["hats"],raw) if active and v]
    cl=[t for t,v in zip(d[s]["hats"],raw) if (not active) or not v]
    return op,cl,ratio,active

def met(d,s,p,th,gate):
    op,cl,ratio,active=decode(d,s,p,th,gate)
    return oh.articulation_metrics(op,cl,d[s]["refs"]),ratio,active

def aggregate(ms):
    z=Counter()
    for m in ms.values():
        for c in ("open","closed"):
            q=m[c];z[f"{c}t"]+=q["tp"];z[f"{c}p"]+=q["predicted"];z[f"{c}r"]+=q["reference"]
    out={}
    for c in ("open","closed"):
        tp,p,r=z[f"{c}t"],z[f"{c}p"],z[f"{c}r"]
        out[c]={"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,
            "recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"]);return out

def select(d,outer):
    probs={}
    for val in outer:
        m=train(d,[s for s in outer if s!=val]);probs[val]=prob(m,d[val]["X"]["timbre_norm"])
    base=aggregate({s:oh.articulation_metrics([],d[s]["hats"],d[s]["refs"]) for s in outer})
    rows=[]
    for th in PROB:
      for gate in GATES:
        mm={};flags={}
        for s in outer:
            mm[s],ratio,active=met(d,s,probs[s],th,gate);flags[s]={"ratio":ratio,"active":active}
        a=aggregate(mm)
        # Stronger guard than Cycle 3: preserve closed F1 within 0.01 of all-closed.
        eligible=a["closed"]["f1"]>=base["closed"]["f1"]-.010
        score=a["macroF1"]+.05*a["open"]["precision"]
        rows.append((eligible,score,a["macroF1"],a["open"]["precision"],th,gate,a,flags))
    rows.sort(reverse=True)
    best=next((x for x in rows if x[0]),rows[0])
    return best[4],best[5],{"baseline":base,"ranking":[{"probThreshold":r[4],"densityGate":r[5],
        "eligible":r[0],"score":r[1],"macroF1":r[2],"openPrecision":r[3],
        "openF1":r[6]["open"]["f1"],"closedF1":r[6]["closed"]["f1"],"flags":r[7]} for r in rows[:12]]}

def main():
    d=sn.prepare();base=oh.baseline(d);per={};folds={}
    for held in SONGS:
        outer=[s for s in SONGS if s!=held];th,gate,inner=select(d,outer)
        m=train(d,outer);p=prob(m,d[held]["X"]["timbre_norm"])
        op,cl,ratio,active=decode(d,held,p,th,gate)
        # write real MIDI
        open_set=set(op);rows=[]
        for t,g,pitch in d[held]["rows"]:
            rows.append((t,"open_hat",46) if g=="hat" and t in open_set else (t,g,pitch))
        path=OUT/f"{held}.mid";oh.write_midi(path,rows,float(d[held]["side"]["bpm"]))
        rr=oh.reread_articulation(path);mm=oh.articulation_metrics(rr["open"],rr["closed"],d[held]["refs"])
        per[held]=mm;folds[held]={"probThreshold":th,"densityGate":gate,"predictedOpenRatio":ratio,
            "gateActive":active,"metrics":mm,"inner":inner}
    summary=aggregate(per)
    result={"schema":1,"description":"Nested-LOO song-level evidence guard on normalized-timbre open-hat promotion.",
      "baselineAllClosed":base,"summary":summary,"folds":folds,
      "guard":{"onsetTimesChanged":False,"eventCountsChanged":False,"otherDrumClassesChanged":False,
               "songIdentityUsed":False,"heldOutChartUsedForGate":False}}
    (EXP/"results-open-hat-guarded-loo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(summary,ensure_ascii=False),flush=True)
    for s,z in folds.items():print("FOLD",s,json.dumps({"th":z["probThreshold"],"gate":z["densityGate"],"ratio":z["predictedOpenRatio"],"active":z["gateActive"],"metrics":z["metrics"]},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
