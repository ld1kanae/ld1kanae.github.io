"""Source-separated ranking on the independent HF Open-HH candidate stream.

This experiment keeps the current production base unchanged and only tests an
additional GM46 rescue selector.  New learning sources are never pooled as rows:

- songs_context: selector fitted only from other DruMaster songs.
- songs_context_tail: same songs-only selector + tail-interruption features.
- gmd_genre_prior: fixed GMD symbolic prior from models/gmd-kst/.
- sync_teacher: fixed acoustic teacher from the synchronized Nanairo pair;
  disabled when Nanairo is held out.
- score_fusion: logistic meta-calibration on out-of-fold SOURCE SCORES only.

The current production base may itself contain historical GMD augmentation; it
is treated strictly as the frozen baseline being improved, not as training data
for these new source-specific selectors.

Rescue only ADDS Open HH (GM46). Kick/snare/tom and existing notes are untouched.
"""
from __future__ import annotations
import importlib.util, json
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfiltfilt
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";MODELS=ROOT/"drumscribe/models"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
THRESHOLDS=[.55,.62,.68,.74,.80,.86,.90,.93,.96,.98,.995,1.01]

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
hfctx=loadmod("sshf_hfctx",EXP/"open_hat_hf_context_rank_loo.py")
src=loadmod("sshf_src",EXP/"open_hat_source_separated_loo.py")
ctx=hfctx.ctx;hf=hfctx.hf;ov=ctx.ov;oh=ctx.oh

def strip_grid(X,base_len):
    # current context block: 6 cyclic phase features, then 3 grid residuals.
    a=base_len+6;b=a+3
    return np.concatenate([X[:,:a],X[:,b:]],axis=1)

def make_item(d,s,gmd,sync,sos):
    print("SSHF_PREP",s,flush=True)
    x=hf.decode(s,"drums.mp3")
    flux,hlev,bands=hf.hf_stream(x)
    times,score,ids=hf.peak_candidates(flux,hlev)
    duration=len(x)/hf.SR
    valid=times<duration-.7;times=times[valid];ids=ids[valid]
    keep=np.asarray([not hf.near(d[s]["hats"],t,.060) for t in times],bool)
    times=times[keep];ids=ids[keep]
    extra=hf.candidate_extra(times,ids,flux,hlev,bands)
    acoustic=hf.extract_at(x,times,d[s]["X"]["timbre"])
    fz=hf.robust1(flux);hz=hf.robust1(hlev)
    sc=np.asarray(score)[ids] if len(ids) else np.zeros(0)
    aux=[]
    for i,z in zip(ids,sc):
        lo=max(0,i-2);hi=min(len(score),i+3)
        aux.append([hfctx.sig(z),hfctx.sig(np.mean(score[lo:hi])),hfctx.sig(np.max(score[lo:hi])),
                    hfctx.sig(hz[i]),hfctx.sig(fz[i])])
    aux=np.asarray(aux,np.float32) if aux else np.zeros((0,5),np.float32)
    base=np.concatenate([acoustic,aux,extra],axis=1)
    fake={"times":times,"Xc":base}
    Xctx,info=ctx.context_features(d,s,fake)
    Xctx=strip_grid(Xctx,base.shape[1])

    hfa=sosfiltfilt(sos,x).astype(np.float32)
    tail=src.feature30(x,hfa,times)
    tailnorm=src.robust(tail)
    Xtail=np.concatenate([Xctx,tailnorm],axis=1)

    gw=src.genre_weights(gmd,d[s]["hats"],d[s]["side"])
    gp=src.gmd_scores(gmd,times,d[s]["side"],gw)
    sy=src.sync_prob(sync,tail)
    y=ctx.one_to_one_labels(times,d[s]["refs"][46])
    info={**info,"oneToOnePositive":int(y.sum()),"featuresNoGrid":int(Xctx.shape[1]),
          "featuresWithTail":int(Xtail.shape[1]),"genreTop":sorted(gw.items(),key=lambda q:q[1],reverse=True)[:5]}
    print("SSHF_COUNTS",s,json.dumps(info),flush=True)
    return {"times":times,"Xctx":Xctx,"Xtail":Xtail,"y":y,"gmd":gp,"sync":sy,"info":info}

def p1(m,X):
    if not len(X):return np.zeros(0)
    p=m.predict_proba(X);cls=list(m.classes_)
    return p[:,cls.index(1)] if 1 in cls else np.zeros(len(X))

