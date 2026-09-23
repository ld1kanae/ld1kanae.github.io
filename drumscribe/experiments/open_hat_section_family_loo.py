"""Arrangement-family Open-HH rescue on the independent HF candidate stream.

Source roles remain separate:
- DruMaster songs: other-song LOO acoustic/context labels.
- offvocal: prediction-side structural family groups from canonical arrangement/index.js.
- GMD v3: fixed genre recurrence/boundary priors only.
- synchronized Nanairo: not pooled into training rows here.
Only GM46 rescue events are added; K/S/T and existing metal notes are untouched.
"""
from __future__ import annotations
import importlib.util,json,math,subprocess,tempfile
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.signal import butter
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";MODELS=ROOT/"drumscribe/models"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
THRESHOLDS=[.50,.56,.62,.68,.74,.80,.86,.90,.93,.96,.98,.995,1.01]
BASE_SEED=41000

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
choke=loadmod("secfam_choke",EXP/"open_hat_choke_gmd_sequence_loo.py")
ctx=choke.ctx;hf=choke.hf;ov=choke.ov

def p1(model,X):
    if not len(X):return np.zeros(0)
    p=model.predict_proba(X);cls=list(model.classes_)
    return p[:,cls.index(1)] if 1 in cls else np.zeros(len(X))

def analyze_sections(song,side):
    audio=ROOT/"DruMaster/songs"/song/"offvocal.mp3"
    if not audio.exists():return {"duration":0,"boundaries":[0],"sections":[],"method":"missing-offvocal"}
    opts={"analysisSampleRate":8000,"bpm":float(side.get("bpm") or 120.),
      "barPhaseSec":float(side.get("barPhaseSec") or side.get("beatPhaseSec") or 0.),
      "numerator":4,"denominator":4,"frameSec":.75,"hopSec":.375,"contextSec":4.5,
      "minSectionSec":7,"noveltyStd":.72,"maxSections":18}
    with tempfile.NamedTemporaryFile("w",suffix=".json",delete=False) as f:
        json.dump(opts,f);op=Path(f.name)
    try:
        out=subprocess.check_output(["node",str(EXP/"arrangement_cli.mjs"),str(audio),str(op)],text=True)
        return json.loads(out)
    finally:op.unlink(missing_ok=True)

def weighted_prior(gmd,weights,path,default=0.):
    num=den=0.
    for name,w in weights.items():
        cur=gmd.get("genres",{}).get(name,{})
        for key in path:
            if not isinstance(cur,dict) or key not in cur:cur=None;break
            cur=cur[key]
        try:v=float(cur)
        except (TypeError,ValueError):continue
        if math.isfinite(v):num+=float(w)*v;den+=float(w)
    return num/den if den else float(default)

def find_section(sections,t):
    if not sections:return None
    for sec in sections:
        if float(sec["startSec"])<=t<float(sec["endSec"]):return sec
    return sections[-1] if t>=float(sections[-1]["startSec"]) else sections[0]

def nearest_score(times,scores,target,tol=.085):
    if not len(times):return None
    i=int(np.searchsorted(times,target));best=None
    for j in (i-2,i-1,i,i+1,i+2):
        if 0<=j<len(times):
            d=abs(float(times[j])-float(target))
            if d<=tol and (best is None or d<best[0]):best=(d,float(scores[j]))
    return None if best is None else best[1]

