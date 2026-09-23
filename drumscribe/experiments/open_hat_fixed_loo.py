"""Cycle 5: fixed conservative threshold for song-normalized open-hat model.

Unknown-song style evaluation: for each held song, train on the other four and
use the SAME fixed probability threshold on every held song. No per-song or
inner-fold threshold adaptation. Current hat onset times/counts remain fixed.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";OUT=EXP/"generated-search-open-hat-fixed-loo"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
THRESHOLDS=[.45,.55,.65,.75,.85,.90]

def loadmod(name,path):
 sp=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
sn=loadmod("openhat_norm_fixed",EXP/"open_hat_songnorm_loo.py");oh=sn.oh

def train(d,held):
 X=np.concatenate([d[s]["X"]["timbre_norm"] for s in SONGS if s!=held])
 y=np.concatenate([(d[s]["y"]==1).astype(np.int8) for s in SONGS if s!=held])
 return ExtraTreesClassifier(n_estimators=320,max_depth=13,min_samples_leaf=4,
  class_weight="balanced",random_state=560,n_jobs=-1).fit(X,y)

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

def main():
 d=sn.prepare();probs={}
 for held in SONGS:
  m=train(d,held);probs[held]=m.predict_proba(d[held]["X"]["timbre_norm"])[:,list(m.classes_).index(1)]
 result={"schema":1,"description":"Fixed-threshold held-out LOO for song-normalized timbre open-hat promoter.","thresholds":{}}
 for th in THRESHOLDS:
  per={}
  for s in SONGS:
   p=probs[s];op=[t for t,v in zip(d[s]["hats"],p) if v>=th];cl=[t for t,v in zip(d[s]["hats"],p) if v<th]
   open_set=set(op);rows=[(t,"open_hat",46) if g=="hat" and t in open_set else (t,g,pitch) for t,g,pitch in d[s]["rows"]]
   path=OUT/f"t{int(th*100):02d}"/f"{s}.mid";oh.write_midi(path,rows,float(d[s]["side"]["bpm"]))
   rr=oh.reread_articulation(path);per[s]=oh.articulation_metrics(rr["open"],rr["closed"],d[s]["refs"])
  a=aggregate(per);result["thresholds"][str(th)]={"summary":a,"songs":per}
  print("THRESHOLD",th,json.dumps(a,ensure_ascii=False),flush=True)
 # Utility favors precision because ambiguous articulation should remain closed.
 def utility(q):
  a=q["summary"];return a["macroF1"]+.08*a["open"]["precision"]+.02*a["closed"]["f1"]
 winner=max(result["thresholds"],key=lambda k:utility(result["thresholds"][k]))
 result["winnerThreshold"]=float(winner);result["final"]=result["thresholds"][winner]["summary"]
 result["selectionNote"]="Threshold sweep is a development comparison; per-song predictions remain strictly held-out. For unbiased future-song validation, test the selected fixed threshold on additional songs."
 (EXP/"results-open-hat-fixed-loo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print("FINAL",winner,json.dumps(result["final"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
