"""Synthetic in-domain open-hi-hat overlay rescue.

The current browser detector often misses an open hi-hat when it is simultaneous
with snare/kick/metal. We do not steal or relabel those notes. This experiment
adds a GM46 only when a separate overlay detector is confident.

Training positives are made in-domain: take NON-open structural event anchors
from the training DruMaster songs and acoustically mix the project's 46.wav
sample into the original drums.mp3 at the anchor. This teaches the model the
delta caused by an open-hat tail while preserving each song's real mix/noise.
Closed 42.wav synthetic overlays are optional hard negatives.

Strictness:
- Outer held song is excluded from every supervised and synthetic training row.
- Nested inner LOO selects a rescue threshold.
- Held-out chart is used only for final scoring.
- Existing hat onset/articulation model remains the retained GMD128 p=.575 model.
- Rescue ADDS open-hat notes; kick/snare/ride/crash notes are never removed.
"""
from __future__ import annotations
import importlib.util,json,math,random
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
BASE_THRESHOLD=.575
THRESHOLDS=[.45,.55,.65,.72,.78,.84,.90,.94,1.01]
MAX_SYNTH_NEG_PER_SONG=220
RATIOS=(.45,.80,1.25)

VARIANTS={
  "decay_synth":{"feature":"decay","closedHard":True,"gmd":False},
  "timbre_synth":{"feature":"timbre","closedHard":True,"gmd":False},
  "timbre_synth_gmd":{"feature":"timbre","closedHard":True,"gmd":True},
}

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ov=loadmod("openhat_overlay_base",EXP/"open_hat_overlay_gmd_loo.py")
ext=ov.ext;sn=ov.sn;oh=ov.oh

def robust_params(hat_raw):
    med=np.median(hat_raw,axis=0);q1=np.percentile(hat_raw,25,axis=0);q3=np.percentile(hat_raw,75,axis=0)
    return med,np.maximum(q3-q1,1e-3)

def norm_rows(X,med,scale):
    return np.clip((X-med)/scale,-8,8).astype(np.float32)

OPEN_SAMPLE=oh.onset_align(oh.read_wav(ROOT/"DruMaster/assets/drums/46.wav")).astype(np.float32)
CLOSED_SAMPLE=oh.onset_align(oh.read_wav(ROOT/"DruMaster/assets/drums/42.wav")).astype(np.float32)

def local_mix_scale(x,t,sample,ratio):
    i=max(0,int(t*oh.SR));j=min(len(x),i+int(.040*oh.SR))
    local=float(np.sqrt(np.mean(x[i:j]*x[i:j])+1e-12)) if j>i else 1e-4
    sj=min(len(sample),int(.040*oh.SR))
    sr=float(np.sqrt(np.mean(sample[:sj]*sample[:sj])+1e-12))
    return ratio*local/(sr+1e-12)

def mixed_window(x,t,a,b,sample,gain):
    i=max(0,int((t+a)*oh.SR));j=min(len(x),int((t+b)*oh.SR))
    if j<=i:return np.zeros(0,np.float32)
    z=x[i:j].astype(np.float64,copy=True)
    # sample starts exactly at t
    absolute=np.arange(i,j)-int(t*oh.SR)
    mask=(absolute>=0)&(absolute<len(sample))
    if np.any(mask):z[mask]+=gain*sample[absolute[mask]]
    return z

def mixed_rms(x,t,a,b,sample,gain):
    z=mixed_window(x,t,a,b,sample,gain)
    return float(np.sqrt(np.mean(z*z)+1e-12)) if len(z) else 1e-8

def mixed_mag(x,t,sample,gain,offset=.015):
    c=int(round((t+offset)*oh.SR));lo=c-oh.NFFT//2;hi=lo+oh.NFFT
    z=np.zeros(oh.NFFT,np.float64);a=max(0,lo);b=min(len(x),hi)
    if b>a:z[a-lo:b-lo]=x[a:b]
    # sample absolute start
    start=int(t*oh.SR)
    aa=max(lo,start);bb=min(hi,start+len(sample))
    if bb>aa:
        z[aa-lo:bb-lo]+=gain*sample[aa-start:bb-start]
    return np.abs(np.fft.rfft(z*oh.WINDOW))+1e-9

