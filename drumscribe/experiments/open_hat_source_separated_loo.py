"""Source-separated Open/Closed HH LOO evaluation.

Learning sources are deliberately NOT pooled:
1) songs_tail: trained only on DruMaster training songs.
2) gmd_genre_slot: fixed symbolic prior read only from models/gmd-kst/.
3) sync_teacher: fixed acoustic teacher trained only from the uploaded synchronized
   Nanairo WAV/MIDI pair.  It is disabled when Nanairo itself is held out.
4) score_fusion: optional meta-model trained only on out-of-fold source SCORES,
   never on concatenated source training rows.

Pedal HH reference 44 is folded into Closed for this experiment.
"""
from __future__ import annotations
import importlib.util, json, math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"; MODELS=ROOT/"drumscribe/models"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
THRESH=.5

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
oh=loadmod("srcsep_oh",EXP/"open_hat_loo.py")

def collapse_times(xs,tol=.001):
    out=[]
    for t in sorted(float(x) for x in xs):
        if not out or t-out[-1]>tol:out.append(t)
        else:out[-1]=(out[-1]+t)/2
    return out

def refs(song):
    tt=oh.truth(song)
    op=collapse_times([t for t,g,p in tt if p==46])
    cl=collapse_times([t for t,g,p in tt if p in (42,44)])
    return {"open":op,"closed":cl}

def candidates(rows):
    return collapse_times([t for t,g,p in rows if g in ("hat","pedal_hat")])

def nearest_label(t,rr,w=.080):
    z=[]
    for u in rr["open"]:
        if abs(t-u)<=w:z.append((abs(t-u),1))
    for u in rr["closed"]:
        if abs(t-u)<=w:z.append((abs(t-u),0))
    return min(z)[1] if z else -1

def robust(X):
    if not len(X):return X
    med=np.median(X,axis=0);q1=np.percentile(X,25,axis=0);q3=np.percentile(X,75,axis=0)
    return np.clip((X-med)/np.maximum(q3-q1,1e-3),-8,8).astype(np.float32)

def rms(x,t,a,b):
    i=max(0,int((t+a)*oh.SR));j=min(len(x),int((t+b)*oh.SR))
    if j<=i:return 1e-8
    z=x[i:j];return float(np.sqrt(np.mean(z*z)+1e-12))

def interrupt(x,t):
    floor=rms(x,t,-.100,-.025)
    cs=np.arange(.07,.651,.02)
    seq=np.asarray([rms(x,t,c-.01,c+.01) for c in cs],float)
    seq=np.maximum(seq-floor,1e-10);seq/=max(seq[0],1e-10)
    d=np.diff(np.log(seq))
    return np.asarray([np.min(d),np.percentile(d,10),np.mean(d),np.std(d),
                       np.mean(seq>.2),np.mean(seq>.1)],np.float32)

def feature30(x,hf,times):
    rows=[]
    for i,t in enumerate(times):
        broad=oh.decay_features(x,t)
        hdec=oh.decay_features(hf,t)
        intr=interrupt(hf,t)
        prev=t-times[i-1] if i else 9.
        nxt=times[i+1]-t if i+1<len(times) else 9.
        rows.append(np.concatenate([broad,hdec,intr,np.asarray([min(prev,2.),min(nxt,2.)],np.float32)]))
    return np.stack(rows) if rows else np.zeros((0,30),np.float32)

def sig(x):
    x=np.clip(x,-30,30);return 1/(1+np.exp(-x))

def sync_prob(model,X):
    mean=np.asarray(model["scaler"]["mean"],float);scale=np.asarray(model["scaler"]["scale"],float)
    coef=np.asarray(model["logistic"]["coef"],float);bias=float(model["logistic"]["intercept"])
    Z=(np.asarray(X,float)-mean)/np.maximum(scale,1e-12)
    return sig(Z@coef+bias)

def slot_of(t,side):
    bpm=float(side.get("bpm") or 120.);beat=60/max(bpm,1e-6)
    phase=float(side.get("barPhaseSec") or side.get("beatPhaseSec") or 0.)
    barpos=((t-phase)%(4*beat))/beat
    return int(round(barpos*4))%16

