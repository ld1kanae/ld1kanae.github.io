"""Cycle: rescue open hi-hats that never reached the current hat detector.

Keep the current GMD128 articulation model and current hat onsets untouched.
Only consider existing browser event times as rescue anchors so timing remains
audio-derived and no dense free-running grid is invented.

Three candidate families:
 A metal          = ride + crash anchors
 B metal_snare    = A + snare anchors
 C metal_snare_kick = B + kick anchors

For each held-out DruMaster song:
- train the open/closed acoustic classifier on the other four songs + the same
  balanced 128/128 GMD augmentation,
- keep normal hat->open promotion at p>=0.575,
- select a conservative rescue threshold by nested LOO on the four training songs,
- add GM46 only at candidate anchors whose open probability exceeds that threshold.

Reference MIDI is used only for training-song labels, inner threshold selection,
and held-out scoring. Held-out chart is never used to create candidates/features.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
FAMILIES={
  "A_metal":("ride","crash"),
  "B_metal_snare":("ride","crash","snare"),
  "C_metal_snare_kick":("ride","crash","snare","kick"),
}
RESCUE_THRESHOLDS=[.65,.70,.75,.80,.85,.90,.95,1.01]
BASE_THRESHOLD=.575

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ext=loadmod("openhat_rescue_ext",EXP/"external_hat_augmentation.py")
oh=ext.oh;sn=ext.sn

def robust_from_hat_basis(hat_raw,rows):
    if not len(rows):return np.zeros((0,hat_raw.shape[1]),np.float32)
    med=np.median(hat_raw,axis=0);q1=np.percentile(hat_raw,25,axis=0);q3=np.percentile(hat_raw,75,axis=0)
    scale=np.maximum(q3-q1,1e-3)
    return np.clip((rows-med)/scale,-8,8).astype(np.float32)

def dedup(rows,w=.035):
    # Priority is encoded by input order: metal first, then snare, then kick.
    out=[]
    for t,g in rows:
        if any(abs(t-u)<=w for u,_ in out):continue
        out.append((t,g))
    return sorted(out)

def prepare():
    d=sn.prepare()
    for s in SONGS:
        # sn.prepare already loaded/decoded once internally, but does not retain audio.
        # Decode here for rescue anchors only.
        x=oh.audio(s)
        browser_rows=d[s]["rows"]
        hats=sorted(t for t,g,p in browser_rows if g=="hat")
        hat_raw=d[s]["X"]["timbre"]
        d[s]["rescue"]={}
        by={g:sorted(t for t,gg,p in browser_rows if gg==g) for g in ("ride","crash","snare","kick")}
        for fam,groups in FAMILIES.items():
            ordered=[]
            for g in groups:
                for t in by[g]:
                    if any(abs(t-h)<=.060 for h in hats):continue
                    ordered.append((t,g))
            cand=dedup(ordered)
            raw=np.stack([oh.timbre_features(x,t) for t,_ in cand]) if cand else np.zeros((0,hat_raw.shape[1]),np.float32)
            X=robust_from_hat_basis(hat_raw,raw)
            d[s]["rescue"][fam]={"rows":cand,"X":X}
        print("RESCUE_COUNTS",s,{k:len(v["rows"]) for k,v in d[s]["rescue"].items()},flush=True)
    return d

def train(data,songs,gX,gY):
    X=np.concatenate([*(data[s]["X"]["timbre_norm"] for s in songs),gX])
    y=np.concatenate([*((data[s]["y"]==1).astype(np.int8) for s in songs),gY])
    from sklearn.ensemble import ExtraTreesClassifier
    return ExtraTreesClassifier(n_estimators=320,max_depth=13,min_samples_leaf=4,
      class_weight="balanced",random_state=560,n_jobs=-1).fit(X,y)

def p1(model,X):
    if not len(X):return np.zeros(0)
    return model.predict_proba(X)[:,list(model.classes_).index(1)]

def base_and_rescue(data,s,model,fam,rescue_th):
    hp=p1(model,data[s]["X"]["timbre_norm"])
    base_open=[t for t,v in zip(data[s]["hats"],hp) if v>=BASE_THRESHOLD]
    base_closed=[t for t,v in zip(data[s]["hats"],hp) if v<BASE_THRESHOLD]
    rr=data[s]["rescue"][fam]
    rp=p1(model,rr["X"])
    rescued=[t for (t,g),v in zip(rr["rows"],rp) if v>=rescue_th]
    # Avoid duplicate GM46 when a rescue anchor is close to an already promoted hat.
    rescued=[t for t in rescued if not any(abs(t-u)<=.060 for u in base_open)]
    m=oh.articulation_metrics(sorted(base_open+rescued),base_closed,data[s]["refs"])
    return m,{"baseOpen":len(base_open),"rescued":len(rescued),"candidates":len(rr["rows"]),
              "maxProb":float(np.max(rp)) if len(rp) else 0.}

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
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"])
    return out

def choose_inner(data,outer,gX,gY,fam):
    # Nested LOO: each inner validation song is excluded from acoustic model fitting.
    cache={}
    for val in outer:
        model=train(data,[s for s in outer if s!=val],gX,gY)
        cache[val]=model
    base_per={};base_diag={}
    for val in outer:
        m,d=base_and_rescue(data,val,cache[val],fam,1.01);base_per[val]=m;base_diag[val]=d
    base=aggregate(base_per)
    rows=[]
    for th in RESCUE_THRESHOLDS:
        per={};diag={}
        for val in outer:
            m,d=base_and_rescue(data,val,cache[val],fam,th);per[val]=m;diag[val]=d
        a=aggregate(per)
        eligible=(a["open"]["precision"]>=base["open"]["precision"]-.02 and
                  a["closed"]["f1"]>=base["closed"]["f1"]-.005 and
                  a["macroF1"]>base["macroF1"])
        score=a["macroF1"]+.06*a["open"]["precision"]
        rows.append((eligible,score,th,a,diag))
    rows.sort(key=lambda x:(x[0],x[1]),reverse=True)
    best=next((x for x in rows if x[0]),None)
    if best is None:return 1.01,{"base":base,"ranking":[{"threshold":r[2],"eligible":r[0],"score":r[1],"summary":r[3]} for r in rows]}
    return best[2],{"base":base,"ranking":[{"threshold":r[2],"eligible":r[0],"score":r[1],"summary":r[3]} for r in rows]}

def evaluate_family(data,gX,gY,fam):
    per={};folds={}
    for held in SONGS:
        outer=[s for s in SONGS if s!=held]
        th,inner=choose_inner(data,outer,gX,gY,fam)
        model=train(data,outer,gX,gY)
        m,d=base_and_rescue(data,held,model,fam,th)
        per[held]=m;folds[held]={"rescueThreshold":th,"metrics":m,"diag":d,"inner":inner}
        print("FOLD",fam,held,th,json.dumps({"open":m["open"],"closed":m["closed"],"diag":d}),flush=True)
    return {"family":fam,"summary":aggregate(per),"songs":per,"folds":folds}

def main():
    data=prepare()
    gX,gY,manifest=ext.select_gmd();gX,gY=ext.balanced_cap(gX,gY,limit=128,seed=528)
    # Baseline is the exact GMD128 p=.575 promoter with no rescue.
    base_per={}
    for held in SONGS:
        model=train(data,[s for s in SONGS if s!=held],gX,gY)
        m,_=base_and_rescue(data,held,model,"A_metal",1.01);base_per[held]=m
    baseline=aggregate(base_per)
    result={"schema":1,"description":"Nested-LOO rescue of open hats missing from current hat detector.",
      "baseThreshold":BASE_THRESHOLD,"gmdRows":len(gY),"baseline":baseline,"families":{}}
    for fam in FAMILIES:
        q=evaluate_family(data,gX,gY,fam);result["families"][fam]=q
        print("RESULT",fam,json.dumps(q["summary"]),flush=True)
    # Keep rescue only if it improves macro/open F1 and preserves precision.
    eligible=[]
    for fam,q in result["families"].items():
        s=q["summary"]
        ok=(s["macroF1"]>baseline["macroF1"] and
            s["open"]["f1"]>baseline["open"]["f1"] and
            s["open"]["precision"]>=baseline["open"]["precision"]-.02 and
            s["closed"]["f1"]>=baseline["closed"]["f1"]-.005)
        q["eligible"]=ok
        if ok:eligible.append(q)
    best=max(eligible,key=lambda q:(q["summary"]["macroF1"],q["summary"]["open"]["f1"])) if eligible else None
    result["retained"]=best["family"] if best else "none"
    result["retainedSummary"]=best["summary"] if best else baseline
    (EXP/"results-open-hat-rescue-loo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("RETAINED",result["retained"],json.dumps(result["retainedSummary"]),flush=True)

if __name__=="__main__":main()
