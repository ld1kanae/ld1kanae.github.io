"""Context/ranking selector for distilled independent open-hi-hat candidates.

Goal
----
The DrumSep-distilled drums-only onset stream already covers most missing Open HH
in the hard song (diamondvirgin), but the v1 selector cannot safely choose among
thousands of peaks. This experiment changes the *selection* problem, not the
candidate generator.

Key correction
--------------
Previous candidate labels marked every peak within 80 ms of a reference Open as
positive. That can label several nearby peaks for one physical hit. Here, each
reference Open is assigned to at most ONE nearest candidate. Selection is also
deduplicated one-to-one before scoring.

Three strict chart-held-out selector hypotheses:
A forest_context
  ExtraTrees on acoustic/student features + rhythmic/event context.
B linear_context
  class-balanced logistic regression on the same features.
C forest_repeat_rank
  ExtraTrees probability fused with within-song beat/bar repetition evidence.

All are evaluated on top of the current production held-out approximation:
GMD128 base articulation + structural overlay repeat_gate_2hands. Student rescue
only ADDS GM46 and cannot remove/relabel kick/snare/tom/metal.

A fourth "guarded_rank_diagnostic" is reported as DEVELOPMENT-ONLY:
it activates only when prediction-side evidence indicates a dense missing-HH
case (large independent-candidate/current-hat ratio AND the existing structural
overlay repeat gate is active). It never reads held-out chart at inference, but
its constants are motivated by the current five-song diagnostics and therefore
are not an independent generalization estimate.
"""
from __future__ import annotations
import importlib.util,json,subprocess,tempfile
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from scipy.signal import find_peaks

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
BASE_THRESHOLD=.575
THRESHOLDS=[.42,.50,.58,.64,.70,.76,.82,.88,.92,.95,.98,1.01]

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
dist=loadmod("ctx_dist",EXP/"open_hat_drumsep_distill_loo.py")
sa=loadmod("ctx_sa",EXP/"open_hat_overlay_selfadapt.py")
ov=sa.ov;oh=sa.oh

def one_to_one_labels(times,refs,w=.080):
    y=np.zeros(len(times),np.int8);used=set()
    for r in sorted(refs):
        best=None
        for i,t in enumerate(times):
            if i in used:continue
            d=abs(float(t)-float(r))
            if d<=w and (best is None or d<best[0]):best=(d,i)
        if best is not None:
            used.add(best[1]);y[best[1]]=1
    return y

def nearest(xs,t,default=9.):
    if not xs:return default
    a=np.asarray(xs,float);return float(np.min(np.abs(a-float(t))))

def repeat_features(times,prob,bpm):
    n=len(times);out=np.zeros((n,5),np.float32)
    if not n:return out
    beat=60/max(float(bpm),1e-6)
    a=np.asarray(times,float);p=np.asarray(prob,float)
    for i,t in enumerate(a):
        vals=[];counts=0;barvals=[]
        for mult in (.5,1.,1.5,2.,4.):
            off=mult*beat
            for sign in (-1,1):
                ids=np.flatnonzero(np.abs(a-(t+sign*off))<=.065)
                ids=ids[ids!=i]
                if len(ids):
                    counts+=1;vals.append(float(np.max(p[ids])))
                    if mult==4.:barvals.append(float(np.max(p[ids])))
        vals.sort(reverse=True);barvals.sort(reverse=True)
        out[i]=[
          float(np.mean(vals[:4])) if vals else 0.,
          float(max(vals)) if vals else 0.,
          min(counts,10)/10.,
          float(np.mean(barvals[:4])) if barvals else 0.,
          min(len(barvals),8)/8.
        ]
    return out

def group_times(rows):
    by={g:[] for g in ("kick","snare","hat","tom","crash","ride","pedal_hat")}
    for t,g,p in rows:
        if g in by:by[g].append(float(t))
    return by


