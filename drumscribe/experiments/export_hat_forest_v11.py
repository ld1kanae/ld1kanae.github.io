"""Export the selected v11 ExtraTrees hi-hat classifier for browser inference.

Model selection/performance is documented by the held-out LOO experiment
results-iterative-hat-fixed-threshold-v11.json. This script trains the selected
model on all five available labeled development songs only after model selection,
serializes the trees to JSON, and verifies JSON-tree inference against sklearn.

The train-all model is a deployment artifact; its training-set score is not
reported as an accuracy estimate.
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"; MODELS=ROOT/"drumscribe/models"

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

bh=loadmod("bh_export",EXP/"browser_hat_meta_nested_loo.py")
SONGS=bh.SONGS

PARAMS=dict(n_estimators=160,max_depth=12,min_samples_leaf=4,
            class_weight="balanced",random_state=225,n_jobs=-1)

BANDS=[(30,180),(180,800),(800,2500),(2500,5000),(5000,10000),(10000,18000),(18000,22000)]
FEATURE_NAMES=[]
for lo,hi in BANDS:
    FEATURE_NAMES += [f"log_energy_{lo}_{hi}",f"log_rise_{lo}_{hi}"]
FEATURE_NAMES += [
    "centroid_norm","flatness","log_rms","crest_div10","zero_crossing",
    "nearest_kick_norm","nearest_snare_norm","nearest_crash_norm","nearest_ride_norm","nearest_pedal_hat_norm",
    "kick_within_25ms","kick_within_45ms","kick_within_70ms","snare_within_45ms",
    "prev_hat_interval_norm","next_hat_interval_norm","periodic_support",
    "sixteenth_slot_error","bar_head_distance_norm","slot_sin","slot_cos"
]

def export_tree(est):
    tr=est.tree_
    val=np.asarray(tr.value)
    # sklearn versions may store counts or normalized proportions; normalize
    # explicitly so the JSON contract is stable.
    raw=val[:,0,:]
    denom=raw.sum(axis=1)
    p1=np.divide(raw[:,1],denom,out=np.zeros(len(raw),dtype=float),where=denom>0)
    return {
      "left":tr.children_left.astype(int).tolist(),
      "right":tr.children_right.astype(int).tolist(),
      "feature":tr.feature.astype(int).tolist(),
      "threshold":[round(float(x),9) for x in tr.threshold],
      "prob1":[round(float(x),9) for x in p1],
    }

def json_predict(tree,x):
    node=0
    while tree["left"][node] != -1:
        f=tree["feature"][node]
        node=tree["left"][node] if float(x[f]) <= tree["threshold"][node] else tree["right"][node]
    return tree["prob1"][node]

def forest_predict(trees,X):
    out=np.zeros(len(X),dtype=float)
    for i,x in enumerate(X):
        out[i]=sum(json_predict(t,x) for t in trees)/len(trees)
    return out

def main():
    data=bh.prepare()
    X=np.concatenate([data[s]["X"] for s in SONGS])
    y=np.concatenate([data[s]["y"] for s in SONGS])
    clf=ExtraTreesClassifier(**PARAMS).fit(X,y)
    if clf.n_features_in_ != len(FEATURE_NAMES):
        raise RuntimeError(f"feature schema mismatch: model={clf.n_features_in_}, schema={len(FEATURE_NAMES)}")

    trees=[export_tree(e) for e in clf.estimators_]
    # Verify the serialized contract on every development candidate. This tests
    # serialization fidelity only, not generalization accuracy.
    sk=clf.predict_proba(X)[:,list(clf.classes_).index(1)]
    js=forest_predict(trees,X)
    maxerr=float(np.max(np.abs(sk-js))) if len(X) else 0.0
    meanerr=float(np.mean(np.abs(sk-js))) if len(X) else 0.0
    if maxerr > 2e-7:
        raise RuntimeError(f"serialized forest mismatch: max abs error {maxerr}")

    result=json.loads((EXP/"results-iterative-hat-fixed-threshold-v11.json").read_text())
    deployment={
      "schema":1,
      "kind":"drumscribe-hat-extra-trees",
      "trainingNote":"Train-all deployment artifact. Generalization estimate is held-out LOO from results-iterative-hat-fixed-threshold-v11.json, not training-set score.",
      "trainingSongs":SONGS,
      "params":{k:v for k,v in PARAMS.items() if k not in ("n_jobs","class_weight")},
      "classWeight":"balanced",
      "sampleRate":44100,
      "nfft":2048,
      "preWindowSec":0.025,
      "bandsHz":[list(x) for x in BANDS],
      "featureNames":FEATURE_NAMES,
      "nFeatures":int(clf.n_features_in_),
      "policy":{
        "probThreshold":0.55,
        "repeatRescue":1.0,
        "intersectionWindowSec":0.060,
        "hatKickDensityGuard":0.55
      },
      "heldOutEstimate":{
        "overallF1":result["final"]["summary"]["f1"],
        "hatF1":result["final"]["summary"]["by_group"]["hat"]["f1"],
        "hatPrecision":result["final"]["summary"]["by_group"]["hat"]["precision"],
        "hatRecall":result["final"]["summary"]["by_group"]["hat"]["recall"],
        "hatFalseDiscoveryRate":result["final"]["summary"]["by_group"]["hat"]["false_discovery_rate"],
        "canonicalScore":result["final"]["canonical_score"]["score"]
      },
      "serializationCheck":{"rows":int(len(X)),"maxAbsError":maxerr,"meanAbsError":meanerr},
      "trees":trees
    }
    MODELS.mkdir(parents=True,exist_ok=True)
    out=MODELS/"hat-extra-trees-v11.json"
    out.write_text(json.dumps(deployment,separators=(",",":"))+"\n")
    report={
      "schema":1,"path":str(out),"bytes":out.stat().st_size,
      "trees":len(trees),"features":int(clf.n_features_in_),
      "trainingRows":int(len(X)),"positiveRows":int(y.sum()),
      "serializationCheck":deployment["serializationCheck"],
      "heldOutEstimate":deployment["heldOutEstimate"],
      "policy":deployment["policy"]
    }
    (EXP/"results-hat-model-export-v11.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
