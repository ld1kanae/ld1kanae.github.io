"""Fast equivalent of browser_hat_meta_nested_loo.py.

Caches inner-fold model probabilities per model family, then evaluates all
threshold/rescue policies without retraining. Statistical protocol is unchanged:
outer held song is never used for model fitting or hyperparameter selection.
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
spec=importlib.util.spec_from_file_location("basehat",EXP/"browser_hat_meta_nested_loo.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

def main():
    data=b.prepare()
    base={s:b.score(s,data[s]["rows"]) for s in b.SONGS};bag=b.aggregate(base)
    cfgs=[];i=0
    for fam in ("logistic","extra"):
      for thr in (.25,.35,.45,.55,.65):
       for rescue in ("none","repeat","offkick"):
        for rep in (.50,.75):
         if rescue!="repeat" and rep!=.50:continue
         cfgs.append({"id":i,"family":fam,"thr":thr,"rescue":rescue,"rep":rep});i+=1

    held={};details={}
    for h in b.SONGS:
        outer=[s for s in b.SONGS if s!=h]
        # Cache inner-fold probabilities: family -> validation song -> p.
        cache={}
        for fam in ("logistic","extra"):
            cache[fam]={}
            for v in outer:
                tr=[s for s in outer if s!=v]
                mod=b.train(data,tr,fam)
                cache[fam][v]=mod.pred(data[v]["X"])

        ranked=[]
        b_outer=b.aggregate({s:base[s] for s in outer})
        for cfg in cfgs:
            inner_scores={}
            for v in outer:
                p=cache[cfg["family"]][v]
                inner_scores[v]=b.score(v,b.build(data[v],p,cfg))
            a=b.aggregate(inner_scores)
            valid=(a["f1"]>=b_outer["f1"]-.003 and
                   a["by_group"]["hat"]["f1"]>=b_outer["by_group"]["hat"]["f1"]-.010)
            ranked.append((bool(valid),float(b.objective(a)),float(a["f1"]),cfg["id"],a))
        ranked.sort(reverse=True)
        valid,objv,_,bid,inner=ranked[0]
        cfg=next(c for c in cfgs if c["id"]==bid)
        mod=b.train(data,outer,cfg["family"])
        p=mod.pred(data[h]["X"])
        pred=b.build(data[h],p,cfg);sc=b.score(h,pred);held[h]=sc
        details[h]={
          "config":cfg,"innerEligible":bool(valid),"innerObjective":float(objv),
          "inner":inner,"heldF1":float(sc["f1"]),"hat":sc["by_group"]["hat"],
          "keptAboveThreshold":int((p>=cfg["thr"]).sum()),
          "candidates":int(len(p))
        }
        print("HELD",h,json.dumps(details[h],ensure_ascii=False),flush=True)

    ag=b.aggregate(held)
    out={"schema":1,
      "description":"Fast fully nested LOO hat suppressor on generated-v2-browser; probability caching only.",
      "baseline":bag,
      "nestedLOO":{"aggregate":ag,"objective":float(b.objective(ag)),"songs":details}}
    (EXP/"results-browser-hat-meta-nested-loo-fast.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(bag,ensure_ascii=False),flush=True)
    print("LOO",json.dumps(out["nestedLOO"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