def build_candidates_fast(d,s,student,frameX):
    """Equivalent to dist.build_candidates, but reuses full-song frame features."""
    pp=student.predict_proba(frameX);cls=list(student.classes_)
    prob=pp[:,cls.index(1)] if 1 in cls else np.zeros(len(frameX))
    peaks,_=find_peaks(prob,height=dist.STUDENT_CANDIDATE_THRESHOLD,
      distance=max(1,round(.025*dist.SR/dist.HOP)),prominence=.015)
    times=peaks*dist.HOP/dist.SR
    keep=np.asarray([not dist.near(d[s]["hats"],t,.060) for t in times],bool)
    times=times[keep];peaks=peaks[keep]
    raw=np.stack([oh.timbre_features(d[s]["audio"],t) for t in times]) if len(times) else np.zeros((0,26),np.float32)
    norm=dist.robust_rows(raw,raw) if len(raw) else raw
    ctx=[]
    for i in peaks:
        lo=max(0,i-2);hi=min(len(prob),i+3)
        ctx.append([float(prob[i]),float(np.mean(prob[lo:hi])),float(np.max(prob[lo:hi])),
                    float(prob[max(0,i-2)]),float(prob[min(len(prob)-1,i+2)])])
    ctx=np.asarray(ctx,np.float32) if ctx else np.zeros((0,5),np.float32)
    X=np.concatenate([norm,ctx],axis=1)
    return {"times":times,"Xa":norm,"Xc":X}

def context_features(d,s,c):
    times=np.asarray(c["times"],float)
    if not len(times):return np.zeros((0,c["Xc"].shape[1]+35),np.float32),{}
    base=np.asarray(c["Xc"],np.float32)
    # Xc[26] is student peak probability; 27..30 are local probability context.
    sp=base[:,26]
    side=d[s]["side"];bpm=float(side.get("bpm") or 120.)
    beat=60/max(bpm,1e-6);bar=4*beat
    phase=float(side.get("barPhaseSec") or side.get("beatPhaseSec") or 0.)
    by=group_times(d[s]["rows"])
    rep=repeat_features(times,sp,bpm)
    rows=[]
    for i,t in enumerate(times):
        barpos=((t-phase)%bar)/beat # 0..4 beats
        prev=t-times[i-1] if i else 9.
        nxt=times[i+1]-t if i+1<len(times) else 9.
        dens25=float(np.sum(np.abs(times-t)<=.25)-1)
        dens50=float(np.sum(np.abs(times-t)<=.50)-1)
        dists=[min(nearest(by[g],t),.30)/.30 for g in ("kick","snare","hat","tom","crash","ride","pedal_hat")]
        flags=[]
        for g in ("kick","snare","hat","crash","ride"):
            z=nearest(by[g],t)
            flags.extend([1. if z<=.035 else 0.,1. if z<=.070 else 0.])
        rows.append([
          np.sin(2*np.pi*barpos),np.cos(2*np.pi*barpos),
          np.sin(4*np.pi*barpos),np.cos(4*np.pi*barpos),
          np.sin(8*np.pi*barpos),np.cos(8*np.pi*barpos),
          min(prev/beat,4.),min(nxt/beat,4.),
          min(dens25,12)/12.,min(dens50,24)/24.,
          *dists,*flags,*rep[i].tolist(),
          len(times)/max(1,len(d[s]["hats"])),
          len(d[s]["hats"])/max(1,len(d[s]["rows"]))
        ])
    X=np.concatenate([base,np.asarray(rows,np.float32)],axis=1)
    y=one_to_one_labels(times,d[s]["refs"][46])
    info={"candidateCount":len(times),"oneToOnePositive":int(y.sum()),
          "candidateHatRatio":len(times)/max(1,len(d[s]["hats"])),
          "distinctOpenCoverage":dist.greedy_coverage(times,d[s]["refs"][46])}
    return X,info

