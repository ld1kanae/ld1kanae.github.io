"""Rule-based open-hi-hat overlay rescue using post-onset sustain only.

This is deliberately independent from the synthetic/GMD overlay classifiers.
Candidate anchors are current non-hat structural events; no kick/snare/etc is
removed. Three scores use the song-normalized 26-D acoustic feature vector:

A tail      : 100-650ms amplitude sustain
B hf_tail   : 80/180/350ms high-frequency persistence
C combined  : amplitude tail + HF persistence + open-vs-closed template delta

Thresholds are selected by nested leave-one-song-out, with an aggressive
precision guard. Held-out chart is final scoring only.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
BASE_THRESHOLD=.575

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ov=loadmod("openhat_rule_overlay",EXP/"open_hat_overlay_gmd_loo.py")
ext=ov.ext;oh=ov.oh

SCORES={
 "tail":lambda x:.65*x[:,8]+.35*x[:,9],
 "hf_tail":lambda x:.35*x[:,23]+.35*x[:,24]+.30*x[:,25],
 "combined":lambda x:.28*x[:,8]+.17*x[:,9]+.18*x[:,23]+.14*x[:,24]+.10*x[:,25]+.13*x[:,22],
}
THRESHOLDS=np.linspace(-.25,3.5,31).tolist()+[99.]

def train_base(d,songs,hx,hy):
    X=np.concatenate([*(d[s]["X"]["timbre_norm"] for s in songs),hx])
    y=np.concatenate([*((d[s]["y"]==1).astype(np.int8) for s in songs),hy])
    return ExtraTreesClassifier(n_estimators=320,max_depth=13,min_samples_leaf=4,
      class_weight="balanced",random_state=560,n_jobs=-1).fit(X,y)

def prob(model,X):
    p=model.predict_proba(X);return p[:,list(model.classes_).index(1)]

def score(d,s,bm,fam,th):
    hp=prob(bm,d[s]["X"]["timbre_norm"])
    bo=[t for t,p in zip(d[s]["hats"],hp) if p>=BASE_THRESHOLD]
    bc=[t for t,p in zip(d[s]["hats"],hp) if p<BASE_THRESHOLD]
    oo=d[s]["overlay"];v=SCORES[fam](oo["X"][:,:26])
    rescued=[a[0] for a,q in zip(oo["anchors"],v) if q>=th and not ov.near(bo,a[0],.060)]
    met=oh.articulation_metrics(sorted(bo+rescued),bc,d[s]["refs"])
    return met,{"baseOpen":len(bo),"candidates":len(v),"rescued":len(rescued),
      "positiveDiagnostic":int(oo["y"].sum()),"maxScore":float(np.max(v)) if len(v) else 0.,
      "p95Score":float(np.percentile(v,95)) if len(v) else 0.}

def aggregate(per):
    z=Counter()
    for m in per.values():
      for c in ("open","closed"):
        q=m[c];z[f"{c}t"]+=q["tp"];z[f"{c}p"]+=q["predicted"];z[f"{c}r"]+=q["reference"]
    out={}
    for c in ("open","closed"):
      tp,p,r=z[f"{c}t"],z[f"{c}p"],z[f"{c}r"]
      out[c]={"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,
        "recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"]);return out

def choose(d,outer,hx,hy,fam):
    cache={}
    for val in outer:
        tr=[s for s in outer if s!=val]
        cache[val]=train_base(d,tr,hx,hy)
    base={s:score(d,s,cache[s],fam,99.)[0] for s in outer};b=aggregate(base)
    rows=[]
    for th in THRESHOLDS:
        per={};diag={}
        for s,bm in cache.items():per[s],diag[s]=score(d,s,bm,fam,th)
        a=aggregate(per)
        eligible=(a["open"]["precision"]>=b["open"]["precision"]-.02 and
                  a["open"]["f1"]>b["open"]["f1"] and a["macroF1"]>b["macroF1"])
        utility=a["macroF1"]+.08*a["open"]["precision"]
        rows.append((eligible,utility,float(th),a))
    rows.sort(key=lambda r:(r[0],r[1]),reverse=True)
    best=next((r for r in rows if r[0]),None)
    return (best[2] if best else 99.),{"base":b,"ranking":[{"threshold":r[2],"eligible":r[0],"utility":r[1],"summary":r[3]} for r in rows[:12]]}

def evaluate(d,hx,hy,fam):
    per={};folds={}
    for held in SONGS:
        outer=[s for s in SONGS if s!=held];th,inner=choose(d,outer,hx,hy,fam)
        bm=train_base(d,outer,hx,hy);m,diag=score(d,held,bm,fam,th)
        per[held]=m;folds[held]={"threshold":th,"metrics":m,"diag":diag,"inner":inner}
        print("FOLD",fam,held,th,json.dumps({"open":m["open"],"diag":diag}),flush=True)
    return {"family":fam,"summary":aggregate(per),"songs":per,"folds":folds}

def main():
    d=ov.local_prepare()
    hx,hy,_,_,manifest=ov.gmd_collect()
    base={}
    for held in SONGS:
        bm=train_base(d,[s for s in SONGS if s!=held],hx,hy)
        hp=prob(bm,d[held]["X"]["timbre_norm"])
        bo=[t for t,p in zip(d[held]["hats"],hp) if p>=BASE_THRESHOLD]
        bc=[t for t,p in zip(d[held]["hats"],hp) if p<BASE_THRESHOLD]
        base[held]=oh.articulation_metrics(bo,bc,d[held]["refs"])
    baseline=aggregate(base)
    result={"schema":1,"description":"Post-onset sustain rule rescue with nested LOO.",
      "baseline":baseline,"families":{}}
    for fam in SCORES:
        q=evaluate(d,hx,hy,fam);s=q["summary"]
        q["eligible"]=(s["macroF1"]>baseline["macroF1"] and s["open"]["f1"]>baseline["open"]["f1"] and
          s["open"]["precision"]>=baseline["open"]["precision"]-.02)
        result["families"][fam]=q
        print("RESULT",fam,json.dumps({"eligible":q["eligible"],"summary":s}),flush=True)
    elig=[q for q in result["families"].values() if q["eligible"]]
    best=max(elig,key=lambda q:(q["summary"]["macroF1"],q["summary"]["open"]["f1"])) if elig else None
    result["retained"]=best["family"] if best else "none";result["retainedSummary"]=best["summary"] if best else baseline
    (EXP/"results-open-hat-overlay-rules-loo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("RETAINED",result["retained"],json.dumps(result["retainedSummary"]),flush=True)

if __name__=="__main__":main()
