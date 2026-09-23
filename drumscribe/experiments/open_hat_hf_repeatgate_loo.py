"""HF-union open-hi-hat rescue benchmark.

Authoritative design:
- freeze pre-overlay browser MIDI at BASE_REF so candidate generation cannot feed
  later open-hat rescues back into itself;
- outer held song is excluded from all supervised fitting;
- held-song chart is used only for final scoring / diagnostics;
- kick/snare/tom/ride/crash are never removed;
- rescue may only ADD Open HH and is rejected if two hands are already occupied.

Hypotheses:
A structural_repeat_safe
  Current structural-anchor overlay model + repeat gate + 2-hand guard.
B hf_union_existing29
  Add independent 5-18 kHz HF candidates to the same 29-D structural model.
  This tests whether the retained model transfers to the larger candidate pool.
C hf_union_retrained41
  Retrain a union model on structural + one-to-one-labeled HF candidates from the
  non-held songs.  Features = 26 timbre + 3 structural proximity bits + 12 HF
  stream features.  GMD structural examples are retained with zero HF-stream tail.

All variants use the same prediction-time repeat-gate constants, then 70 ms NMS.
"""
from __future__ import annotations
import importlib.util,json,os,shutil,subprocess
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
BASE_REF="8ef45bf10b97f4ae5e324b88376821c2f5f27fa5"
TMP=EXP/"_hf_union_pre_overlay"
BASE_THRESHOLD=.575
FAM="C_metal_snare_kick"

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
sa=loadmod("hf_union_sa",EXP/"open_hat_overlay_selfadapt.py")
ov=sa.ov;oh=sa.oh
hf=loadmod("hf_union_hf",EXP/"open_hat_hf_offvocal_loo.py")

def materialize_base():
    if TMP.exists():shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    for s in SONGS:
        for ext in ("mid","json"):
            rel=f"drumscribe/experiments/generated-v2-browser/{s}.{ext}"
            data=subprocess.check_output(["git","show",f"{BASE_REF}:{rel}"])
            (TMP/f"{s}.{ext}").write_bytes(data)
    oh.BASE=TMP
    print("FROZEN_BASE",BASE_REF,flush=True)

def near(xs,t,w):
    return any(abs(float(x)-float(t))<=w for x in xs)

def structural_bits(rows,t):
    metal=snare=kick=0
    for u,g,p in rows:
        if abs(float(u)-float(t))>.055:continue
        if g in ("ride","crash"):metal=1
        elif g=="snare":snare=1
        elif g=="kick":kick=1
    return metal,snare,kick

def stream_extra(times,flux,hfen,bands):
    ids=np.clip(np.rint(np.asarray(times)*hf.SR/hf.HOP).astype(int),0,len(flux)-1)
    return hf.candidate_extra(np.asarray(times,float),ids,flux,hfen,bands)

def one2one_labels(times,refs,w=.080):
    times=np.asarray(times,float);y=np.zeros(len(times),np.int8);near_any=np.zeros(len(times),bool);used=set()
    for i,t in enumerate(times):near_any[i]=near(refs,t,w)
    for r in refs:
        cand=[(abs(float(t)-float(r)),i) for i,t in enumerate(times) if i not in used and abs(float(t)-float(r))<=w]
        if cand:
            _,i=min(cand);used.add(i);y[i]=1
    y[(near_any)&(y==0)]=-1
    return y

def prepare_hf(d):
    for s in SONGS:
        print("HF_UNION_FEATURES",s,flush=True)
        x=hf.decode(s,"drums.mp3")
        flux,hfen,bands=hf.hf_stream(x)
        cand,_,ids=hf.peak_candidates(flux,hfen)
        cand=cand[cand<(len(x)/hf.SR-.7)];ids=ids[:len(cand)]
        hats=d[s]["hats"]
        mask=np.asarray([not near(hats,t,.060) for t in cand],bool)
        cand=cand[mask];ids=ids[mask]
        raw=np.stack([oh.timbre_features(x,float(t)) for t in cand]) if len(cand) else np.zeros((0,26),np.float32)
        ac=ov.robust_basis(d[s]["X"]["timbre"],raw)
        bits=np.asarray([structural_bits(d[s]["rows"],t) for t in cand],np.float32) if len(cand) else np.zeros((0,3),np.float32)
        ex=hf.candidate_extra(cand,ids,flux,hfen,bands) if len(cand) else np.zeros((0,12),np.float32)
        X29=np.concatenate([ac,bits],axis=1)
        X41=np.concatenate([X29,hf.robust1(ex[:,0])[:,None] if False else ex],axis=1)
        # Normalize HF-stream columns within song. Acoustic columns are already
        # normalized against the song's retained-hat basis.
        if len(ex):
            ez=ex.copy()
            for j in range(ex.shape[1]):ez[:,j]=hf.robust1(ex[:,j])
            X41=np.concatenate([X29,ez],axis=1)
        y=one2one_labels(cand,d[s]["refs"][46])
        d[s]["hfUnion"]={"times":cand,"X29":X29,"X41":X41,"y":y,
          "counts":{"candidates":len(cand),"positive":int(np.sum(y==1)),"ignored":int(np.sum(y<0))}}
        # Build 41-D structural features using the same per-song HF stream.
        st=d[s]["overlay"];stimes=np.asarray([a[0] for a in st["anchors"]],float)
        sex=stream_extra(stimes,flux,hfen,bands) if len(stimes) else np.zeros((0,12),np.float32)
        if len(sex):
            for j in range(sex.shape[1]):sex[:,j]=hf.robust1(sex[:,j])
        d[s]["struct41"]=np.concatenate([st["X"],sex],axis=1)
        print("HF_UNION_COUNTS",s,json.dumps(d[s]["hfUnion"]["counts"]),flush=True)
    return d

