"""GMD-trained open-hi-hat overlay rescue.

Problem addressed:
The normal open-hat classifier only relabels already detected hat onsets.
In diamondvirgin, many reference open hats coincide with snare/kick/metal events
but never survive as hat candidates.

This experiment learns a distinct binary task:
"At this non-hat browser event time, is an open hi-hat sounding simultaneously?"

Three candidate families are evaluated with nested leave-one-song-out:
 A metal          : ride/crash anchors only
 B metal_snare    : metal + snare anchors
 C metal_snare_kick: metal + snare + kick anchors

Training combines:
- candidate/label pairs from the non-held DruMaster songs
- aligned GMD audio/MIDI overlay examples from the same deterministic short-clip
  subset used by the retained GMD128 articulation model.

No held-out chart is used for candidate generation, normalization, fitting, or
threshold selection. The current hat detector is unchanged.
"""
from __future__ import annotations
import csv,io,importlib.util,json,random
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from remotezip import RemoteZip

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
BASE_THRESHOLD=.575
THRESHOLDS=[.45,.55,.65,.75,.82,.88,.93,1.01]
FAMILIES={
 "A_metal":(1,0,0),
 "B_metal_snare":(1,1,0),
 "C_metal_snare_kick":(1,1,1),
}
OPEN={26,46};CLOSED={22,42}
KICK={35,36};SNARE={37,38,39,40};CRASH={49,52,55,57};RIDE={51,53,59}

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ext=loadmod("openhat_overlay_ext",EXP/"external_hat_augmentation.py")
sn=ext.sn;oh=ext.oh

def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)

def robust_basis(hat_raw,rows):
    if not len(rows):return np.zeros((0,hat_raw.shape[1]),np.float32)
    med=np.median(hat_raw,axis=0);q1=np.percentile(hat_raw,25,axis=0);q3=np.percentile(hat_raw,75,axis=0)
    scale=np.maximum(q3-q1,1e-3)
    return np.clip((rows-med)/scale,-8,8).astype(np.float32)

def cluster_anchors(items,w=.035):
    """items=(time, groupKind) -> (time, metal,snare,kick), merging simultaneous limbs."""
    items=sorted(items)
    out=[];i=0
    while i<len(items):
        t0=items[i][0];cluster=[];j=i
        while j<len(items) and items[j][0]-t0<=w:
            cluster.append(items[j]);j+=1
        # anchor at strongest structural priority time: metal, then snare, then kick
        mt=[t for t,g in cluster if g=="metal"];st=[t for t,g in cluster if g=="snare"];kt=[t for t,g in cluster if g=="kick"]
        t=(mt or st or kt)[0]
        out.append((t,int(bool(mt)),int(bool(st)),int(bool(kt))))
        i=j
    return out

def allowed(bits,fam):
    am,as_,ak=FAMILIES[fam];m,s,k=bits
    return bool((am and m) or (as_ and s) or (ak and k))

def local_prepare():
    d=sn.prepare()
    for song in SONGS:
        audio=oh.audio(song);rows=d[song]["rows"];hats=sorted(t for t,g,p in rows if g=="hat")
        items=[]
        for t,g,p in rows:
            if g in ("ride","crash"):items.append((t,"metal"))
            elif g=="snare":items.append((t,"snare"))
            elif g=="kick":items.append((t,"kick"))
        anchors=[a for a in cluster_anchors(items) if not near(hats,a[0],.060)]
        raw=np.stack([oh.timbre_features(audio,a[0]) for a in anchors]) if anchors else np.zeros((0,26),np.float32)
        acoustic=robust_basis(d[song]["X"]["timbre"],raw)
        X=np.concatenate([acoustic,np.asarray([[a[1],a[2],a[3]] for a in anchors],np.float32)],axis=1) if len(anchors) else np.zeros((0,29),np.float32)
        refopen=d[song]["refs"][46]
        y=np.asarray([1 if near(refopen,a[0],.080) else 0 for a in anchors],np.int8)
        d[song]["overlay"]={"anchors":anchors,"X":X,"y":y}
        print("LOCAL_OVERLAY",song,"rows",len(y),"positive",int(y.sum()),
              "by_family",{f:int(sum(allowed(a[1:],f) for a in anchors)) for f in FAMILIES},flush=True)
    return d

