"""Independent high-frequency open-hi-hat rescue + offvocal diagnostic.

Research questions:
1) Can an audio-only high-frequency onset stream find open hats that never survive
   the current browser hat detector?
2) At known 42/46 hit times, is offvocal acoustically more separable than drums.mp3?
3) Does optional offvocal fusion improve rescue enough to justify later distillation?

Production constraint:
- held-out candidate generation is drums.mp3 only for production-eligible variants.
- offvocal variants are diagnostic/teacher-only and are never called production-ready.
- kick/snare/tom/etc are untouched; rescue only adds candidate Open HH (GM46).
- held-out chart is used only for scoring/labels, never candidate generation.

Variants:
A hf_student:
  low-threshold 5-18 kHz spectral-flux candidates + drums-only acoustic classifier.
B hf_student_refpos:
  same inference as A; training additionally includes missed reference-open times
  from the non-held songs, teaching the student overlapped-open acoustics.
C hf_offvocal_optional:
  same drums-only candidate times, but classifier features concatenate offvocal.
  This is an oracle/optional-input diagnostic, not production eligible.
"""
from __future__ import annotations
import importlib.util,json,math,subprocess
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import roc_auc_score

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
SR=44100; NFFT=2048; HOP=441
BASE_THRESHOLD=.575
RESCUE_THRESHOLDS=[.45,.55,.62,.68,.74,.80,.86,.91,.95,.98,1.01]
WINDOW=np.hanning(NFFT).astype(np.float32)
FREQ=np.fft.rfftfreq(NFFT,1/SR)
HF=(FREQ>=5000)&(FREQ<18000)
BANDS=[(3000,6000),(6000,9000),(9000,13000),(13000,18000),(18000,22000)]

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ov=loadmod("hf_rescue_ov",EXP/"open_hat_overlay_gmd_loo.py")
ext=ov.ext; sn=ov.sn; oh=ov.oh

