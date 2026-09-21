"""Cycles 19-21: ride section detection.

Audio-only window features are trained on four songs and evaluated on the held-out
song. A positive ride section converts hat candidates to ride; chart.mid is used
only for training labels on non-held-out songs and final held-out scoring.
"""
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

def metal_frames(d):
    raw=base.raw_candidates(d["band"],d["sim"])
    return sorted(set(e["frame"] for e in raw if e["group"]=="hat")|set(base.peaks(d["band"][3],.16,.05)))

def window_feature(d,start,end,frames):
    times=np.asarray(frames)*ev.HOP/ev.SR
    idx=np.where((times>=start)&(times<end))[0]
    dur=max(.05,end-start)
    if not len(idx):
        return np.zeros(26,dtype="f4")
    fs=[frames[i] for i in idx]
    sim=d["sim"];band=d["band"]
    hat=np.asarray([sim[2,f] for f in fs],dtype=float)
    ride=np.asarray([sim[5,f] for f in fs],dtype=float)
    crash=np.asarray([sim[4,f] for f in fs],dtype=float)
    hi=np.asarray([band[3,f] for f in fs],dtype=float)
    mid=np.asarray([band[2,f] for f in fs],dtype=float)
    ratio=hi/(mid+1e-6)
    delta=ride-hat
    vals=[len(fs)/dur]
    for arr in (hat,ride,crash,hi,mid,ratio,delta):
        vals += [float(np.mean(arr)),float(np.median(arr)),float(np.percentile(arr,75))]
    # Inter-onset regularity within the metal stream.
    tt=times[idx]
    if len(tt)>=3:
        dt=np.diff(tt);vals += [float(np.median(dt)),float(np.std(dt)),float(np.mean(dt<.40)),float(np.mean(dt<.24))]
    else:vals += [0,0,0,0]
    return np.asarray(vals,dtype="f4")

def build_windows(data,beats_per_window):
    for song,d in data.items():
        frames=metal_frames(d);d["section_frames"]=frames
        beat=60/d["bpm"]*4/d["den"];win=beat*beats_per_window;step=beat
        truth=[(t+d["shift"],g) for t,g,*_ in ev.midi_events(d["folder"]/"chart.mid")]
        duration=float(json.loads((d["folder"]/"song.json").read_text())["duration"])
        rows=[];labels=[];ranges=[]
        start=0.
        while start<duration:
            end=start+win
            ride=sum(1 for t,g in truth if g=="ride" and start<=t<end)
            hat=sum(1 for t,g in truth if g=="hat" and start<=t<end)
            total=ride+hat
            if total>=2:
                rows.append(window_feature(d,start,end,frames))
                labels.append(1 if ride/(total or 1)>=.55 else 0)
                ranges.append((start,end))
            start+=step
        d["section_X"]=np.stack(rows) if rows else np.zeros((0,26),dtype="f4")
        d["section_y"]=np.asarray(labels,dtype=np.int8)
        # Prediction windows include all windows, not only labeled ones.
        starts=np.arange(0,duration,step)
        d["section_ranges_all"]=[(float(s),float(s+win)) for s in starts]
        d["section_X_all"]=np.stack([window_feature(d,s,s+win,frames) for s in starts])

class Model:
    def __init__(self,family):self.family=family;self.scaler=None;self.model=None;self.constant=None
    def fit(self,X,y):
        if len(y)==0 or y.min()==y.max():self.constant=float(y[0]) if len(y) else 0.;return self
        if self.family=="logistic":
            self.scaler=StandardScaler().fit(X);X=self.scaler.transform(X)
            self.model=LogisticRegression(max_iter=600,class_weight="balanced",C=.7,solver="liblinear").fit(X,y)
        elif self.family=="rf":
            self.model=RandomForestClassifier(n_estimators=120,max_depth=9,min_samples_leaf=4,class_weight="balanced_subsample",random_state=31,n_jobs=-1).fit(X,y)
        else:
            self.model=ExtraTreesClassifier(n_estimators=140,max_depth=10,min_samples_leaf=4,class_weight="balanced",random_state=37,n_jobs=-1).fit(X,y)
        return self
    def predict(self,X):
        if self.constant is not None:return np.full(len(X),self.constant)
        if self.scaler is not None:X=self.scaler.transform(X)
        return self.model.predict_proba(X)[:,1]