def gmd_collect():
    """Fetch same deterministic 24 GMD clips; return hat augmentation + overlay rows."""
    with RemoteZip(ext.GMD_ZIP) as z:
        names=z.namelist();name_set=set(names)
        info_name=min([n for n in names if n.endswith("info.csv")],key=len)
        rows=ext.read_csv_bytes(z.read(info_name))
        candidates=[r for r in rows if ext.suitable(r) and (r.get("beat_type") or "")=="beat"]
        random.Random(117).shuffle(candidates)
        chosen=[]
        for r in candidates:
            midi_name=ext.resolve_name(name_set,r["midi_filename"])
            notes=ext.midi_notes_bytes(z.read(midi_name));c=ext.counts(notes)
            if c["open"]>=6 and c["closed"]>=8:chosen.append((r,notes,midi_name))
            if len(chosen)>=ext.TARGET_GMD_SEQS:break

        hatX=[];hatY=[];ovX=[];ovY=[];manifest=[]
        for idx,(r,notes,midi_name) in enumerate(chosen):
            audio_name=ext.resolve_name(name_set,r["audio_filename"])
            audio=ext.decode_wav(z.read(audio_name))
            hats=[(t,1 if p in OPEN else 0) for t,p,v in notes if p in OPEN|CLOSED]
            if len(hats)<4:continue
            hatraw=np.stack([oh.timbre_features(audio,t) for t,_ in hats])
            hatnorm=ext.robust_rows(hatraw)
            hatX.append(hatnorm);hatY.append(np.asarray([v for _,v in hats],np.int8))

            items=[]
            for t,p,v in notes:
                if p in CRASH|RIDE:items.append((t,"metal"))
                elif p in SNARE:items.append((t,"snare"))
                elif p in KICK:items.append((t,"kick"))
            anchors=cluster_anchors(items)
            raw=np.stack([oh.timbre_features(audio,a[0]) for a in anchors]) if anchors else np.zeros((0,26),np.float32)
            acoustic=robust_basis(hatraw,raw)
            X=np.concatenate([acoustic,np.asarray([[a[1],a[2],a[3]] for a in anchors],np.float32)],axis=1) if len(anchors) else np.zeros((0,29),np.float32)
            opens=[t for t,p,v in notes if p in OPEN]
            y=np.asarray([1 if near(opens,a[0],.045) else 0 for a in anchors],np.int8)
            ovX.append(X);ovY.append(y)
            manifest.append({"id":r.get("id"),"style":r.get("style"),"hats":len(hats),
                "overlayRows":len(y),"overlayPositive":int(y.sum())})
            print("GMD_OVERLAY",idx+1,len(chosen),manifest[-1],flush=True)

    hx=np.concatenate(hatX);hy=np.concatenate(hatY)
    # Reproduce retained GMD128 training subset exactly.
    hx,hy=ext.balanced_cap(hx,hy,seed=101)
    hx,hy=ext.balanced_cap(hx,hy,limit=128,seed=528)
    ox=np.concatenate(ovX);oy=np.concatenate(ovY)
    return hx,hy,ox,oy,manifest

def subset_local(d,songs,fam):
    XX=[];yy=[]
    for s in songs:
        ov=d[s]["overlay"];mask=np.asarray([allowed(a[1:],fam) for a in ov["anchors"]],bool)
        if mask.any():XX.append(ov["X"][mask]);yy.append(ov["y"][mask])
    return (np.concatenate(XX),np.concatenate(yy)) if XX else (np.zeros((0,29),np.float32),np.zeros(0,np.int8))

def subset_gmd(X,y,fam,seed=0):
    am,as_,ak=FAMILIES[fam]
    mask=((X[:,26]>0)&bool(am))|((X[:,27]>0)&bool(as_))|((X[:,28]>0)&bool(ak))
    X=X[mask];y=y[mask]
    # Keep all positive overlays; cap negatives at 3x positives to avoid external
    # no-open anchors overwhelming the small DruMaster task.
    pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0)
    rng=np.random.default_rng(800+seed)
    if len(pos) and len(neg)>3*len(pos):neg=rng.choice(neg,3*len(pos),replace=False)
    ids=np.sort(np.concatenate([pos,neg]))
    return X[ids],y[ids]

def train_overlay(d,songs,gX,gY,fam,seed):
    lx,ly=subset_local(d,songs,fam);gx,gy=subset_gmd(gX,gY,fam,seed)
    X=np.concatenate([lx,gx]);y=np.concatenate([ly,gy])
    return ExtraTreesClassifier(n_estimators=280,max_depth=12,min_samples_leaf=3,
      class_weight="balanced",random_state=740+seed,n_jobs=-1).fit(X,y),{
        "localRows":len(ly),"localPositive":int(ly.sum()),"gmdRows":len(gy),"gmdPositive":int(gy.sum())}

def train_base(d,songs,hatX,hatY):
    return ext.train_model(d,songs,(hatX,hatY))

def probs(model,X):
    if not len(X):return np.zeros(0)
    return model.predict_proba(X)[:,list(model.classes_).index(1)]