def section_features(d,s,item,sections,gmd_arr,gmd_seq):
    times=np.asarray(item["times"],float);n=len(times)
    if not n:return np.zeros((0,14),np.float32),np.zeros(0),np.zeros(0),{"sections":0}
    side=d[s]["side"];bpm=float(side.get("bpm") or 120.);beat=60/max(bpm,1e-6)
    conf=np.asarray(item["Xctx"][:,26],float) if item["Xctx"].shape[1]>26 else np.zeros(n)
    groups=defaultdict(list)
    for sec in sections:groups[str(sec.get("group") or f'S{sec.get("index",0)}')].append(sec)
    gw=choke.genre_weights(gmd_seq,d[s]["hats"],side)
    pchg=weighted_prior(gmd_arr,gw,["boundary","changeFromPrev","pAnyCymbal"],0.)
    pcr=weighted_prior(gmd_arr,gw,["boundary","changeFromPrev","pCrash"],0.)
    pstart=weighted_prior(gmd_arr,gw,["boundary","sequenceStart","pAnyCymbal"],0.)
    popen=weighted_prior(gmd_arr,gw,["openRate"],.10)
    rep1=weighted_prior(gmd_arr,gw,["barRepeat","1","similar75Rate"],0.)
    rep2=weighted_prior(gmd_arr,gw,["barRepeat","2","similar75Rate"],0.)
    rep4=weighted_prior(gmd_arr,gw,["barRepeat","4","similar75Rate"],0.)
    rows=[];support=np.zeros(n,float);bpen=np.zeros(n,float)
    for i,t in enumerate(times):
        sec=find_section(sections,float(t))
        if sec is None:rows.append([0]*14);continue
        start=float(sec["startSec"]);end=float(sec["endSec"]);dur=max(end-start,beat)
        relbeat=(float(t)-start)/beat;pos=(float(t)-start)/dur
        sd=max(0.,(float(t)-start)/beat);ed=max(0.,(end-float(t))/beat)
        g=str(sec.get("group") or f'S{sec.get("index",0)}');fam=groups.get(g,[sec])
        vals=[];matched=0
        for other in fam:
            if int(other.get("index",-1))==int(sec.get("index",-2)):continue
            target=float(other["startSec"])+relbeat*beat
            if target>=float(other["endSec"])+.05:continue
            z=nearest_score(times,conf,target,.085)
            if z is not None:vals.append(z);matched+=1
        sup=float(np.mean(sorted(vals,reverse=True)[:3])) if vals else 0.;support[i]=sup
        headw=math.exp(-sd/.45);bpen[i]=headw*max(pchg,pcr,pstart)
        occ=int(sec.get("occurrence") or 1)
        rows.append([math.sin(2*math.pi*pos),math.cos(2*math.pi*pos),min(sd,8)/8,min(ed,8)/8,
          min(len(fam),4)/4,min(occ,4)/4,float(sec.get("repeatSimilarity") or 0.),sup,min(matched,3)/3,
          popen,rep1,rep2,rep4,bpen[i]])
    diag={"sections":len(sections),"labels":[x.get("label") for x in sections],
      "groups":[x.get("group") for x in sections],"occurrences":[x.get("occurrence") for x in sections],
      "genreTop":sorted(gw.items(),key=lambda q:q[1],reverse=True)[:5],
      "gmd":{"pChangeAnyCymbal":pchg,"pChangeCrash":pcr,"pSequenceStartAnyCymbal":pstart,
             "pOpen":popen,"repeatSimilar75":{"lag1":rep1,"lag2":rep2,"lag4":rep4}}}
    return np.asarray(rows,np.float32),support,bpen,diag

def make_items(d,gmd_arr,gmd_seq,sos):
    items={}
    for s in SONGS:
        print("SECFAM_PREP",s,flush=True);it=choke.prep_item(d,s,sos);arr=analyze_sections(s,d[s]["side"])
        sec,sup,bpen,diag=section_features(d,s,it,arr.get("sections",[]),gmd_arr,gmd_seq)
        it["XsectionCtx"]=np.concatenate([it["Xctx"],sec],axis=1)
        it["XsectionTail"]=np.concatenate([it["Xchoke"],sec],axis=1)
        it["familySupport"]=sup;it["boundaryPenalty"]=bpen;it["arrangement"]=diag;items[s]=it
        print("SECFAM_COUNTS",s,json.dumps({**it["info"],**diag},ensure_ascii=False),flush=True)
    return items

