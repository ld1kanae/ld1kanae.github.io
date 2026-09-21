"""Leave-one-song-out lightweight supervised drum classifier.

Each fold trains only on four songs and evaluates the fifth. Candidate onset
generation never consults MIDI. MIDI labels are used only for the four training
songs during fitting, and for the held-out song after prediction for scoring.
The model is deliberately small (hand-crafted features + logistic heads) so the
learned weights can later be ported to browser-side inference.
"""
from __future__ import annotations
import json, math, argparse
from pathlib import Path
from collections import Counter

import numpy as np
from scipy.optimize import minimize
from scipy.signal import find_peaks

from evaluate_v2 import (
    SR, HOP, ORDER, audio, spectrum, templates, features, midi_events,
    score, confusion, count_ratios
)

SONGS = ["arcaround","diamondvirgin","kaiju","nanairo","ray"]
PRED_GROUPS = ["kick","snare","hat","tom","crash","ride"]


def union_candidates(band):
    """Generous onset detector shared by all classes; no labels are used."""
    configs=[(band[0],.16,.040),(band[1],.16,.040),(band[3],.10,.035),(band[2],.16,.045)]
    pts=[]
    for s,thr,dist in configs:
        peaks,_=find_peaks(s,distance=max(1,int(dist*SR/HOP)),prominence=.035)
        pts.extend(int(p) for p in peaks if s[p]>=thr)
    pts=sorted(set(pts))
    if not pts: return []

    # Cluster very close band-specific peaks into one physical onset.
    clusters=[]; cur=[pts[0]]
    for p in pts[1:]:
        if (p-cur[-1])*HOP/SR <= .032:
            cur.append(p)
        else:
            clusters.append(cur); cur=[p]
    clusters.append(cur)

    out=[]
    for cl in clusters:
        p=max(cl,key=lambda q: float(band[0,q]+band[1,q]+.75*band[2,q]+.75*band[3,q]))
        out.append(p)
    return out


def estimate_beat_phase(times, strengths, bpm):
    beat=60.0/bpm if bpm else .5
    if not times: return 0.0
    best=(float("-inf"),0.0)
    sigma=max(.025,beat*.11)
    for i in range(72):
        phase=beat*i/72
        sc=0.0
        for t,w in zip(times,strengths):
            x=(t-phase)%beat
            d=min(x,beat-x)
            sc += min(2.0,math.sqrt(max(w,0))) * math.exp(-.5*(d/sigma)**2)
        if sc>best[0]: best=(sc,phase)
    return best[1]


def build_features(band, sim, candidates, bpm):
    if not candidates:
        return np.empty((0,1),dtype=np.float64), []
    times=[p*HOP/SR for p in candidates]
    strengths=[float(np.max(band[:,p])) for p in candidates]
    phase=estimate_beat_phase(times,strengths,bpm)
    beat=60.0/bpm if bpm else .5
    rows=[]

    for i,p in enumerate(candidates):
        b=np.asarray(band[:,p],dtype=np.float64)
        sm=np.asarray(sim[:,p],dtype=np.float64)
        total=float(b.sum())+1e-6
        norm=b/total

        ctx=[]
        for off in (-2,0,2):
            q=max(0,min(band.shape[1]-1,p+off))
            ctx.extend(float(x) for x in band[:,q])

        prev=(times[i]-times[i-1])/beat if i>0 else 8.0
        nex=(times[i+1]-times[i])/beat if i+1<len(times) else 8.0
        prev=min(prev,8.0); nex=min(nex,8.0)

        pos=((times[i]-phase)%beat)/beat
        phase_feats=[math.sin(2*math.pi*pos),math.cos(2*math.pi*pos)]

        ratios=[
            math.log1p(b[0]/(b[1]+1e-4)),
            math.log1p(b[1]/(b[0]+1e-4)),
            math.log1p(b[2]/(b[3]+1e-4)),
            math.log1p(b[3]/(b[2]+1e-4)),
        ]
        row=list(b)+list(np.log1p(b))+list(norm)+list(sm)+ratios+ctx+[prev,nex]+phase_feats
        rows.append(row)
    return np.asarray(rows,dtype=np.float64), times


def make_labels(times, truth, shift, tol=.08):
    truth_times={g:np.asarray([t+shift for t,gg,*_ in truth if gg==g],dtype=np.float64) for g in PRED_GROUPS}
    Y=np.zeros((len(times),len(PRED_GROUPS)),dtype=np.float64)
    for i,t in enumerate(times):
        for j,g in enumerate(PRED_GROUPS):
            a=truth_times[g]
            if len(a):
                k=np.searchsorted(a,t)
                if any(0<=q<len(a) and abs(a[q]-t)<=tol for q in (k-1,k,k+1)):
                    Y[i,j]=1.0
    return Y


def oracle_recall(times, truth, shift, tol=.08):
    out={}
    arr=np.asarray(times)
    for g in PRED_GROUPS:
        tt=[t+shift for t,gg,*_ in truth if gg==g]
        hit=0
        for t in tt:
            if len(arr) and np.min(np.abs(arr-t))<=tol: hit+=1
        out[g]={"hit":hit,"reference":len(tt),"recall":round(hit/len(tt),3) if tt else None}
    return out


def sigmoid(z):
    z=np.clip(z,-35,35)
    return 1/(1+np.exp(-z))


