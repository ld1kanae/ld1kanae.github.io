"""Cycles 25-27: tom-specific supervised candidate classification and fill priors."""
from __future__ import annotations
import copy, importlib.util, json, math
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT=Path(".")
spec=importlib.util.spec_from_file_location("ml",ROOT/"drumscribe/experiments/iterative_search_cymbal_ml.py")
ml=importlib.util.module_from_spec(spec);spec.loader.exec_module(ml)
anc=ml.anc;ps=ml.ps;base=ml.base;ev=ml.ev
SONGS=base.SONGS

def tom_frames(d):
    fs=set(base.peaks(d["band"][1],.30,.045))|set(base.peaks(d["band"][0],.24,.045))
    return sorted(fs)

def tom_feat(d,fr):
    band,sim=d["band"],d["sim"];n=band.shape[1]
    b=[float(band[i,fr]) for i in range(4)]
    s=[float(sim[i,fr]) for i in range(6)]
    vals=b+s+[
      b[0]/(b[1]+1e-6),b[1]/(b[0]+1e-6),
      (b[0]+b[1])/(b[2]+b[3]+1e-6),
      s[3]-s[1],s[3]-s[0]
    ]
    for radius in (2,5,10,20):
        lo=max(0,fr-radius);hi=min(n,fr+radius+1)
        for i in range(4):
            x=band[i,lo:hi];vals += [float(np.mean(x)),float(np.max(x))]
    return np.asarray(vals,dtype="f4")

def build_tom(data):
    for song,d in data.items():
        frames=tom_frames(d);X=np.stack([tom_feat(d,f) for f in frames])
        truth=[(t+d["shift"],g) for t,g,*_ in ev.midi_events(d["folder"]/"chart.mid")]
        y=np.zeros(len(frames),dtype=np.int8)
        for i,fr in enumerate(frames):
            t=fr*ev.HOP/ev.SR
            y[i]=1 if any(g=="tom" and abs(t-tt)<=.08 for tt,g in truth) else 0
        d["tom_frames"]=frames;d["tom_X"]=X;d["tom_y"]=y

class Model:
    def __init__(self,fam):self.fam=fam;self.scaler=None;self.model=None;self.constant=None
    def fit(self,X,y):
        if y.min()==y.max():self.constant=float(y[0]);return self
        pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0)
        rng=np.random.default_rng(71)
        if len(neg)>max(300,len(pos)*10):neg=rng.choice(neg,max(300,len(pos)*10),replace=False)
        idx=np.concatenate([pos,neg]);rng.shuffle(idx);X=X[idx];y=y[idx]
        if self.fam=="logistic":
            self.scaler=StandardScaler().fit(X);X=self.scaler.transform(X)
            self.model=LogisticRegression(max_iter=800,class_weight="balanced",C=.6,solver="liblinear").fit(X,y)
        elif self.fam=="rf":
            self.model=RandomForestClassifier(n_estimators=140,max_depth=10,min_samples_leaf=3,class_weight="balanced_subsample",random_state=73,n_jobs=-1).fit(X,y)
        else:
            self.model=ExtraTreesClassifier(n_estimators=160,max_depth=12,min_samples_leaf=3,class_weight="balanced",random_state=79,n_jobs=-1).fit(X,y)
        return self
    def predict(self,X):
        if self.constant is not None:return np.full(len(X),self.constant)
        if self.scaler is not None:X=self.scaler.transform(X)
        return self.model.predict_proba(X)[:,1]

def train_tom(data,held,fam):
    X=np.concatenate([data[s]["tom_X"] for s in SONGS if s!=held])
    y=np.concatenate([data[s]["tom_y"] for s in SONGS if s!=held])
    return Model(fam).fit(X,y)

def params():
    p=ml.params()
    p.update({"snare_ratio":1.65,"snare_margin":.22,"poly_window":.033,
              "crash_window_beats":.15,"crash_prob":.60,
              "tom_prob":.62,"tom_context":"none","tom_cluster_window":.70,
              "tom_cluster_min":2,"tom_prehead_beats":1.15})
    return p

def phase_and_crash(d,held,data,p):
    crash=ml.train_fold(data,held,"rf")[0]
    pc=crash.predict(d["cym_X"]);phase=ml.phase_from_probs(d,d["cym_frames"],pc)
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"]
    crashes=[]
    for i,fr in enumerate(d["cym_frames"]):
        t=fr*ev.HOP/ev.SR;x=(t-phase)%bar;dist=min(x,bar-x)/beat
        if pc[i]>=p["crash_prob"] and dist<=p["crash_window_beats"]:
            crashes.append({"time":t,"frame":fr,"group":"crash","score":float(pc[i]),"confidence":float(1+2*pc[i])})
    return phase,crashes