def fit_model(items,songs,key,seed):
    XX=[];yy=[]
    for s in songs:
        X=items[s][key];y=items[s]["y"];pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0)
        rng=np.random.default_rng(seed+SONGS.index(s)*59);cap=max(400,5*len(pos))
        if len(neg)>cap:neg=rng.choice(neg,cap,replace=False)
        ids=np.sort(np.concatenate([pos,neg]));XX.append(X[ids]);yy.append(y[ids])
    X=np.concatenate(XX);y=np.concatenate(yy)
    m=ExtraTreesClassifier(n_estimators=560,max_depth=16,min_samples_leaf=3,max_features="sqrt",
      class_weight="balanced",random_state=seed,n_jobs=-1).fit(X,y)
    return m,{"rows":len(y),"positive":int(y.sum()),"features":int(X.shape[1])}

def vkey(v):return "XsectionCtx" if v=="section_context" else "XsectionTail"
def vscore(item,p,v):
    p=np.asarray(p,float)
    if v in ("section_context","section_tail_context"):return p
    z=.78*p+.22*np.asarray(item["familySupport"],float)
    if v=="family_repeat_rank":return z
    if v=="family_boundary_rank":return z-.12*np.asarray(item["boundaryPenalty"],float)
    raise KeyError(v)

def select_add(d,s,item,score,th,base_open):
    ids=[i for i,(t,z) in enumerate(zip(item["times"],score))
      if z>=th and not ov.near(base_open,float(t),.060) and ctx.physical_ok(d,s,float(t))]
    return ctx.dedup(item["times"][ids],score[ids]) if ids else []

def base_for(d,s,train,hx,hy,gx,gy):
    return choke.baseline_cached(d,s,train,hx,hy,gx,gy,BASE_SEED+SONGS.index(s))

def choose(d,items,outer,v,hx,hy,gx,gy,seed):
    key=vkey(v);cache={}
    for i,val in enumerate(outer):
        tr=[s for s in outer if s!=val];m,_=fit_model(items,tr,key,seed+i)
        bo,bc,bd=base_for(d,val,tr,hx,hy,gx,gy);sc=vscore(items[val],p1(m,items[val][key]),v)
        cache[val]=(bo,bc,bd,sc)
    base={s:ctx.articulation(x[0],x[1],d[s]["refs"]) for s,x in cache.items()};bs=ctx.aggregate(base);ranking=[]
    for th in THRESHOLDS:
        per={}
        for s,(bo,bc,bd,sc) in cache.items():
            add=select_add(d,s,items[s],sc,th,bo);per[s]=ctx.articulation(sorted(bo+add),bc,d[s]["refs"])
        a=ctx.aggregate(per);ok=(a["open"]["precision"]>=bs["open"]["precision"]-.025 and
          a["open"]["f1"]>bs["open"]["f1"] and a["macroF1"]>bs["macroF1"])
        ranking.append({"threshold":th,"eligible":ok,"utility":a["macroF1"]+.08*a["open"]["precision"],"summary":a})
    ranking.sort(key=lambda r:(r["eligible"],r["utility"]),reverse=True);best=next((r for r in ranking if r["eligible"]),None)
    return (best["threshold"] if best else 1.01),{"base":bs,"ranking":ranking}

def evaluate(d,items,v,hx,hy,gx,gy):
    per={};folds={};key=vkey(v)
    for oi,held in enumerate(SONGS):
        outer=[s for s in SONGS if s!=held];th,inner=choose(d,items,outer,v,hx,hy,gx,gy,43000+oi*40)
        m,train=fit_model(items,outer,key,44000+oi);bo,bc,bd=base_for(d,held,outer,hx,hy,gx,gy)
        sc=vscore(items[held],p1(m,items[held][key]),v);add=select_add(d,held,items[held],sc,th,bo)
        met=ctx.articulation(sorted(bo+add),bc,d[held]["refs"]);per[held]=met
        folds[held]={"threshold":th,"metrics":met,"base":bd,"train":train,"candidate":items[held]["info"],
          "arrangement":items[held]["arrangement"],"selected":len(add),
          "addedTpDiagnostic":sum(ov.near(d[held]["refs"][46],t,.080) for t in add),
          "scoreMax":float(np.max(sc)) if len(sc) else 0.,"inner":inner}
        print("SECFAM_FOLD",v,held,json.dumps({"threshold":th,"open":met["open"],"selected":len(add),
          "tpDiag":folds[held]["addedTpDiagnostic"],"labels":items[held]["arrangement"].get("labels")},ensure_ascii=False),flush=True)
    return {"summary":ctx.aggregate(per),"songs":per,"folds":folds}

