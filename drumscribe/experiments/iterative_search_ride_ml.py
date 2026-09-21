"""Cycles 16-18: learn ride as a hat-vs-ride timbre decision."""
from __future__ import annotations
import copy, importlib.util, json
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".")
spec=importlib.util.spec_from_file_location("ml",ROOT/"drumscribe/experiments/iterative_search_cymbal_ml.py")
ml=importlib.util.module_from_spec(spec);spec.loader.exec_module(ml)
anc=ml.anc;ps=ml.ps;base=ml.base;ev=ml.ev
SONGS=base.SONGS

def build_hatride(data):
    for song,d in data.items():
        raw=base.raw_candidates(d["band"],d["sim"])
        frames=sorted(set(e["frame"] for e in raw if e["group"]=="hat")|set(base.peaks(d["band"][3],.16,.05)))
        truth=ev.midi_events(d["folder"]/"chart.mid");truth=[(t+d["shift"],g) for t,g,*_ in truth]
        X=[];y=[];train_frames=[]
        for fr in frames:
            t=fr*ev.HOP/ev.SR
            isr=any(g=="ride" and abs(t-tt)<=.08 for tt,g in truth)
            ish=any(g=="hat" and abs(t-tt)<=.08 for tt,g in truth)
            if not (isr or ish):continue
            # When both labels exist, prefer ride: it is the harder metal-timbre class.
            X.append(ml.feat(d,fr,True));y.append(1 if isr else 0);train_frames.append(fr)
        d["hr_frames_all"]=frames
        d["hr_X_all"]=np.stack([ml.feat(d,f,True) for f in frames])
        d["hr_X_train"]=np.stack(X) if X else np.zeros((0,d["hr_X_all"].shape[1]),dtype="f4")
        d["hr_y_train"]=np.asarray(y,dtype=np.int8)

def train_hr(data,held,family):
    X=np.concatenate([data[s]["hr_X_train"] for s in SONGS if s!=held])
    y=np.concatenate([data[s]["hr_y_train"] for s in SONGS if s!=held])
    return ml.BinModel(family).fit(X,y)

def params():
    p=ml.params();p.update({"crash_window_beats":.15,"crash_prob":.60,
      "hr_prob":.72,"hr_floor":.40,"hr_periodic":.50,"hr_add_missing":False,"hr_add_prob":.88})
    return p

def transcribe(d,crash_model,hr_model,p):
    # Non-cymbal heuristic base, including hats.
    raw=base.raw_candidates(d["band"],d["sim"])
    stage=base.ks_arbitrate([e for e in raw if e["group"]!="cymbal"],d["band"],d["sim"],p)

    # Crash model from the best family in cycles 13-15.
    frames=d["cym_frames"];pc=crash_model.predict(d["cym_X"]);phase=ml.phase_from_probs(d,frames,pc)
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"]
    for i,fr in enumerate(frames):
        t=fr*ev.HOP/ev.SR;x=(t-phase)%bar;dist=min(x,bar-x)/beat
        if pc[i]>=p["crash_prob"] and dist<=p["crash_window_beats"]:
            stage.append({"time":t,"frame":fr,"group":"crash","score":float(pc[i]),"confidence":float(1+2*pc[i])})

    # Ride is learned only against hat-like timbres, then constrained by repetition.
    hrp=hr_model.predict(d["hr_X_all"]);idx={fr:i for i,fr in enumerate(d["hr_frames_all"])}
    ride_idx=[i for i,v in enumerate(hrp) if v>=p["hr_floor"]]
    ride_times=[d["hr_frames_all"][i]*ev.HOP/ev.SR for i in ride_idx];ride_pos={idxv:k for k,idxv in enumerate(ride_idx)}
    used=set();converted=[]
    for e in stage:
        if e["group"]!="hat":converted.append(e);continue
        i=idx.get(e["frame"])
        if i is None:converted.append(e);continue
        k=ride_pos.get(i);per=base.periodic_support(ride_times,k,d["bpm"]) if k is not None else 0.
        if hrp[i]>=p["hr_prob"] and per>=p["hr_periodic"]:
            x=dict(e);x["group"]="ride";x["confidence"]=float(max(x["confidence"],1+2*hrp[i]+.3*per));converted.append(x);used.add(i)
        else:converted.append(e)
    if p["hr_add_missing"]:
        for i,fr in enumerate(d["hr_frames_all"]):
            if i in used or hrp[i]<p["hr_add_prob"]:continue
            k=ride_pos.get(i);per=base.periodic_support(ride_times,k,d["bpm"]) if k is not None else 0.
            if per<p["hr_periodic"]:continue
            t=fr*ev.HOP/ev.SR
            if any(abs(e["time"]-t)<=.045 and e["group"] in ("hat","ride") for e in converted):continue
            converted.append({"time":t,"frame":fr,"group":"ride","score":float(hrp[i]),"confidence":float(1+2*hrp[i]+.3*per)})
    return base.enforce_two_limb(converted,p),phase