def fit_songs(items,songs,key,seed):
    XX=[];yy=[]
    for s in songs:
        y=items[s]["y"];pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0)
        rng=np.random.default_rng(seed+SONGS.index(s)*43)
        cap=max(400,5*len(pos))
        if len(neg)>cap:neg=rng.choice(neg,cap,replace=False)
        ids=np.sort(np.concatenate([pos,neg]))
        XX.append(items[s][key][ids]);yy.append(y[ids])
    X=np.concatenate(XX);y=np.concatenate(yy)
    m=ExtraTreesClassifier(n_estimators=460,max_depth=15,min_samples_leaf=3,
        max_features="sqrt",class_weight="balanced",random_state=seed,n_jobs=-1)
    m.fit(X,y);return m,{"rows":len(y),"positive":int(y.sum()),"features":X.shape[1]}

def oof_scores(items,outer,key,seed):
    rows=[];ys=[]
    for i,val in enumerate(outer):
        tr=[s for s in outer if s!=val]
        m,_=fit_songs(items,tr,key,seed+i)
        sp=p1(m,items[val][key]);gp=items[val]["gmd"];sy=items[val]["sync"].copy()
        avail=np.ones(len(sy),float)
        if val=="nanairo":sy[:]=.5;avail[:]=0.
        rows.append(np.column_stack([sp,gp,sy,avail]));ys.append(items[val]["y"])
    return np.concatenate(rows),np.concatenate(ys)

def fit_fusion(items,outer,key,seed):
    X,y=oof_scores(items,outer,key,seed)
    # Candidate labels are one-to-one and extremely imbalanced.
    m=LogisticRegression(C=.5,class_weight="balanced",max_iter=1600,random_state=seed)
    m.fit(X,y);return m,{"rows":len(y),"positive":int(y.sum())}

def score_variant(items,s,variant,songs_model=None,fusion=None):
    if variant=="gmd_genre_prior":return items[s]["gmd"]
    if variant=="sync_teacher":
        z=items[s]["sync"].copy()
        if s=="nanairo":z[:]=.5
        return z
    if variant in ("songs_context","songs_context_tail"):
        key="Xctx" if variant=="songs_context" else "Xtail"
        return p1(songs_model,items[s][key])
    if variant=="score_fusion":
        sp=p1(songs_model,items[s]["Xtail"]);gp=items[s]["gmd"];sy=items[s]["sync"].copy()
        avail=np.ones(len(sy),float)
        if s=="nanairo":sy[:]=.5;avail[:]=0.
        return p1(fusion,np.column_stack([sp,gp,sy,avail]))
    raise KeyError(variant)

def select_add(d,s,item,prob,th,base_open):
    ids=[i for i,(t,p) in enumerate(zip(item["times"],prob))
         if p>=th and not ov.near(base_open,float(t),.060) and ctx.physical_ok(d,s,float(t))]
    return ctx.dedup(item["times"][ids],prob[ids]) if ids else []

def baseline_for(d,s,train,hx,hy,gx,gy,seed):
    return ctx.production_base(d,s,train,hx,hy,gx,gy,seed)

def choose_threshold(d,items,outer,variant,hx,hy,gx,gy,seed):
    cache={}
    for i,val in enumerate(outer):
        tr=[s for s in outer if s!=val]
        key="Xctx" if variant=="songs_context" else "Xtail"
        sm=None;fm=None
        if variant in ("songs_context","songs_context_tail"):
            sm,_=fit_songs(items,tr,key,seed+10+i)
        elif variant=="score_fusion":
            sm,_=fit_songs(items,tr,"Xtail",seed+10+i)
            fm,_=fit_fusion(items,tr,"Xtail",seed+100+i)
        bo,bc,bdiag=baseline_for(d,val,tr,hx,hy,gx,gy,seed+200+i)
        prob=score_variant(items,val,variant,sm,fm)
        cache[val]=(bo,bc,bdiag,prob)

    base={s:ctx.articulation(v[0],v[1],d[s]["refs"]) for s,v in cache.items()}
    b=ctx.aggregate(base);ranking=[]
    for th in THRESHOLDS:
        per={}
        for s,(bo,bc,bdiag,prob) in cache.items():
            add=select_add(d,s,items[s],prob,th,bo)
            per[s]=ctx.articulation(sorted(bo+add),bc,d[s]["refs"])
        a=ctx.aggregate(per)
        eligible=(a["open"]["precision"]>=b["open"]["precision"]-.025 and
                  a["open"]["f1"]>b["open"]["f1"] and a["macroF1"]>b["macroF1"])
        util=a["macroF1"]+.08*a["open"]["precision"]
        ranking.append({"threshold":th,"eligible":eligible,"utility":util,"summary":a})
    ranking.sort(key=lambda r:(r["eligible"],r["utility"]),reverse=True)
    best=next((r for r in ranking if r["eligible"]),None)
    return (best["threshold"] if best else 1.01),{"base":b,"ranking":ranking}