def fit_head(X,y,l2=.04):
    n,d=X.shape
    pos=float(y.sum()); neg=n-pos
    if pos<2:
        return np.zeros(d+1), .99
    pos_w=min(12.0,max(1.0,neg/max(pos,1.0)))
    sw=np.where(y>0.5,pos_w,1.0)

    def fun(w):
        z=X@w[:-1]+w[-1]
        # stable weighted logistic loss
        loss=np.sum(sw*(np.logaddexp(0,z)-y*z))/np.sum(sw)
        loss += .5*l2*np.dot(w[:-1],w[:-1])
        p=sigmoid(z)
        r=sw*(p-y)/np.sum(sw)
        grad=np.r_[X.T@r + l2*w[:-1], r.sum()]
        return loss,grad

    res=minimize(lambda w:fun(w),np.zeros(d+1),jac=True,method="L-BFGS-B",options={"maxiter":180})
    w=res.x
    pr=sigmoid(X@w[:-1]+w[-1])

    # Threshold is fitted only on training songs.
    best=(0.0,.5)
    positives=int(y.sum())
    for th in np.linspace(.18,.82,33):
        pred=pr>=th
        tp=int(np.sum(pred & (y>0.5))); npr=int(pred.sum())
        f1=2*tp/(npr+positives) if npr+positives else 0
        if f1>best[0]: best=(f1,float(th))
    return w,best[1]


def fit_models(X,Y):
    mu=X.mean(axis=0); sd=X.std(axis=0); sd[sd<1e-5]=1.0
    Z=(X-mu)/sd
    models={}
    for j,g in enumerate(PRED_GROUPS):
        w,th=fit_head(Z,Y[:,j])
        models[g]={"w":w,"threshold":th}
    return mu,sd,models


def predict_models(X,mu,sd,models,times):
    Z=(X-mu)/sd
    probs={}
    for g,m in models.items():
        w=m["w"]; probs[g]=sigmoid(Z@w[:-1]+w[-1])

    pred=[]
    high=("hat","crash","ride")
    for i,t in enumerate(times):
        # Low/mid drums are multi-label; simultaneous kick+snare remains possible.
        for g in ("kick","snare","tom"):
            if probs[g][i] >= models[g]["threshold"]:
                pred.append((t,g,float(probs[g][i])))

        # Hat/crash/ride are mutually exclusive per physical onset.
        scores=[(probs[g][i]-models[g]["threshold"],g,probs[g][i]) for g in high]
        margin,g,p=max(scores)
        if margin>=0:
            pred.append((t,g,float(p)))
    return sorted(pred)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args(); root=args.repo_root

    tmpl=templates(root/"DruMaster/assets/drums")
    cache={}
    for name in SONGS:
        folder=root/"DruMaster/songs"/name
        meta=json.loads((folder/"song.json").read_text())
        bpm=float(meta.get("bpm") or 0)
        shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
        x=audio(folder/"drums.mp3"); spec=spectrum(x); band,sim=features(spec,tmpl)
        cand=union_candidates(band)
        X,times=build_features(band,sim,cand,bpm)
        truth=midi_events(folder/"chart.mid")
        Y=make_labels(times,truth,shift)
        cache[name]={"X":X,"times":times,"Y":Y,"truth":truth,"shift":shift,"bpm":bpm,
                     "oracle":oracle_recall(times,truth,shift)}
        print("features",name,len(times),cache[name]["oracle"],flush=True)

    result={
        "schema":1,
        "experiment":"leave-one-song-out lightweight logistic multi-label classifier",
        "note":"For each fold, the held-out song's MIDI is not used for fitting or threshold selection.",
        "folds":{}
    }
    agg=Counter()

    for held in SONGS:
        train=[n for n in SONGS if n!=held]
        X=np.concatenate([cache[n]["X"] for n in train],axis=0)
        Y=np.concatenate([cache[n]["Y"] for n in train],axis=0)
        mu,sd,models=fit_models(X,Y)

        test=cache[held]
        pred=predict_models(test["X"],mu,sd,models,test["times"])
        sc=score(pred,test["truth"],test["shift"])
        cf=confusion(pred,test["truth"],test["shift"])
        sc["count_ratio"]=count_ratios(sc); sc["confusion"]=cf
        thresholds={g:round(float(models[g]["threshold"]),4) for g in PRED_GROUPS}
        result["folds"][held]={
            "trained_on":train,
            "candidate_oracle_recall":test["oracle"],
            "thresholds":thresholds,
            "metrics":sc,
        }

        agg.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],
                   double_supported=cf["kick_snare_double_supported"],
                   double_unsupported=cf["kick_snare_double_unsupported"])
        for g,d in sc["by_group"].items():
            agg[f"{g}_tp"]+=d["tp"];agg[f"{g}_pred"]+=d["predicted"];agg[f"{g}_ref"]+=d["reference"]
        print("heldout",held,sc["f1"],sc["count_ratio"],cf,flush=True)

    tp,n,m=agg["tp"],agg["predicted"],agg["reference"]
    summary={
        "tp":tp,"predicted":n,"reference":m,
        "precision":round(tp/n,3) if n else 0,
        "recall":round(tp/m,3) if m else 0,
        "f1":round(2*tp/(n+m),3) if n+m else 0,
        "kick_to_snare":agg["kick_to_snare"],
        "snare_to_kick":agg["snare_to_kick"],
        "kick_snare_double_supported":agg["double_supported"],
        "kick_snare_double_unsupported":agg["double_unsupported"],
        "by_group":{}
    }
    for g in ORDER:
        a,b,d=agg[f"{g}_tp"],agg[f"{g}_pred"],agg[f"{g}_ref"]
        summary["by_group"][g]={"tp":a,"predicted":b,"reference":d,
                                "count_ratio":round(b/d,3) if d else None}
    result["summary"]=summary

    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")


if __name__=="__main__":
    main()