def evaluate(name,p,data,hr_family,outdir):
    result={"params":p,"hatride_family":hr_family,"songs":{}};tot=Counter()
    for held in SONGS:
        crash_model=ml.train_fold(data,held,"rf")[0];hr=train_hr(data,held,hr_family)
        pred,phase=transcribe(data[held],crash_model,hr,p);mid=outdir/name/f"{held}.mid";base.write_midi(mid,pred,data[held]["bpm"])
        parsed=ev.midi_events(mid);truth=ev.midi_events(data[held]["folder"]/"chart.mid")
        sc=ev.score(parsed,truth,data[held]["shift"]);cf=ev.confusion(parsed,truth,data[held]["shift"]);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc)
        sc["two_limb_violations"]=ps.poly_violations(parsed,p["poly_window"]);sc["phase_error_vs_midi_bar_beats"]=anc.phase_err(phase,data[held]);result["songs"][held]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],poly=sc["two_limb_violations"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,m=tot["tp"],tot["predicted"],tot["reference"];s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4),"recall":round(tp/m,4),"f1":round(2*tp/(n+m),4),"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":tot["poly"],"by_group":{}}
    macro=[]
    for g in ["kick","snare","hat","tom","crash","ride"]:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0;macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/6,4);cym=(s["by_group"]["crash"]["f1"]+s["by_group"]["ride"]["f1"])/2;ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(s["f1"]+.15*s["macro_f1"]+.20*cym-.20*ks,6);result["summary"]=s;return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data=anc.load();ml.build_dataset(data,True);build_hatride(data);root=ROOT/"drumscribe/experiments/generated-search-ride-ml";report={"schema":1,"cycles":[]};bestfam=None;bestp=None
    res={}
    for fam in ("logistic","rf","extra"):
        name="c16_"+fam;res[name]=evaluate(name,params(),data,fam,root/"cycle16");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestfam=res[win]["hatride_family"];bestp=copy.deepcopy(res[win]["params"]);report["cycles"].append({"cycle":16,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    res={}
    for name,thr in [("c17_strict",.82),("c17_balanced",.72),("c17_recall",.62)]:
        p=copy.deepcopy(bestp);p["hr_prob"]=thr;res[name]=evaluate(name,p,data,bestfam,root/"cycle17");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestp=copy.deepcopy(res[win]["params"]);report["cycles"].append({"cycle":17,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    res={}
    for name,per,add in [("c18_periodic_strict",.70,False),("c18_periodic_medium",.50,False),("c18_add_strong",.60,True)]:
        p=copy.deepcopy(bestp);p["hr_periodic"]=per;p["hr_add_missing"]=add;res[name]=evaluate(name,p,data,bestfam,root/"cycle18");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestp=copy.deepcopy(res[win]["params"]);report["cycles"].append({"cycle":18,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"hatride_family":bestfam,"summary":res[win]["summary"],"params":bestp}
    (ROOT/"drumscribe/experiments/results-iterative-ride-ml.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
