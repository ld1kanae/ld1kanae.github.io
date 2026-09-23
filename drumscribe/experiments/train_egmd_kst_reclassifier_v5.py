"""E-GMD K/S/T reclassifier v5: substantially larger external corpus.

v5 keeps the v3/v4 browser-compatible feature representation and expands only
external supervision. Three hypotheses are compared on official E-GMD validation
sequences rendered with drum kits never used for fitting:

A scale_large: all candidates equally, class-balanced logistic regression.
B sequence_balanced: down-weight long/dense sequences so each performance has
  roughly equal influence.
C mild_hard_context: sequence-balanced plus mild emphasis on kick+snare overlap,
  weak hits, tom fills and class-confusion negatives.

DruMaster data is not used in training or model/threshold selection.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter,defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score,roc_auc_score
from sklearn.preprocessing import StandardScaler
from remotezip import RemoteZip

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
spec=importlib.util.spec_from_file_location("v4",EXP/"train_egmd_kst_reclassifier_v4.py")
v4=importlib.util.module_from_spec(spec); spec.loader.exec_module(v4)
v3=v4.v3
GROUPS=v4.GROUPS
FEATURE_NAMES=v4.FEATURE_NAMES
EGMD_ZIP=v4.EGMD_ZIP
EGMD_CSV=v4.EGMD_CSV
LOW_SCALE=v4.LOW_SCALE
PROD_SCALE=v4.PROD_SCALE
BASE_THRESH=v4.BASE_THRESH
MATCH=v4.MATCH
FPS=v4.FPS

def take_diverse(items,n,score):
    ranked=sorted(items,key=lambda x:(score(x[1]),x[0]),reverse=True)
    chosen=[]; fam_count=Counter()
    # Allow up to three per style family before filling globally.
    for x in ranked:
        fam=x[1]["styleFamily"]
        if fam_count[fam]>=3: continue
        chosen.append(x); fam_count[fam]+=1
        if len(chosen)>=n:return chosen
    used={x[0] for x in chosen}
    for x in ranked:
        if x[0] in used:continue
        chosen.append(x);used.add(x[0])
        if len(chosen)>=n:break
    return chosen

def choose_expanded(profiles,counts):
    fills=[x for x in profiles if x[1]["beatType"]=="fill" and x[1]["tom"]>=2]
    beats=[x for x in profiles if x[1]["beatType"]=="beat" and x[1]["kick"]>=4 and x[1]["snare"]>=2]
    ks=[x for x in profiles if x[1]["kickSnareOverlap"]>=2]
    tom=[x for x in profiles if x[1]["tom"]>=5]
    snare_dense=[x for x in profiles if x[1]["snare"]>=16]
    kick_dense=[x for x in profiles if x[1]["kick"]>=16]
    buckets={
      "generic_fill":take_diverse(fills,counts["generic_fill"],lambda p:p["tom"]+.2*(p["kick"]+p["snare"])),
      "generic_beat":take_diverse(beats,counts["generic_beat"],lambda p:p["kick"]+p["snare"]),
      "kick_snare_overlap":take_diverse(ks,counts["kick_snare_overlap"],lambda p:5*p["kickSnareOverlap"]+p["snare"]),
      "tom_heavy":take_diverse(tom,counts["tom_heavy"],lambda p:3*p["tom"]+p["kickTomOverlap"]),
      "snare_dense":take_diverse(snare_dense,counts["snare_dense"],lambda p:p["snare"]+2*p["kickSnareOverlap"]),
      "kick_dense":take_diverse(kick_dense,counts["kick_dense"],lambda p:p["kick"]+p["snare"]),
    }
    tags=defaultdict(set); prof={}
    for tag,items in buckets.items():
        for key,p in items:
            tags[key].add(tag);prof[key]=p
    seqs=sorted(tags)
    return seqs,{k:sorted(v) for k,v in tags.items()},prof,buckets

def kit_partition(rows):
    kits=sorted({r.get("kit_name","") for r in rows if r.get("kit_name")})
    if len(kits)<24:raise RuntimeError(f"too few kits: {len(kits)}")
    # 12 training kits, 7 completely disjoint held-out kits.
    train=[];hold=[]
    for i in np.linspace(0,len(kits)-1,20).round().astype(int):
        k=kits[int(i)]
        if k not in train:train.append(k)
        if len(train)>=12:break
    for i in np.linspace(1,len(kits)-2,28).round().astype(int):
        k=kits[int(i)]
        if k not in train and k not in hold:hold.append(k)
        if len(hold)>=7:break
    for k in kits:
        if len(hold)>=7:break
        if k not in train and k not in hold:hold.append(k)
    return train[:12],hold[:7]

def candidate_weights(rows,g,hyp):
    if hyp=="scale_large":return None
    seq_count=Counter(x[5]["sequence"] for x in rows)
    base=np.asarray([1.0/np.sqrt(max(1,seq_count[x[5]["sequence"]])) for x in rows],dtype=np.float64)
    base/=max(1e-12,float(np.mean(base)))
    if hyp=="sequence_balanced":
        return np.clip(base,.35,3.0)
    if hyp=="mild_hard_context":
        out=base.copy()
        for i,x in enumerate(rows):
            y=int(x[2]);c=x[5];m=1.0
            if c["classConfusionNegative"]:m*=1.45
            if g=="snare" and y and c["nearKickTruth"]:m*=1.45
            if g=="snare" and y and c["weakRaw"]:m*=1.25
            if g=="tom" and y and c["fill"]:m*=1.35
            if g=="tom" and (not y) and c["nearKickTruth"]:m*=1.55
            if g=="kick" and y and c["weakRaw"]:m*=1.20
            out[i]*=m
        out/=max(1e-12,float(np.mean(out)))
        return np.clip(out,.30,4.0)
    raise ValueError(hyp)

def fit_binary(rows,C,weights):
    X=np.stack([x[1] for x in rows]); y=np.asarray([x[2] for x in rows],np.int8)
    sc=StandardScaler().fit(X)
    clf=LogisticRegression(C=C,max_iter=1800,class_weight="balanced",solver="lbfgs",random_state=923)
    clf.fit(sc.transform(X),y,sample_weight=weights)
    return sc,clf

def probs(rows,sc,clf):
    X=np.stack([x[1] for x in rows])
    return clf.predict_proba(sc.transform(X))[:,list(clf.classes_).index(1)]

def metric(tp,pred,ref):
    tp=int(tp);pred=int(pred);ref=int(ref)
    p=tp/pred if pred else 0.;r=tp/ref if ref else 0.
    return {"tp":tp,"predicted":pred,"reference":ref,"precision":p,"recall":r,
            "f1":2*tp/(pred+ref) if pred+ref else 0.}

def threshold_score(rows,pr,thr):
    y=np.asarray([x[2] for x in rows],np.int8); keep=np.asarray(pr)>=thr
    return metric(np.sum(keep&(y==1)),np.sum(keep),np.sum(y==1))

def choose_threshold(rows,pr,g):
    floor={"kick":.97,"snare":.95,"tom":.95}[g]
    best=None
    for thr in np.arange(.30,.991,.01):
        s=threshold_score(rows,pr,float(thr))
        eligible=bool(s["precision"]>=floor and s["predicted"]>=12)
        key=(eligible,s["f1"],s["recall"],s["precision"])
        if best is None or key>best[0]:best=(key,float(thr),s,eligible)
    return best[1],best[2],best[3],floor

def by_context(rows,pr,thr):
    y=np.asarray([x[2] for x in rows],np.int8); pr=np.asarray(pr)
    masks={
      "all":np.ones(len(rows),bool),
      "nearKick":np.asarray([bool(x[5]["nearKickTruth"]) for x in rows]),
      "fill":np.asarray([bool(x[5]["fill"]) for x in rows]),
      "weakRaw":np.asarray([bool(x[5]["weakRaw"]) for x in rows]),
      "classConfusionNegative":np.asarray([bool(x[5]["classConfusionNegative"]) for x in rows]),
    }
    out={}
    for name,mask in masks.items():
        if not np.any(mask):continue
        keep=(pr>=thr)&mask; ref=np.sum((y==1)&mask)
        out[name]=metric(np.sum(keep&(y==1)),np.sum(keep),ref)
    return out

def by_kit(rows,pr,thr):
    out={}
    kits=sorted({x[5]["kit"] for x in rows})
    y=np.asarray([x[2] for x in rows],np.int8);pr=np.asarray(pr)
    for kit in kits:
        mask=np.asarray([x[5]["kit"]==kit for x in rows],bool)
        keep=(pr>=thr)&mask
        out[kit]=metric(np.sum(keep&(y==1)),np.sum(keep),np.sum((y==1)&mask))
    return out

def export_model(sc,clf):
    return {"mean":sc.mean_.tolist(),"scale":sc.scale_.tolist(),
            "coef":clf.coef_[0].tolist(),"intercept":float(clf.intercept_[0])}

def aggregate_prod(truth_all,g):
    tp=pred=ref=0
    for prod,truth in truth_all:
        s=v3.score_events(prod[g],truth[g]);tp+=s["tp"];pred+=s["predicted"];ref+=s["reference"]
    return metric(tp,pred,ref)

def main():
    rows=v3.read_csv_url(EGMD_CSV)
    train_kits,held_kits=kit_partition(rows)
    print("TRAIN_KITS",train_kits,flush=True);print("HELDOUT_KITS",held_kits,flush=True)
    model=v3.frozen_model();processor=v3.create_adtof_processor()
    with RemoteZip(EGMD_ZIP) as z:
        names=set(z.namelist())
        trg=v3.sequence_groups(rows,"train");vag=v3.sequence_groups(rows,"validation")
        trp=v4.scan_profiles(z,names,trg);vap=v4.scan_profiles(z,names,vag)
        trseq,trtags,trprof,_=choose_expanded(trp,{
          "generic_fill":12,"generic_beat":12,"kick_snare_overlap":16,
          "tom_heavy":16,"snare_dense":12,"kick_dense":12})
        vaseq,vatags,vaprof,_=choose_expanded(vap,{
          "generic_fill":7,"generic_beat":7,"kick_snare_overlap":9,
          "tom_heavy":9,"snare_dense":7,"kick_dense":7})
        trrows=v4.rows_for_sequences(trg,trseq,train_kits,trtags,trprof)
        varows=v4.rows_for_sequences(vag,vaseq,held_kits,vatags,vaprof)
        print("TRAIN_SEQS",len(trseq),trseq,flush=True)
        print("VAL_SEQS",len(vaseq),vaseq,flush=True)
        train,train_truth,train_manifest=v4.collect(z,names,trrows,model,processor,"train")
        val,val_truth,val_manifest=v4.collect(z,names,varows,model,processor,"val")

    report={"schema":5,"dataset":"E-GMD v1.0.0","trainKits":train_kits,"heldOutKits":held_kits,
      "trainSequences":trseq,"validationSequences":vaseq,
      "trainSelectionTags":trtags,"validationSelectionTags":vatags,
      "trainManifest":train_manifest,"validationManifest":val_manifest,
      "hypotheses":{},"retainedByClass":{}}
    deployment={"schema":5,"kind":"egmd-kst-candidate-logreg-v5-expanded",
      "sampleRate":44100,"fps":FPS,
      "source":{"dataset":"E-GMD v1.0.0","license":"CC BY 4.0",
        "split":"official train fit; official validation + disjoint held-out kits for selection",
        "url":"https://magenta.tensorflow.org/datasets/e-gmd"},
      "featureNames":FEATURE_NAMES,"lowScale":LOW_SCALE,"productionScale":PROD_SCALE,
      "baseThresholds":BASE_THRESH,"matchToleranceSec":MATCH,
      "trainKits":train_kits,"heldOutKits":held_kits,"models":{}}

    for g in GROUPS:
        report["hypotheses"][g]={};prod=aggregate_prod(val_truth,g);final=[]
        for hyp in ("scale_large","sequence_balanced","mild_hard_context"):
            weights=candidate_weights(train[g],g,hyp)
            best=None
            for C in (.02,.05,.10,.20,.50,1.0,2.0):
                sc,clf=fit_binary(train[g],C,weights);pr=probs(val[g],sc,clf)
                thr,score,eligible,floor=choose_threshold(val[g],pr,g)
                y=np.asarray([x[2] for x in val[g]],np.int8)
                ap=float(average_precision_score(y,pr));auc=float(roc_auc_score(y,pr))
                key=(eligible,score["f1"],ap,score["recall"],score["precision"])
                if best is None or key>best[0]:
                    best=(key,C,thr,score,eligible,floor,ap,auc,sc,clf,pr)
            _,C,thr,score,eligible,floor,ap,auc,sc,clf,pr=best
            info={"eligible":bool(eligible),"C":C,"threshold":thr,"precisionFloor":floor,
              "trainCandidates":len(train[g]),"trainPositive":int(sum(x[2] for x in train[g])),
              "validationCandidates":len(val[g]),"validationPositive":int(sum(x[2] for x in val[g])),
              "averagePrecision":ap,"rocAuc":auc,"rawProduction":prod,
              "reclassifiedLowPool":score,"contexts":by_context(val[g],pr,thr),
              "byHeldOutKit":by_kit(val[g],pr,thr)}
            report["hypotheses"][g][hyp]=info
            final.append((bool(eligible),score["f1"],ap,score["recall"],hyp,sc,clf,thr,info))
            print("HYP",g,hyp,json.dumps(info,ensure_ascii=False),flush=True)
        final.sort(key=lambda x:(x[0],x[1],x[2],x[3]),reverse=True)
        eligible,f1,ap,rec,hyp,sc,clf,thr,info=final[0]
        report["retainedByClass"][g]=hyp
        deployment["models"][g]={**export_model(sc,clf),"C":info["C"],"threshold":thr,
          "hypothesis":hyp,"externalValidation":{
            "rawProduction":prod,"reclassifiedLowPool":info["reclassifiedLowPool"],
            "averagePrecision":info["averagePrecision"],"rocAuc":info["rocAuc"],
            "contexts":info["contexts"],"byHeldOutKit":info["byHeldOutKit"]}}
        print("RETAIN",g,hyp,thr,info["reclassifiedLowPool"],flush=True)

    op=ROOT/"drumscribe/models/egmd-kst-reclassifier-v5.json"
    rp=EXP/"results-egmd-kst-reclassifier-v5.json"
    op.write_text(json.dumps(deployment,separators=(",",":"))+"\n")
    rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("MODEL",str(op),op.stat().st_size,flush=True)

if __name__=="__main__":main()
