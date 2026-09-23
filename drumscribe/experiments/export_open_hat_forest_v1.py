"""Export train-all open-hi-hat ExtraTrees model for browser inference.

Hyperparameters/threshold were selected in held-out development experiments.
This train-all artifact is for deployment only; its training-set score is not
reported as a generalization estimate.
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";MODELS=ROOT/"drumscribe/models"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
sn=loadmod("openhat_export",EXP/"open_hat_songnorm_loo.py")
oh=sn.oh

PARAMS=dict(n_estimators=320,max_depth=13,min_samples_leaf=4,
            class_weight="balanced",random_state=560,n_jobs=-1)
THRESHOLD=.55

def export_tree(est):
    tr=est.tree_;raw=np.asarray(tr.value)[:,0,:];den=raw.sum(axis=1)
    # Classes are [0,1] in this experiment.
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

def robust(X):
    med=np.median(X,axis=0);q1=np.percentile(X,25,axis=0);q3=np.percentile(X,75,axis=0)
    scale=np.maximum(q3-q1,1e-3)
    return np.clip((X-med)/scale,-8,8).astype(np.float32)

def main():
    data=sn.prepare()
    X=np.concatenate([data[s]["X"]["timbre_norm"] for s in SONGS])
    y=np.concatenate([(data[s]["y"]==1).astype(np.int8) for s in SONGS])
    clf=ExtraTreesClassifier(**PARAMS).fit(X,y)
    trees=[export_tree(e) for e in clf.estimators_]
    sk=clf.predict_proba(X)[:,list(clf.classes_).index(1)]
    # serialization check
    js=np.asarray([sum(predict_tree(t,x) for t in trees)/len(trees) for x in X])
    maxerr=float(np.max(np.abs(sk-js)));meanerr=float(np.mean(np.abs(sk-js)))
    if maxerr>3e-7:raise RuntimeError(f"serialization mismatch {maxerr}")

    fixed=json.loads((EXP/"results-open-hat-fixed-loo.json").read_text())
    t55=fixed["thresholds"]["0.55"]["summary"]
    model={
      "schema":1,
      "kind":"drumscribe-open-hat-extra-trees",
      "trainingNote":"Train-all deployment artifact. Accuracy estimate comes from held-out LOO, not this training fit.",
      "trainingSongs":SONGS,
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
      "heldOutEstimate":{"open":t55["open"],"closed":t55["closed"],"macroF1":t55["macroF1"]},
      "serializationCheck":{"rows":int(len(X)),"positiveRows":int(y.sum()),"maxAbsError":maxerr,"meanAbsError":meanerr},
      "trees":trees
    }
    MODELS.mkdir(parents=True,exist_ok=True)
    path=MODELS/"open-hat-extra-trees-v1.json"
    path.write_text(json.dumps(model,separators=(",",":"))+"\n")
    report={"schema":1,"path":str(path),"bytes":path.stat().st_size,"trees":len(trees),
      "features":int(clf.n_features_in_),"trainingRows":int(len(X)),"positiveRows":int(y.sum()),
      "threshold":THRESHOLD,"heldOutEstimate":model["heldOutEstimate"],
      "serializationCheck":model["serializationCheck"]}
    (EXP/"results-open-hat-model-export-v1.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
