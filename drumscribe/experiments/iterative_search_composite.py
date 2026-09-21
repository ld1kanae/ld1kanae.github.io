"""Cycles 28-30: combine the best kick/snare, tom, crash and ride subsystems.

Every candidate follows:
drums.mp3 -> prediction -> real MIDI file -> re-parse MIDI -> chart.mid scoring.
All learned models use leave-one-song-out training for evaluation.
"""
from __future__ import annotations
import copy, importlib.util, json
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".")
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
tom=loadmod("tom", "drumscribe/experiments/iterative_search_tom.py")
sec=loadmod("sec", "drumscribe/experiments/iterative_search_ride_section.py")
ml=tom.ml;anc=tom.anc;ps=tom.ps;base=tom.base;ev=tom.ev
SONGS=base.SONGS

def params():
    p=tom.params()
    p.update({
      "tom_prob":.62,"tom_context":"none",
      "crash_prob":.60,"crash_window_beats":.15,
      "ride_mode":"off","section_threshold":.70,"section_timbre_gate":-.12,
      "section_min_windows":1
    })
    return p

def active_windows(probs,thr,min_run):
    raw=np.asarray(probs)>=thr
    active=np.zeros_like(raw,dtype=bool)
    i=0
    while i<len(raw):
        if not raw[i]:i+=1;continue
        j=i+1
        while j<len(raw) and raw[j]:j+=1
        if j-i>=min_run:active[i:j]=True
        i=j
    return active

def transcribe(d,held,data,tom_model,crash_model,section_model,p):
    raw=base.raw_candidates(d["band"],d["sim"])
    stage=base.ks_arbitrate([e for e in raw if e["group"] not in ("cymbal","tom")],d["band"],d["sim"],p)

    pc=crash_model.predict(d["cym_X"]);phase=ml.phase_from_probs(d,d["cym_frames"],pc)
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"]
    for i,fr in enumerate(d["cym_frames"]):
        t=fr*ev.HOP/ev.SR;x=(t-phase)%bar;dist=min(x,bar-x)/beat
        # User rule: crash stays a hard measure-head-only decision.
        if pc[i]>=p["crash_prob"] and dist<=p["crash_window_beats"]:
            stage.append({"time":t,"frame":fr,"group":"crash","score":float(pc[i]),"confidence":float(1+2*pc[i])})

    probs=tom_model.predict(d["tom_X"])
    for i,prob in enumerate(probs):
        if prob<p["tom_prob"]:continue
        fr=d["tom_frames"][i];t=fr*ev.HOP/ev.SR
        close=[e for e in stage if e["group"] in ("kick","snare") and abs(e["time"]-t)<=.035]
        if close and prob<.78:continue
        stage.append({"time":t,"frame":fr,"group":"tom","score":float(prob),"confidence":float(1+2*prob)})

    if p["ride_mode"]!="off":
        rprob=section_model.predict(d["section_X_all"])
        active=active_windows(rprob,p["section_threshold"],p["section_min_windows"])
        ranges=d["section_ranges_all"]
        converted=[]
        for e in stage:
            if e["group"]!="hat":converted.append(e);continue
            cover=[i for i,(a,b) in enumerate(ranges) if a<=e["time"]<b and active[i]]
            secp=max([float(rprob[i]) for i in cover],default=0.)
            timbre=float(d["sim"][5,e["frame"]]-d["sim"][2,e["frame"]])
            if secp>=p["section_threshold"] and timbre>=p["section_timbre_gate"]:
                x=dict(e);x["group"]="ride";x["confidence"]=max(x["confidence"],1+1.8*secp+.25*max(0,timbre));converted.append(x)
            else:converted.append(e)
        stage=converted

    return base.enforce_two_limb(stage,p),phase

def evaluate(name,p,data,outdir):
    result={"params":p,"songs":{}};tot=Counter()
    for held in SONGS:
        tm=tom.train_tom(data,held,"rf")
        cm=ml.train_fold(data,held,"rf")[0]
        sm=sec.train_section(data,held,"extra")
        pred,phase=transcribe(data[held],held,data,tm,cm,sm,p)
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
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(
        s["f1"]+.12*s["macro_f1"]
        +.12*s["by_group"]["tom"]["f1"]+.12*s["by_group"]["crash"]["f1"]+.14*s["by_group"]["ride"]["f1"]
        -.20*ks,6)
    result["summary"]=s;return result

def prepare():
    data=anc.load();ml.build_dataset(data,True);tom.build_tom(data);sec.build_windows(data,2);return data
def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data=prepare();root=ROOT/"drumscribe/experiments/generated-search-composite";report={"schema":1,"cycles":[]};best=None

    # Cycle 28: ride policy on top of best tom/crash.
    res={}
    configs=[
      ("c28_ride_off","off",.82,-.05,1),
      ("c28_ride_balanced","section",.70,-.12,1),
      ("c28_ride_recall","section",.58,-.20,1),
    ]
    for name,mode,thr,gate,run in configs:
        p=params();p.update(ride_mode=mode,section_threshold=thr,section_timbre_gate=gate,section_min_windows=run)
        res[name]=evaluate(name,p,data,root/"cycle28")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":28,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    # Cycle 29: kick/snare arbitration around the winner.
    res={}
    for name,ratio,margin in [("c29_ks_guard",1.80,.30),("c29_ks_balanced",1.65,.22),("c29_ks_snare_recall",1.50,.15)]:
        p=copy.deepcopy(best);p["snare_ratio"]=ratio;p["snare_margin"]=margin
        res[name]=evaluate(name,p,data,root/"cycle29")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":29,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    # Cycle 30: crash model threshold/measure-head window. All variants still
    # reject crash outside the measure-head window.
    res={}
    for name,prob,w in [("c30_crash_strict",.72,.12),("c30_crash_balanced",.60,.15),("c30_crash_recall",.50,.18)]:
        p=copy.deepcopy(best);p["crash_prob"]=prob;p["crash_window_beats"]=w
        res[name]=evaluate(name,p,data,root/"cycle30")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":30,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    report["final"]={"winner":win,"summary":res[win]["summary"],"params":best}
    (ROOT/"drumscribe/experiments/results-iterative-composite.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
