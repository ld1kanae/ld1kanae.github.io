"""Open-HH transition/subtype ranking with policy-correct Closed=42+44 scoring.

This iteration tests the user's two acoustic/sequence modes explicitly:
- O->O: sustained/open sequence, where HF tail may continue into the next Open.
- O->C: Open followed by Closed/Pedal, where the tail is expected to be choked.

Strict source separation:
- DruMaster songs: other-song LOO audio/chart labels only.
- offvocal: prediction-side canonical structural family context only.
- GMD v3: fixed genre-conditioned O->O/O->C and recurrence priors only.
- synchronized Nanairo: no rows pooled; prior feature design only.

Only GM46 rescue candidates are added. Existing notes and K/S/T are untouched.
Primary articulation policy: Open=46, Closed=42+44.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";MODELS=ROOT/"drumscribe/models"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
THRESHOLDS=[.42,.48,.54,.60,.66,.72,.78,.84,.89,.93,.96,.98,.995,1.01]
BASE_SEED=51000

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
secv1=loadmod("sectrans_v1",EXP/"open_hat_section_family_loo.py")
choke=secv1.choke;ctx=secv1.ctx;hf=secv1.hf;ov=secv1.ov;oh=ctx.oh

def truth_hats(song):
    rows=[(float(t),int(p)) for t,g,p in oh.truth(song) if int(p) in (42,44,46)]
    rows.sort()
    out=[]
    for t,p in rows:
        if out and abs(t-out[-1][0])<=.003:
            # One physical hat instant: Open wins, otherwise preserve pedal/closed as Closed.
            if p==46:out[-1]=(out[-1][0],46)
        else:out.append((t,p))
    return out

def policy_refs(song):
    h=truth_hats(song)
    return {"open":[t for t,p in h if p==46],"closed":[t for t,p in h if p in (42,44)]}

def greedy(pred,ref,w=.080):
    pred=sorted(map(float,pred));ref=sorted(map(float,ref));used=set();tp=0
    for x in pred:
        i=int(np.searchsorted(ref,x));cand=[]
        for j in (i-2,i-1,i,i+1,i+2):
            if 0<=j<len(ref) and j not in used and abs(x-ref[j])<=w:cand.append((abs(x-ref[j]),j))
        if cand:
            _,j=min(cand);used.add(j);tp+=1
    return tp

def prf(pred,ref):
    tp=greedy(pred,ref);p=len(pred);r=len(ref)
    return {"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,
      "recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}

def pedal_pred(d,s):
    return sorted(float(t) for t,g,p in d[s]["rows"] if g=="pedal_hat" or int(p)==44)

def articulation44(d,s,openp,closed_stick):
    refs=policy_refs(s);op=prf(openp,refs["open"]);cl=prf(sorted(list(closed_stick)+pedal_pred(d,s)),refs["closed"])
    return {"open":op,"closed":cl,"macroF1":.5*(op["f1"]+cl["f1"])}

def aggregate(per):
    z=defaultdict(int)
    for m in per.values():
        for c in ("open","closed"):
            q=m[c];z[c+"t"]+=q["tp"];z[c+"p"]+=q["predicted"];z[c+"r"]+=q["reference"]
    o={}
    for c in ("open","closed"):
        tp,p,r=z[c+"t"],z[c+"p"],z[c+"r"]
        o[c]={"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,
          "recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}
    o["macroF1"]=.5*(o["open"]["f1"]+o["closed"]["f1"]);return o

def one_to_one_subtype(times,truth):
    y=np.zeros(len(times),np.int8);used=set()
    opens=[(i,t) for i,(t,p) in enumerate(truth) if p==46]
    for hi,r in opens:
        best=None
        for i,t in enumerate(times):
            if i in used:continue
            d=abs(float(t)-float(r))
            if d<=.080 and (best is None or d<best[0]):best=(d,i)
        if best is None:continue
        nxt=None
        for j in range(hi+1,len(truth)):
            if truth[j][0]>r+.003:nxt=truth[j][1];break
        y[best[1]]=2 if nxt==46 else 1
        used.add(best[1])
    return y

def section_vector_features(times,sections):
    groups=defaultdict(list)
    for s in sections:groups[str(s.get("group"))].append(s)
    rows=[]
    for t in times:
        sec=secv1.find_section(sections,float(t))
        if not sec:rows.append([0.]*14);continue
        v=np.asarray(sec.get("vector") or [0.]*7,float)
        fam=groups.get(str(sec.get("group")),[])
        vv=[np.asarray(x.get("vector") or [0.]*len(v),float) for x in fam]
        mu=np.mean(vv,axis=0) if vv else np.zeros_like(v)
        rows.append(np.concatenate([v,v-mu]).tolist())
    return np.asarray(rows,np.float32) if rows else np.zeros((0,14),np.float32)

def genre_transition_prior(gmd,weights):
    oo=oc=o=c=0.
    for name,w in weights.items():
        g=gmd.get("genres",{}).get(name,{})
        tr=g.get("transitions",{})
        oo+=w*float(tr.get("O>O",0));oc+=w*float(tr.get("O>C",0))
        o+=w*float(g.get("openHits",0));c+=w*float(g.get("closedHits",0))
    poo=oo/(oo+oc) if oo+oc else .3
    popen=o/(o+c) if o+c else .1
    return float(poo),float(1-poo),float(popen)

def make_items(d,gmd_arr,gmd_seq,sos):
    items={}
    for s in SONGS:
        print("SECTRANS_PREP",s,flush=True)
        it=choke.prep_item(d,s,sos)
        arr=secv1.analyze_sections(s,d[s]["side"]);sections=arr.get("sections",[])
        sf,support,bpen,diag=secv1.section_features(d,s,it,sections,gmd_arr,gmd_seq)
        vf=section_vector_features(it["times"],sections)
        gw=choke.genre_weights(gmd_seq,d[s]["hats"],d[s]["side"])
        poo,poc,popen=genre_transition_prior(gmd_arr,gw)
        prior=np.tile(np.asarray([poo,poc,popen],np.float32),(len(it["times"]),1))
        X=np.concatenate([it["Xchoke"],sf,vf,prior],axis=1)
        y3=one_to_one_subtype(it["times"],truth_hats(s))
        it.update({"Xtrans":X,"y3":y3,"familySupportRaw":support,"sections":sections,
          "transitionPrior":{"pOOgivenO":poo,"pOCgivenO":poc,"pOpen":popen},
          "arrangement":diag})
        it["info"]={**it["info"],"subtypeOC":int(np.sum(y3==1)),"subtypeOO":int(np.sum(y3==2)),
          "sectionVectorFeatures":int(vf.shape[1]),"transitionPrior":it["transitionPrior"]}
        items[s]=it
        print("SECTRANS_COUNTS",s,json.dumps(it["info"],ensure_ascii=False),flush=True)
    return items

def sample_rows(item,seed):
    y=item["y3"];pos=np.flatnonzero(y>0);neg=np.flatnonzero(y==0);rng=np.random.default_rng(seed)
    cap=max(500,6*len(pos))
    if len(neg)>cap:neg=rng.choice(neg,cap,replace=False)
    return np.sort(np.concatenate([pos,neg]))

def fit_multi(items,songs,seed):
    XX=[];yy=[];counts=defaultdict(int)
    for s in songs:
        ids=sample_rows(items[s],seed+SONGS.index(s)*67);XX.append(items[s]["Xtrans"][ids]);yy.append(items[s]["y3"][ids])
        for q in items[s]["y3"][ids]:counts[int(q)]+=1
    X=np.concatenate(XX);y=np.concatenate(yy)
    m=ExtraTreesClassifier(n_estimators=620,max_depth=17,min_samples_leaf=3,max_features="sqrt",
      class_weight="balanced",random_state=seed,n_jobs=-1).fit(X,y)
    return m,{"rows":len(y),"features":int(X.shape[1]),"classes":{str(k):v for k,v in counts.items()}}

def fit_binary(items,songs,seed):
    XX=[];yy=[]
    for s in songs:
        ids=sample_rows(items[s],seed+SONGS.index(s)*71);XX.append(items[s]["Xtrans"][ids]);yy.append((items[s]["y3"][ids]>0).astype(np.int8))
    X=np.concatenate(XX);y=np.concatenate(yy)
    m=ExtraTreesClassifier(n_estimators=620,max_depth=17,min_samples_leaf=3,max_features="sqrt",
      class_weight="balanced",random_state=seed,n_jobs=-1).fit(X,y)
    return m,{"rows":len(y),"features":int(X.shape[1]),"positive":int(y.sum())}

def probs(model,X):
    p=model.predict_proba(X);cls=list(model.classes_)
    out=np.zeros((len(X),3),float)
    for j,c in enumerate(cls):
        if int(c) in (0,1,2):out[:,int(c)]=p[:,j]
    return out

def base_open_prob(model,item,kind):
    p=probs(model,item["Xtrans"])
    return p[:,1]+p[:,2] if kind=="multi" else p[:,1]

def model_family_support(item,p):
    times=np.asarray(item["times"],float);sections=item["sections"];groups=defaultdict(list)
    for sec in sections:groups[str(sec.get("group"))].append(sec)
    sup=np.zeros(len(times),float);cnt=np.zeros(len(times),float)
    for i,t in enumerate(times):
        sec=secv1.find_section(sections,float(t))
        if not sec:continue
        beat=60/max(float(item["sideBpm"]),1e-6);rel=(float(t)-float(sec["startSec"]))/beat
        vals=[]
        for other in groups.get(str(sec.get("group")),[]):
            if int(other.get("index",-1))==int(sec.get("index",-2)):continue
            target=float(other["startSec"])+rel*beat
            if target>=float(other["endSec"])+.05:continue
            z=secv1.nearest_score(times,p,target,.080)
            if z is not None:vals.append(z)
        if vals:sup[i]=float(np.mean(sorted(vals,reverse=True)[:3]));cnt[i]=min(len(vals),3)/3
    return sup,cnt

def score_variant(item,model,variant):
    kind="binary" if variant=="binary_section_vector" else "multi"
    p=base_open_prob(model,item,kind)
    if variant in ("binary_section_vector","transition_multiclass"):return p,{}
    sup,cnt=model_family_support(item,p)
    if variant=="transition_family_consensus":
        # Geometric consensus: a peer can help only if the candidate itself is plausible.
        peer=np.sqrt(np.clip(p*sup,0,1));score=np.where(cnt>0,.78*p+.22*peer,p)
    elif variant=="transition_family_strict":
        # Conservative listwise filter for repeated families.
        score=np.where(cnt>0,p*(.82+.18*sup),p)
    else:raise KeyError(variant)
    return score,{"peerSupportMean":float(np.mean(sup)),"peerAvailable":int(np.sum(cnt>0))}

def select_add(d,s,item,score,th,base_open):
    ids=[i for i,(t,z) in enumerate(zip(item["times"],score))
      if z>=th and not ov.near(base_open,float(t),.060) and ctx.physical_ok(d,s,float(t))]
    return ctx.dedup(item["times"][ids],score[ids]) if ids else []

def base_for(d,s,train,hx,hy,gx,gy):
    return choke.baseline_cached(d,s,train,hx,hy,gx,gy,BASE_SEED+SONGS.index(s))

def choose(d,items,outer,variant,hx,hy,gx,gy,seed):
    kind="binary" if variant=="binary_section_vector" else "multi";cache={}
    for i,val in enumerate(outer):
        tr=[s for s in outer if s!=val];m,_=(fit_binary(items,tr,seed+i) if kind=="binary" else fit_multi(items,tr,seed+i))
        bo,bc,bd=base_for(d,val,tr,hx,hy,gx,gy);sc,_=score_variant(items[val],m,variant);cache[val]=(bo,bc,sc)
    base={s:articulation44(d,s,x[0],x[1]) for s,x in cache.items()};bs=aggregate(base);ranking=[]
    for th in THRESHOLDS:
        per={}
        for s,(bo,bc,sc) in cache.items():
            add=select_add(d,s,items[s],sc,th,bo);per[s]=articulation44(d,s,sorted(bo+add),bc)
        a=aggregate(per);ok=(a["open"]["precision"]>=bs["open"]["precision"]-.025 and a["open"]["f1"]>bs["open"]["f1"] and a["macroF1"]>bs["macroF1"])
        ranking.append({"threshold":th,"eligible":ok,"utility":a["macroF1"]+.08*a["open"]["precision"],"summary":a})
    ranking.sort(key=lambda r:(r["eligible"],r["utility"]),reverse=True);best=next((r for r in ranking if r["eligible"]),None)
    return (best["threshold"] if best else 1.01),{"base":bs,"ranking":ranking}

def evaluate(d,items,variant,hx,hy,gx,gy):
    kind="binary" if variant=="binary_section_vector" else "multi";per={};folds={}
    for oi,held in enumerate(SONGS):
        outer=[s for s in SONGS if s!=held];th,inner=choose(d,items,outer,variant,hx,hy,gx,gy,53000+oi*40)
        m,train=(fit_binary(items,outer,54000+oi) if kind=="binary" else fit_multi(items,outer,54000+oi))
        bo,bc,bd=base_for(d,held,outer,hx,hy,gx,gy);sc,sd=score_variant(items[held],m,variant)
        add=select_add(d,held,items[held],sc,th,bo);met=articulation44(d,held,sorted(bo+add),bc);per[held]=met
        folds[held]={"threshold":th,"metrics":met,"base":bd,"train":train,"selected":len(add),
          "addedTpDiagnostic":sum(ov.near(policy_refs(held)["open"],t,.080) for t in add),
          "scoreMax":float(np.max(sc)) if len(sc) else 0.,"scoreDiag":sd,"candidate":items[held]["info"],
          "arrangementLabels":[x.get("label") for x in items[held]["sections"]],"inner":inner}
        print("SECTRANS_FOLD",variant,held,json.dumps({"threshold":th,"open":met["open"],"closed":met["closed"],
          "selected":len(add),"tpDiag":folds[held]["addedTpDiagnostic"]},ensure_ascii=False),flush=True)
    return {"summary":aggregate(per),"songs":per,"folds":folds}

def main():
    d=ov.local_prepare()
    for s in SONGS:
        # Expose BPM to model-family support without touching upstream item contracts.
        pass
    hx,hy,gx,gy,manifest=ov.gmd_collect()
    ga=json.loads((MODELS/"gmd-kst/hihat-arrangement-patterns-v3.json").read_text())
    gs=json.loads((MODELS/"gmd-kst/hihat-sequence-patterns-v2.json").read_text())
    from scipy.signal import butter
    sos=butter(4,[5000,18000],btype="bandpass",fs=hf.SR,output="sos");items=make_items(d,ga,gs,sos)
    for s in SONGS:items[s]["sideBpm"]=float(d[s]["side"].get("bpm") or 120.)

    baseper={}
    for held in SONGS:
        tr=[s for s in SONGS if s!=held];bo,bc,_=base_for(d,held,tr,hx,hy,gx,gy);baseper[held]=articulation44(d,held,bo,bc)
    baseline=aggregate(baseper)

    saved=json.loads((EXP/"results-open-hat-hf-context-rank-best-v1.json").read_text())
    old=saved.get("retainedStrictSummary") or saved["strictVariants"]["forest_context"]["summary"]
    # The retained selector only adds Open 46; it never changes Closed/Pedal predictions.
    oldPolicy={"open":old["open"],"closed":baseline["closed"],
      "macroF1":.5*(old["open"]["f1"]+baseline["closed"]["f1"])}

    out={"schema":2,"description":"O->O / O->Closed transition-aware Open-HH rescue with Closed=42+44 policy scoring.",
      "labelPolicy":{"open":[46],"closed":[42,44],"pedal44FoldedIntoClosed":True,
        "subtype1":"Open followed by Closed/Pedal/end","subtype2":"Open followed by Open"},
      "sourcePolicy":{"trainingRowsPooled":False,"songs":"other-song LOO only","offvocal":"prediction-side structural context",
        "gmd":"fixed genre prior only","syncNanairo":"no rows pooled; physics/feature teacher only"},
      "baselinePolicy44":baseline,"previousNonGridHFBestPolicy44":oldPolicy,"variants":{}}
    for v in ("binary_section_vector","transition_multiclass","transition_family_consensus","transition_family_strict"):
        q=evaluate(d,items,v,hx,hy,gx,gy);ss=q["summary"]
        q["beatsPreviousBest"]=(ss["open"]["f1"]>oldPolicy["open"]["f1"] and ss["macroF1"]>oldPolicy["macroF1"] and
          ss["open"]["precision"]>=oldPolicy["open"]["precision"]-.025)
        out["variants"][v]=q
        print("SECTRANS_RESULT",v,json.dumps({"beatsPreviousBest":q["beatsPreviousBest"],"summary":ss}),flush=True)
    elig=[(q["summary"]["macroF1"],q["summary"]["open"]["f1"],k,q) for k,q in out["variants"].items() if q["beatsPreviousBest"]]
    best=max(elig) if elig else None
    out["retainedStrict"]=best[2] if best else "previous_non_grid_hf_best"
    out["retainedStrictSummary"]=best[3]["summary"] if best else oldPolicy
    out["guard"]={"kickSnareTomChanged":False,"existingNotesRemoved":False,"operation":"only add GM46",
      "adoptionRule":"must beat saved best under policy-correct Closed=42+44 nested LOO"}
    (EXP/"results-open-hat-section-transition-policy44-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("SECTRANS_RETAINED",out["retainedStrict"],json.dumps(out["retainedStrictSummary"]),flush=True)
if __name__=="__main__":main()