def p1(m,X):
    if not len(X):return np.zeros(0)
    p=m.predict_proba(X);cls=list(m.classes_)
    if 1 not in cls:return np.zeros(len(X))
    return p[:,cls.index(1)]

def train_union41(d,songs,gx,gy,seed):
    XX=[];yy=[]
    # Existing in-domain structural anchors.
    for s in songs:
        st=d[s]["overlay"];XX.append(d[s]["struct41"]);yy.append(st["y"])
        h=d[s]["hfUnion"];keep=h["y"]>=0;X=h["X41"][keep];y=h["y"][keep]
        pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0)
        rng=np.random.default_rng(5100+seed+SONGS.index(s)*29)
        # Dense HF stream needs hard negative coverage but must not swamp positives.
        cap=max(450,5*len(pos))
        if len(neg)>cap:neg=rng.choice(neg,cap,replace=False)
        ids=np.sort(np.concatenate([pos,neg]));XX.append(X[ids]);yy.append(y[ids])
    # Retain GMD structural prior. It has no corresponding HF-stream representation;
    # append zeros only to the stream-specific columns.
    ggx,ggy=ov.subset_gmd(gx,gy,FAM,seed)
    if len(ggy):
        XX.append(np.concatenate([ggx,np.zeros((len(ggx),12),np.float32)],axis=1));yy.append(ggy)
    X=np.concatenate(XX);y=np.concatenate(yy)
    model=ExtraTreesClassifier(n_estimators=420,max_depth=14,min_samples_leaf=3,max_features="sqrt",
      class_weight="balanced",random_state=5200+seed,n_jobs=-1).fit(X,y)
    return model,{"rows":len(y),"positive":int(y.sum()),"songs":list(songs),"gmdRows":len(ggy)}

def physical_ok(rows,t):
    hands=sum(1 for u,g,p in rows if g in ("snare","tom","hat","crash","ride") and abs(float(u)-float(t))<=.035)
    return hands<2

def nms_selected(times,prob,mask,w=.070):
    ids=np.flatnonzero(mask)
    ids=ids[np.argsort(prob[ids])[::-1]]
    keep=[]
    for i in ids:
        if all(abs(float(times[i])-float(times[j]))>w for j in keep):keep.append(int(i))
    return sorted(keep,key=lambda i:times[i])

def metrics(pred_open,pred_closed,refs):
    return oh.articulation_metrics(sorted(pred_open),sorted(pred_closed),refs)

def base_predictions(d,s,bm):
    hp=ov.probs(bm,d[s]["X"]["timbre_norm"])
    bo=[t for t,p in zip(d[s]["hats"],hp) if p>=BASE_THRESHOLD]
    bc=[t for t,p in zip(d[s]["hats"],hp) if p<BASE_THRESHOLD]
    return bo,bc

def score_structural(d,s,bm,om):
    bo,bc=base_predictions(d,s,bm);oo=d[s]["overlay"]
    times=np.asarray([a[0] for a in oo["anchors"]],float);pp=ov.probs(om,oo["X"])
    mask,adapt=sa.select("repeat_gate",times,pp,float(d[s]["side"].get("bpm") or 0))
    ids=nms_selected(times,pp,mask)
    selected=[];blocked=0
    for i in ids:
        t=float(times[i])
        if near(bo,t,.060):continue
        if not physical_ok(d[s]["rows"],t):blocked+=1;continue
        selected.append(t)
    return metrics(bo+selected,bc,d[s]["refs"]),{"candidates":len(times),"rescued":len(selected),"blocked":blocked,"adapt":adapt,
      "rescueTpDiagnostic":sum(near(d[s]["refs"][46],t,.080) for t in selected)}