def main():
    d=ov.local_prepare();hx,hy,gx,gy,manifest=ov.gmd_collect()
    ga=json.loads((MODELS/"gmd-kst/hihat-arrangement-patterns-v3.json").read_text())
    gs=json.loads((MODELS/"gmd-kst/hihat-sequence-patterns-v2.json").read_text())
    if not ga.get("sourceSeparation",{}).get("gmdOnly"):raise RuntimeError("GMD v3 source separation violated")
    sos=butter(4,[5000,18000],btype="bandpass",fs=hf.SR,output="sos");items=make_items(d,ga,gs,sos)
    bp={}
    for held in SONGS:
        tr=[s for s in SONGS if s!=held];bo,bc,_=base_for(d,held,tr,hx,hy,gx,gy);bp[held]=ctx.articulation(bo,bc,d[held]["refs"])
    baseline=ctx.aggregate(bp)
    saved=json.loads((EXP/"results-open-hat-hf-context-rank-best-v1.json").read_text())
    prior=saved.get("retainedStrictSummary") or saved.get("strictVariants",{}).get("forest_context",{}).get("summary") or baseline
    out={"schema":1,"description":"Offvocal structural-family + GMD phrase-prior ranking on deterministic independent HF Open-HH candidates.",
      "sourcePolicy":{"trainingRowsPooled":False,"songs":"DruMaster other-song LOO acoustic/context labels only",
        "offvocal":"prediction-side canonical arrangement/index.js structure only",
        "gmd":"fixed GMD-only genre recurrence/boundary priors; no GMD rows concatenated",
        "syncNanairo":"not pooled; existing tail/choke feature design only",
        "heldChart":"score only after prediction; never section/candidate/threshold input"},
      "arrangementContract":{"group":"stable structural family (A)","label":"occurrence label (A, A-prime, A-double-prime)",
        "occurrence":"1-based occurrence within group"},
      "baselineProductionApprox":baseline,"previousNonGridHFBest":prior,
      "gmdAsset":"drumscribe/models/gmd-kst/hihat-arrangement-patterns-v3.json","variants":{}}
    for v in ("section_context","section_tail_context","family_repeat_rank","family_boundary_rank"):
        q=evaluate(d,items,v,hx,hy,gx,gy);ss=q["summary"]
        q["passesBaselineGuard"]=(ss["open"]["f1"]>baseline["open"]["f1"] and ss["macroF1"]>baseline["macroF1"] and
          ss["open"]["precision"]>=baseline["open"]["precision"]-.025)
        q["beatsPreviousBest"]=(ss["open"]["f1"]>prior["open"]["f1"] and ss["macroF1"]>prior["macroF1"] and
          ss["open"]["precision"]>=prior["open"]["precision"]-.025)
        out["variants"][v]=q
        print("SECFAM_RESULT",v,json.dumps({"baselineGuard":q["passesBaselineGuard"],"beatsPreviousBest":q["beatsPreviousBest"],"summary":ss}),flush=True)
    elig=[(q["summary"]["macroF1"],q["summary"]["open"]["f1"],name,q) for name,q in out["variants"].items() if q["beatsPreviousBest"]]
    best=max(elig) if elig else None
    out["retainedStrict"]=best[2] if best else "previous_non_grid_hf_best";out["retainedStrictSummary"]=best[3]["summary"] if best else prior
    out["guard"]={"kickSnareTomChanged":False,"existingNotesRemoved":False,
      "operation":"only add high-confidence GM46 rescue candidates","adoptionRule":"must beat saved non-grid HF best under strict nested LOO"}
    (EXP/"results-open-hat-section-family-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("SECFAM_RETAINED",out["retainedStrict"],json.dumps(out["retainedStrictSummary"]),flush=True)
if __name__=="__main__":main()