def decode(song,name):
    p=ROOT/"DruMaster/songs"/song/name
    cmd=["ffmpeg","-v","error","-i",str(p),"-ac","1","-ar",str(SR),
         "-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

def near(xs,t,w=.080):
    return any(abs(x-t)<=w for x in xs)

def hf_stream(x):
    """100 fps HF spectral features without materializing a full spectrogram."""
    n=max(0,1+(len(x)-NFFT)//HOP)
    flux=np.zeros(n,np.float32); hf=np.zeros(n,np.float32)
    bands=np.zeros((n,len(BANDS)),np.float32)
    prev=np.zeros(int(HF.sum()),np.float32)
    for start in range(0,n,1200):
        ids=np.arange(start,min(n,start+1200))
        frames=np.stack([x[i*HOP:i*HOP+NFFT] for i in ids]).astype(np.float32)
        mag=np.abs(np.fft.rfft(frames*WINDOW[None,:],axis=1)).astype(np.float32)+1e-8
        hm=np.log1p(mag[:,HF])
        if start:
            first=np.maximum(hm[0]-prev,0).mean()
            flux[start]=first
        if len(ids)>1:
            flux[start+1:start+len(ids)]=np.maximum(hm[1:]-hm[:-1],0).mean(axis=1)
        prev=hm[-1].copy()
        hf[ids]=np.log1p(mag[:,HF].mean(axis=1))
        for j,(lo,hi) in enumerate(BANDS):
            mask=(FREQ>=lo)&(FREQ<hi)
            bands[ids,j]=np.log1p(mag[:,mask].mean(axis=1))
    return flux,hf,bands

def robust1(x):
    med=float(np.median(x)); q1=float(np.percentile(x,25)); q3=float(np.percentile(x,75))
    return (x-med)/max(q3-q1,1e-6)

def peak_candidates(flux,hf):
    fz=robust1(flux); hz=robust1(hf)
    # Broad by design. Precision is delegated to the rescue classifier.
    score=fz+.18*np.maximum(hz,0)
    floor=max(float(np.percentile(score,63)),.12)
    idx=[]
    for i in range(2,len(score)-2):
        if score[i]<floor: continue
        if score[i]<score[i-1] or score[i]<score[i+1]: continue
        if score[i]-min(score[i-2],score[i+2])<.05: continue
        idx.append(i)
    idx=sorted(idx,key=lambda i:score[i],reverse=True)
    minf=max(1,round(.028*SR/HOP)); keep=[]
    for i in idx:
        if all(abs(i-j)>=minf for j in keep): keep.append(i)
        if len(keep)>=4500: break
    keep.sort()
    return np.asarray([i*HOP/SR for i in keep],float),score,np.asarray(keep,int)

def candidate_extra(times,ids,flux,hf,bands):
    fz=robust1(flux); hz=robust1(hf)
    bz=np.column_stack([robust1(bands[:,j]) for j in range(bands.shape[1])])
    out=[]
    for t,i in zip(times,ids):
        fut=[]
        for sec in (.08,.18,.35):
            j=min(len(hz)-1,i+round(sec*SR/HOP))
            fut.append(float(hz[j]-hz[i]))
        pre=max(0,i-3); post=min(len(hz),i+4)
        out.append([fz[i],hz[i],*bz[i].tolist(),*fut,
                    float(np.mean(fz[pre:post])),float(np.max(fz[pre:post]))])
    return np.asarray(out,np.float32)

def norm_from_hat(hat_raw,rows):
    if not len(rows): return np.zeros((0,hat_raw.shape[1]),np.float32)
    med=np.median(hat_raw,axis=0); q1=np.percentile(hat_raw,25,axis=0); q3=np.percentile(hat_raw,75,axis=0)
    scale=np.maximum(q3-q1,1e-3)
    return np.clip((rows-med)/scale,-8,8).astype(np.float32)

def extract_at(x,times,hat_basis):
    raw=np.stack([oh.timbre_features(x,t) for t in times]) if len(times) else np.zeros((0,26),np.float32)
    return norm_from_hat(hat_basis,raw)

def prepare():
    d=sn.prepare()
    for s in SONGS:
        print("HF_PREP",s,flush=True)
        drums=decode(s,"drums.mp3"); off=decode(s,"offvocal.mp3")
        # Ensure equal local-time range only; files need not have byte-identical length.
        duration=min(len(drums),len(off))/SR
        flux,hf,bands=hf_stream(drums)
        cand,score,ids=peak_candidates(flux,hf)
        cand=cand[cand<duration-.7]; ids=ids[:len(cand)]
        # Only rescue candidates not already covered by the retained hat onset stream.
        mask=np.asarray([not near(d[s]["hats"],t,.060) for t in cand],bool)
        cand=cand[mask]; ids=ids[mask]
        extra=candidate_extra(cand,ids,flux,hf,bands)
        drumx=extract_at(drums,cand,d[s]["X"]["timbre"])
        off_raw=np.stack([oh.timbre_features(off,t) for t in cand]) if len(cand) else np.zeros((0,26),np.float32)
        # offvocal gets its own unlabeled robust basis over these candidates.
        offx=ov.robust_basis(off_raw,off_raw) if len(off_raw) else off_raw
        y=np.asarray([1 if near(d[s]["refs"][46],t,.080) else 0 for t in cand],np.int8)
        Xd=np.concatenate([drumx,extra],axis=1)
        Xf=np.concatenate([drumx,offx,extra],axis=1)

        # Missed training positives: exact reference-open times that are not near current hats.
        missed=np.asarray([t for t in d[s]["refs"][46] if not near(d[s]["hats"],t,.060) and t<duration-.7],float)
        mdr=extract_at(drums,missed,d[s]["X"]["timbre"])
        # derive stream extras at nearest frame for the same times
        mids=np.clip(np.round(missed*SR/HOP).astype(int),0,len(flux)-1) if len(missed) else np.zeros(0,int)
        mex=candidate_extra(missed,mids,flux,hf,bands) if len(missed) else np.zeros((0,12),np.float32)
        mXd=np.concatenate([mdr,mex],axis=1) if len(missed) else np.zeros((0,Xd.shape[1]),np.float32)

        d[s]["hf"]={"times":cand,"Xd":Xd,"Xf":Xf,"y":y,"missed":missed,"missedXd":mXd,
                    "counts":{"candidates":len(cand),"positive":int(y.sum()),"missedOpen":len(missed)}}

        # articulation separability diagnostic at true 42/46 reference hit times.
        rt=np.asarray(d[s]["refs"][42]+d[s]["refs"][46],float)
        ry=np.asarray([0]*len(d[s]["refs"][42])+[1]*len(d[s]["refs"][46]),np.int8)
        dr=extract_at(drums,rt,d[s]["X"]["timbre"])
        oraw=np.stack([oh.timbre_features(off,t) for t in rt])
        ox=ov.robust_basis(oraw,oraw)
        d[s]["diag"]={"drums":dr,"off":ox,"fusion":np.concatenate([dr,ox],axis=1),"y":ry}
        print("HF_COUNTS",s,json.dumps(d[s]["hf"]["counts"]),flush=True)
    return d

def fit_base(d,songs,hx,hy):
    X=np.concatenate([*(d[s]["X"]["timbre_norm"] for s in songs),hx])
    y=np.concatenate([*((d[s]["y"]==1).astype(np.int8) for s in songs),hy])
    return ExtraTreesClassifier(n_estimators=320,max_depth=13,min_samples_leaf=4,
      class_weight="balanced",random_state=560,n_jobs=-1).fit(X,y)

def p1(model,X):
    if not len(X): return np.zeros(0)
    p=model.predict_proba(X); cls=list(model.classes_)
    if 1 not in cls:return np.zeros(len(X))
    return p[:,cls.index(1)]

def fit_rescue(d,songs,variant,seed):
    XX=[];yy=[]
    for s in songs:
        h=d[s]["hf"]; X=h["Xf"] if variant=="hf_offvocal_optional" else h["Xd"]
        y=h["y"]
        pos=np.flatnonzero(y==1); neg=np.flatnonzero(y==0)
        rng=np.random.default_rng(seed+SONGS.index(s)*31)
        if len(neg)>max(250,5*len(pos)): neg=rng.choice(neg,max(250,5*len(pos)),replace=False)
        ids=np.sort(np.concatenate([pos,neg]))
        XX.append(X[ids]); yy.append(y[ids])
        if variant=="hf_student_refpos" and len(h["missedXd"]):
            XX.append(h["missedXd"]); yy.append(np.ones(len(h["missedXd"]),np.int8))
    X=np.concatenate(XX); y=np.concatenate(yy)
    return ExtraTreesClassifier(n_estimators=360,max_depth=14,min_samples_leaf=3,max_features="sqrt",
      class_weight="balanced",random_state=1200+seed,n_jobs=-1).fit(X,y),{"rows":len(y),"positive":int(y.sum())}

def score(d,s,bm,rm,variant,th):
    hp=p1(bm,d[s]["X"]["timbre_norm"])
    bo=[t for t,p in zip(d[s]["hats"],hp) if p>=BASE_THRESHOLD]
    bc=[t for t,p in zip(d[s]["hats"],hp) if p<BASE_THRESHOLD]
    h=d[s]["hf"]; X=h["Xf"] if variant=="hf_offvocal_optional" else h["Xd"]
    rp=p1(rm,X)
    rescue=[t for t,p in zip(h["times"],rp) if p>=th and not near(bo,t,.060)]
    met=oh.articulation_metrics(sorted(bo+rescue),bc,d[s]["refs"])
    return met,{"baseOpen":len(bo),"hfCandidates":len(rp),"trueOpenCandidatesDiagnostic":int(h["y"].sum()),
                "rescued":len(rescue),"maxProb":float(np.max(rp)) if len(rp) else 0.,
                "p95Prob":float(np.percentile(rp,95)) if len(rp) else 0.}

def aggregate(per):
    z=Counter()
    for m in per.values():
      for c in ("open","closed"):
        q=m[c]; z[f"{c}t"]+=q["tp"]; z[f"{c}p"]+=q["predicted"]; z[f"{c}r"]+=q["reference"]
    out={}
    for c in ("open","closed"):
      tp,p,r=z[f"{c}t"],z[f"{c}p"],z[f"{c}r"]
      out[c]={"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,
              "recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"]); return out

def choose(d,outer,hx,hy,variant):
    cache={}
    for i,val in enumerate(outer):
        tr=[s for s in outer if s!=val]
        cache[val]=(fit_base(d,tr,hx,hy),fit_rescue(d,tr,variant,30+i)[0])
    base={s:score(d,s,*cache[s],variant,1.01)[0] for s in outer}; b=aggregate(base)
    rows=[]
    for th in RESCUE_THRESHOLDS:
        per={}
        for s,(bm,rm) in cache.items(): per[s]=score(d,s,bm,rm,variant,th)[0]
        a=aggregate(per)
        eligible=(a["open"]["precision"]>=b["open"]["precision"]-.025 and
                  a["open"]["f1"]>b["open"]["f1"] and a["macroF1"]>b["macroF1"])
        utility=a["macroF1"]+.08*a["open"]["precision"]
        rows.append((eligible,utility,th,a))
    rows.sort(key=lambda r:(r[0],r[1]),reverse=True)
    best=next((r for r in rows if r[0]),None)
    return (best[2] if best else 1.01),{"base":b,"ranking":[{"threshold":r[2],"eligible":r[0],"utility":r[1],"summary":r[3]} for r in rows]}

def evaluate(d,hx,hy,variant):
    per={}; folds={}
    for oi,held in enumerate(SONGS):
        outer=[s for s in SONGS if s!=held]
        th,inner=choose(d,outer,hx,hy,variant)
        bm=fit_base(d,outer,hx,hy); rm,train=fit_rescue(d,outer,variant,100+oi)
        m,diag=score(d,held,bm,rm,variant,th)
        per[held]=m; folds[held]={"threshold":th,"metrics":m,"diag":diag,"train":train,"inner":inner}
        print("HF_FOLD",variant,held,th,json.dumps({"open":m["open"],"diag":diag}),flush=True)
    return {"variant":variant,"summary":aggregate(per),"songs":per,"folds":folds}

def diagnostic(d):
    out={}
    for mode in ("drums","off","fusion"):
        per={}
        for held in SONGS:
            tr=[s for s in SONGS if s!=held]
            X=np.concatenate([d[s]["diag"][mode] for s in tr]); y=np.concatenate([d[s]["diag"]["y"] for s in tr])
            model=ExtraTreesClassifier(n_estimators=320,max_depth=13,min_samples_leaf=4,class_weight="balanced",
              random_state=1700,n_jobs=-1).fit(X,y)
            ph=p1(model,d[held]["diag"][mode]); yy=d[held]["diag"]["y"]
            auc=float(roc_auc_score(yy,ph)) if len(np.unique(yy))>1 else None
            # Fixed .55 for an interpretable comparison only.
            pred=ph>=.55; tp=int(np.sum(pred&(yy==1))); pp=int(pred.sum()); rr=int((yy==1).sum())
            per[held]={"auc":auc,"tp":tp,"predicted":pp,"referenceOpen":rr,
              "precision":tp/pp if pp else 0.,"recall":tp/rr if rr else 0.,"f1":2*tp/(pp+rr) if pp+rr else 0.}
        aucs=[v["auc"] for v in per.values() if v["auc"] is not None]
        out[mode]={"meanAUC":float(np.mean(aucs)),"songs":per}
    return out

def main():
    d=prepare()
    hx,hy,_,_,manifest=ov.gmd_collect()
    baseline={}
    for held in SONGS:
        bm=fit_base(d,[s for s in SONGS if s!=held],hx,hy)
        hp=p1(bm,d[held]["X"]["timbre_norm"])
        bo=[t for t,p in zip(d[held]["hats"],hp) if p>=BASE_THRESHOLD]
        bc=[t for t,p in zip(d[held]["hats"],hp) if p<BASE_THRESHOLD]
        baseline[held]=oh.articulation_metrics(bo,bc,d[held]["refs"])
    base=aggregate(baseline)
    result={"schema":1,"description":"Independent high-frequency open-hat rescue and offvocal diagnostic.",
      "baseline":base,"candidateCounts":{s:d[s]["hf"]["counts"] for s in SONGS},
      "referenceArticulationDiagnostic":diagnostic(d),"variants":{}}
    for v in ("hf_student","hf_student_refpos","hf_offvocal_optional"):
        q=evaluate(d,hx,hy,v); s=q["summary"]
        q["productionEligible"]=v!="hf_offvocal_optional"
        q["passesGuard"]=(s["macroF1"]>base["macroF1"] and s["open"]["f1"]>base["open"]["f1"] and
                          s["open"]["precision"]>=base["open"]["precision"]-.025)
        result["variants"][v]=q
        print("HF_RESULT",v,json.dumps({"eligible":q["productionEligible"],"passes":q["passesGuard"],"summary":s}),flush=True)
    eligible=[q for q in result["variants"].values() if q["productionEligible"] and q["passesGuard"]]
    best=max(eligible,key=lambda q:(q["summary"]["macroF1"],q["summary"]["open"]["f1"])) if eligible else None
    result["retained"]=best["variant"] if best else "none"
    result["retainedSummary"]=best["summary"] if best else base
    (EXP/"results-open-hat-hf-offvocal-loo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("HF_RETAINED",result["retained"],json.dumps(result["retainedSummary"]),flush=True)

if __name__=="__main__": main()
