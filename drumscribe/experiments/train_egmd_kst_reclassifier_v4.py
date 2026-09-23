"""E-GMD K/S/T reclassifier v4: larger corpus + targeted hard contexts.

Three hypotheses are trained on the same sequence/kit-held-out protocol:
A scale: larger generic corpus, ordinary balanced logistic regression.
B targeted_oversample: duplicate kick/snare overlap and tom-fill hard contexts.
C targeted_weighted: keep all rows once, but sample-weight the same hard contexts.

The feature representation is identical to v3, so a retained model can replace the
v3 JSON without changing browser feature extraction. DruMaster charts are never
used here.
"""
from __future__ import annotations
import importlib.util,io,json,math
from collections import Counter,defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score,roc_auc_score
from sklearn.preprocessing import StandardScaler
from remotezip import RemoteZip

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"
spec=importlib.util.spec_from_file_location("v3",EXP/"train_egmd_kst_reclassifier_v3.py")
v3=importlib.util.module_from_spec(spec);spec.loader.exec_module(v3)

GROUPS=v3.GROUPS
CLASS_INDEX=v3.CLASS_INDEX
BASE_THRESH=v3.BASE_THRESH
LOW_SCALE=v3.LOW_SCALE
PROD_SCALE=v3.PROD_SCALE
MATCH=v3.MATCH
FPS=v3.FPS
FEATURE_NAMES=v3.FEATURE_NAMES
EGMD_ZIP=v3.EGMD_ZIP
EGMD_CSV=v3.EGMD_CSV

def style_family(row):
    return (row.get("style") or "unknown").split("/")[0].strip().lower() or "unknown"

def sequence_profile(notes,row):
    by={g:sorted(t for t,gg in notes if gg==g) for g in GROUPS}
    ks=sum(1 for s in by["snare"] if any(abs(k-s)<=.040 for k in by["kick"]))
    kt=sum(1 for t in by["tom"] if any(abs(k-t)<=.040 for k in by["kick"]))
    return {
      "kick":len(by["kick"]),"snare":len(by["snare"]),"tom":len(by["tom"]),
      "kickSnareOverlap":ks,"kickTomOverlap":kt,
      "beatType":row.get("beat_type") or "unknown",
      "styleFamily":style_family(row)
    }

def scan_profiles(z,names,groups):
    out=[]
    ids=sorted(groups,key=lambda k:(style_family(groups[k][0]),float(groups[k][0].get("duration") or 0),k))
    for key in ids:
        row=sorted(groups[key],key=lambda r:r.get("kit_name",""))[0]
        try:
            mn=v3.resolve_name(names,row["midi_filename"])
            notes=v3.midi_notes_bytes(z.read(mn))
        except Exception:
            continue
        p=sequence_profile(notes,row)
        if p["kick"]+p["snare"]+p["tom"]<3:continue
        out.append((key,p))
    return out

def take_diverse(items,n,score):
    ranked=sorted(items,key=lambda x:(score(x[1]),x[0]),reverse=True)
    chosen=[];families=set()
    # first pass: style diversity
    for x in ranked:
        fam=x[1]["styleFamily"]
        if fam in families:continue
        chosen.append(x);families.add(fam)
        if len(chosen)>=n:return chosen
    # second pass: fill by difficulty
    used={x[0] for x in chosen}
    for x in ranked:
        if x[0] in used:continue
        chosen.append(x);used.add(x[0])
        if len(chosen)>=n:break
    return chosen

def choose_targeted(profiles,counts):
    fills=[x for x in profiles if x[1]["beatType"]=="fill" and x[1]["tom"]>=3]
    beats=[x for x in profiles if x[1]["beatType"]=="beat" and x[1]["kick"]>=4 and x[1]["snare"]>=2]
    ks=[x for x in profiles if x[1]["kickSnareOverlap"]>=2]
    tom=[x for x in profiles if x[1]["tom"]>=5]
    buckets={
      "generic_fill":take_diverse(fills,counts["generic_fill"],lambda p:p["tom"]+.2*(p["kick"]+p["snare"])),
      "generic_beat":take_diverse(beats,counts["generic_beat"],lambda p:p["kick"]+p["snare"]),
      "kick_snare_overlap":take_diverse(ks,counts["kick_snare_overlap"],lambda p:4*p["kickSnareOverlap"]+p["snare"]),
      "tom_heavy":take_diverse(tom,counts["tom_heavy"],lambda p:3*p["tom"]+p["kickTomOverlap"]),
    }
    tags=defaultdict(set);prof={}
    for tag,items in buckets.items():
        for key,p in items:
            tags[key].add(tag);prof[key]=p
    seqs=sorted(tags)
    return seqs,{k:sorted(v) for k,v in tags.items()},prof,buckets