def mixed_timbre(x,t,sample,gain):
    floor=mixed_rms(x,t,-.100,-.025,sample,gain)
    env=[]
    for a,b in oh.DECAY_WINDOWS:
        r=mixed_rms(x,t,a,b,sample,gain)
        env.append(math.sqrt(max(r*r-floor*floor,1e-12)))
    e0=max(env[0],1e-8)
    logrel=[math.log(max(e,1e-8)/e0) for e in env]
    centers=np.array([(a+b)/2 for a,b in oh.DECAY_WINDOWS],dtype=float)
    yy=np.asarray(logrel);slope=float(np.polyfit(centers,yy,1)[0])
    weights=np.maximum(np.asarray(env)-floor,0)
    tcent=float(np.sum(centers*weights)/(np.sum(weights)+1e-12))
    tail=float((env[3]+env[4]+env[5])/(3*e0+1e-12))
    late=float(env[-1]/(e0+1e-12));pre=float(floor/e0)
    decay=np.asarray(logrel+[slope,tcent,tail,late,pre],np.float32)

    m=mixed_mag(x,t,sample,gain);tot=float(m.sum())+1e-12
    band=[]
    for lo,hi in oh.BANDS:
        q=float(m[(oh.FREQ>=lo)&(oh.FREQ<hi)].sum())/tot
        band.append(math.log1p(100*q))
    centroid=float(np.sum(oh.FREQ*m)/tot)/22050
    flat=float(np.exp(np.mean(np.log(m)))/(np.mean(m)+1e-12))
    cs=np.cumsum(m);roll=float(oh.FREQ[min(len(oh.FREQ)-1,int(np.searchsorted(cs,.85*cs[-1])))])/22050
    mn=m/(np.linalg.norm(m)+1e-12)
    sim42=oh.cosine(mn,oh.ASSET42);sim46=oh.cosine(mn,oh.ASSET46)
    onset_hf=float(m[oh.FREQ>=5000].sum())+1e-12
    persist=[]
    for off in (.080,.180,.350):
        mm=mixed_mag(x,t,sample,gain,off)
        persist.append(math.log1p(float(mm[oh.FREQ>=5000].sum())/onset_hf))
    return np.concatenate([decay,np.asarray(band+[centroid,flat,roll,sim42,sim46,sim46-sim42]+persist,np.float32)])

def feature_select(X,variant):
    # acoustic 26 + 3 structural bits
    if VARIANTS[variant]["feature"]=="decay":
        return np.concatenate([X[:,:11],X[:,26:29]],axis=1)
    return X

def prepare():
    d=ov.local_prepare()
    # Cache original audio and normalization basis; generate synthetic rows only
    # from chart-confirmed non-open anchors.
    for song in SONGS:
        x=oh.audio(song);d[song]["audio"]=x
        med,scale=robust_params(d[song]["X"]["timbre"])
        d[song]["overlayNorm"]=(med,scale)
        oo=d[song]["overlay"];neg=np.flatnonzero(oo["y"]==0)
        rng=np.random.default_rng(4600+SONGS.index(song))
        if len(neg)>MAX_SYNTH_NEG_PER_SONG:neg=rng.choice(neg,MAX_SYNTH_NEG_PER_SONG,replace=False)
        rows_open=[];rows_closed=[]
        for j in neg:
            a=oo["anchors"][int(j)];t=a[0];bits=np.asarray(a[1:],np.float32)
            ratio=RATIOS[int(j)%len(RATIOS)]
            go=local_mix_scale(x,t,OPEN_SAMPLE,ratio)
            gc=local_mix_scale(x,t,CLOSED_SAMPLE,ratio)
            ro=mixed_timbre(x,t,OPEN_SAMPLE,go)
            rc=mixed_timbre(x,t,CLOSED_SAMPLE,gc)
            rows_open.append(np.concatenate([norm_rows(ro[None,:],med,scale)[0],bits]))
            rows_closed.append(np.concatenate([norm_rows(rc[None,:],med,scale)[0],bits]))
        d[song]["synthOpen"]=np.asarray(rows_open,np.float32) if rows_open else np.zeros((0,29),np.float32)
        d[song]["synthClosed"]=np.asarray(rows_closed,np.float32) if rows_closed else np.zeros((0,29),np.float32)
        print("SYNTH",song,"negAnchors",len(neg),"openRows",len(rows_open),flush=True)
    return d