def genre_weights(gmd,times,side):
    obs=np.zeros(16,float)
    for t in times:obs[slot_of(t,side)]+=1
    obs/=np.linalg.norm(obs)+1e-12
    rows=[]
    for name,g in gmd["genres"].items():
        ref=np.asarray(g["slotOpen"],float)+np.asarray(g["slotClosed"],float)
        ref/=np.linalg.norm(ref)+1e-12
        sim=float(np.dot(obs,ref))
        rows.append((name,sim))
    sims=np.asarray([v for _,v in rows],float)
    w=np.exp(8*(sims-np.max(sims)));w/=w.sum()+1e-12
    return {name:float(z) for (name,_),z in zip(rows,w)}

def gmd_scores(gmd,times,side,weights):
    base=float(gmd["global"]["openRate"])
    eps=1e-4
    base_log=math.log((base+eps)/(1-base+eps))
    out=[]
    for t in times:
        sl=slot_of(t,side);p=0.
        for name,w in weights.items():
            v=gmd["genres"][name]["pOpenGivenHatSlot"][sl]
            if v is None:v=base
            p+=w*float(v)
        log=math.log((p+eps)/(1-p+eps))
        out.append(float(sig(log-base_log)))
    return np.asarray(out,float)

def fit_songs(data,train):
    XX=[];yy=[]
    for s in train:
        ids=np.flatnonzero(data[s]["y"]>=0)
        XX.append(data[s]["Xnorm"][ids]);yy.append(data[s]["y"][ids])
    X=np.concatenate(XX);y=np.concatenate(yy)
    m=ExtraTreesClassifier(n_estimators=420,max_depth=13,min_samples_leaf=4,
        max_features="sqrt",class_weight="balanced",random_state=2609,n_jobs=-1)
    m.fit(X,y);return m

def p1(m,X):
    p=m.predict_proba(X);cls=list(m.classes_)
    return p[:,cls.index(1)] if 1 in cls else np.zeros(len(X))

def oof_source_scores(data,gmd,sync,outer):
    rows=[];labels=[]
    for val in outer:
        tr=[s for s in outer if s!=val]
        sm=fit_songs(data,tr)
        sp=p1(sm,data[val]["Xnorm"])
        gp=data[val]["gmd"]
        sy=data[val]["sync"].copy()
        avail=np.ones(len(sy),float)
        if val=="nanairo":
            sy[:]=.5;avail[:]=0.
        ids=np.flatnonzero(data[val]["y"]>=0)
        rows.append(np.column_stack([sp[ids],gp[ids],sy[ids],avail[ids]]))
        labels.append(data[val]["y"][ids])
    return np.concatenate(rows),np.concatenate(labels)

def fit_fusion(data,gmd,sync,outer):
    X,y=oof_source_scores(data,gmd,sync,outer)
    m=LogisticRegression(C=.6,class_weight="balanced",max_iter=1500,random_state=2610)
    m.fit(X,y);return m,{"rows":len(y),"positive":int(y.sum())}