def kit_partition(rows):
    kits=sorted({r.get("kit_name","") for r in rows if r.get("kit_name")})
    if len(kits)<18:raise RuntimeError(f"too few kits: {len(kits)}")
    # More domain coverage than v3: 8 train kits + 5 fully disjoint held-out kits.
    train=[];hold=[]
    for i in np.linspace(0,len(kits)-1,12).round().astype(int):
        k=kits[int(i)]
        if k not in train:train.append(k)
        if len(train)>=8:break
    for i in np.linspace(1,len(kits)-2,15).round().astype(int):
        k=kits[int(i)]
        if k not in train and k not in hold:hold.append(k)
        if len(hold)>=5:break
    for k in kits:
        if len(hold)>=5:break
        if k not in train and k not in hold:hold.append(k)
    return train[:8],hold[:5]

def rows_for_sequences(groups,seqs,kits,tags,profiles):
    out=[]
    for seq in seqs:
        bykit={r.get("kit_name"):r for r in groups[seq]}
        for kit in kits:
            if kit not in bykit:continue
            row=dict(bykit[kit])
            row["_v4_tags"]=list(tags.get(seq,[]))
            row["_v4_profile"]=profiles.get(seq,{})
            out.append(row)
    return out

def near_times(xs,t,w=.040):
    return any(abs(x-t)<=w for x in xs)

def enrich_candidate(g,item,truth,row,synthetic=False):
    t,features,y,activation,residual=item[:5]
    by={gg:sorted(x for x,g0 in truth if g0==gg) for gg in GROUPS}
    ctx={
      "sequence":row.get("id"),"kit":row.get("kit_name"),
      "beatType":row.get("beat_type"),"tags":row.get("_v4_tags",[]),
      "nearKickTruth":near_times(by["kick"],t),
      "nearSnareTruth":near_times(by["snare"],t),
      "nearTomTruth":near_times(by["tom"],t),
      "classConfusionNegative":bool(not y and any(
          near_times(by[gg],t) for gg in GROUPS if gg!=g)),
      "weakRaw":bool(activation < {"kick":.11,"snare":.12,"tom":.16}[g]),
      "targetedSequence":bool(set(row.get("_v4_tags",[])) & {"kick_snare_overlap","tom_heavy"}),
      "fill":row.get("beat_type")=="fill",
    }
    return (t,features,y,activation,residual,ctx)

def collect(z,names,rows,model,processor,tag):
    data={g:[] for g in GROUPS};truth_all=[];manifest=[]
    for i,row in enumerate(rows,1):
        try:
            an=v3.resolve_name(names,row["audio_filename"])
            mn=v3.resolve_name(names,row["midi_filename"])
            raw=z.read(an);audio=v3.decode_wav(raw);notes=v3.midi_notes_bytes(z.read(mn))
            acts=v3.activities(model,processor,audio)
            cand=v3.candidate_rows(acts,notes,hard_negatives=(tag=="train"))
            prod=v3.production_events(acts)
        except Exception as e:
            print("SKIP",tag,row.get("id"),row.get("kit_name"),type(e).__name__,str(e)[:140],flush=True)
            continue
        for g in GROUPS:
            data[g].extend(enrich_candidate(g,x,notes,row) for x in cand[g])
        truth={g:sorted(t for t,gg in notes if gg==g) for g in GROUPS}
        truth_all.append((prod,truth))
        p=row.get("_v4_profile",{})
        manifest.append({
          "id":row.get("id"),"kit":row.get("kit_name"),"style":row.get("style"),
          "beat_type":row.get("beat_type"),"duration":float(row.get("duration") or 0),
          "tags":row.get("_v4_tags",[]),"profile":p,
          "counts":v3.count_groups(notes),"audioBytes":len(raw)
        })
        print("CLIP",tag,i,len(rows),manifest[-1],
              {g:len(cand[g]) for g in GROUPS},flush=True)
    return data,truth_all,manifest

def targeted_row(g,row):
    y=int(row[2]);c=row[5]
    if g=="snare":
        return (y and c["nearKickTruth"]) or c["classConfusionNegative"] or (y and c["weakRaw"])
    if g=="tom":
        return (y and c["fill"]) or (not y and c["nearKickTruth"]) or c["classConfusionNegative"]
    return c["classConfusionNegative"] or (y and c["weakRaw"])