def train_base(d,songs,hatX,hatY):
    X=np.concatenate([*(d[s]["X"]["timbre_norm"] for s in songs),hatX])
    y=np.concatenate([*((d[s]["y"]==1).astype(np.int8) for s in songs),hatY])
    return ExtraTreesClassifier(n_estimators=320,max_depth=13,min_samples_leaf=4,
      class_weight="balanced",random_state=560,n_jobs=-1).fit(X,y)

def gmd_overlay():
    # Reuse exact GMD feature collection from the previous experiment.
    hx,hy,gX,gY,manifest=ov.gmd_collect()
    return hx,hy,gX,gY,manifest

def fit_overlay(d,songs,gX,gY,variant,seed):
    cfg=VARIANTS[variant];XX=[];yy=[]
    # Real in-domain examples from training songs.
    for s in songs:
        X=d[s]["overlay"]["X"];y=d[s]["overlay"]["y"]
        XX.append(feature_select(X,variant));yy.append(y)
        # Synthetic positives, plus closed hard negatives.
        XX.append(feature_select(d[s]["synthOpen"],variant));yy.append(np.ones(len(d[s]["synthOpen"]),np.int8))
        if cfg["closedHard"]:
            XX.append(feature_select(d[s]["synthClosed"],variant));yy.append(np.zeros(len(d[s]["synthClosed"]),np.int8))
    if cfg["gmd"]:
        # external overlay rows already have identical 29-d feature layout
        XX.append(feature_select(gX,variant));yy.append(gY)
    X=np.concatenate(XX);y=np.concatenate(yy)
    model=ExtraTreesClassifier(n_estimators=360,max_depth=13,min_samples_leaf=3,
      max_features="sqrt",class_weight="balanced",random_state=900+seed,n_jobs=-1).fit(X,y)
    return model,{"rows":len(y),"positive":int(y.sum()),"negative":int((y==0).sum()),
      "realSongs":list(songs),"usedGmd":cfg["gmd"]}

def prob(model,X):
    if not len(X):return np.zeros(0)
    classes=list(model.classes_)
    if 1 not in classes:return np.zeros(len(X))
    return model.predict_proba(X)[:,classes.index(1)]

def score(d,s,bm,om,variant,th):
    hp=prob(bm,d[s]["X"]["timbre_norm"])
    bo=[t for t,p in zip(d[s]["hats"],hp) if p>=BASE_THRESHOLD]
    bc=[t for t,p in zip(d[s]["hats"],hp) if p<BASE_THRESHOLD]
    oo=d[s]["overlay"];pp=prob(om,feature_select(oo["X"],variant))
    rescued=[a[0] for a,p in zip(oo["anchors"],pp) if p>=th and not ov.near(bo,a[0],.060)]
    met=oh.articulation_metrics(sorted(bo+rescued),bc,d[s]["refs"])
    return met,{"baseOpen":len(bo),"overlayCandidates":len(pp),"rescued":len(rescued),
      "candidateTrueOpenDiagnostic":int(oo["y"].sum()),"maxProb":float(np.max(pp)) if len(pp) else 0.,
      "p95Prob":float(np.percentile(pp,95)) if len(pp) else 0.}

def aggregate(per):
    z=Counter()
    for m in per.values():
      for c in ("open","closed"):
        q=m[c];z[f"{c}t"]+=q["tp"];z[f"{c}p"]+=q["predicted"];z[f"{c}r"]+=q["reference"]
    out={}
    for c in ("open","closed"):
      tp,p,r=z[f"{c}t"],z[f"{c}p"],z[f"{c}r"]
      out[c]={"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,
        "recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"]);return out

