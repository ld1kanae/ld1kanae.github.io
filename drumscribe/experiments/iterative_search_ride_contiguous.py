"""Cycles 22-24: contiguous ride-section filtering and periodic gating."""
from __future__ import annotations
import copy, importlib.util, json
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".")
spec=importlib.util.spec_from_file_location("sec",ROOT/"drumscribe/experiments/iterative_search_ride_section.py")
sec=importlib.util.module_from_spec(spec);spec.loader.exec_module(sec)
ml=sec.ml;anc=sec.anc;ps=sec.ps;base=sec.base;ev=sec.ev
SONGS=sec.SONGS

def smooth_active(probs,threshold,min_run):
    raw=np.asarray(probs)>=threshold
    active=np.zeros_like(raw,dtype=bool)
    i=0
    while i<len(raw):
        if not raw[i]:i+=1;continue
        j=i+1
        while j<len(raw) and raw[j]:j+=1
        if j-i>=min_run:active[i:j]=True
        i=j
    return active

def params():
    p=sec.params()
    p.update({"crash_window_beats":.15,"crash_prob":.60,
              "section_threshold":.58,"section_min_windows":2,"section_timbre_gate":-.20,
              "ride_hit_periodic":.0})
    return p

def transcribe(d,crash_model,section_model,p):
    raw=base.raw_candidates(d["band"],d["sim"])
    stage=base.ks_arbitrate([e for e in raw if e["group"]!="cymbal"],d["band"],d["sim"],p)

    pc=crash_model.predict(d["cym_X"]);phase=ml.phase_from_probs(d,d["cym_frames"],pc)
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"]
    for i,fr in enumerate(d["cym_frames"]):
        t=fr*ev.HOP/ev.SR;x=(t-phase)%bar;dist=min(x,bar-x)/beat
        if pc[i]>=p["crash_prob"] and dist<=p["crash_window_beats"]:
            stage.append({"time":t,"frame":fr,"group":"crash","score":float(pc[i]),"confidence":float(1+2*pc[i])})

    probs=section_model.predict(d["section_X_all"])
    active=smooth_active(probs,p["section_threshold"],p["section_min_windows"])
    ranges=d["section_ranges_all"]
    hat_times=[e["time"] for e in stage if e["group"]=="hat"]
    converted=[]
    for e in stage:
        if e["group"]!="hat":converted.append(e);continue
        covering=[i for i,(a,b) in enumerate(ranges) if a<=e["time"]<b and active[i]]
        secp=max([float(probs[i]) for i in covering],default=0.)
        timbre=float(d["sim"][5,e["frame"]]-d["sim"][2,e["frame"]])
        if hat_times:
            hi=min(range(len(hat_times)),key=lambda k:abs(hat_times[k]-e["time"]))
            per=base.periodic_support(hat_times,hi,d["bpm"])
        else:per=0.
        if secp>=p["section_threshold"] and timbre>=p["section_timbre_gate"] and per>=p["ride_hit_periodic"]:
            x=dict(e);x["group"]="ride";x["confidence"]=max(x["confidence"],1+1.8*secp+.25*max(0,timbre)+.2*per);converted.append(x)
        else:converted.append(e)
    return base.enforce_two_limb(converted,p),phase

def evaluate(name,p,data,family,outdir):
    result={"params":p,"family":family,"songs":{}};tot=Counter()
    for held in SONGS:
        crash=ml.train_fold(data,held,"rf")[0];section=sec.train_section(data,held,family)
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
    s["selection_score"]=round(s["f1"]+.15*s["macro_f1"]+.24*cym-.20*ks,6);result["summary"]=s;return result

def prepare():
    data=anc.load();ml.build_dataset(data,True);sec.build_windows(data,2);return data
def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data=prepare();root=ROOT/"drumscribe/experiments/generated-search-ride-contiguous";report={"schema":1,"cycles":[]};bestp=None
    # Cycle 22: contiguous positive-window run length.
    res={}
    for name,run in [("c22_run1",1),("c22_run2",2),("c22_run3",3)]:
        p=params();p["section_min_windows"]=run
        res[name]=evaluate(name,p,data,"extra",root/"cycle22")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestp=copy.deepcopy(res[win]["params"]);report["cycles"].append({"cycle":22,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    # Cycle 23: probability threshold around winner.
    res={}
    for name,thr in [("c23_thr_055",.55),("c23_thr_065",.65),("c23_thr_075",.75)]:
        p=copy.deepcopy(bestp);p["section_threshold"]=thr
        res[name]=evaluate(name,p,data,"extra",root/"cycle23")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestp=copy.deepcopy(res[win]["params"]);report["cycles"].append({"cycle":23,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    # Cycle 24: require the converted ride hits themselves to follow a pulse.
    res={}
    for name,per,gate in [("c24_no_hit_gate",0.,-.18),("c24_periodic_050",.50,-.18),("c24_periodic_075",.75,-.22)]:
        p=copy.deepcopy(bestp);p["ride_hit_periodic"]=per;p["section_timbre_gate"]=gate
        res[name]=evaluate(name,p,data,"extra",root/"cycle24")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];bestp=copy.deepcopy(res[win]["params"]);report["cycles"].append({"cycle":24,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"family":"extra","beats_per_window":2,"summary":res[win]["summary"],"params":bestp}
    (ROOT/"drumscribe/experiments/results-iterative-ride-contiguous.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
