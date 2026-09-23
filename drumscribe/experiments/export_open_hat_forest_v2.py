"""Export the retained GMD-augmented open-hi-hat model for browser inference.

Training:
- all five DruMaster development songs
- balanced 128 open + 128 closed examples from the deterministic GMD subset
- ExtraTrees architecture unchanged from the songs-only model
- fixed deployment probability threshold 0.575

The held-out estimate embedded in the model comes from
results-open-hat-gmd128-thresholds.json. The train-all fit itself is not treated
as an independent accuracy estimate.
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";MODELS=ROOT/"drumscribe/models"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
PARAMS=dict(n_estimators=320,max_depth=13,min_samples_leaf=4,
            class_weight="balanced",random_state=560,n_jobs=-1)
THRESHOLD=.575

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ext=loadmod("openhat_external_export",EXP/"external_hat_augmentation.py")
sn=ext.sn;oh=ext.oh

def export_tree(est):
    tr=est.tree_;raw=np.asarray(tr.value)[:,0,:];den=raw.sum(axis=1)
    p1=np.divide(raw[:,1],den,out=np.zeros(len(raw),dtype=float),where=den>0)
    return {
      "left":tr.children_left.astype(int).tolist(),
      "right":tr.children_right.astype(int).tolist(),
      "feature":tr.feature.astype(int).tolist(),
      "threshold":[float(x) for x in tr.threshold],
      "prob1":[float(x) for x in p1],
    }

def predict_tree(tree,x):
    n=0
    while tree["left"][n]!=-1:
        f=tree["feature"][n]
        n=tree["left"][n] if float(x[f])<=tree["threshold"][n] else tree["right"][n]
    return tree["prob1"][n]

def main():
    data=sn.prepare()
    gX,gY,manifest=ext.select_gmd()
    gX,gY=ext.balanced_cap(gX,gY,limit=128,seed=528)

    X=np.concatenate([*(data[s]["X"]["timbre_norm"] for s in SONGS),gX])
    y=np.concatenate([*((data[s]["y"]==1).astype(np.int8) for s in SONGS),gY])
    clf=ExtraTreesClassifier(**PARAMS).fit(X,y)
    trees=[export_tree(e) for e in clf.estimators_]

    sk=clf.predict_proba(X)[:,list(clf.classes_).index(1)]
    js=np.asarray([sum(predict_tree(t,x) for t in trees)/len(trees) for x in X])
    maxerr=float(np.max(np.abs(sk-js)));meanerr=float(np.mean(np.abs(sk-js)))
    if maxerr>3e-7:raise RuntimeError(f"serialization mismatch {maxerr}")

    calibration=json.loads((EXP/"results-open-hat-gmd128-thresholds.json").read_text())
    if abs(float(calibration["retainedThreshold"])-THRESHOLD)>1e-12:
        raise RuntimeError(f"retained threshold changed: {calibration['retainedThreshold']}")
    held=calibration["retained"]

    model={
      "schema":2,
      "kind":"drumscribe-open-hat-extra-trees",
      "trainingNote":"Train-all deployment artifact; use heldOutEstimate for development generalization estimate.",
      "trainingSongs":SONGS,
      "externalTraining":{
        "dataset":"Google Magenta Groove MIDI Dataset v1.0.0",
        "license":"CC BY 4.0",
        "selection":"deterministic short train beats, open={26,46}, closed={22,42}",
        "balancedPerClass":int((gY==0).sum()),
        "rows":int(len(gY)),
        "sourceClips":len(manifest),
        "seed":528
      },
      "sampleRate":44100,"nfft":2048,
      "params":{k:v for k,v in PARAMS.items() if k not in ("n_jobs","class_weight")},
      "classWeight":"balanced",
      "probThreshold":THRESHOLD,
      "featureSet":"per-song robust-normalized timbre/decay features",
      "featureCount":int(clf.n_features_in_),
      "assetTemplates":{
        "closed42":[float(x) for x in oh.ASSET42],
        "open46":[float(x) for x in oh.ASSET46]
      },
      "heldOutEstimate":held,
      "serializationCheck":{"rows":int(len(X)),"positiveRows":int(y.sum()),
        "maxAbsError":maxerr,"meanAbsError":meanerr},
      "trees":trees
    }
    MODELS.mkdir(parents=True,exist_ok=True)
    path=MODELS/"open-hat-extra-trees-v2.json"
    path.write_text(json.dumps(model,separators=(",",":"))+"\n")
    report={"schema":2,"path":str(path),"bytes":path.stat().st_size,"trees":len(trees),
      "features":int(clf.n_features_in_),"trainingRows":int(len(X)),
      "trainingPositiveRows":int(y.sum()),"gmdRows":int(len(gY)),
      "gmdOpen":int(gY.sum()),"gmdClosed":int((gY==0).sum()),"gmdClips":len(manifest),
      "threshold":THRESHOLD,"heldOutEstimate":held,
      "serializationCheck":model["serializationCheck"]}
    (EXP/"results-open-hat-model-export-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