def score(d,s,base_model,overlay_model,fam,th):
    hp=probs(base_model,d[s]["X"]["timbre_norm"])
    bo=[t for t,p in zip(d[s]["hats"],hp) if p>=BASE_THRESHOLD]
    bc=[t for t,p in zip(d[s]["hats"],hp) if p<BASE_THRESHOLD]
    ov=d[s]["overlay"];mask=np.asarray([allowed(a[1:],fam) for a in ov["anchors"]],bool)
    anchors=[a for a,m in zip(ov["anchors"],mask) if m];X=ov["X"][mask]
    pp=probs(overlay_model,X)
    rescued=[a[0] for a,p in zip(anchors,pp) if p>=th and not near(bo,a[0],.060)]
    m=oh.articulation_metrics(sorted(bo+rescued),bc,d[s]["refs"])
    return m,{"baseOpen":len(bo),"candidateRows":len(anchors),"rescued":len(rescued),
              "candidatePositiveForDiagnostic":int(ov["y"][mask].sum()),"maxProb":float(np.max(pp)) if len(pp) else 0.}

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

def choose_inner(d,outer,hatX,hatY,gX,gY,fam):
    cache={}
    for i,val in enumerate(outer):
        train=[s for s in outer if s!=val]
        bm=train_base(d,train,hatX,hatY)
        om,info=train_overlay(d,train,gX,gY,fam,10+i)
        cache[val]=(bm,om,info)
    base={}
    for val,(bm,om,_) in cache.items():base[val]=score(d,val,bm,om,fam,1.01)[0]
    b=aggregate(base);rows=[]
    for th in THRESHOLDS:
        per={};diag={}
        for val,(bm,om,_) in cache.items():per[val],diag[val]=score(d,val,bm,om,fam,th)
        a=aggregate(per)
        eligible=(a["open"]["precision"]>=b["open"]["precision"]-.02 and a["macroF1"]>b["macroF1"])
        scorev=a["macroF1"]+.05*a["open"]["precision"]
        rows.append((eligible,scorev,th,a,diag))
    rows.sort(key=lambda r:(r[0],r[1]),reverse=True)
    best=next((r for r in rows if r[0]),None)
    return (best[2] if best else 1.01),{"base":b,"ranking":[{"threshold":r[2],"eligible":r[0],"score":r[1],"summary":r[3]} for r in rows]}

def eval_family(d,hatX,hatY,gX,gY,fam):
    per={};folds={}
    for oi,held in enumerate(SONGS):
        outer=[s for s in SONGS if s!=held]
        th,inner=choose_inner(d,outer,hatX,hatY,gX,gY,fam)
        bm=train_base(d,outer,hatX,hatY);om,traininfo=train_overlay(d,outer,gX,gY,fam,100+oi)
        m,diag=score(d,held,bm,om,fam,th)
        per[held]=m;folds[held]={"threshold":th,"metrics":m,"diag":diag,"train":traininfo,"inner":inner}
        print("FOLD",fam,held,th,json.dumps({"open":m["open"],"diag":diag}),flush=True)
    return {"family":fam,"summary":aggregate(per),"songs":per,"folds":folds}

def main():
    d=local_prepare();hatX,hatY,gX,gY,manifest=gmd_collect()
    base={}
    # base held-out GMD128, no rescue
    for held in SONGS:
        bm=train_base(d,[s for s in SONGS if s!=held],hatX,hatY)
        # dummy overlay model not used at threshold 1.01, but score() needs one.
        om,_=train_overlay(d,[s for s in SONGS if s!=held],gX,gY,"A_metal",900)
        base[held]=score(d,held,bm,om,"A_metal",1.01)[0]
    baseline=aggregate(base)
    result={"schema":1,"description":"GMD/local specialized simultaneous open-hat overlay detector with nested LOO.",
      "baseThreshold":BASE_THRESHOLD,"baseline":baseline,
      "gmd":{"clips":manifest,"hatRows":len(hatY),"overlayRows":len(gY),"overlayPositive":int(gY.sum())},
      "families":{}}
    for fam in FAMILIES:
        q=eval_family(d,hatX,hatY,gX,gY,fam);result["families"][fam]=q
        s=q["summary"];q["eligible"]=(s["macroF1"]>baseline["macroF1"] and
          s["open"]["f1"]>baseline["open"]["f1"] and
          s["open"]["precision"]>=baseline["open"]["precision"]-.02)
        print("RESULT",fam,json.dumps({"eligible":q["eligible"],"summary":s}),flush=True)
    eligible=[q for q in result["families"].values() if q["eligible"]]
    best=max(eligible,key=lambda q:(q["summary"]["macroF1"],q["summary"]["open"]["f1"])) if eligible else None
    result["retained"]=best["family"] if best else "none";result["retainedSummary"]=best["summary"] if best else baseline
    (EXP/"results-open-hat-overlay-gmd-loo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("RETAINED",result["retained"],json.dumps(result["retainedSummary"]),flush=True)

if __name__=="__main__":main()