def training_rows(rows,g,hypothesis):
    if hypothesis=="scale":
        return list(rows),None
    if hypothesis=="targeted_oversample":
        extra=[x for x in rows if targeted_row(g,x)]
        # duplicate hard contexts twice while preserving all generic contexts.
        return list(rows)+extra+extra,None
    if hypothesis=="targeted_weighted":
        w=[]
        for x in rows:
            y=int(x[2]);c=x[5];z=1.0
            if c["classConfusionNegative"]:z*=2.5
            if g=="snare" and y and c["nearKickTruth"]:z*=3.0
            if g=="snare" and y and c["weakRaw"]:z*=2.0
            if g=="tom" and y and c["fill"]:z*=2.5
            if g=="tom" and (not y) and c["nearKickTruth"]:z*=3.0
            if g=="kick" and y and c["weakRaw"]:z*=1.5
            w.append(min(z,6.0))
        return list(rows),np.asarray(w,dtype=np.float64)
    raise ValueError(hypothesis)

def fit_binary(rows,C,weights=None):
    X=np.stack([x[1] for x in rows]);y=np.asarray([x[2] for x in rows],np.int8)
    sc=StandardScaler().fit(X)
    clf=LogisticRegression(C=C,max_iter=1600,class_weight="balanced",solver="lbfgs",random_state=923)
    clf.fit(sc.transform(X),y,sample_weight=weights)
    return sc,clf

def probs(rows,sc,clf):
    X=np.stack([x[1] for x in rows])
    return clf.predict_proba(sc.transform(X))[:,list(clf.classes_).index(1)]

def metric_counts(tp,pred,ref):
    p=tp/pred if pred else 0.;r=tp/ref if ref else 0.
    return {"tp":int(tp),"predicted":int(pred),"reference":int(ref),
            "precision":p,"recall":r,"f1":2*tp/(pred+ref) if pred+ref else 0.}

def threshold_score(rows,pr,thr):
    y=np.asarray([x[2] for x in rows],np.int8);keep=np.asarray(pr)>=thr
    return metric_counts(np.sum(keep & (y==1)),np.sum(keep),np.sum(y==1))

def choose_threshold(rows,pr,g):
    floor={"kick":.97,"snare":.95,"tom":.95}[g]
    best=None
    for thr in np.arange(.30,.991,.01):
        s=threshold_score(rows,pr,float(thr))
        eligible=s["precision"]>=floor and s["predicted"]>=8
        key=(eligible,s["f1"],s["recall"],s["precision"])
        if best is None or key>best[0]:best=(key,float(thr),s,eligible)
    return best[1],best[2],best[3],floor

def export_binary(sc,clf):
    return {"mean":sc.mean_.tolist(),"scale":sc.scale_.tolist(),
            "coef":clf.coef_[0].tolist(),"intercept":float(clf.intercept_[0])}

def aggregate_prod(truth_all,g):
    tp=pred=ref=0
    for prod,truth in truth_all:
        s=v3.score_events(prod[g],truth[g]);tp+=s["tp"];pred+=s["predicted"];ref+=s["reference"]
    return metric_counts(tp,pred,ref)

def context_metrics(rows,pr,thr,g):
    out={}
    masks={
      "all":[True]*len(rows),
      "nearKick":[bool(x[5]["nearKickTruth"]) for x in rows],
      "fill":[bool(x[5]["fill"]) for x in rows],
      "weakRaw":[bool(x[5]["weakRaw"]) for x in rows],
    }
    y=np.asarray([x[2] for x in rows],np.int8);pr=np.asarray(pr)
    for name,mask0 in masks.items():
        mask=np.asarray(mask0,dtype=bool)
        if not np.any(mask):continue
        keep=(pr>=thr)&mask
        ref=int(np.sum((y==1)&mask));pred=int(np.sum(keep));tp=int(np.sum(keep&(y==1)))
        out[name]=metric_counts(tp,pred,ref)
    return out

