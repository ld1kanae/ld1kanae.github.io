"""Threshold calibration for the GMD-128 open-hat augmentation candidate.

External data and held-out protocol are identical to external_hat_augmentation.py.
This run fetches only GMD (not E-GMD) and evaluates a fixed threshold grid.
The threshold sweep is development tuning; each per-threshold prediction remains
leave-one-song-out with the held song excluded from fitting.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
THRESHOLDS=[.55,.575,.60,.625,.65,.675,.70]

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ext=loadmod("openhat_ext_threshold",EXP/"external_hat_augmentation.py")
oh=ext.oh

def aggregate(per):
    z=Counter()
    for m in per.values():
        for c in ("open","closed"):
            q=m[c];z[f"{c}t"]+=q["tp"];z[f"{c}p"]+=q["predicted"];z[f"{c}r"]+=q["reference"]
    out={}
    for c in ("open","closed"):
        tp,p,r=z[f"{c}t"],z[f"{c}p"],z[f"{c}r"]
        out[c]={"tp":tp,"predicted":p,"reference":r,
          "precision":tp/p if p else 0.,"recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"])
    return out

def main():
    data=ext.sn.prepare()
    gX,gY,manifest=ext.select_gmd()
    gX,gY=ext.balanced_cap(gX,gY,limit=128,seed=528)

    probs={}
    for held in SONGS:
        model=ext.train_model(data,held,(gX,gY))
        X=data[held]["X"]["timbre_norm"]
        probs[held]=model.predict_proba(X)[:,list(model.classes_).index(1)]

    rows={}
    for th in THRESHOLDS:
        per={}
        for s in SONGS:
            p=probs[s]
            op=[t for t,v in zip(data[s]["hats"],p) if v>=th]
            cl=[t for t,v in zip(data[s]["hats"],p) if v<th]
            per[s]=oh.articulation_metrics(op,cl,data[s]["refs"])
        rows[str(th)]={"summary":aggregate(per),"songs":per}
        print("THRESHOLD",th,json.dumps(rows[str(th)]["summary"],ensure_ascii=False),flush=True)

    # Current songs-only fixed-threshold baseline from the same feature/model family.
    base_per={}
    for held in SONGS:
        model=ext.train_model(data,held,None)
        X=data[held]["X"]["timbre_norm"]
        p=model.predict_proba(X)[:,list(model.classes_).index(1)]
        op=[t for t,v in zip(data[held]["hats"],p) if v>=.55]
        cl=[t for t,v in zip(data[held]["hats"],p) if v<.55]
        base_per[held]=oh.articulation_metrics(op,cl,data[held]["refs"])
    base=aggregate(base_per)

    eligible=[]
    for k,v in rows.items():
        s=v["summary"]
        ok=(s["open"]["precision"]>=base["open"]["precision"]-.02 and
            s["closed"]["f1"]>=base["closed"]["f1"]-.01 and
            s["macroF1"]>base["macroF1"])
        v["eligible"]=ok
        if ok:eligible.append((s["macroF1"],s["open"]["f1"],float(k),v))
    best=max(eligible) if eligible else None
    result={"schema":1,"source":"GMD balanced 128/class","externalRows":len(gY),
      "externalOpen":int(gY.sum()),"externalClosed":int((gY==0).sum()),
      "clips":manifest,"baseline":base,"thresholds":rows,
      "guard":{"maxOpenPrecisionDrop":.02,"maxClosedF1Drop":.01,"requireMacroF1Improvement":True},
      "retainedThreshold":best[2] if best else None,
      "retained":best[3]["summary"] if best else base,
      "note":"Threshold grid is development tuning; use future songs for an independent post-selection estimate."}
    (EXP/"results-open-hat-gmd128-thresholds.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(base,ensure_ascii=False),flush=True)
    print("RETAINED",result["retainedThreshold"],json.dumps(result["retained"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
