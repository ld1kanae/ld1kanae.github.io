"""Fast contextual selector over the audio-only 5–18 kHz independent HH stream.

No DrumSep at inference or training. Uses binary-search rhythmic neighborhoods and 8th/16th/32nd grid residuals from context_rank. Candidate generation is deterministic from
held-out drums.mp3, then chart labels are used only to train selectors on the
other songs and to score the held-out song.

The key label correction is one physical reference Open -> at most one nearest
candidate, preventing clustered peaks around one hit from all becoming positives.

Variants mirror the DrumSep-student context study:
- forest_context
- linear_context
- forest_repeat_rank
plus the same development-only guarded rank diagnostic.
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
hf=loadmod("hfctx_hf",EXP/"open_hat_hf_offvocal_loo.py")
ctx=loadmod("hfctx_ctx",EXP/"open_hat_context_rank_loo.py")
ov=ctx.ov;oh=ctx.oh

def sig(x):
    x=np.clip(np.asarray(x,float),-12,12)
    return 1/(1+np.exp(-x))

def make_item(d,s):
    print("HFCTX_PREP",s,flush=True)
    x=hf.decode(s,"drums.mp3")
    flux,hlev,bands=hf.hf_stream(x)
    times,score,ids=hf.peak_candidates(flux,hlev)
    duration=len(x)/hf.SR
    valid=times<duration-.7
    times=times[valid];ids=ids[valid]
    keep=np.asarray([not hf.near(d[s]["hats"],t,.060) for t in times],bool)
    times=times[keep];ids=ids[keep]
    extra=hf.candidate_extra(times,ids,flux,hlev,bands)
    acoustic=hf.extract_at(x,times,d[s]["X"]["timbre"])
    fz=hf.robust1(flux);hz=hf.robust1(hlev)
    sc=np.asarray(score)[ids] if len(ids) else np.zeros(0)
    aux=[]
    for i,z in zip(ids,sc):
        lo=max(0,i-2);hi=min(len(score),i+3)
        aux.append([sig(z),sig(np.mean(score[lo:hi])),sig(np.max(score[lo:hi])),
                    sig(hz[i]),sig(fz[i])])
    aux=np.asarray(aux,np.float32) if aux else np.zeros((0,5),np.float32)
    # Keep acoustic 26 first; ctx.context_features treats column 26 as candidate confidence.
    base=np.concatenate([acoustic,aux,extra],axis=1)
    fake={"times":times,"Xc":base}
    X,info=ctx.context_features(d,s,fake)
    y=ctx.one_to_one_labels(times,d[s]["refs"][46])
    info={**info,"oneToOnePositive":int(y.sum())}
    print("HFCTX_COUNTS",s,json.dumps(info),flush=True)
    return {"times":times,"X":X,"y":y,"info":info}

def evaluate(d,items,hx,hy,gx,gy,variant,kind):
    per={};folds={}
    for oi,held in enumerate(SONGS):
        outer=[s for s in SONGS if s!=held]
        th,inner=ctx.inner_choose(d,items,outer,kind,hx,hy,gx,gy,variant,12000+oi*30)
        model,minfo=ctx.fit_selector(items,outer,kind,13000+oi)
        bo,bc,bdiag=ctx.production_base(d,held,outer,hx,hy,gx,gy,11000+oi)
        add,sdiag=ctx.select_student(d,held,items[held],model,variant,th,bo,bdiag)
        m=ctx.articulation(sorted(bo+add),bc,d[held]["refs"])
        per[held]=m;folds[held]={"threshold":th,"metrics":m,"base":bdiag,"selector":sdiag,
          "candidate":items[held]["info"],"selectorTrain":minfo,"inner":inner,
          "studentAddedTpDiagnostic":sum(ov.near(d[held]["refs"][46],t,.080) for t in add)}
        print("HFCTX_FOLD",variant,held,json.dumps({"threshold":th,"open":m["open"],
          "add":len(add),"tpDiag":folds[held]["studentAddedTpDiagnostic"],"candidate":items[held]["info"]}),flush=True)
    return {"summary":ctx.aggregate(per),"songs":per,"folds":folds}

def guarded(d,items,hx,hy,gx,gy):
    per={};folds={}
    for oi,held in enumerate(SONGS):
        outer=[s for s in SONGS if s!=held]
        model,minfo=ctx.fit_selector(items,outer,"forest_context",15000+oi)
        bo,bc,bdiag=ctx.production_base(d,held,outer,hx,hy,gx,gy,11000+oi)
        add,sdiag=ctx.select_student(d,held,items[held],model,"guarded_rank_diagnostic",None,bo,bdiag)
        m=ctx.articulation(sorted(bo+add),bc,d[held]["refs"])
        per[held]=m;folds[held]={"metrics":m,"base":bdiag,"selector":sdiag,
          "candidate":items[held]["info"],"studentAddedTpDiagnostic":sum(ov.near(d[held]["refs"][46],t,.080) for t in add)}
        print("HFCTX_GUARD",held,json.dumps({"open":m["open"],"add":len(add),
          "tpDiag":folds[held]["studentAddedTpDiagnostic"],"selector":sdiag}),flush=True)
    return {"summary":ctx.aggregate(per),"songs":per,"folds":folds,
      "warning":"Development-only gate constants; not an independent future-song estimate."}

def main():
    d=ov.local_prepare();hx,hy,gx,gy,manifest=ov.gmd_collect()
    items={s:make_item(d,s) for s in SONGS}

    base={}
    for i,held in enumerate(SONGS):
        tr=[s for s in SONGS if s!=held]
        bo,bc,dg=ctx.production_base(d,held,tr,hx,hy,gx,gy,11000+i)
        base[held]=ctx.articulation(bo,bc,d[held]["refs"])
    baseline=ctx.aggregate(base)

    out={"schema":1,"description":"One-to-one contextual ranking on deterministic drums-only HF candidate stream.",
      "baselineProductionApprox":baseline,"candidates":{s:items[s]["info"] for s in SONGS},"strictVariants":{}}
    specs=[("forest_context","forest_context"),("linear_context","linear_context"),("forest_repeat_rank","forest_context")]
    for v,k in specs:
        q=evaluate(d,items,hx,hy,gx,gy,v,k);ss=q["summary"]
        q["passesGuard"]=(ss["open"]["f1"]>baseline["open"]["f1"] and ss["macroF1"]>baseline["macroF1"]
          and ss["open"]["precision"]>=baseline["open"]["precision"]-.025)
        out["strictVariants"][v]=q
        print("HFCTX_RESULT",v,json.dumps({"passes":q["passesGuard"],"summary":ss}),flush=True)
    gd=guarded(d,items,hx,hy,gx,gy);gs=gd["summary"]
    gd["passesDevelopmentGuard"]=(gs["open"]["f1"]>baseline["open"]["f1"] and gs["macroF1"]>baseline["macroF1"]
      and gs["open"]["precision"]>=baseline["open"]["precision"]-.025)
    out["guardedRankDiagnostic"]=gd
    elig=[q|{"name":k} for k,q in out["strictVariants"].items() if q["passesGuard"]]
    best=max(elig,key=lambda q:(q["summary"]["macroF1"],q["summary"]["open"]["f1"])) if elig else None
    out["retainedStrict"]=best["name"] if best else "none"
    out["retainedStrictSummary"]=best["summary"] if best else baseline
    out["developmentCandidate"]="guarded_rank_diagnostic" if gd["passesDevelopmentGuard"] else "none"
    (EXP/"results-open-hat-hf-context-rank-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("HFCTX_RETAINED",out["retainedStrict"],"DEV",out["developmentCandidate"],flush=True)

if __name__=="__main__":main()
