"""Self-adaptive open-hi-hat overlay rescue.

Previous fixed-threshold overlay models correctly rank some diamondvirgin
structural anchors as open-like, but a global nested-LOO threshold turns rescue
off because the other songs contain little/no analogous overlay-open material.

This cycle tests three prediction-time-only policies. They use only:
- overlay probabilities from a model trained without the held-out song,
- candidate times / audio-estimated BPM from the held-out song,
- within-song probability distribution and repetition.

No held-out chart is read until final scoring. These policies are DEVELOPMENT
candidates: their constants were proposed after observing the preceding five-song
development diagnostics, so a future song is required for independent validation.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
FAM="C_metal_snare_kick"
BASE_THRESHOLD=.575

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ov=loadmod("openhat_selfadapt_base",EXP/"open_hat_overlay_gmd_loo.py")
oh=ov.oh

def aggregate(per):
    z=Counter()
    for m in per.values():
        for c in ("open","closed"):
            q=m[c];z[f"{c}t"]+=q["tp"];z[f"{c}p"]+=q["predicted"];z[f"{c}r"]+=q["reference"]
    out={}
    for c in ("open","closed"):
        tp,p,r=z[f"{c}t"],z[f"{c}p"],z[f"{c}r"]
        out[c]={"tp":tp,"predicted":p,"reference":r,
            "precision":tp/p if p else 0.,"recall":tp/r if r else 0.,
            "f1":2*tp/(p+r) if p+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"])
    return out

def repeat_support(times,p,bpm):
    if not len(times):return np.zeros(0)
    beat=60/max(float(bpm),1e-6)
    offsets=[.5*beat,beat,1.5*beat,2*beat,4*beat]
    out=np.zeros(len(times),dtype=float)
    for i,t in enumerate(times):
        vals=[]
        for off in offsets:
            for sign in (-1,1):
                target=t+sign*off
                ids=np.flatnonzero(np.abs(times-target)<=.065)
                if len(ids):vals.append(float(np.max(p[ids])))
        out[i]=float(np.mean(sorted(vals,reverse=True)[:4])) if vals else 0.
    return out

def select(policy,times,p,bpm):
    if not len(p):return np.zeros(0,dtype=bool),{}
    mx=float(np.max(p));q95=float(np.percentile(p,95));q98=float(np.percentile(p,98));q99=float(np.percentile(p,99))
    rep=repeat_support(times,p,bpm)
    if policy=="peak_gate":
        active=mx>=.80
        mask=(p>=.75) if active else np.zeros(len(p),bool)
        info={"active":bool(active),"threshold":.75,"max":mx,"q95":q95,"q99":q99}
    elif policy=="quantile_gate":
        active=mx>=.80 and q99>=.68
        th=max(.68,q95)
        mask=(p>=th) if active else np.zeros(len(p),bool)
        info={"active":bool(active),"threshold":th,"max":mx,"q95":q95,"q99":q99}
    else:
        # High raw evidence plus recurring support. The gate prevents this rule
        # from activating on ordinary songs whose entire overlay distribution is low.
        score=.72*p+.28*rep
        smx=float(np.max(score));sth=max(.68,float(np.percentile(score,96)))
        active=mx>=.78 and smx>=.72
        mask=((score>=sth)&(p>=.58)&(rep>=.35)) if active else np.zeros(len(p),bool)
        info={"active":bool(active),"threshold":sth,"max":mx,"scoreMax":smx,
              "q95":q95,"q99":q99,"repeatMax":float(np.max(rep))}
    return mask,info

def fold_predict(d,held,hx,hy,gx,gy,policy,seed):
    train=[s for s in SONGS if s!=held]
    bm=ov.train_base(d,train,hx,hy)
    om,tinfo=ov.train_overlay(d,train,gx,gy,FAM,seed)
    hp=ov.probs(bm,d[held]["X"]["timbre_norm"])
    bo=[t for t,p in zip(d[held]["hats"],hp) if p>=BASE_THRESHOLD]
    bc=[t for t,p in zip(d[held]["hats"],hp) if p<BASE_THRESHOLD]

    oo=d[held]["overlay"];times=np.asarray([a[0] for a in oo["anchors"]],dtype=float)
    pp=ov.probs(om,oo["X"])
    bpm=float(d[held]["side"].get("bpm") or 0)
    base_policy="repeat_gate" if policy=="repeat_gate_2hands" else policy
    mask,ainfo=select(base_policy,times,pp,bpm)
    physicalSkipped=0
    if policy=="repeat_gate_2hands":
        rows=d[held]["rows"]
        safe=[]
        for t,yes in zip(times,mask):
            if not yes:
                safe.append(False);continue
            # Kick/pedal are feet. Existing hand events are snare/tom/hat/metal.
            hands=sum(1 for u,g,pitch in rows
                      if g in ("snare","tom","hat","crash","ride") and abs(u-float(t))<=.035)
            ok=hands<2
            if not ok:physicalSkipped+=1
            safe.append(ok)
        mask=np.asarray(safe,dtype=bool)
    rescued=[float(t) for t,yes in zip(times,mask) if yes and not ov.near(bo,float(t),.060)]
    met=oh.articulation_metrics(sorted(bo+rescued),bc,d[held]["refs"])

    # Chart-derived diagnostics below are reporting only; never feed selection.
    pred_resc=[float(t) for t,yes in zip(times,mask) if yes]
    true_open=d[held]["refs"][46]
    rescue_tp=sum(1 for t in pred_resc if ov.near(true_open,t,.080))
    return met,{"baseOpen":len(bo),"candidates":len(times),"rescued":len(rescued),
      "rescuePredBeforeDedup":len(pred_resc),"rescueTpDiagnostic":rescue_tp,
      "trueOverlayDiagnostic":int(oo["y"].sum()),"physicalSkipped":physicalSkipped,
      "adapt":ainfo,"train":tinfo}

def main():
    d=ov.local_prepare();hx,hy,gx,gy,manifest=ov.gmd_collect()
    baseline={}
    for i,held in enumerate(SONGS):
        train=[s for s in SONGS if s!=held]
        bm=ov.train_base(d,train,hx,hy)
        hp=ov.probs(bm,d[held]["X"]["timbre_norm"])
        bo=[t for t,p in zip(d[held]["hats"],hp) if p>=BASE_THRESHOLD]
        bc=[t for t,p in zip(d[held]["hats"],hp) if p<BASE_THRESHOLD]
        baseline[held]=oh.articulation_metrics(bo,bc,d[held]["refs"])
    base=aggregate(baseline)

    out={"schema":1,"description":"Held-song-label-free self-adaptive overlay policies; development-selected constants.",
      "baseline":base,"policies":{}}
    for pi,policy in enumerate(("peak_gate","quantile_gate","repeat_gate","repeat_gate_2hands")):
        per={};folds={}
        for i,held in enumerate(SONGS):
            m,diag=fold_predict(d,held,hx,hy,gx,gy,policy,300+pi*10+i)
            per[held]=m;folds[held]={"metrics":m,"diag":diag}
            print("FOLD",policy,held,json.dumps({"open":m["open"],"diag":diag}),flush=True)
        s=aggregate(per)
        eligible=(s["macroF1"]>base["macroF1"] and s["open"]["f1"]>base["open"]["f1"] and
                  s["open"]["precision"]>=base["open"]["precision"]-.025)
        out["policies"][policy]={"summary":s,"songs":per,"folds":folds,"eligible":eligible}
        print("RESULT",policy,json.dumps({"eligible":eligible,"summary":s}),flush=True)
    eligible=[q|{"name":k} for k,q in out["policies"].items() if q["eligible"]]
    best=max(eligible,key=lambda q:(q["summary"]["macroF1"],q["summary"]["open"]["f1"])) if eligible else None
    out["retained"]=best["name"] if best else "none"
    out["retainedSummary"]=best["summary"] if best else base
    out["warning"]="Policy constants were chosen after prior development diagnostics; future-song post-selection validation is required before production adoption."
    (EXP/"results-open-hat-overlay-selfadapt-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("RETAINED",out["retained"],json.dumps(out["retainedSummary"]),flush=True)

if __name__=="__main__":main()
