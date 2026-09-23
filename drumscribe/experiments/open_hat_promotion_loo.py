"""Cycle 2: conservative open-hi-hat promotion.

Train on the exact deployment candidate distribution:
positive = current browser hat candidate matched to reference MIDI 46
negative = every other current browser hat candidate (matched MIDI 42 or unmatched)

The held-out song is excluded from all fitting and threshold selection.
Three model families reuse the Cycle-1 feature sets.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
OUT=EXP/"generated-search-open-hat-promotion-loo"
THRESHOLDS=[.35,.45,.55,.65,.75,.82,.88,.92]
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
oh=loadmod("openhat_cycle1",EXP/"open_hat_loo.py")
ev=oh.ev

class Model:
    def __init__(self,family):self.family=family;self.scaler=None;self.model=None
    def fit(self,X,y):
        if self.family=="promotion_decay":
            self.scaler=StandardScaler().fit(X);XX=self.scaler.transform(X)
            self.model=LogisticRegression(max_iter=1200,class_weight="balanced",C=.55,solver="lbfgs").fit(XX,y)
        else:
            depth=12 if self.family=="promotion_timbre" else 14
            leaf=5 if self.family=="promotion_timbre" else 4
            self.model=ExtraTreesClassifier(n_estimators=280,max_depth=depth,min_samples_leaf=leaf,
                class_weight="balanced",random_state=460 if self.family=="promotion_timbre" else 461,n_jobs=-1).fit(X,y)
        return self
    def prob(self,X):
        if self.scaler is not None:X=self.scaler.transform(X)
        p=self.model.predict_proba(X);return p[:,list(self.model.classes_).index(1)]

def key(family):
    return "decay" if family=="promotion_decay" else "timbre" if family=="promotion_timbre" else "context"

def train(data,songs,family):
    X=np.concatenate([data[s]["X"][key(family)] for s in songs])
    # Unmatched predicted hats are explicit negatives: do not promote uncertain events.
    y=np.concatenate([(data[s]["y"]==1).astype(np.int8) for s in songs])
    return Model(family).fit(X,y)

def metrics_for(data,s,p,thr):
    hats=data[s]["hats"]
    op=[t for t,v in zip(hats,p) if v>=thr]
    cl=[t for t,v in zip(hats,p) if v<thr]
    return oh.articulation_metrics(op,cl,data[s]["refs"])

def aggregate(ms):
    z=Counter()
    for m in ms.values():
        for c in ("open","closed"):
            q=m[c];z[f"{c}t"]+=q["tp"];z[f"{c}p"]+=q["predicted"];z[f"{c}r"]+=q["reference"]
    out={}
    for c in ("open","closed"):
        tp,p,r=z[f"{c}t"],z[f"{c}p"],z[f"{c}r"]
        out[c]={"tp":tp,"predicted":p,"reference":r,
                "precision":tp/p if p else 0.,"recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"])
    return out

def select_threshold(data,outer,family):
    probs={}
    for val in outer:
        m=train(data,[s for s in outer if s!=val],family)
        probs[val]=m.prob(data[val]["X"][key(family)])
    base=aggregate({s:oh.articulation_metrics([],data[s]["hats"],data[s]["refs"]) for s in outer})
    ranked=[]
    for th in THRESHOLDS:
        a=aggregate({s:metrics_for(data,s,probs[s],th) for s in outer})
        # Prefer macro articulation F1, but require the existing closed-hat quality
        # to remain near the all-closed baseline and mildly reward open precision.
        eligible=a["closed"]["f1"]>=base["closed"]["f1"]-.035
        score=a["macroF1"]+.04*a["open"]["precision"]
        ranked.append((eligible,score,a["macroF1"],a["open"]["precision"],th,a))
    ranked.sort(reverse=True)
    r=next((x for x in ranked if x[0]),ranked[0])
    return r[4],{"baseline":base,"ranking":[{"threshold":x[4],"eligible":x[0],"score":x[1],
        "macroF1":x[2],"openPrecision":x[3],"openF1":x[5]["open"]["f1"],"closedF1":x[5]["closed"]["f1"]} for x in ranked]}

def evaluate(data,family):
    per={};folds={};agg=Counter()
    for held in SONGS:
        outer=[s for s in SONGS if s!=held]
        th,inner=select_threshold(data,outer,family)
        m=train(data,outer,family);p=m.prob(data[held]["X"][key(family)])
        rows,_,_=oh.relabel_rows(data[held],p,th)
        path=OUT/family/f"{held}.mid";oh.write_midi(path,rows,float(data[held]["side"]["bpm"]))
        rr=oh.reread_articulation(path)
        met=oh.articulation_metrics(rr["open"],rr["closed"],data[held]["refs"])
        per[held]=met
        folds[held]={"threshold":th,"inner":inner,"openPredictions":len(rr["open"]),
                     "closedPredictions":len(rr["closed"]),"metrics":met}
        for c in ("open","closed"):
            q=met[c];agg[f"{c}t"]+=q["tp"];agg[f"{c}p"]+=q["predicted"];agg[f"{c}r"]+=q["reference"]
    summary=aggregate(per)
    return {"family":family,"featureSet":key(family),"folds":folds,"summary":summary}

def main():
    data=oh.prepare()
    baseline=oh.baseline(data)
    out={"schema":1,"description":"Conservative open-hat promotion; unmatched current hat candidates are training negatives.",
         "baselineAllClosed":baseline,"variants":{}}
    for family in ("promotion_decay","promotion_timbre","promotion_context"):
        q=evaluate(data,family);out["variants"][family]=q
        print("VARIANT",family,json.dumps(q["summary"],ensure_ascii=False),flush=True)
    winner=max(out["variants"],key=lambda k:out["variants"][k]["summary"]["macroF1"])
    out["winner"]=winner;out["final"]=out["variants"][winner]["summary"]
    out["guard"]={"onsetTimesChanged":False,"eventCountsChanged":False,"otherDrumClassesChanged":False,
                  "defaultArticulation":"closed","promotionTarget":"open"}
    (EXP/"results-open-hat-promotion-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",winner,json.dumps(out["final"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
