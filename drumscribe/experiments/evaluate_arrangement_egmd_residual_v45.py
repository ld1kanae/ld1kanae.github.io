from __future__ import annotations
import importlib.util, json
from pathlib import Path
import numpy as np

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"
OUT=EXP/"results-arrangement-egmd-residual-v45.json"
MD=EXP/"ARRANGEMENT_EGMD_RESIDUAL_V45.md"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("v44",EXP/"evaluate_arrangement_egmd_fusion_v44.py")
v44=importlib.util.module_from_spec(spec);spec.loader.exec_module(v44)

def key(row):
    return (row["song"],row["group"],round(float(row["time"]),3))

def fixed_maps(rows):
    return {s:v44.fixed_v39(rows,s) for s in SONGS}

def fixed_keyset(fixed):
    return {key(r) for items in fixed.values() for r,_ in items}

def augmented_baselines(baselines,fixed):
    out={}
    for s in SONGS:
        out[s]=[*baselines[s],*({"time":r["time"],"group":r["group"]} for r,_ in fixed[s])]
    return out

def train_model(rows,kind):
    y=np.asarray([r["y"] for r in rows],int)
    if len(rows)<16 or y.sum()<3 or (len(rows)-y.sum())<3:return None
    X=np.asarray([r["x"] for r in rows],float)
    m=v44.model_for(kind);m.fit(X,y);return m

def preds(model,rows):
    if model is None:return []
    X=np.asarray([r["x"] for r in rows],float)
    p=model.predict_proba(X)[:,1]
    return [(r,float(q)) for r,q in zip(rows,p)]

def group_metric(songs,base,truth,selected):
    scores=[];added=tpadd=0
    for s in songs:
        a=v44.dedupe([(r,p) for r,p in selected if r["song"]==s])
        pred=[*base[s],*({"time":r["time"],"group":"snare"} for r,_ in a)]
        sc=v44.score_group(pred,truth[s],"snare")
        b=v44.score_group(base[s],truth[s],"snare")
        scores.append(sc);added+=sc["pred"]-b["pred"];tpadd+=sc["tp"]-b["tp"]
    tp=sum(x["tp"] for x in scores);pp=sum(x["pred"] for x in scores);ref=sum(x["ref"] for x in scores)
    return {"tp":tp,"pred":pp,"ref":ref,"f1":2*tp/(pp+ref) if pp+ref else 0.0,
            "added":added,"added_tp":tpadd,"added_precision":tpadd/added if added else None}

def choose_prob_threshold(train_songs,base,truth,predictions):
    b=group_metric(train_songs,base,truth,[])
    best={"threshold":1.01,"delta":0.0,"added":0,"added_tp":0,"added_precision":None}
    for th in np.linspace(.15,.95,33):
        sel=[(r,p) for r,p in predictions if p>=th]
        x=group_metric(train_songs,base,truth,sel)
        delta=x["f1"]-b["f1"]
        if x["added"]<=0 or x["added_tp"]<=0 or x["added_precision"] is None or x["added_precision"]<.80 or delta<=0:continue
        k=(delta,x["added_precision"],x["added_tp"],-x["added"],float(th))
        old=(best["delta"],best["added_precision"] or -1,best["added_tp"],-best["added"],best["threshold"])
        if k>old:best={"threshold":float(th),"delta":delta,"added":x["added"],
                       "added_tp":x["added_tp"],"added_precision":x["added_precision"]}
    return best

def loocv_model(residual,base,truth,kind):
    chosen={s:[] for s in SONGS};folds={}
    for held in SONGS:
        train_songs=[s for s in SONGS if s!=held]
        tr=[r for r in residual if r["song"] in train_songs]
        te=[r for r in residual if r["song"]==held]
        m=train_model(tr,kind)
        meta={"rows":len(tr),"positive":sum(r["y"] for r in tr),"negative":sum(not r["y"] for r in tr)}
        pp=preds(m,tr);th=choose_prob_threshold(train_songs,base,truth,pp) if m else {"threshold":1.01,"delta":0.0}
        hp=preds(m,te)
        chosen[held]=v44.dedupe([(r,p) for r,p in hp if p>=th["threshold"]]) if m else []
        folds[held]={"training":meta,"threshold":th,"heldoutCandidates":len(te),"selected":len(chosen[held])}
    return chosen,folds

def rule_selected(rows,pmin,cmin,lmin):
    return [(r,r["egmd_probability"]) for r in rows
            if r["egmd_probability"]>=pmin and r["confidence"]>=cmin and r["gmd_lift"]>=lmin]

def choose_rule(train_songs,base,truth,residual):
    b=group_metric(train_songs,base,truth,[])
    best={"pmin":1.01,"cmin":1.01,"lmin":9.0,"delta":0.0,"added":0,"added_tp":0,"added_precision":None}
    for pmin in (.80,.85,.90,.93,.95,.97,.99):
      for cmin in (.50,.60,.70,.80,.90):
       for lmin in (.80,1.00,1.30,1.50):
        rr=[r for r in residual if r["song"] in train_songs]
        x=group_metric(train_songs,base,truth,rule_selected(rr,pmin,cmin,lmin))
        delta=x["f1"]-b["f1"]
        if x["added"]<=0 or x["added_tp"]<=0 or x["added_precision"] is None or x["added_precision"]<.80 or delta<=0:continue
        k=(delta,x["added_precision"],x["added_tp"],-x["added"],pmin,cmin,lmin)
        old=(best["delta"],best["added_precision"] or -1,best["added_tp"],-best["added"],best["pmin"],best["cmin"],best["lmin"])
        if k>old:best={"pmin":pmin,"cmin":cmin,"lmin":lmin,"delta":delta,"added":x["added"],
                       "added_tp":x["added_tp"],"added_precision":x["added_precision"]}
    return best

