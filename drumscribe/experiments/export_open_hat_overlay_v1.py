"""Export train-all structural open-hat overlay model for browser inference.

The model predicts whether an open hi-hat is simultaneously present at an
existing non-hat structural anchor (kick/snare/ride/crash). It never replaces
those notes; browser policy may add GM46 when song-level repeat evidence agrees.

Generalization estimate comes from results-open-hat-overlay-selfadapt-loo.json.
That policy is development-selected and still requires future-song validation.
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";MODELS=ROOT/"drumscribe/models"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
FAM="C_metal_snare_kick"
SEED=777

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ov=loadmod("overlay_export",EXP/"open_hat_overlay_gmd_loo.py")

def export_tree(est):
    tr=est.tree_;raw=np.asarray(tr.value)[:,0,:];den=raw.sum(axis=1)
    classes=list(est.classes_)
    j=classes.index(1)
    p1=np.divide(raw[:,j],den,out=np.zeros(len(raw),dtype=float),where=den>0)
    return {"left":tr.children_left.astype(int).tolist(),"right":tr.children_right.astype(int).tolist(),
      "feature":tr.feature.astype(int).tolist(),"threshold":[float(x) for x in tr.threshold],
      "prob1":[float(x) for x in p1]}

def predict_tree(t,x):
    n=0
    while t["left"][n]!=-1:
        n=t["left"][n] if float(x[t["feature"][n]])<=t["threshold"][n] else t["right"][n]
    return t["prob1"][n]

def main():
    d=ov.local_prepare();hx,hy,gx,gy,manifest=ov.gmd_collect()
    model,info=ov.train_overlay(d,SONGS,gx,gy,FAM,SEED)
    # Gather exact train matrix again for serialization parity check.
    lx,ly=ov.subset_local(d,SONGS,FAM);egx,egy=ov.subset_gmd(gx,gy,FAM,SEED)
    X=np.concatenate([lx,egx]);y=np.concatenate([ly,egy])
    trees=[export_tree(e) for e in model.estimators_]
    sk=model.predict_proba(X)[:,list(model.classes_).index(1)]
    js=np.asarray([sum(predict_tree(t,x) for t in trees)/len(trees) for x in X])
    maxerr=float(np.max(np.abs(sk-js)));meanerr=float(np.mean(np.abs(sk-js)))
    if maxerr>3e-7:raise RuntimeError(f"serialization mismatch {maxerr}")
    dev=json.loads((EXP/"results-open-hat-overlay-selfadapt-loo.json").read_text())
    held=dev["policies"]["repeat_gate_2hands"]["summary"]
    artifact={
      "schema":1,"kind":"drumscribe-open-hat-overlay-extra-trees",
      "trainingNote":"Train-all deployment artifact. Held-out estimate is development-selected; validate on future songs.",
      "trainingSongs":SONGS,"featureCount":int(model.n_features_in_),"trees":trees,
      "params":{"nEstimators":280,"maxDepth":12,"minSamplesLeaf":3,"classWeight":"balanced","randomState":740+SEED},
      "externalTraining":{"dataset":"Google Magenta Groove MIDI Dataset v1.0.0","license":"CC BY 4.0",
        "gmdRows":int(len(egy)),"gmdPositive":int(egy.sum()),"sourceClips":len(manifest)},
      "localTraining":{"rows":int(len(ly)),"positive":int(ly.sum())},
      "policy":{
        "name":"repeat_gate_2hands","gateMaxProbability":.78,"gateMaxRepeatScore":.72,
        "scoreProbabilityWeight":.72,"scoreRepeatWeight":.28,"scoreQuantile":.96,
        "minimumScore":.68,"minimumProbability":.58,"minimumRepeatSupport":.35,
        "neighborBeatOffsets":[.5,1,1.5,2,4],"neighborToleranceSec":.065,
        "existingHatExclusionSec":.060,"handClusterSec":.035
      },
      "heldOutDevelopmentEstimate":held,
      "serializationCheck":{"rows":int(len(X)),"positiveRows":int(y.sum()),
        "maxAbsError":maxerr,"meanAbsError":meanerr}
    }
    MODELS.mkdir(parents=True,exist_ok=True)
    p=MODELS/"open-hat-overlay-extra-trees-v1.json";p.write_text(json.dumps(artifact,separators=(",",":"))+"\n")
    report={"schema":1,"path":str(p),"bytes":p.stat().st_size,"trees":len(trees),"features":int(model.n_features_in_),
      "trainingRows":len(X),"positiveRows":int(y.sum()),"heldOutDevelopmentEstimate":held,
      "serializationCheck":artifact["serializationCheck"]}
    (EXP/"results-open-hat-overlay-model-export-v1.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