def greedy(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        q=[(abs(t-u),i) for i,u in enumerate(ref) if i not in used and abs(t-u)<=w]
        if q:
            _,i=min(q);used.add(i);tp+=1
    return tp

def articulation(times,prob,rr,th=.5):
    op=[t for t,p in zip(times,prob) if p>=th]
    cl=[t for t,p in zip(times,prob) if p<th]
    out={}
    for name,pred,ref in (("open",op,rr["open"]),("closed",cl,rr["closed"])):
        tp=greedy(pred,ref);n=len(pred);r=len(ref)
        out[name]={"tp":tp,"predicted":n,"reference":r,
          "precision":tp/n if n else 0.,"recall":tp/r if r else 0.,"f1":2*tp/(n+r) if n+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"]);return out

def aggregate(per,songs=None):
    songs=songs or list(per)
    z=Counter()
    for s in songs:
        for c in ("open","closed"):
            q=per[s][c];z[c+"t"]+=q["tp"];z[c+"p"]+=q["predicted"];z[c+"r"]+=q["reference"]
    out={}
    for c in ("open","closed"):
        tp,p,r=z[c+"t"],z[c+"p"],z[c+"r"]
        out[c]={"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,
          "recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"]);return out

def prepare(gmd,sync):
    sos=butter(4,[5000,18000],btype="bandpass",fs=oh.SR,output="sos")
    out={}
    for s in SONGS:
        print("SOURCE_PREP",s,flush=True)
        x=oh.audio(s);hf=sosfiltfilt(sos,x).astype(np.float32)
        rows,side=oh.browser(s);tt=candidates(rows);rr=refs(s)
        X=feature30(x,hf,tt);Xn=robust(X)
        y=np.asarray([nearest_label(t,rr) for t in tt],np.int8)
        gw=genre_weights(gmd,tt,side);gp=gmd_scores(gmd,tt,side,gw);sp=sync_prob(sync,X)
        out[s]={"times":tt,"refs":rr,"X":X,"Xnorm":Xn,"y":y,"side":side,
                "gmd":gp,"sync":sp,"genreWeights":gw,
                "counts":{"candidates":len(tt),"matched":int(np.sum(y>=0)),"matchedOpen":int(np.sum(y==1)),
                          "matchedClosed":int(np.sum(y==0)),"refOpen":len(rr["open"]),"refClosed":len(rr["closed"])}}
        print("SOURCE_COUNTS",s,json.dumps(out[s]["counts"]),flush=True)
    return out

def evaluate(data,gmd,sync):
    variants={k:{} for k in ("songs_tail","gmd_genre_slot","sync_teacher","score_fusion")}
    folds={k:{} for k in variants}
    for held in SONGS:
        outer=[s for s in SONGS if s!=held]
        sm=fit_songs(data,outer);songs_p=p1(sm,data[held]["Xnorm"])
        gmd_p=data[held]["gmd"]
        sync_p=data[held]["sync"].copy()
        sync_available=held!="nanairo"
        if not sync_available:sync_p[:]=.5
        fm,finfo=fit_fusion(data,gmd,sync,outer)
        avail=np.ones(len(sync_p),float) if sync_available else np.zeros(len(sync_p),float)
        fusion_p=p1(fm,np.column_stack([songs_p,gmd_p,sync_p,avail]))
        pred={"songs_tail":songs_p,"gmd_genre_slot":gmd_p,"sync_teacher":sync_p,"score_fusion":fusion_p}
        for name,p in pred.items():
            met=articulation(data[held]["times"],p,data[held]["refs"],THRESH)
            variants[name][held]=met
            folds[name][held]={"metrics":met,"syncAvailable":sync_available,
              "openPredictions":int(np.sum(p>=THRESH)),"meanScore":float(np.mean(p)) if len(p) else 0.,
              "genreWeights":sorted(data[held]["genreWeights"].items(),key=lambda q:q[1],reverse=True)[:5]}
            if name=="score_fusion":folds[name][held]["train"]=finfo
    out={}
    for name,per in variants.items():
        q={"summary":aggregate(per),"songs":per,"folds":folds[name]}
        if name=="sync_teacher":
            q["strictNonNanairo"]=aggregate(per,[s for s in SONGS if s!="nanairo"])
            q["nanairoPolicy"]="teacher disabled (neutral 0.5) to prevent same-song leakage"
        out[name]=q
        print("SOURCE_RESULT",name,json.dumps(q["summary"]),flush=True)
    return out

def main():
    gmd=json.loads((MODELS/"gmd-kst/hihat-style-patterns-v1.json").read_text())
    sync=json.loads((MODELS/"open-hat-sync-nanairo-tail-v1.json").read_text())
    if not gmd["sourceSeparation"]["gmdOnly"]:raise RuntimeError("GMD source separation violated")
    if "trained only from this synchronized pair" not in sync["source"]["sourceSeparation"]:
        raise RuntimeError("sync teacher provenance invalid")
    d=prepare(gmd,sync)
    variants=evaluate(d,gmd,sync)
    base_per={s:articulation(d[s]["times"],np.zeros(len(d[s]["times"])),d[s]["refs"]) for s in SONGS}
    result={"schema":1,
      "description":"Source-separated current-candidate Open/Closed HH LOO. Pedal 44 folded into Closed.",
      "sourcePolicy":{
        "trainingRowsPooled":False,
        "gmd":"symbolic genre prior only",
        "songs":"DruMaster audio/chart LOO only",
        "syncNanairo":"fixed external acoustic teacher; disabled on Nanairo held-out fold",
        "fusion":"out-of-fold source scores only"
      },
      "referencePolicy":{"open":[46],"closed":[42,44]},
      "counts":{s:d[s]["counts"] for s in SONGS},
      "allClosedBaseline":aggregate(base_per),
      "variants":variants}
    eligible={k:v for k,v in variants.items() if k!="sync_teacher"}
    best=max(eligible,key=lambda k:(eligible[k]["summary"]["macroF1"],eligible[k]["summary"]["open"]["f1"]))
    result["bestResearchVariant"]=best;result["bestResearchSummary"]=eligible[best]["summary"]
    (EXP/"results-open-hat-source-separated-loo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("SOURCE_BEST",best,json.dumps(result["bestResearchSummary"]),flush=True)

if __name__=="__main__":main()