def fit_selector(items,songs,kind,seed):
    XX=[];yy=[]
    for s in songs:
        X=items[s]["X"];y=items[s]["y"]
        pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0)
        rng=np.random.default_rng(seed+SONGS.index(s)*37)
        cap=max(400,5*len(pos))
        if len(neg)>cap:neg=rng.choice(neg,cap,replace=False)
        ids=np.sort(np.concatenate([pos,neg]))
        XX.append(X[ids]);yy.append(y[ids])
    X=np.concatenate(XX);y=np.concatenate(yy)
    if kind=="linear_context":
        model=make_pipeline(StandardScaler(),
          LogisticRegression(C=.35,class_weight="balanced",max_iter=1200,random_state=seed))
    else:
        model=ExtraTreesClassifier(n_estimators=420,max_depth=15,min_samples_leaf=3,
          max_features="sqrt",class_weight="balanced",random_state=seed,n_jobs=-1)
    model.fit(X,y)
    return model,{"rows":len(y),"positive":int(y.sum()),"features":X.shape[1]}

def p1(model,X):
    if not len(X):return np.zeros(0)
    p=model.predict_proba(X)
    cls=list(model.classes_ if hasattr(model,"classes_") else model[-1].classes_)
    return p[:,cls.index(1)] if 1 in cls else np.zeros(len(X))

def physical_ok(d,s,t):
    hands=sum(1 for u,g,p in d[s]["rows"]
      if g in ("snare","tom","hat","crash","ride") and abs(float(u)-float(t))<=.035)
    return hands<2

def dedup(times,scores,minsep=.060):
    ids=np.argsort(-np.asarray(scores,float));keep=[]
    for i in ids:
        t=float(times[i])
        if all(abs(t-u)>=minsep for u in keep):keep.append(t)
    return sorted(keep)

def production_base(d,s,train,hx,hy,gx,gy,seed):
    bm=ov.train_base(d,train,hx,hy)
    hp=ov.probs(bm,d[s]["X"]["timbre_norm"])
    bo=[t for t,p in zip(d[s]["hats"],hp) if p>=BASE_THRESHOLD]
    bc=[t for t,p in zip(d[s]["hats"],hp) if p<BASE_THRESHOLD]

    om,tinfo=ov.train_overlay(d,train,gx,gy,"C_metal_snare_kick",seed)
    oo=d[s]["overlay"];ot=np.asarray([a[0] for a in oo["anchors"]],float)
    op=ov.probs(om,oo["X"]);bpm=float(d[s]["side"].get("bpm") or 0.)
    mask,adapt=sa.select("repeat_gate",ot,op,bpm)
    add=[];physicalSkipped=0
    for t,yes in zip(ot,mask):
        if not yes or ov.near(bo,float(t),.060):continue
        if physical_ok(d,s,float(t)):add.append(float(t))
        else:physicalSkipped+=1
    return sorted(bo+add),bc,{"baseOpen":len(bo),"overlayAdded":len(add),"overlayGate":bool(adapt.get("active")),
      "overlayAdapt":adapt,"physicalSkipped":physicalSkipped,"overlayTrain":tinfo}

def select_student(d,s,item,model,variant,param,base_open,base_diag):
    prob=p1(model,item["X"]);times=np.asarray(item["times"],float)
    # Last context block contains repeat mean/max/count/bar mean/bar count at
    # positions [-7:-2], followed by song-level ratios.
    rep=item["X"][:,-7]
    barrep=item["X"][:,-4]
    if variant=="forest_repeat_rank":
        score=.68*prob+.20*rep+.12*barrep
    else:score=prob.copy()

    if variant=="guarded_rank_diagnostic":
        active=(item["info"]["candidateHatRatio"]>=10.0 and base_diag.get("overlayGate",False))
        if not active:return [],{"active":False,"probMax":float(np.max(prob)) if len(prob) else 0.}
        th=max(.58,float(np.percentile(score,97.5)))
    else:
        th=float(param);active=th<=1.

    ids=[i for i,(t,z) in enumerate(zip(times,score))
         if z>=th and not ov.near(base_open,float(t),.060) and physical_ok(d,s,float(t))]
    sel=dedup(times[ids],score[ids]) if ids else []
    return sel,{"active":bool(active),"threshold":th,"selected":len(sel),
      "probMax":float(np.max(prob)) if len(prob) else 0.,"scoreMax":float(np.max(score)) if len(score) else 0.,
      "q95":float(np.percentile(score,95)) if len(score) else 0.,
      "q99":float(np.percentile(score,99)) if len(score) else 0.}

