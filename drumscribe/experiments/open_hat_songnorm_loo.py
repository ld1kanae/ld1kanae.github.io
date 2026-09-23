"""Cycle 3: song-adaptive open-hi-hat promotion.

The current browser hat onsets are unchanged. Acoustic features are robustly
normalized within each song using only prediction-time hat candidates
(median/IQR), then a model trained on the other four songs promotes high-confidence
events to MIDI 46. This targets kit/mix/domain shift without using held-out chart.
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
OUT=EXP/"generated-search-open-hat-songnorm-loo"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
THRESHOLDS=[.35,.45,.55,.65,.75,.82,.88,.92]

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
oh=loadmod("openhat_cycle1_norm",EXP/"open_hat_loo.py")

def robust(X):
    if len(X)==0:return X
    med=np.median(X,axis=0);q1=np.percentile(X,25,axis=0);q3=np.percentile(X,75,axis=0)
    scale=np.maximum(q3-q1,1e-3)
    return np.clip((X-med)/scale,-8,8).astype(np.float32)

def prepare():
    d=oh.prepare()
    for s in SONGS:
        for k in ("decay","timbre"):
            d[s]["X"][k+"_norm"]=robust(d[s]["X"][k])
        d[s]["X"]["timbre_hybrid"]=np.concatenate([d[s]["X"]["timbre"],d[s]["X"]["timbre_norm"]],axis=1)
    return d

class Model:
    def __init__(self,f):self.f=f;self.scaler=None;self.model=None
    def fit(self,X,y):
        if self.f=="norm_decay":
            self.scaler=StandardScaler().fit(X);X=self.scaler.transform(X)
            self.model=LogisticRegression(max_iter=1200,class_weight="balanced",C=.7,solver="lbfgs").fit(X,y)
        else:
            self.model=ExtraTreesClassifier(n_estimators=320,max_depth=13,min_samples_leaf=4,
                class_weight="balanced",random_state=560 if self.f=="norm_timbre" else 561,n_jobs=-1).fit(X,y)
        return self
    def prob(self,X):
        if self.scaler is not None:X=self.scaler.transform(X)
        p=self.model.predict_proba(X);return p[:,list(self.model.classes_).index(1)]

def key(f):
    return "decay_norm" if f=="norm_decay" else "timbre_norm" if f=="norm_timbre" else "timbre_hybrid"

def train(d,songs,f):
    X=np.concatenate([d[s]["X"][key(f)] for s in songs])
    y=np.concatenate([(d[s]["y"]==1).astype(np.int8) for s in songs])
    return Model(f).fit(X,y)

def metrics(d,s,p,th):
    op=[t for t,v in zip(d[s]["hats"],p) if v>=th];cl=[t for t,v in zip(d[s]["hats"],p) if v<th]
    return oh.articulation_metrics(op,cl,d[s]["refs"])

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
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"])
    return out

def choose(d,outer,f):
    probs={}
    for val in outer:
        m=train(d,[s for s in outer if s!=val],f);probs[val]=m.prob(d[val]["X"][key(f)])
    base=aggregate({s:oh.articulation_metrics([],d[s]["hats"],d[s]["refs"]) for s in outer})
    rows=[]
    for th in THRESHOLDS:
        a=aggregate({s:metrics(d,s,probs[s],th) for s in outer})
        eligible=a["closed"]["f1"]>=base["closed"]["f1"]-.035
        score=a["macroF1"]+.04*a["open"]["precision"]
        rows.append((eligible,score,a["macroF1"],a["open"]["precision"],th,a))
    rows.sort(reverse=True);best=next((x for x in rows if x[0]),rows[0])
    return best[4],{"baseline":base,"ranking":[{"threshold":r[4],"eligible":r[0],"score":r[1],
        "macroF1":r[2],"openPrecision":r[3],"openF1":r[5]["open"]["f1"],"closedF1":r[5]["closed"]["f1"]} for r in rows]}

def evaluate(d,f):
    per={};folds={}
    for held in SONGS:
        outer=[s for s in SONGS if s!=held];th,inner=choose(d,outer,f)
        m=train(d,outer,f);p=m.prob(d[held]["X"][key(f)])
        rows,_,_=oh.relabel_rows(d[held],p,th)
        path=OUT/f/f"{held}.mid";oh.write_midi(path,rows,float(d[held]["side"]["bpm"]))
        rr=oh.reread_articulation(path);met=oh.articulation_metrics(rr["open"],rr["closed"],d[held]["refs"])
        per[held]=met;folds[held]={"threshold":th,"inner":inner,"metrics":met,
            "openPredictions":len(rr["open"]),"closedPredictions":len(rr["closed"])}
    return {"family":f,"featureSet":key(f),"folds":folds,"summary":aggregate(per)}

def main():
    d=prepare();base=oh.baseline(d)
    out={"schema":1,"description":"Song-adaptive robust-normalized open-hat promotion; all normalization uses prediction-time candidates only.",
         "baselineAllClosed":base,"variants":{}}
    for f in ("norm_decay","norm_timbre","hybrid_timbre"):
        q=evaluate(d,f);out["variants"][f]=q
        print("VARIANT",f,json.dumps(q["summary"],ensure_ascii=False),flush=True)
    w=max(out["variants"],key=lambda k:out["variants"][k]["summary"]["macroF1"])
    out["winner"]=w;out["final"]=out["variants"][w]["summary"]
    out["guard"]={"onsetTimesChanged":False,"eventCountsChanged":False,"otherDrumClassesChanged":False,
                  "heldOutChartUsedForNormalization":False}
    (EXP/"results-open-hat-songnorm-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",w,json.dumps(out["final"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