def union_candidates(d,s,use41=False):
    st=d[s]["overlay"];ht=d[s]["hfUnion"]
    times=[];features=[];kind=[]
    sx=d[s]["struct41"] if use41 else st["X"];hx=ht["X41"] if use41 else ht["X29"]
    for i,a in enumerate(st["anchors"]):
        times.append(float(a[0]));features.append(sx[i]);kind.append("struct")
    for i,t in enumerate(ht["times"]):
        if near(times,float(t),.035):continue
        times.append(float(t));features.append(hx[i]);kind.append("hf")
    order=np.argsort(times);times=np.asarray(times,float)[order]
    X=np.asarray(features,np.float32)[order];kind=[kind[i] for i in order]
    return times,X,kind

def score_union(d,s,bm,om,use41):
    bo,bc=base_predictions(d,s,bm);times,X,kind=union_candidates(d,s,use41)
    pp=p1(om,X);mask,adapt=sa.select("repeat_gate",times,pp,float(d[s]["side"].get("bpm") or 0))
    ids=nms_selected(times,pp,mask)
    selected=[];blocked=0;by=Counter()
    for i in ids:
        t=float(times[i])
        if near(bo,t,.060):continue
        if not physical_ok(d[s]["rows"],t):blocked+=1;continue
        selected.append(t);by[kind[i]]+=1
    return metrics(bo+selected,bc,d[s]["refs"]),{"candidates":len(times),"rescued":len(selected),"blocked":blocked,
      "rescuedByKind":dict(by),"adapt":adapt,"maxProbability":float(np.max(pp)) if len(pp) else 0.,
      "rescueTpDiagnostic":sum(near(d[s]["refs"][46],t,.080) for t in selected)}

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

def main():
    materialize_base();d=prepare_hf(ov.local_prepare());hx,hy,gx,gy,manifest=ov.gmd_collect()
    out={"schema":1,"triggerSha":os.environ.get("GITHUB_SHA"),"frozenBrowserRef":BASE_REF,
      "description":"Structural repeat gate vs independent-HF union rescue on frozen pre-overlay browser MIDI.",
      "variants":{}}
    for name in ("structural_repeat_safe","hf_union_existing29","hf_union_retrained41"):
        per={};folds={}
        for i,held in enumerate(SONGS):
            tr=[s for s in SONGS if s!=held];bm=ov.train_base(d,tr,hx,hy)
            if name=="structural_repeat_safe":
                om,tinfo=ov.train_overlay(d,tr,gx,gy,FAM,600+i);m,diag=score_structural(d,held,bm,om)
            elif name=="hf_union_existing29":
                om,tinfo=ov.train_overlay(d,tr,gx,gy,FAM,700+i);m,diag=score_union(d,held,bm,om,False)
            else:
                om,tinfo=train_union41(d,tr,gx,gy,800+i);m,diag=score_union(d,held,bm,om,True)
            per[held]=m;folds[held]={"metrics":m,"diag":diag,"train":tinfo}
            print("HF_UNION_FOLD",name,held,json.dumps({"open":m["open"],"diag":diag}),flush=True)
        summary=aggregate(per);out["variants"][name]={"summary":summary,"songs":per,"folds":folds}
        print("HF_UNION_RESULT",name,json.dumps(summary),flush=True)
    base=out["variants"]["structural_repeat_safe"]["summary"]
    for name,q in out["variants"].items():
        s=q["summary"]
        q["eligible"]=(name!="structural_repeat_safe" and s["open"]["f1"]>base["open"]["f1"] and
          s["macroF1"]>base["macroF1"] and s["open"]["precision"]>=base["open"]["precision"]-.02 and
          s["closed"]["f1"]>=base["closed"]["f1"]-.002)
    good=[q|{"name":k} for k,q in out["variants"].items() if q.get("eligible")]
    best=max(good,key=lambda q:(q["summary"]["macroF1"],q["summary"]["open"]["f1"])) if good else None
    out["retained"]=best["name"] if best else "structural_repeat_safe"
    out["retainedSummary"]=best["summary"] if best else base
    out["note"]="Development benchmark; current best must still pass real-browser grouped K/S/T non-regression before runtime adoption."
    (EXP/"results-open-hat-hf-repeatgate-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("HF_UNION_RETAINED",out["retained"],json.dumps(out["retainedSummary"]),flush=True)
if __name__=="__main__":main()
