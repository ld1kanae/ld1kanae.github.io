"""Calibrate frozen E-GMD v5 snare thresholds on E-GMD held-out data only.

This script NEVER reads DruMaster audio, MIDI, scores, or browser results.
It keeps the frozen v5 model coefficients unchanged and reconstructs the same
official-validation/disjoint-kit set used by v5.  It reports conservative
precision tiers for later frozen transfer tests.
"""
from __future__ import annotations
import importlib.util, json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from remotezip import RemoteZip

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
spec=importlib.util.spec_from_file_location("v4",EXP/"train_egmd_kst_reclassifier_v4.py")
v4=importlib.util.module_from_spec(spec); spec.loader.exec_module(v4)
v3=v4.v3
EGMD_ZIP=v4.EGMD_ZIP
EGMD_CSV=v4.EGMD_CSV

def take_diverse(items,n,score):
    ranked=sorted(items,key=lambda x:(score(x[1]),x[0]),reverse=True)
    chosen=[]; fam_count=Counter()
    for x in ranked:
        fam=x[1]["styleFamily"]
        if fam_count[fam]>=3: continue
        chosen.append(x); fam_count[fam]+=1
        if len(chosen)>=n:return chosen
    used={x[0] for x in chosen}
    for x in ranked:
        if x[0] in used:continue
        chosen.append(x); used.add(x[0])
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
            tags[key].add(tag); prof[key]=p
    seqs=sorted(tags)
    return seqs,{k:sorted(v) for k,v in tags.items()},prof

def kit_partition(rows):
    kits=sorted({r.get("kit_name","") for r in rows if r.get("kit_name")})
    if len(kits)<24:raise RuntimeError(f"too few kits: {len(kits)}")
    train=[]; hold=[]
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

def metric(y,pr,thr):
    keep=pr>=thr
    tp=int(np.sum(keep&(y==1))); pred=int(np.sum(keep)); ref=int(np.sum(y==1))
    p=tp/pred if pred else 0.; r=tp/ref if ref else 0.
    return {"tp":tp,"predicted":pred,"reference":ref,"precision":p,"recall":r,
            "f1":2*tp/(pred+ref) if pred+ref else 0.}

def probs_from_frozen(rows,m):
    X=np.stack([x[1] for x in rows]).astype(np.float64)
    mean=np.asarray(m["mean"],dtype=np.float64)
    scale=np.maximum(np.asarray(m["scale"],dtype=np.float64),1e-12)
    coef=np.asarray(m["coef"],dtype=np.float64)
    z=((X-mean)/scale)@coef+float(m["intercept"])
    return np.where(z>=0,1/(1+np.exp(-z)),np.exp(z)/(1+np.exp(z)))

def precision_tier(y,pr,floor):
    # Fixed .001 grid: more conservative than the original .01 search while
    # avoiding thresholds tailored to any DruMaster result.
    best=None
    for thr in np.arange(.300,.991,.001):
        s=metric(y,pr,float(thr))
        if s["predicted"]<12 or s["precision"]<floor: continue
        key=(s["recall"],s["f1"],s["precision"],-float(thr))
        if best is None or key>best[0]:best=(key,float(thr),s)
    if best is None:return {"eligible":False,"precisionFloor":floor}
    return {"eligible":True,"precisionFloor":floor,"threshold":best[1],**best[2]}

def main():
    frozen=json.loads((ROOT/"drumscribe/models/egmd-kst-reclassifier-v5.json").read_text())
    snare_model=frozen["models"]["snare"]
    rows=v3.read_csv_url(EGMD_CSV)
    train_kits,held_kits=kit_partition(rows)
    if held_kits!=frozen.get("heldOutKits"):
        raise RuntimeError(f"held-out kit mismatch: {held_kits} != {frozen.get('heldOutKits')}")
    base_model=v3.frozen_model(); processor=v3.create_adtof_processor()
    with RemoteZip(EGMD_ZIP) as z:
        names=set(z.namelist())
        vag=v3.sequence_groups(rows,"validation")
        vap=v4.scan_profiles(z,names,vag)
        vaseq,vatags,vaprof=choose_expanded(vap,{
          "generic_fill":7,"generic_beat":7,"kick_snare_overlap":9,
          "tom_heavy":9,"snare_dense":7,"kick_dense":7})
        varows=v4.rows_for_sequences(vag,vaseq,held_kits,vatags,vaprof)
        val,_,manifest=v4.collect(z,names,varows,base_model,processor,"calibration")
    vr=val["snare"]; y=np.asarray([x[2] for x in vr],np.int8)
    pr=probs_from_frozen(vr,snare_model)

    original_thr=float(snare_model["threshold"])
    check=metric(y,pr,original_thr)
    expected=snare_model.get("externalValidation",{}).get("reclassifiedLowPool",{})
    expected_triplet=(int(expected.get("tp",-1)),int(expected.get("predicted",-1)),int(expected.get("reference",-1)))
    actual_triplet=(check["tp"],check["predicted"],check["reference"])
    if actual_triplet!=expected_triplet:
        raise RuntimeError(f"frozen validation reconstruction mismatch: {actual_triplet} != {expected_triplet}")

    tiers={str(f):precision_tier(y,pr,f) for f in (.95,.975,.99)}
    report={
      "schema":1,
      "kind":"egmd-kst-v5-frozen-snare-calibration",
      "selectionData":"E-GMD official validation sequences + disjoint held-out kits only",
      "druMasterUsedForSelection":False,
      "modelKind":frozen.get("kind"),
      "hypothesis":snare_model.get("hypothesis"),
      "heldOutKits":held_kits,
      "validationSequences":vaseq,
      "validationCandidates":len(vr),
      "validationPositive":int(np.sum(y==1)),
      "original":{"threshold":original_thr,**check},
      "precisionTiers":tiers,
      "manifest":manifest,
    }
    out=EXP/"results-egmd-kst-v5-snare-calibration.json"
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="manifest"},ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
