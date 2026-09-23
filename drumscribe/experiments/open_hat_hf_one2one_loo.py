"""Cycle: one-to-one training for dense HF open-hi-hat rescue.

The previous HF student used every candidate within 80 ms of an open reference
as a positive. Dense HF peaks therefore created multiple "positives" for one
true hit and taught the model to emit clusters. This cycle fixes the target:

- exactly one nearest HF candidate may represent each training-song Open 46;
- additional candidates in the same +/-80 ms neighborhood are ignored;
- all rescue outputs get probability NMS before scoring.

Three hypotheses:
A one2one_acoustic:
  per-song robust-normalized drums-only HF/acoustic features.
B one2one_context:
  A + audio-derived beat/bar phase + repetition + proximity to existing
  kick/snare/metal events. These are clues only; those events are never edited.
C selfcal:
  no candidate chart labels at inference. On each song, use the held-out base
  articulation model's very high/low confidence existing hats as pseudo-labels
  to learn that kit's open-vs-closed timbre, then score HF candidates.

All outer held-song chart data is final scoring only.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
BASE_THRESHOLD=.575
SELFCAL_CACHE={}
THRESHOLDS=[.55,.62,.68,.74,.80,.85,.89,.92,.95,.97,.985,.995,1.01]

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
hf=loadmod("hf_one2one_base",EXP/"open_hat_hf_offvocal_loo.py")
ov=hf.ov;oh=hf.oh

def robust(X):
    if not len(X):return X
    med=np.median(X,axis=0);q1=np.percentile(X,25,axis=0);q3=np.percentile(X,75,axis=0)
    return np.clip((X-med)/np.maximum(q3-q1,1e-3),-8,8).astype(np.float32)

def one2one_labels(times,refs,w=.080):
    y=np.zeros(len(times),np.int8)
    near_any=np.zeros(len(times),bool)
    for i,t in enumerate(times):
        near_any[i]=any(abs(t-r)<=w for r in refs)
    used=set()
    for r in refs:
        cand=[(abs(times[i]-r),i) for i in range(len(times)) if i not in used and abs(times[i]-r)<=w]
        if cand:
            _,i=min(cand);used.add(i);y[i]=1
    # -1 means duplicate/ambiguous candidate around a real Open; ignore in training.
    y[(near_any)&(y==0)]=-1
    return y

def near_times(xs,t,w):
    return any(abs(x-t)<=w for x in xs)

def periodic_support(times,t,bpm):
    if bpm<=0:return 0.
    best=0.
    for step in (15/bpm,30/bpm,60/bpm):
        n=0
        for k in (-4,-3,-2,-1,1,2,3,4):
            n+=near_times(times,t+k*step,.040)
        best=max(best,n/8)
    return best

def context(d,s,times):
    rows=d[s]["rows"];side=d[s]["side"]
    by={g:sorted(t for t,gg,p in rows if gg==g) for g in ("kick","snare","tom","ride","crash","pedal_hat")}
    bpm=float(side.get("bpm") or 0.);phase=float(side.get("barPhaseSec") or side.get("beatPhaseSec") or 0.)
    beat=60/bpm if bpm>0 else 1.
    out=[]
    for t in times:
        pos=((t-phase)/beat)%4
        slot=pos*4
        out.append([
          math.sin(2*math.pi*slot/16),math.cos(2*math.pi*slot/16),
          min(abs(slot-round(slot)),.5)*2,
          periodic_support(times,t,bpm),
          float(near_times(by["kick"],t,.045)),
          float(near_times(by["snare"],t,.045)),
          float(near_times(by["ride"],t,.055)),
          float(near_times(by["crash"],t,.055)),
          float(near_times(by["pedal_hat"],t,.055)),
          min(min((abs(t-u) for u in by["snare"]),default=.25),.25)/.25,
          min(min((abs(t-u) for u in by["kick"]),default=.25),.25)/.25,
        ])
    return np.asarray(out,np.float32)

def prepare():
    d=hf.prepare()
    for s in SONGS:
        h=d[s]["hf"];times=h["times"]
        X=robust(h["Xd"])
        C=context(d,s,times)
        h["Xone"]=X
        h["Xctx"]=np.concatenate([X,C],axis=1)
        h["yone"]=one2one_labels(times,d[s]["refs"][46])
        print("O2O",s,json.dumps({
          "candidate":len(times),"positive":int(np.sum(h["yone"]==1)),
          "ignored":int(np.sum(h["yone"]<0)),"negative":int(np.sum(h["yone"]==0))
        }),flush=True)
    return d

def fit_base(d,songs,hx,hy):
    X=np.concatenate([*(d[s]["X"]["timbre_norm"] for s in songs),hx])
    y=np.concatenate([*((d[s]["y"]==1).astype(np.int8) for s in songs),hy])
    return ExtraTreesClassifier(n_estimators=320,max_depth=13,min_samples_leaf=4,
      class_weight="balanced",random_state=560,n_jobs=-1).fit(X,y)

def p1(m,X):
    if not len(X):return np.zeros(0)
    p=m.predict_proba(X);c=list(m.classes_)
    if 1 not in c:return np.zeros(len(X))
    return p[:,c.index(1)]

def train_global(d,songs,variant,seed):
    XX=[];yy=[]
    key="Xctx" if variant=="one2one_context" else "Xone"
    for s in songs:
        h=d[s]["hf"];mask=h["yone"]>=0;X=h[key][mask];y=h["yone"][mask]
        pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0)
        rng=np.random.default_rng(seed+SONGS.index(s)*19)
        if len(neg)>max(350,6*len(pos)):neg=rng.choice(neg,max(350,6*len(pos)),replace=False)
        ids=np.sort(np.concatenate([pos,neg]));XX.append(X[ids]);yy.append(y[ids])
    X=np.concatenate(XX);y=np.concatenate(yy)
    m=ExtraTreesClassifier(n_estimators=420,max_depth=15,min_samples_leaf=3,max_features="sqrt",
      class_weight="balanced",random_state=2100+seed,n_jobs=-1).fit(X,y)
    return m,{"rows":len(y),"positive":int(y.sum())}

def pseudo_selfcal(d,s,bm):
    # Current retained model provides kit-specific anchor labels only on existing
    # hat candidates. Held-song chart is never consulted.
    pp=p1(bm,d[s]["X"]["timbre_norm"])
    pos=np.flatnonzero(pp>=.78);neg=np.flatnonzero(pp<=.18)
    if len(pos)<3 or len(neg)<12:return None,{"positiveAnchors":len(pos),"negativeAnchors":len(neg)}
    X=d[s]["X"]["timbre_norm"]
    ids=np.concatenate([pos,neg]);y=np.concatenate([np.ones(len(pos),np.int8),np.zeros(len(neg),np.int8)])
    m=ExtraTreesClassifier(n_estimators=240,max_depth=10,min_samples_leaf=2,class_weight="balanced",
      random_state=3100+SONGS.index(s),n_jobs=-1).fit(X[ids],y)
    return m,{"positiveAnchors":len(pos),"negativeAnchors":len(neg)}

def nms(times,prob,th,window=.070):
    ids=np.flatnonzero(prob>=th)
    ids=ids[np.argsort(prob[ids])[::-1]]
    keep=[]
    for i in ids:
        if all(abs(times[i]-times[j])>window for j in keep):keep.append(int(i))
    return sorted(times[i] for i in keep)

def score_global(d,s,bm,rm,variant,th):
    hp=p1(bm,d[s]["X"]["timbre_norm"])
    bo=[t for t,p in zip(d[s]["hats"],hp) if p>=BASE_THRESHOLD]
    bc=[t for t,p in zip(d[s]["hats"],hp) if p<BASE_THRESHOLD]
    h=d[s]["hf"];key="Xctx" if variant=="one2one_context" else "Xone";rp=p1(rm,h[key])
    rescue=[t for t in nms(h["times"],rp,th) if not near_times(bo,t,.060)]
    met=oh.articulation_metrics(sorted(bo+rescue),bc,d[s]["refs"])
    return met,{"baseOpen":len(bo),"rescue":len(rescue),"maxProb":float(np.max(rp)) if len(rp) else 0.,
                "p99":float(np.percentile(rp,99)) if len(rp) else 0.}

def score_selfcal(d,s,bm,th):
    hp=p1(bm,d[s]["X"]["timbre_norm"])
    bo=[t for t,p in zip(d[s]["hats"],hp) if p>=BASE_THRESHOLD]
    bc=[t for t,p in zip(d[s]["hats"],hp) if p<BASE_THRESHOLD]
    h=d[s]["hf"];key=(id(bm),s)
    if key not in SELFCAL_CACHE:
        sm,anchor=pseudo_selfcal(d,s,bm)
        rp=np.zeros(len(h["times"])) if sm is None else p1(sm,h["Xd"][:,:26])
        SELFCAL_CACHE[key]=(rp,dict(anchor))
    rp,anchor=SELFCAL_CACHE[key]
    info=dict(anchor)
    rescue=[t for t in nms(h["times"],rp,th) if not near_times(bo,t,.060)]
    met=oh.articulation_metrics(sorted(bo+rescue),bc,d[s]["refs"])
    info.update({"baseOpen":len(bo),"rescue":len(rescue),"maxProb":float(np.max(rp)) if len(rp) else 0.,
                 "p99":float(np.percentile(rp,99)) if len(rp) else 0.})
    return met,info

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

def choose(d,outer,hx,hy,variant):
    cache={}
    for i,val in enumerate(outer):
        tr=[x for x in outer if x!=val];bm=fit_base(d,tr,hx,hy)
        rm=None
        if variant!="selfcal":rm=train_global(d,tr,variant,40+i)[0]
        cache[val]=(bm,rm)
    base={}
    for s,(bm,rm) in cache.items():
        base[s]=(score_selfcal(d,s,bm,1.01)[0] if variant=="selfcal" else score_global(d,s,bm,rm,variant,1.01)[0])
    b=aggregate(base);rows=[]
    for th in THRESHOLDS:
        per={}
        for s,(bm,rm) in cache.items():
            per[s]=(score_selfcal(d,s,bm,th)[0] if variant=="selfcal" else score_global(d,s,bm,rm,variant,th)[0])
        a=aggregate(per)
        eligible=(a["open"]["precision"]>=b["open"]["precision"]-.02 and a["open"]["f1"]>b["open"]["f1"] and a["macroF1"]>b["macroF1"])
        utility=a["macroF1"]+.10*a["open"]["precision"]
        rows.append((eligible,utility,th,a))
    rows.sort(key=lambda r:(r[0],r[1]),reverse=True)
    best=next((r for r in rows if r[0]),None)
    return (best[2] if best else 1.01),{"base":b,"ranking":[{"threshold":r[2],"eligible":r[0],"utility":r[1],"summary":r[3]} for r in rows]}

def evaluate(d,hx,hy,variant):
    per={};folds={}
    for oi,held in enumerate(SONGS):
        outer=[s for s in SONGS if s!=held];th,inner=choose(d,outer,hx,hy,variant)
        bm=fit_base(d,outer,hx,hy)
        if variant=="selfcal":
            m,diag=score_selfcal(d,held,bm,th);train=None
        else:
            rm,train=train_global(d,outer,variant,100+oi);m,diag=score_global(d,held,bm,rm,variant,th)
        per[held]=m;folds[held]={"threshold":th,"metrics":m,"diag":diag,"train":train,"inner":inner}
        print("O2O_FOLD",variant,held,th,json.dumps({"open":m["open"],"diag":diag}),flush=True)
    return {"variant":variant,"summary":aggregate(per),"songs":per,"folds":folds}

def main():
    d=prepare();hx,hy,_,_,_=ov.gmd_collect()
    baseline={}
    for held in SONGS:
        bm=fit_base(d,[s for s in SONGS if s!=held],hx,hy);hp=p1(bm,d[held]["X"]["timbre_norm"])
        bo=[t for t,p in zip(d[held]["hats"],hp) if p>=BASE_THRESHOLD];bc=[t for t,p in zip(d[held]["hats"],hp) if p<BASE_THRESHOLD]
        baseline[held]=oh.articulation_metrics(bo,bc,d[held]["refs"])
    base=aggregate(baseline)
    result={"schema":1,"description":"One-to-one dense HF rescue with NMS and self-calibration.","baseline":base,"variants":{}}
    for v in ("one2one_acoustic","one2one_context","selfcal"):
        q=evaluate(d,hx,hy,v);s=q["summary"]
        q["passesGuard"]=(s["macroF1"]>base["macroF1"] and s["open"]["f1"]>base["open"]["f1"] and s["open"]["precision"]>=base["open"]["precision"]-.02)
        result["variants"][v]=q
        print("O2O_RESULT",v,json.dumps({"passes":q["passesGuard"],"summary":s}),flush=True)
    good=[q for q in result["variants"].values() if q["passesGuard"]]
    best=max(good,key=lambda q:(q["summary"]["macroF1"],q["summary"]["open"]["f1"])) if good else None
    result["retained"]=best["variant"] if best else "none";result["retainedSummary"]=best["summary"] if best else base
    (EXP/"results-open-hat-hf-one2one-loo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("O2O_RETAINED",result["retained"],json.dumps(result["retainedSummary"]),flush=True)
if __name__=="__main__":main()
