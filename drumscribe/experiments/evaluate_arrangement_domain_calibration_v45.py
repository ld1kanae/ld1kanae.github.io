from __future__ import annotations
import importlib.util, json, math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"
spec=importlib.util.spec_from_file_location("v44",EXP/"evaluate_arrangement_egmd_fusion_v44.py")
v44=importlib.util.module_from_spec(spec);spec.loader.exec_module(v44)

IN=EXP/"results-arrangement-kst-candidates-v44.json"
PRIOR=ROOT/"drumscribe/models/gmd-kst/slot-prior-v1.json"
OUT=EXP/"results-arrangement-domain-calibration-v45.json"
MD=EXP/"ARRANGEMENT_DOMAIN_CALIBRATION_V45.md"
SONGS=v44.SONGS
GROUPS=v44.GROUPS

def rank_values(vals):
    order=sorted((float(v),i) for i,v in enumerate(vals))
    out=[0.5]*len(vals)
    n=len(vals)
    if n<=1:return out
    i=0
    while i<n:
        j=i+1
        while j<n and abs(order[j][0]-order[i][0])<=1e-12:j+=1
        r=((i+j-1)/2)/(n-1)
        for k in range(i,j):out[order[k][1]]=r
        i=j
    return out

def robust_z(vals):
    a=np.asarray(vals,dtype=float)
    if not len(a):return []
    med=float(np.median(a));mad=float(np.median(np.abs(a-med)))
    scale=max(1.4826*mad,0.15)
    return [float((x-med)/scale) for x in a]

def logit(p):
    p=min(1-1e-6,max(1e-6,float(p)))
    return math.log(p/(1-p))

def add_calibration(rows):
    by=defaultdict(list)
    for r in rows:by[(r["song"],r["group"])].append(r)
    for key,rr in by.items():
        ps=[r["egmd_probability"] for r in rr]
        cs=[r["confidence"] for r in rr]
        gs=[r["gmd_lift"] for r in rr]
        pr=rank_values(ps);cr=rank_values(cs);gr=rank_values(gs)
        pz=robust_z([logit(p) for p in ps])
        for r,a,b,c,z in zip(rr,pr,cr,gr,pz):
            r["egmd_rank"]=a;r["confidence_rank"]=b;r["gmd_lift_rank"]=c;r["egmd_robust_z"]=z
            fq=max(0.0,min(1.0,(r["family_quality"]-.85)/.15)) if r["family_quality"] else 0.0
            r["calibration_soft_score"]=(
                .34*a+.21*b+.16*c+.17*float(r["support_rate"])+.12*fq
            )
    return rows

def keyset(items):
    return {(r["song"],r["group"],round(float(r["time"]),3)) for r,_ in items}

def extras(rows,song,kind,fixed_keys):
    out=[]
    for r in rows:
        if r["song"]!=song:continue
        k=(r["song"],r["group"],round(float(r["time"]),3))
        if k in fixed_keys:continue
        if kind=="C1_rank_extreme":
            ok=(r["egmd_rank"]>=.90 and r["confidence_rank"]>=.60 and r["gmd_lift"]>=1.30)
            score=r["egmd_rank"]+.25*r["confidence_rank"]+.10*min(2,r["gmd_lift"])
        elif kind=="C2_robust_extreme":
            ok=(r["egmd_robust_z"]>=1.15 and r["confidence_rank"]>=.65 and
                (r["gmd_lift"]>=1.30 or r["support_rate"]>=.50))
            score=r["egmd_robust_z"]+.3*r["confidence_rank"]+.15*r["support_rate"]
        else:
            raise KeyError(kind)
        if ok:out.append((r,score))
    return v44.dedupe(out)

def fixed_plus_static(rows,kind):
    adds={}
    for song in SONGS:
        fixed=v44.fixed_v39(rows,song)
        fk=keyset(fixed)
        adds[song]=v44.dedupe(fixed+extras(rows,song,kind,fk))
    return adds

def aggregate_group_with_fixed(songs,baselines,truth,fixed_by_song,preds,threshold,group):
    rows=[];added=0
    for song in songs:
        fixed=fixed_by_song[song]
        fk=keyset(fixed)
        extra=v44.dedupe([(r,p) for r,p in preds
                          if r["song"]==song and r["group"]==group and
                          p>=threshold and
                          (r["song"],r["group"],round(float(r["time"]),3)) not in fk])
        all_add=v44.dedupe(fixed+extra)
        pred=[*baselines[song],*({"time":r["time"],"group":r["group"]} for r,_ in all_add)]
        rows.append(v44.score_group(pred,truth[song],group))
        added+=sum(1 for r,_ in extra if r["group"]==group)
    tp=sum(x["tp"] for x in rows);pp=sum(x["pred"] for x in rows);ref=sum(x["ref"] for x in rows)
    return {"tp":tp,"pred":pp,"ref":ref,"f1":2*tp/(pp+ref) if pp+ref else 0.0,"added":added}