def articulation(openp,closedp,refs):
    return oh.articulation_metrics(sorted(openp),sorted(closedp),refs)

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

def build_outer_items(d,teacher,outer,targets,seed,frame_cache):
    student,sinfo=dist.fit_student(teacher,outer,seed)
    items={}
    for s in targets:
        c=build_candidates_fast(d,s,student,frame_cache[s])
        X,info=context_features(d,s,c)
        items[s]={"times":c["times"],"X":X,"y":one_to_one_labels(c["times"],d[s]["refs"][46]),"info":info}
    return items,sinfo

def inner_choose(d,items,outer,kind,hx,hy,gx,gy,variant,seed):
    cache={}
    for i,val in enumerate(outer):
        tr=[s for s in outer if s!=val]
        model,minfo=fit_selector(items,tr,kind,seed+i)
        bo,bc,bdiag=production_base(d,val,tr,hx,hy,gx,gy,seed+100+i)
        cache[val]=(model,bo,bc,bdiag,minfo)
    base={s:articulation(v[1],v[2],d[s]["refs"]) for s,v in cache.items()}
    b=aggregate(base);rows=[]
    for th in THRESHOLDS:
        per={}
        for s,(model,bo,bc,bdiag,_) in cache.items():
            add,_=select_student(d,s,items[s],model,variant,th,bo,bdiag)
            per[s]=articulation(sorted(bo+add),bc,d[s]["refs"])
        a=aggregate(per)
        eligible=(a["open"]["precision"]>=b["open"]["precision"]-.025 and
                  a["open"]["f1"]>b["open"]["f1"] and a["macroF1"]>b["macroF1"])
        util=a["macroF1"]+.08*a["open"]["precision"]
        rows.append((eligible,util,th,a))
    rows.sort(key=lambda x:(x[0],x[1]),reverse=True)
    best=next((x for x in rows if x[0]),None)
    return (best[2] if best else 1.01),{"base":b,"ranking":[{"threshold":r[2],"eligible":r[0],
      "utility":r[1],"summary":r[3]} for r in rows]}

def evaluate_all(d,teacher,hx,hy,gx,gy,frame_cache):
    specs=[("forest_context","forest_context"),("linear_context","linear_context"),("forest_repeat_rank","forest_context")]
    per={v:{} for v,_ in specs};folds={v:{} for v,_ in specs}
    gper={};gfolds={}
    for oi,held in enumerate(SONGS):
        outer=[s for s in SONGS if s!=held]
        items,sinfo=build_outer_items(d,teacher,outer,[*outer,held],5000+oi,frame_cache)
        bo,bc,bdiag=production_base(d,held,outer,hx,hy,gx,gy,8000+oi)
        trained={}
        for vi,(variant,kind) in enumerate(specs):
            th,inner=inner_choose(d,items,outer,kind,hx,hy,gx,gy,variant,6000+oi*30+vi*7)
            key=kind
            if key not in trained:trained[key]=fit_selector(items,outer,kind,7000+oi+vi)
            model,minfo=trained[key]
            add,sdiag=select_student(d,held,items[held],model,variant,th,bo,bdiag)
            m=articulation(sorted(bo+add),bc,d[held]["refs"])
            per[variant][held]=m;folds[variant][held]={"threshold":th,"metrics":m,"base":bdiag,"selector":sdiag,
              "candidate":items[held]["info"],"studentTrain":sinfo,"selectorTrain":minfo,"inner":inner,
              "studentAddedTpDiagnostic":sum(ov.near(d[held]["refs"][46],t,.080) for t in add)}
            print("CTX_FOLD",variant,held,json.dumps({"threshold":th,"open":m["open"],
              "add":len(add),"tpDiag":folds[variant][held]["studentAddedTpDiagnostic"],"candidate":items[held]["info"]}),flush=True)

        # Development-only guarded rank reuses the fold's forest model and candidates.
        model,minfo=trained["forest_context"]
        add,sdiag=select_student(d,held,items[held],model,"guarded_rank_diagnostic",None,bo,bdiag)
        m=articulation(sorted(bo+add),bc,d[held]["refs"])
        gper[held]=m;gfolds[held]={"metrics":m,"base":bdiag,"selector":sdiag,
          "candidate":items[held]["info"],"studentAddedTpDiagnostic":sum(ov.near(d[held]["refs"][46],t,.080) for t in add)}
        print("CTX_GUARD",held,json.dumps({"open":m["open"],"add":len(add),
          "tpDiag":gfolds[held]["studentAddedTpDiagnostic"],"candidate":items[held]["info"],"selector":sdiag}),flush=True)
    strict={v:{"summary":aggregate(per[v]),"songs":per[v],"folds":folds[v]} for v,_ in specs}
    guarded={"summary":aggregate(gper),"songs":gper,"folds":gfolds,
      "warning":"Development-only self-adaptive gate; not an independent future-song estimate."}
    return strict,guarded

