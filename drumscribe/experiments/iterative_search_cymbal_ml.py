"""Cycles 13-15: supervised crash/ride classification with leave-one-song-out evaluation.

For each held-out song:
- train only on the other four songs' aligned drums.mp3 + chart.mid
- transcribe held-out drums.mp3
- write a real MIDI file
- re-parse it and compare with held-out chart.mid
"""
from __future__ import annotations
import copy, importlib.util, json, math
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.preprocessing import StandardScaler

ROOT=Path(".")
spec=importlib.util.spec_from_file_location("anc",ROOT/"drumscribe/experiments/iterative_search_anchor.py")
anc=importlib.util.module_from_spec(spec);spec.loader.exec_module(anc)
ps=anc.ps;base=anc.base;ev=anc.ev
SONGS=base.SONGS

def cymbal_frames(band):
    fs=set(base.peaks(band[2],.24,.05))|set(base.peaks(band[3],.16,.05))
    return sorted(fs)

def feat(d,fr,temporal=True):
    band,sim=d["band"],d["sim"];n=band.shape[1]
    vals=[float(band[i,fr]) for i in range(4)]+[float(sim[i,fr]) for i in range(6)]
    b=[float(band[i,fr]) for i in range(4)]
    vals += [b[2]/(b[3]+1e-6),b[3]/(b[2]+1e-6),(b[0]+b[1])/(b[2]+b[3]+1e-6)]
    if temporal:
        for radius in (3,8,16):
            lo=max(0,fr-radius);hi=min(n,fr+radius+1)
            for i in (2,3):
                x=band[i,lo:hi];vals += [float(np.mean(x)),float(np.max(x))]
        for off in (-8,-3,3,8,16):
            q=max(0,min(n-1,fr+off));vals += [float(band[2,q]),float(band[3,q])]
    return np.asarray(vals,dtype="f4")

def build_dataset(data,temporal=True):
    for song,d in data.items():
        frames=cymbal_frames(d["band"]);X=np.stack([feat(d,f,temporal) for f in frames])
        truth=ev.midi_events(d["folder"]/"chart.mid")
        audio_truth=[(t+d["shift"],g) for t,g,*_ in truth]
        Y=np.zeros((len(frames),2),dtype=np.int8)
        for i,fr in enumerate(frames):
            t=fr*ev.HOP/ev.SR
            Y[i,0]=any(g=="crash" and abs(t-tt)<=.08 for tt,g in audio_truth)
            Y[i,1]=any(g=="ride" and abs(t-tt)<=.08 for tt,g in audio_truth)
        d["cym_frames"]=frames;d["cym_X"]=X;d["cym_Y"]=Y

def downsample(X,y,ratio=5):
    pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0)
    if len(pos)==0:return X,y
    keep_neg=neg[:min(len(neg),len(pos)*ratio)]
    idx=np.sort(np.concatenate([pos,keep_neg]));return X[idx],y[idx]

class BinModel:
    def __init__(self,family):
        self.family=family;self.scaler=None;self.model=None;self.constant=None
    def fit(self,X,y):
        if y.min()==y.max():self.constant=float(y[0]);return self
        X,y=downsample(X,y)
        if self.family=="logistic":
            self.scaler=StandardScaler().fit(X);X=self.scaler.transform(X)
            self.model=LogisticRegression(max_iter=600,class_weight="balanced",C=.7,solver="liblinear").fit(X,y)
        elif self.family=="rf":
            self.model=RandomForestClassifier(n_estimators=80,max_depth=10,min_samples_leaf=4,class_weight="balanced_subsample",random_state=17,n_jobs=-1).fit(X,y)
        elif self.family=="extra":
            self.model=ExtraTreesClassifier(n_estimators=100,max_depth=12,min_samples_leaf=3,class_weight="balanced",random_state=23,n_jobs=-1).fit(X,y)
        else:raise ValueError(self.family)
        return self
    def predict(self,X):
        if self.constant is not None:return np.full(len(X),self.constant)
        if self.scaler is not None:X=self.scaler.transform(X)
        return self.model.predict_proba(X)[:,1]

def train_fold(data,held,family):
    X=np.concatenate([data[s]["cym_X"] for s in SONGS if s!=held])
    Y=np.concatenate([data[s]["cym_Y"] for s in SONGS if s!=held])
    return [BinModel(family).fit(X,Y[:,j]) for j in range(2)]

def phase_from_probs(d,frames,pc):
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"];sigma=max(.03,beat*.09)
    ranked=sorted(range(len(frames)),key=lambda i:pc[i],reverse=True)
    early=[i for i in ranked if frames[i]*ev.HOP/ev.SR<=45][:12]
    chosen=early if len(early)>=3 else ranked[:20]
    best=(-1,0.)
    for k in range(160):
        ph=bar*k/160;score=0.
        for i in chosen:
            t=frames[i]*ev.HOP/ev.SR;x=(t-ph)%bar;dist=min(x,bar-x)
            score+=float(pc[i])*math.exp(-.5*(dist/sigma)**2)
        if score>best[0]:best=(score,ph)
    return best[1]

def periodic(times,i,bpm):
    return base.periodic_support(times,i,bpm)

def heuristic_non_cym(d,p):
    raw=base.raw_candidates(d["band"],d["sim"])
    raw=[e for e in raw if e["group"]!="cymbal"]
    return base.ks_arbitrate(raw,d["band"],d["sim"],p)