def train_section(data,held,family):
    X=np.concatenate([data[s]["section_X"] for s in SONGS if s!=held])
    y=np.concatenate([data[s]["section_y"] for s in SONGS if s!=held])
    return Model(family).fit(X,y)

def params():
    p=ml.params()
    p.update({"snare_ratio":1.65,"snare_margin":.22,"poly_window":.033,
      "crash_window_beats":.15,"crash_prob":.60,
      "section_threshold":.70,"section_min_windows":1,"section_timbre_gate":-1.0})
    return p

def phase_from_crash(d,pc):
    return ml.phase_from_probs(d,d["cym_frames"],pc)

def transcribe(d,crash_model,section_model,p):
    raw=base.raw_candidates(d["band"],d["sim"])
    stage=base.ks_arbitrate([e for e in raw if e["group"]!="cymbal"],d["band"],d["sim"],p)

    pc=crash_model.predict(d["cym_X"]);phase=phase_from_crash(d,pc)
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"]
    for i,fr in enumerate(d["cym_frames"]):
        t=fr*ev.HOP/ev.SR;x=(t-phase)%bar;dist=min(x,bar-x)/beat
        if pc[i]>=p["crash_prob"] and dist<=p["crash_window_beats"]:
            stage.append({"time":t,"frame":fr,"group":"crash","score":float(pc[i]),"confidence":float(1+2*pc[i])})

    probs=section_model.predict(d["section_X_all"])
    ranges=d["section_ranges_all"]
    converted=[]
    for e in stage:
        if e["group"]!="hat":converted.append(e);continue
        covering=[float(probs[i]) for i,(a,b) in enumerate(ranges) if a<=e["time"]<b]
        sec=max(covering) if covering else 0.
        timbre=float(d["sim"][5,e["frame"]]-d["sim"][2,e["frame"]])
        if sec>=p["section_threshold"] and timbre>=p["section_timbre_gate"]:
            x=dict(e);x["group"]="ride";x["confidence"]=max(x["confidence"],1+1.8*sec+.25*max(0,timbre));converted.append(x)
        else:converted.append(e)
    return base.enforce_two_limb(converted,p),phase

def evaluate(name,p,data,family,outdir):
    result={"params":p,"family":family,"songs":{}};tot=Counter()
    for held in SONGS:
        crash=ml.train_fold(data,held,"rf")[0];section=train_section(data,held,family)
        pred,phase=transcribe(data[held],crash,section,p)
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
    s["macro_f1"]=round(sum(macro)/6,4);cym=(s["by_group"]["crash"]["f1"]+s["by_group"]["ride"]["f1"])/2;ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(s["f1"]+.15*s["macro_f1"]+.22*cym-.20*ks,6);result["summary"]=s;return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def prepare(beats):
    data=anc.load();ml.build_dataset(data,True);build_windows(data,beats);return data

def main():
    root=ROOT/"drumscribe/experiments/generated-search-ride-section";report={"schema":1,"cycles":[]}
    # Cycle 19: section length, RF fixed.
    res={}
    data_by={}
    for beats in (2,4,8):
        data=prepare(beats);data_by[beats]=data;name=f"c19_{beats}beat"
        res[name]=evaluate(name,params(),data,"rf",root/"cycle19");res[name]["beats_per_window"]=beats
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best_beats=res[win]["beats_per_window"];bestp=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":19,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    # Cycle 20: family.
    data=data_by[best_beats];res={}
    for fam in ("logistic","rf","extra"):
        name="c20_"+fam;res[name]=evaluate(name,bestp,data,fam,root/"cycle20");res[name]["beats_per_window"]=best_beats
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestfam=res[win]["family"];bestp=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":20,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    # Cycle 21: section confidence and optional timbre gate.
    res={}
    for name,thr,gate in [("c21_strict",.82,-.05),("c21_balanced",.70,-.12),("c21_recall",.58,-.20)]:
        p=copy.deepcopy(bestp);p["section_threshold"]=thr;p["section_timbre_gate"]=gate
        res[name]=evaluate(name,p,data,bestfam,root/"cycle21");res[name]["beats_per_window"]=best_beats
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestp=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":21,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"family":bestfam,"beats_per_window":best_beats,"summary":res[win]["summary"],"params":bestp}
    (ROOT/"drumscribe/experiments/results-iterative-ride-section.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