def main():
    rows=v3.read_csv_url(EGMD_CSV)
    train_kits,held_kits=kit_partition(rows)
    print("TRAIN_KITS",train_kits,flush=True);print("HELDOUT_KITS",held_kits,flush=True)
    model=v3.frozen_model();processor=v3.create_adtof_processor()

    with RemoteZip(EGMD_ZIP) as z:
        names=set(z.namelist())
        trg=v3.sequence_groups(rows,"train");vag=v3.sequence_groups(rows,"validation")
        tr_profiles=scan_profiles(z,names,trg);va_profiles=scan_profiles(z,names,vag)
        trseq,trtags,trprof,trbuckets=choose_targeted(tr_profiles,{
          "generic_fill":6,"generic_beat":6,"kick_snare_overlap":8,"tom_heavy":8})
        vaseq,vatags,vaprof,vabuckets=choose_targeted(va_profiles,{
          "generic_fill":4,"generic_beat":4,"kick_snare_overlap":5,"tom_heavy":5})
        trrows=rows_for_sequences(trg,trseq,train_kits,trtags,trprof)
        varows=rows_for_sequences(vag,vaseq,held_kits,vatags,vaprof)
        print("TRAIN_SEQS",len(trseq),trseq,flush=True)
        print("VAL_SEQS",len(vaseq),vaseq,flush=True)
        train,train_truth,train_manifest=collect(z,names,trrows,model,processor,"train")
        val,val_truth,val_manifest=collect(z,names,varows,model,processor,"val")

    report={
      "schema":4,"dataset":"E-GMD v1.0.0",
      "trainKits":train_kits,"heldOutKits":held_kits,
      "trainSequences":trseq,"validationSequences":vaseq,
      "trainSelectionTags":trtags,"validationSelectionTags":vatags,
      "trainManifest":train_manifest,"validationManifest":val_manifest,
      "hypotheses":{},"retainedByClass":{}
    }
    deployment={
      "schema":4,"kind":"egmd-kst-candidate-logreg-v4-targeted",
      "sampleRate":44100,"fps":FPS,
      "source":{"dataset":"E-GMD v1.0.0","license":"CC BY 4.0",
        "split":"official train fit; official validation + disjoint held-out kits for selection",
        "url":"https://magenta.tensorflow.org/datasets/e-gmd"},
      "featureNames":FEATURE_NAMES,"lowScale":LOW_SCALE,"productionScale":PROD_SCALE,
      "baseThresholds":BASE_THRESH,"matchToleranceSec":MATCH,
      "trainKits":train_kits,"heldOutKits":held_kits,"models":{}
    }

    for g in GROUPS:
        report["hypotheses"][g]={}
        prod=aggregate_prod(val_truth,g)
        finalists=[]
        for hyp in ("scale","targeted_oversample","targeted_weighted"):
            fitrows,weights=training_rows(train[g],g,hyp)
            best=None
            for C in (.03,.08,.20,.50,1.0,2.0):
                sc,clf=fit_binary(fitrows,C,weights)
                pr=probs(val[g],sc,clf)
                thr,score,eligible,floor=choose_threshold(val[g],pr,g)
                y=np.asarray([x[2] for x in val[g]],np.int8)
                ap=average_precision_score(y,pr) if len(set(y.tolist()))>1 else 0.
                auc=roc_auc_score(y,pr) if len(set(y.tolist()))>1 else 0.
                key=(eligible,score["f1"],ap,score["recall"],score["precision"])
                if best is None or key>best[0]:
                    best=(key,C,thr,score,eligible,floor,ap,auc,sc,clf,pr,len(fitrows),
                          float(np.mean(weights)) if weights is not None else None)
            _,C,thr,score,eligible,floor,ap,auc,sc,clf,pr,nfit,wmean=best
            info={
              "eligible":eligible,"C":C,"threshold":thr,"precisionFloor":floor,
              "trainCandidates":len(train[g]),"fitRows":nfit,
              "trainPositive":int(sum(x[2] for x in train[g])),
              "validationCandidates":len(val[g]),"validationPositive":int(sum(x[2] for x in val[g])),
              "sampleWeightMean":wmean,"averagePrecision":ap,"rocAuc":auc,
              "rawProduction":prod,"reclassifiedLowPool":score,
              "contexts":context_metrics(val[g],pr,thr,g)
            }
            report["hypotheses"][g][hyp]=info
            finalists.append((eligible,score["f1"],ap,score["recall"],hyp,sc,clf,thr,info))
            print("HYP",g,hyp,json.dumps(info,ensure_ascii=False),flush=True)
        finalists.sort(key=lambda x:(x[0],x[1],x[2],x[3]),reverse=True)
        eligible,f1,ap,rec,hyp,sc,clf,thr,info=finalists[0]
        report["retainedByClass"][g]=hyp
        deployment["models"][g]={
          **export_binary(sc,clf),"C":info["C"],"threshold":thr,"hypothesis":hyp,
          "externalValidation":{
             "rawProduction":prod,"reclassifiedLowPool":info["reclassifiedLowPool"],
             "averagePrecision":info["averagePrecision"],"rocAuc":info["rocAuc"],
             "contexts":info["contexts"]
          }
        }
        print("RETAIN",g,hyp,thr,info["reclassifiedLowPool"],flush=True)

    op=ROOT/"drumscribe/models/egmd-kst-reclassifier-v4.json"
    rp=EXP/"results-egmd-kst-reclassifier-v4.json"
    op.write_text(json.dumps(deployment,separators=(",",":"))+"\n")
    rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("MODEL",str(op),op.stat().st_size,flush=True)

if __name__=="__main__":main()
