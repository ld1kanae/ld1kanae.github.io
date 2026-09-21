"""Cycles 31-33: split stick hi-hat from pedal hi-hat (MIDI 44).

Evaluation uses the corrected reference taxonomy:
hat = 42/46, pedal_hat = 44. pedal_hat is exempt from the two-hand limit.
"""
from __future__ import annotations
import copy, importlib.util, json
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT=Path(".")
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
tom=loadmod("tom_new","drumscribe/experiments/iterative_search_tom.py")
ml=tom.ml;anc=tom.anc;ps=tom.ps;base=tom.base;ev=tom.ev
SONGS=base.SONGS

def pedal_frames(d):
    raw=base.raw_candidates(d["band"],d["sim"])
    fs=set(e["frame"] for e in raw if e["group"]=="hat")
    fs |= set(base.peaks(d["band"][3],.12,.04))
    return sorted(fs)

def feat(d,fr):
    band,sim=d["band"],d["sim"];n=band.shape[1]
    b=[float(band[i,fr]) for i in range(4)]
    vals=b+[float(sim[i,fr]) for i in range(min(8,sim.shape[0]))]
    while len(vals)<12:vals.append(0.)
    ph=float(sim[7,fr]) if sim.shape[0]>7 else 0.
    hh=float(sim[2,fr])
    vals += [ph-hh,ph/(abs(hh)+1e-4),b[3]/(b[2]+1e-6)]
    for radius in (2,5,10,20):
        lo=max(0,fr-radius);hi=min(n,fr+radius+1)
        for i in (2,3):
            x=band[i,lo:hi];vals += [float(np.mean(x)),float(np.max(x))]
    return np.asarray(vals,dtype="f4")

def build(data):
    for song,d in data.items():
        frames=pedal_frames(d)
        truth=[(t+d["shift"],g) for t,g,*_ in ev.midi_events(d["folder"]/"chart.mid")]
        X=[];y=[];use=[]
        for fr in frames:
            t=fr*ev.HOP/ev.SR
            pedal=any(g=="pedal_hat" and abs(t-tt)<=.08 for tt,g in truth)
            stick=any(g=="hat" and abs(t-tt)<=.08 for tt,g in truth)
            if not (pedal or stick):continue
            X.append(feat(d,fr));y.append(1 if pedal else 0);use.append(fr)
        d["pedal_frames_all"]=frames
        d["pedal_X_all"]=np.stack([feat(d,f) for f in frames])
        d["pedal_X_train"]=np.stack(X) if X else np.zeros((0,d["pedal_X_all"].shape[1]),dtype="f4")
        d["pedal_y_train"]=np.asarray(y,dtype=np.int8)
        d["pedal_index"]={f:i for i,f in enumerate(frames)}

class Model:
    def __init__(self,fam):self.fam=fam;self.scaler=None;self.model=None;self.constant=None
    def fit(self,X,y):
        if len(y)==0 or y.min()==y.max():self.constant=float(y[0]) if len(y) else 0.;return self
        if self.fam=="logistic":
            self.scaler=StandardScaler().fit(X);X=self.scaler.transform(X)
            self.model=LogisticRegression(max_iter=800,class_weight="balanced",C=.65,solver="liblinear").fit(X,y)
        elif self.fam=="rf":
            self.model=RandomForestClassifier(n_estimators=140,max_depth=10,min_samples_leaf=3,class_weight="balanced_subsample",random_state=83,n_jobs=-1).fit(X,y)
        else:
            self.model=ExtraTreesClassifier(n_estimators=160,max_depth=12,min_samples_leaf=3,class_weight="balanced",random_state=89,n_jobs=-1).fit(X,y)
        return self
    def predict(self,X):
        if self.constant is not None:return np.full(len(X),self.constant)
        if self.scaler is not None:X=self.scaler.transform(X)
        return self.model.predict_proba(X)[:,1]

def train(data,held,fam):
    X=np.concatenate([data[s]["pedal_X_train"] for s in SONGS if s!=held])
    y=np.concatenate([data[s]["pedal_y_train"] for s in SONGS if s!=held])
    return Model(fam).fit(X,y)

def params():
    p=tom.params()
    p.update({"snare_ratio":1.65,"snare_margin":.22,"poly_window":.033,
              "crash_prob":.60,"crash_window_beats":.15,
              "tom_prob":.62,"tom_context":"none",
              "pedal_prob":.65,"pedal_sim_margin":-1.0})
    return p