def choose_soft_threshold(train_songs,baselines,truth,fixed,preds,group):
    base=aggregate_group_with_fixed(train_songs,baselines,truth,fixed,[],2.0,group)
    floor={"kick":.90,"snare":.85,"tom":.80}[group]
    best={"threshold":1.01,"delta":0.0,"added":0,"added_tp":0,"added_precision":None}
    for th in np.linspace(.50,.92,22):
        sc=aggregate_group_with_fixed(train_songs,baselines,truth,fixed,preds,float(th),group)
        ap=sc["pred"]-base["pred"];atp=sc["tp"]-base["tp"]
        prec=atp/ap if ap else None;delta=sc["f1"]-base["f1"]
        if ap<=0 or atp<=0 or prec is None or prec<floor or delta<=0:continue
        key=(delta,prec,atp,-ap,float(th))
        old=(best["delta"],best["added_precision"] or -1,best["added_tp"],-best["added"],best["threshold"])
        if key>old:
            best={"threshold":float(th),"delta":delta,"added":ap,"added_tp":atp,"added_precision":prec}
    return best

def soft_loocv(rows,baselines,truth):
    fixed={s:v44.fixed_v39(rows,s) for s in SONGS}
    adds={s:list(fixed[s]) for s in SONGS};folds={}
    for held in SONGS:
        train_songs=[s for s in SONGS if s!=held]
        folds[held]={"groups":{}}
        for g in GROUPS:
            train_pred=[(r,float(r["calibration_soft_score"])) for r in rows if r["song"] in train_songs and r["group"]==g]
            th=choose_soft_threshold(train_songs,baselines,truth,fixed,train_pred,g)
            fk=keyset(fixed[held])
            test=v44.dedupe([(r,float(r["calibration_soft_score"])) for r in rows
                             if r["song"]==held and r["group"]==g and
                             r["calibration_soft_score"]>=th["threshold"] and
                             (r["song"],r["group"],round(float(r["time"]),3)) not in fk])
            adds[held].extend(test)
            folds[held]["groups"][g]={"threshold":th,"heldoutExtraSelected":len(test)}
        adds[held]=v44.dedupe(adds[held])
    agg,scores,detail=v44.evaluate(adds,baselines,truth)
    return {"aggregate":agg,"songs":scores,"detail":detail,"folds":folds}

def decorate(v,baseline):
    a=v["aggregate"];a["delta_f1"]=a["f1"]-baseline["f1"]
    for g in GROUPS:a["by_group"][g]["delta_f1"]=a["by_group"][g]["f1"]-baseline["by_group"][g]["f1"]
    return v

def main():
    data=json.loads(IN.read_text());prior=json.loads(PRIOR.read_text())
    truth={}
    for s in SONGS:
        meta=json.loads((ROOT/"DruMaster"/"songs"/s/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        truth[s]=v44.parse_midi(ROOT/"DruMaster"/"songs"/s/"chart.mid",shift)
    rows,baselines=v44.build_rows(data,prior,truth)
    rows=add_calibration(rows)
    base_scores={s:v44.score(baselines[s],truth[s]) for s in SONGS}
    baseline=v44.merge_scores(list(base_scores.values()))

    variants={}
    fixed={s:v44.fixed_v39(rows,s) for s in SONGS}
    agg,scores,detail=v44.evaluate(fixed,baselines,truth)
    variants["fixed_v39d"]=decorate({"aggregate":agg,"songs":scores,"detail":detail},baseline)

    for name in ("C1_rank_extreme","C2_robust_extreme"):
        adds=fixed_plus_static(rows,name)
        agg,scores,detail=v44.evaluate(adds,baselines,truth)
        variants[name]=decorate({"aggregate":agg,"songs":scores,"detail":detail},baseline)

    variants["C3_soft_rank_loocv"]=decorate(soft_loocv(rows,baselines,truth),baseline)

    result={
      "schema":1,"date":"2026-09-23","experiment":"arrangement-domain-calibration-v45",
      "reference_policy":"Calibration values are computed from each song/group candidate distribution without chart.mid. C3 thresholds use only the other four songs in each held-out fold.",
      "baseline":baseline,"candidate_rows":len(rows),"variants":variants,
      "calibration":{
        "egmd_rank":"within-song, within-instrument empirical CDF rank",
        "egmd_robust_z":"within-song robust z of logit(E-GMD probability)",
        "soft_score":".34 egmd rank + .21 acoustic confidence rank + .16 GMD slot-lift rank + .17 A/A-prime support + .12 normalized family quality"
      }
    }
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    def f(x):return f"{x:.6f}"
    lines=["# Arrangement E-GMD domain calibration v45","",
      "Every calibrated variant starts from the already validated fixed v39D rescues; calibration is allowed only to add extra candidates.",
      "",
      "| variant | KST F1 | delta | kick delta | snare delta | tom delta | total added TP/FP |",
      "|---|---:|---:|---:|---:|---:|---:|"]
    for name in ("fixed_v39d","C1_rank_extreme","C2_robust_extreme","C3_soft_rank_loocv"):
        v=variants[name];a=v["aggregate"];d=v["detail"]
        tp=sum(x["tp"] for x in d.values());fp=sum(x["fp"] for x in d.values())
        lines.append(f"| {name} | {f(a['f1'])} | {f(a['delta_f1'])} | {f(a['by_group']['kick']['delta_f1'])} | {f(a['by_group']['snare']['delta_f1'])} | {f(a['by_group']['tom']['delta_f1'])} | {tp}/{fp} |")
    lines += ["","Guardrails:",
      "- fixed v39D rescues are preserved; E-GMD calibration never vetoes them.",
      "- calibration is song-local and reference-free at prediction time.",
      "- C3 is song-held-out for threshold selection.",
      "- production adoption requires beating fixed v39D without per-part regression, then fresh browser rhythm-grid/MIDI validation.",
      ""]
    MD.write_text("\n".join(lines))
    print("\n".join(lines))

if __name__=="__main__":main()