def context_ok(t,prob_times,phase,d,p):
    if p["tom_context"]=="none":return True
    nearby=sum(1 for x in prob_times if abs(x-t)<=p["tom_cluster_window"])
    cluster=nearby>=p["tom_cluster_min"]
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"]
    x=(t-phase)%bar
    to_head=(bar-x)/beat if x>1e-9 else 0.
    prehead=(0<to_head<=p["tom_prehead_beats"])
    if p["tom_context"]=="cluster":return cluster
    if p["tom_context"]=="fill_or_cluster":return cluster or prehead
    return True

def transcribe(d,held,data,tom_model,p):
    raw=base.raw_candidates(d["band"],d["sim"])
    base_events=[e for e in raw if e["group"] not in ("cymbal","tom")]
    stage=base.ks_arbitrate(base_events,d["band"],d["sim"],p)
    phase,crashes=phase_and_crash(d,held,data,p);stage.extend(crashes)

    probs=tom_model.predict(d["tom_X"])
    prob_idx=[i for i,x in enumerate(probs) if x>=p["tom_prob"]]
    prob_times=[d["tom_frames"][i]*ev.HOP/ev.SR for i in prob_idx]
    for i in prob_idx:
        fr=d["tom_frames"][i];t=fr*ev.HOP/ev.SR
        if not context_ok(t,prob_times,phase,d,p):continue
        # Avoid replacing a clearly supported kick/snare onset with a weak tom.
        close=[e for e in stage if e["group"] in ("kick","snare") and abs(e["time"]-t)<=.035]
        if close and probs[i]<.78:continue
        stage.append({"time":t,"frame":fr,"group":"tom","score":float(probs[i]),"confidence":float(1+2*probs[i])})
    return base.enforce_two_limb(stage,p),phase

def evaluate(name,p,data,fam,outdir):
    result={"params":p,"family":fam,"songs":{}};tot=Counter()
    for held in SONGS:
        tom=train_tom(data,held,fam)
        pred,phase=transcribe(data[held],held,data,tom,p)
        mid=outdir/name/f"{held}.mid";base.write_midi(mid,pred,data[held]["bpm"])
        parsed=ev.midi_events(mid);truth=ev.midi_events(data[held]["folder"]/"chart.mid")
        sc=ev.score(parsed,truth,data[held]["shift"]);cf=ev.confusion(parsed,truth,data[held]["shift"])
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);sc["two_limb_violations"]=ps.poly_violations(parsed,p["poly_window"])
        sc["phase_error_vs_midi_bar_beats"]=anc.phase_err(phase,data[held]);result["songs"][held]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],poly=sc["two_limb_violations"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,m=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4),"recall":round(tp/m,4),"f1":round(2*tp/(n+m),4),
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":tot["poly"],"by_group":{}}
    macro=[]
    for g in ["kick","snare","hat","tom","crash","ride"]:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0;macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/6,4)
    cym=(s["by_group"]["crash"]["f1"]+s["by_group"]["ride"]["f1"])/2;ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(s["f1"]+.18*s["macro_f1"]+.10*cym+.12*s["by_group"]["tom"]["f1"]-.20*ks,6)
    result["summary"]=s;return result

def prepare():
    data=anc.load();ml.build_dataset(data,True);build_tom(data);return data
def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data=prepare();root=ROOT/"drumscribe/experiments/generated-search-tom";report={"schema":1,"cycles":[]};bestfam=None;bestp=None
    # Cycle 25: model family.
    res={}
    for fam in ("logistic","rf","extra"):
        name="c25_"+fam;p=params()
        res[name]=evaluate(name,p,data,fam,root/"cycle25")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestfam=res[win]["family"];bestp=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":25,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    # Cycle 26: probability threshold.
    res={}
    for name,thr in [("c26_strict",.75),("c26_balanced",.62),("c26_recall",.50)]:
        p=copy.deepcopy(bestp);p["tom_prob"]=thr
        res[name]=evaluate(name,p,data,bestfam,root/"cycle26")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestp=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":26,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    # Cycle 27: fill context.
    res={}
    for name,context in [("c27_no_context","none"),("c27_cluster","cluster"),("c27_fill_or_cluster","fill_or_cluster")]:
        p=copy.deepcopy(bestp);p["tom_context"]=context
        res[name]=evaluate(name,p,data,bestfam,root/"cycle27")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestp=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":27,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"family":bestfam,"summary":res[win]["summary"],"params":bestp}
    (ROOT/"drumscribe/experiments/results-iterative-tom.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