def choose_inner(d,outer,hatX,hatY,gX,gY,variant):
    cache={}
    for i,val in enumerate(outer):
        tr=[s for s in outer if s!=val]
        bm=train_base(d,tr,hatX,hatY);om,info=fit_overlay(d,tr,gX,gY,variant,10+i)
        cache[val]=(bm,om,info)
    base={s:score(d,s,*cache[s][:2],variant,1.01)[0] for s in outer}
    b=aggregate(base);rows=[]
    for th in THRESHOLDS:
        per={};diag={}
        for s,(bm,om,_) in cache.items():per[s],diag[s]=score(d,s,bm,om,variant,th)
        a=aggregate(per)
        # Rescue is additive, so guard open precision aggressively.
        eligible=(a["open"]["precision"]>=b["open"]["precision"]-.025 and
                  a["open"]["f1"]>b["open"]["f1"] and a["macroF1"]>b["macroF1"])
        utility=a["macroF1"]+.08*a["open"]["precision"]
        rows.append((eligible,utility,th,a,diag))
    rows.sort(key=lambda r:(r[0],r[1]),reverse=True)
    best=next((r for r in rows if r[0]),None)
    return (best[2] if best else 1.01),{"base":b,
      "ranking":[{"threshold":r[2],"eligible":r[0],"utility":r[1],"summary":r[3]} for r in rows]}

def evaluate(d,hatX,hatY,gX,gY,variant):
    per={};folds={}
    for oi,held in enumerate(SONGS):
        outer=[s for s in SONGS if s!=held]
        th,inner=choose_inner(d,outer,hatX,hatY,gX,gY,variant)
        bm=train_base(d,outer,hatX,hatY);om,traininfo=fit_overlay(d,outer,gX,gY,variant,100+oi)
        met,diag=score(d,held,bm,om,variant,th)
        per[held]=met;folds[held]={"threshold":th,"metrics":met,"diag":diag,"train":traininfo,"inner":inner}
        print("FOLD",variant,held,th,json.dumps({"open":met["open"],"diag":diag}),flush=True)
    return {"variant":variant,"summary":aggregate(per),"songs":per,"folds":folds}

def main():
    d=prepare();hatX,hatY,gX,gY,manifest=gmd_overlay()
    # Exact retained GMD128 baseline.
    baseline={}
    for held in SONGS:
        bm=train_base(d,[s for s in SONGS if s!=held],hatX,hatY)
        # No overlay needed for baseline.
        hp=prob(bm,d[held]["X"]["timbre_norm"])
        bo=[t for t,p in zip(d[held]["hats"],hp) if p>=BASE_THRESHOLD]
        bc=[t for t,p in zip(d[held]["hats"],hp) if p<BASE_THRESHOLD]
        baseline[held]=oh.articulation_metrics(bo,bc,d[held]["refs"])
    base=aggregate(baseline)

    result={"schema":1,"description":"In-domain synthetic 46.wav overlay rescue, strict nested LOO.",
      "baseThreshold":BASE_THRESHOLD,"baseline":base,
      "synthetic":{"ratios":RATIOS,"maxNegativeAnchorsPerSong":MAX_SYNTH_NEG_PER_SONG},
      "gmd":{"overlayRows":len(gY),"overlayPositive":int(gY.sum()),"clips":manifest},"variants":{}}
    for v in VARIANTS:
        q=evaluate(d,hatX,hatY,gX,gY,v);s=q["summary"]
        q["eligible"]=(s["macroF1"]>base["macroF1"] and s["open"]["f1"]>base["open"]["f1"] and
                       s["open"]["precision"]>=base["open"]["precision"]-.025)
        result["variants"][v]=q
        print("RESULT",v,json.dumps({"eligible":q["eligible"],"summary":s}),flush=True)
    eligible=[q for q in result["variants"].values() if q["eligible"]]
    best=max(eligible,key=lambda q:(q["summary"]["macroF1"],q["summary"]["open"]["f1"])) if eligible else None
    result["retained"]=best["variant"] if best else "none";result["retainedSummary"]=best["summary"] if best else base
    (EXP/"results-open-hat-synthetic-overlay-loo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("RETAINED",result["retained"],json.dumps(result["retainedSummary"]),flush=True)

if __name__=="__main__":main()