def transcribe(d,held,data,tm,pm,p):
    raw=base.raw_candidates(d["band"],d["sim"])
    stage=base.ks_arbitrate([e for e in raw if e["group"] not in ("cymbal","tom")],d["band"],d["sim"],p)

    cm=ml.train_fold(data,held,"rf")[0]
    pc=cm.predict(d["cym_X"]);phase=ml.phase_from_probs(d,d["cym_frames"],pc)
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"]
    for i,fr in enumerate(d["cym_frames"]):
        t=fr*ev.HOP/ev.SR;x=(t-phase)%bar;dist=min(x,bar-x)/beat
        if pc[i]>=p["crash_prob"] and dist<=p["crash_window_beats"]:
            stage.append({"time":t,"frame":fr,"group":"crash","score":float(pc[i]),"confidence":float(1+2*pc[i])})

    tp=tm.predict(d["tom_X"])
    for i,prob in enumerate(tp):
        if prob<p["tom_prob"]:continue
        fr=d["tom_frames"][i];t=fr*ev.HOP/ev.SR
        close=[e for e in stage if e["group"] in ("kick","snare") and abs(e["time"]-t)<=.035]
        if close and prob<.78:continue
        stage.append({"time":t,"frame":fr,"group":"tom","score":float(prob),"confidence":float(1+2*prob)})

    pp=pm.predict(d["pedal_X_all"])
    converted=[]
    for e in stage:
        if e["group"]!="hat":converted.append(e);continue
        i=d["pedal_index"].get(e["frame"])
        if i is None:converted.append(e);continue
        sim_margin=float(d["sim"][7,e["frame"]]-d["sim"][2,e["frame"]]) if d["sim"].shape[0]>7 else -99.
        if pp[i]>=p["pedal_prob"] and sim_margin>=p["pedal_sim_margin"]:
            x=dict(e);x["group"]="pedal_hat";x["confidence"]=max(x["confidence"],1+2*float(pp[i]));converted.append(x)
        else:converted.append(e)

    # base LIMITED contains only hand-played classes, so pedal_hat remains exempt.
    return base.enforce_two_limb(converted,p),phase

def evaluate(name,p,data,fam,outdir):
    result={"params":p,"family":fam,"songs":{}};tot=Counter()
    groups=["kick","snare","hat","pedal_hat","tom","crash","ride"]
    for held in SONGS:
        tm=tom.train_tom(data,held,"rf");pm=train(data,held,fam)
        pred,phase=transcribe(data[held],held,data,tm,pm,p)
        mid=outdir/name/f"{held}.mid";base.write_midi(mid,pred,data[held]["bpm"])
        parsed=ev.midi_events(mid);truth=ev.midi_events(data[held]["folder"]/"chart.mid")
        sc=ev.score(parsed,truth,data[held]["shift"]);cf=ev.confusion(parsed,truth,data[held]["shift"])
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);sc["two_limb_violations"]=ps.poly_violations(parsed,p["poly_window"])
        result["songs"][held]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],poly=sc["two_limb_violations"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,m=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4) if n else 0,"recall":round(tp/m,4) if m else 0,"f1":round(2*tp/(n+m),4) if n+m else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":tot["poly"],"by_group":{}}
    macro=[]
    for g in groups:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0;macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/len(macro),4)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(s["f1"]+.12*s["macro_f1"]+.14*s["by_group"]["tom"]["f1"]+.12*s["by_group"]["crash"]["f1"]+.14*s["by_group"]["pedal_hat"]["f1"]-.20*ks,6)
    result["summary"]=s;return result

def prepare():
    data=anc.load();ml.build_dataset(data,True);tom.build_tom(data);build(data);return data
def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data=prepare();root=ROOT/"drumscribe/experiments/generated-search-pedal-hat";report={"schema":1,"cycles":[]};bestfam=None;bestp=None
    res={}
    for fam in ("logistic","rf","extra"):
        name="c31_"+fam;p=params();res[name]=evaluate(name,p,data,fam,root/"cycle31")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestfam=res[win]["family"];bestp=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":31,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,thr in [("c32_strict",.78),("c32_balanced",.65),("c32_recall",.52)]:
        p=copy.deepcopy(bestp);p["pedal_prob"]=thr;res[name]=evaluate(name,p,data,bestfam,root/"cycle32")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestp=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":32,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,margin in [("c33_no_sim_gate",-1.0),("c33_soft_sim_gate",-.05),("c33_positive_sim_gate",0.0)]:
        p=copy.deepcopy(bestp);p["pedal_sim_margin"]=margin;res[name]=evaluate(name,p,data,bestfam,root/"cycle33")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestp=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":33,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"family":bestfam,"summary":res[win]["summary"],"params":bestp}
    (ROOT/"drumscribe/experiments/results-iterative-pedal-hat.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