def evaluate(d,items,variant,hx,hy,gx,gy):
    per={};folds={}
    for oi,held in enumerate(SONGS):
        outer=[s for s in SONGS if s!=held]
        th,inner=choose_threshold(d,items,outer,variant,hx,hy,gx,gy,17000+oi*50)
        sm=None;fm=None;train={}
        if variant=="songs_context":
            sm,train=fit_songs(items,outer,"Xctx",18000+oi)
        elif variant=="songs_context_tail":
            sm,train=fit_songs(items,outer,"Xtail",18000+oi)
        elif variant=="score_fusion":
            sm,st=fit_songs(items,outer,"Xtail",18000+oi)
            fm,ft=fit_fusion(items,outer,"Xtail",19000+oi);train={"songs":st,"fusion":ft}
        bo,bc,bdiag=baseline_for(d,held,outer,hx,hy,gx,gy,16000+oi)
        prob=score_variant(items,held,variant,sm,fm)
        add=select_add(d,held,items[held],prob,th,bo)
        met=ctx.articulation(sorted(bo+add),bc,d[held]["refs"])
        per[held]=met;folds[held]={"threshold":th,"metrics":met,"base":bdiag,"train":train,
          "candidate":items[held]["info"],"selected":len(add),
          "addedTpDiagnostic":sum(ov.near(d[held]["refs"][46],t,.080) for t in add),
          "scoreMax":float(np.max(prob)) if len(prob) else 0.,
          "syncAvailable":held!="nanairo","inner":inner}
        print("SSHF_FOLD",variant,held,json.dumps({"threshold":th,"open":met["open"],
          "selected":len(add),"tpDiag":folds[held]["addedTpDiagnostic"]}),flush=True)
    return {"summary":ctx.aggregate(per),"songs":per,"folds":folds}

def main():
    d=ov.local_prepare();hx,hy,gx,gy,manifest=ov.gmd_collect()
    gmd=json.loads((MODELS/"gmd-kst/hihat-style-patterns-v1.json").read_text())
    sync=json.loads((MODELS/"open-hat-sync-nanairo-tail-v1.json").read_text())
    sos=butter(4,[5000,18000],btype="bandpass",fs=hf.SR,output="sos")
    items={s:make_item(d,s,gmd,sync,sos) for s in SONGS}

    base={}
    for i,held in enumerate(SONGS):
        tr=[s for s in SONGS if s!=held]
        bo,bc,_=baseline_for(d,held,tr,hx,hy,gx,gy,15000+i)
        base[held]=ctx.articulation(bo,bc,d[held]["refs"])
    baseline=ctx.aggregate(base)
    saved=json.loads((EXP/"results-open-hat-hf-context-rank-best-v1.json").read_text())
    prior_best=saved.get("retainedStrictSummary") or saved.get("strictVariants",{}).get("forest_context",{}).get("summary")

    out={"schema":1,
      "description":"Source-separated ranking on deterministic independent HF Open-HH candidates.",
      "baselineProductionApprox":baseline,
      "previousNonGridHFBest":prior_best,
      "sourcePolicy":{"newTrainingRowsPooled":False,
        "songs":"DruMaster-only selector",
        "gmd":"fixed genre symbolic prior under models/gmd-kst/",
        "syncNanairo":"fixed acoustic teacher; neutralized on Nanairo held-out fold",
        "fusion":"OOF source scores only"},
      "candidates":{s:items[s]["info"] for s in SONGS},"variants":{}}

    for v in ("songs_context","songs_context_tail","gmd_genre_prior","sync_teacher","score_fusion"):
        q=evaluate(d,items,v,hx,hy,gx,gy);ss=q["summary"]
        q["passesGuard"]=(ss["open"]["f1"]>baseline["open"]["f1"] and
                          ss["macroF1"]>baseline["macroF1"] and
                          ss["open"]["precision"]>=baseline["open"]["precision"]-.025)
        out["variants"][v]=q
        print("SSHF_RESULT",v,json.dumps({"passes":q["passesGuard"],"summary":ss}),flush=True)

    elig=[(q["summary"]["macroF1"],q["summary"]["open"]["f1"],k,q)
          for k,q in out["variants"].items() if q["passesGuard"]]
    best=max(elig) if elig else None
    out["retainedStrict"]=best[2] if best else "none"
    out["retainedStrictSummary"]=best[3]["summary"] if best else baseline
    out["guard"]={"kickSnareTomChanged":False,"existingNotesRemoved":False,
      "operation":"only add high-confidence GM46 rescue candidates"}
    (EXP/"results-open-hat-source-separated-hf-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("SSHF_RETAINED",out["retainedStrict"],json.dumps(out["retainedStrictSummary"]),flush=True)

if __name__=="__main__":main()