def main():
    from mdxnet_infer import MDX23CInference
    d=ov.local_prepare()
    for s in SONGS:d[s]["audio"]=dist.decode_mono(s)
    hx,hy,gx,gy,manifest=ov.gmd_collect()

    engine=MDX23CInference.from_pretrained("drumsep-6stem",device="cpu")
    teacher={}
    with tempfile.TemporaryDirectory() as td:
      tmp=Path(td)
      for s in SONGS:
        X,y,meta=dist.make_teacher_data(engine,s,tmp)
        teacher[s]={"X":X,"y":y,"segments":meta}

    print("PRECOMPUTE_FULL_FRAME_FEATURES",flush=True)
    frame_cache={s:dist.frame_matrix(d[s]["audio"]) for s in SONGS}

    # Current production held-out approximation.
    base={}
    for i,held in enumerate(SONGS):
        tr=[s for s in SONGS if s!=held]
        bo,bc,dg=production_base(d,held,tr,hx,hy,gx,gy,4000+i)
        base[held]=articulation(bo,bc,d[held]["refs"])
    baseline=aggregate(base)

    out={"schema":1,"description":"One-to-one contextual ranking over DrumSep-distilled independent HH candidates.",
      "baselineProductionApprox":baseline,
      "labelPolicy":"one nearest independent candidate per reference Open within 80 ms",
      "strictVariants":{}}
    strict,gd=evaluate_all(d,teacher,hx,hy,gx,gy,frame_cache)
    for variant,q in strict.items():
        ss=q["summary"]
        q["passesGuard"]=(ss["open"]["f1"]>baseline["open"]["f1"] and
          ss["macroF1"]>baseline["macroF1"] and ss["open"]["precision"]>=baseline["open"]["precision"]-.025)
        out["strictVariants"][variant]=q
        print("CTX_RESULT",variant,json.dumps({"passes":q["passesGuard"],"summary":ss}),flush=True)

    gs=gd["summary"]
    gd["passesDevelopmentGuard"]=(gs["open"]["f1"]>baseline["open"]["f1"] and
      gs["macroF1"]>baseline["macroF1"] and gs["open"]["precision"]>=baseline["open"]["precision"]-.025)
    out["guardedRankDiagnostic"]=gd
    elig=[q|{"name":k} for k,q in out["strictVariants"].items() if q["passesGuard"]]
    best=max(elig,key=lambda q:(q["summary"]["macroF1"],q["summary"]["open"]["f1"])) if elig else None
    out["retainedStrict"]=best["name"] if best else "none"
    out["retainedStrictSummary"]=best["summary"] if best else baseline
    out["developmentCandidate"]="guarded_rank_diagnostic" if gd["passesDevelopmentGuard"] else "none"
    (EXP/"results-open-hat-context-rank-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("CTX_RETAINED",out["retainedStrict"],"DEV",out["developmentCandidate"],flush=True)

if __name__=="__main__":main()