def loocv_rule(residual,base,truth):
    chosen={s:[] for s in SONGS};folds={}
    for held in SONGS:
        train_songs=[s for s in SONGS if s!=held]
        rule=choose_rule(train_songs,base,truth,residual)
        te=[r for r in residual if r["song"]==held]
        chosen[held]=v44.dedupe(rule_selected(te,rule["pmin"],rule["cmin"],rule["lmin"]))
        folds[held]={"rule":rule,"heldoutCandidates":len(te),"selected":len(chosen[held])}
    return chosen,folds

def union_additions(fixed,residual):
    out={}
    for s in SONGS:out[s]=v44.dedupe([*fixed[s],*residual.get(s,[])])
    return out

def evaluate_union(adds,baselines,truth):
    return v44.evaluate(adds,baselines,truth)

def decorate(name,adds,baselines,truth,baseline,fixed_agg,folds=None):
    agg,scores,detail=evaluate_union(adds,baselines,truth)
    agg["delta_vs_baseline"]=agg["f1"]-baseline["f1"]
    agg["delta_vs_fixed"]=agg["f1"]-fixed_agg["f1"]
    for g in v44.GROUPS:
        agg["by_group"][g]["delta_vs_baseline"]=agg["by_group"][g]["f1"]-baseline["by_group"][g]["f1"]
        agg["by_group"][g]["delta_vs_fixed"]=agg["by_group"][g]["f1"]-fixed_agg["by_group"][g]["f1"]
    return {"name":name,"aggregate":agg,"songs":scores,"detail":detail,"folds":folds}

def main():
    data=json.loads((EXP/"results-arrangement-kst-candidates-v44.json").read_text())
    prior=json.loads((ROOT/"drumscribe/models/gmd-kst/slot-prior-v1.json").read_text())
    truth={}
    for s in SONGS:
        meta=json.loads((ROOT/"DruMaster"/"songs"/s/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        truth[s]=v44.parse_midi(ROOT/"DruMaster"/"songs"/s/"chart.mid",shift)
    rows,baselines=v44.build_rows(data,prior,truth)
    baseline=v44.merge_scores([v44.score(baselines[s],truth[s]) for s in SONGS])
    fixed=fixed_maps(rows);fixed_agg,_,fixed_detail=v44.evaluate(fixed,baselines,truth)
    ks=fixed_keyset(fixed)
    residual=[r for r in rows if r["group"]=="snare" and key(r) not in ks]
    residual_stats={"rows":len(residual),"positive":sum(r["y"] for r in residual),"negative":sum(not r["y"] for r in residual)}

    variants={}
    for kind,name in [("logistic","H5_fixed_plus_logistic_residual"),("extra_trees","H6_fixed_plus_extra_trees_residual")]:
        add,folds=loocv_model(residual,augmented_baselines(baselines,fixed),truth,kind)
        variants[name]=decorate(name,union_additions(fixed,add),baselines,truth,baseline,fixed_agg,folds)
    add,folds=loocv_rule(residual,augmented_baselines(baselines,fixed),truth)
    variants["H7_fixed_plus_interpretable_egmd_rule"]=decorate(
        "H7_fixed_plus_interpretable_egmd_rule",union_additions(fixed,add),baselines,truth,baseline,fixed_agg,folds)

    result={"schema":1,"date":"2026-09-23","experiment":"arrangement-egmd-residual-v45",
            "reference_policy":"Residual Snare model/rule is trained and thresholded on four songs; held-out chart is scoring-only. fixed v39D remains frozen.",
            "baseline":baseline,"fixed_v39d":{"aggregate":fixed_agg,"detail":fixed_detail},
            "residual_snare_pool":residual_stats,"variants":variants}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")

    def f(x):return f"{x:.6f}"
    lines=["# Arrangement + E-GMD residual Snare v45","",
      "Frozen v39D remains the base. Only candidates not already rescued by v39D are eligible for an additional E-GMD-informed Snare rescue.","",
      f"Residual Snare pool: **{residual_stats['rows']}** rows / **{residual_stats['positive']}** recoverable positives.",
      "",
      "| variant | KST F1 | vs baseline | vs fixed v39D | kick vs fixed | snare vs fixed | tom vs fixed | added TP/FP total |",
      "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name in ["H5_fixed_plus_logistic_residual","H6_fixed_plus_extra_trees_residual","H7_fixed_plus_interpretable_egmd_rule"]:
        v=variants[name];a=v["aggregate"];d=v["detail"]
        tp=sum(x["tp"] for x in d.values());fp=sum(x["fp"] for x in d.values())
        lines.append(f"| {name} | {f(a['f1'])} | {f(a['delta_vs_baseline'])} | {f(a['delta_vs_fixed'])} | {f(a['by_group']['kick']['delta_vs_fixed'])} | {f(a['by_group']['snare']['delta_vs_fixed'])} | {f(a['by_group']['tom']['delta_vs_fixed'])} | {tp}/{fp} |")
    lines += ["","Guardrails:",
      "- fixed v39D is never removed; v45 is additive-only on residual Snare candidates.",
      "- All learned/rule thresholds are selected without the held-out song.",
      "- No Kick/Tom change is permitted in this round.",
      "- Runtime adoption still requires a full-data portable rule/model plus fresh Chromium rhythm-grid/MIDI/two-hand validation.",
      ""]
    MD.write_text("\n".join(lines))
    print("\n".join(lines))

if __name__=="__main__":main()