def transcribe_fold(d,models,p):
    X=d["cym_X"];frames=d["cym_frames"];pc=models[0].predict(X);pr=models[1].predict(X)
    phase=phase_from_probs(d,frames,pc)
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"]
    times=[f*ev.HOP/ev.SR for f in frames if pr[frames.index(f)]>=p["ride_prob_floor"]]
    # avoid O(n^2) index lookup later
    ride_indices=[i for i,x in enumerate(pr) if x>=p["ride_prob_floor"]]
    ride_times=[frames[i]*ev.HOP/ev.SR for i in ride_indices]
    ride_pos={idx:k for k,idx in enumerate(ride_indices)}
    out=heuristic_non_cym(d,p)
    for i,fr in enumerate(frames):
        t=fr*ev.HOP/ev.SR;x=(t-phase)%bar;dist=min(x,bar-x)/beat
        crash_ok=pc[i]>=p["crash_prob"] and dist<=p["crash_window_beats"]
        rp=ride_pos.get(i);per=periodic(ride_times,rp,d["bpm"]) if rp is not None else 0.
        ride_ok=pr[i]>=p["ride_prob"] and per>=p["ride_periodic_ml"] and pr[i]>=pc[i]*p["ride_vs_crash"]
        if crash_ok and (not ride_ok or pc[i]>=pr[i]):
            out.append({"time":t,"frame":fr,"group":"crash","score":float(pc[i]),"confidence":float(1+2*pc[i])})
        elif ride_ok:
            out.append({"time":t,"frame":fr,"group":"ride","score":float(pr[i]),"confidence":float(1+2*pr[i]+.3*per)})
    return base.enforce_two_limb(out,p),phase

def evaluate_variant(name,p,data,family,outdir):
    total=Counter();result={"params":p,"family":family,"songs":{}}
    for held in SONGS:
        models=train_fold(data,held,family);pred,phase=transcribe_fold(data[held],models,p)
        mid=outdir/name/f"{held}.mid";base.write_midi(mid,pred,data[held]["bpm"])
        parsed=ev.midi_events(mid);truth=ev.midi_events(data[held]["folder"]/"chart.mid")
        sc=ev.score(parsed,truth,data[held]["shift"]);cf=ev.confusion(parsed,truth,data[held]["shift"])
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);sc["two_limb_violations"]=ps.poly_violations(parsed,p["poly_window"])
        sc["phase_error_vs_midi_bar_beats"]=anc.phase_err(phase,data[held]);result["songs"][held]=sc
        total.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],poly=sc["two_limb_violations"])
        for g,x in sc["by_group"].items():
            total[f"{g}_tp"]+=x["tp"];total[f"{g}_pred"]+=x["predicted"];total[f"{g}_ref"]+=x["reference"]
    tp,n,m=total["tp"],total["predicted"],total["reference"];s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4),"recall":round(tp/m,4),"f1":round(2*tp/(n+m),4),"kick_to_snare":total["kick_to_snare"],"snare_to_kick":total["snare_to_kick"],"two_limb_violations":total["poly"],"by_group":{}}
    macro=[]
    for g in ["kick","snare","hat","tom","crash","ride"]:
        a,b,c=total[f"{g}_tp"],total[f"{g}_pred"],total[f"{g}_ref"];f=2*a/(b+c) if b+c else 0;macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/6,4);cym=(s["by_group"]["crash"]["f1"]+s["by_group"]["ride"]["f1"])/2;ks=total["kick_to_snare"]/max(1,total["kick_ref"])
    s["selection_score"]=round(s["f1"]+.15*s["macro_f1"]+.18*cym-.20*ks,6);result["summary"]=s;return result

def params():
    p=ps.starting();p.update({"snare_ratio":1.65,"snare_margin":.22,"poly_window":.033,
      "crash_window_beats":.10,"crash_prob":.62,"ride_prob":.62,"ride_prob_floor":.30,"ride_periodic_ml":.55,"ride_vs_crash":1.02})
    return p

def rank(r):return sorted(r.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data=anc.load();build_dataset(data,True);root=ROOT/"drumscribe/experiments/generated-search-ml";report={"schema":1,"cycles":[]};best_family=None;best_p=None
    # Cycle 13: model family.
    variants={f"c13_{fam}":fam for fam in ("logistic","rf","extra")};res={}
    for name,fam in variants.items():
        print("EVAL 13",name,flush=True);res[name]=evaluate_variant(name,params(),data,fam,root/"cycle13");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);winner=rr[0][0];best_family=res[winner]["family"];best_p=copy.deepcopy(res[winner]["params"]);report["cycles"].append({"cycle":13,"candidates":res,"ranking":[n for n,_ in rr],"winner":winner,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    # Cycle 14: probability thresholds.
    res={}
    for name,cp,rp in [("c14_strict",.72,.72),("c14_balanced",.60,.58),("c14_recall",.50,.48)]:
        p=copy.deepcopy(best_p);p.update(crash_prob=cp,ride_prob=rp);res[name]=evaluate_variant(name,p,data,best_family,root/"cycle14");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);winner=rr[0][0];best_p=copy.deepcopy(res[winner]["params"]);report["cycles"].append({"cycle":14,"candidates":res,"ranking":[n for n,_ in rr],"winner":winner,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    # Cycle 15: crash-head width, all remain head-only.
    res={}
    for name,w in [("c15_head_005",.05),("c15_head_010",.10),("c15_head_015",.15)]:
        p=copy.deepcopy(best_p);p["crash_window_beats"]=w;res[name]=evaluate_variant(name,p,data,best_family,root/"cycle15");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);winner=rr[0][0];best_p=copy.deepcopy(res[winner]["params"]);report["cycles"].append({"cycle":15,"candidates":res,"ranking":[n for n,_ in rr],"winner":winner,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":winner,"family":best_family,"summary":res[winner]["summary"],"params":best_p}
    (ROOT/"drumscribe/experiments/results-iterative-ml.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
