"""Cycles 37-39: corrected taxonomy composite search.

Classes: kick, snare, stick hat, pedal_hat, tom, crash, ride.
pedal_hat and kick are exempt from the two-hand limit.
All crash candidates remain hard-limited to the measure-head window.
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
pg=loadmod("pg","drumscribe/experiments/iterative_search_pedal_grid.py")
sec=loadmod("sec2","drumscribe/experiments/iterative_search_ride_section.py")
ped=pg.ped;tom=pg.tom;ml=pg.ml;anc=pg.anc;ps=pg.ps;base=pg.base;ev=pg.ev
SONGS=pg.SONGS

GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride"]

def params():
    p=pg.params()
    p.update({
      "snare_ratio":1.80,"snare_margin":.30,
      "crash_prob":.50,"crash_window_beats":.18,
      "pedal_prob":.70,"pedal_grid_beats":.10,"pedal_periodic":.25,"pedal_sim_margin":-.05,
      "ride_mode":"off","section_threshold":.70,"section_timbre_gate":-.12,"section_min_windows":1
    })
    return p

def active_windows(probs,thr,min_run):
    raw=np.asarray(probs)>=thr;active=np.zeros_like(raw,dtype=bool);i=0
    while i<len(raw):
        if not raw[i]:i+=1;continue
        j=i+1
        while j<len(raw) and raw[j]:j+=1
        if j-i>=min_run:active[i:j]=True
        i=j
    return active

def transcribe(d,held,data,tm,pm,cm,sm,p):
    raw=base.raw_candidates(d["band"],d["sim"])
    stage=base.ks_arbitrate([e for e in raw if e["group"] not in ("cymbal","tom")],d["band"],d["sim"],p)

    pc=cm.predict(d["cym_X"]);phase=ml.phase_from_probs(d,d["cym_frames"],pc)
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"]
    for i,fr in enumerate(d["cym_frames"]):
        t=fr*ev.HOP/ev.SR;x=(t-phase)%bar;dist=min(x,bar-x)/beat
        if pc[i]>=p["crash_prob"] and dist<=p["crash_window_beats"]:
            stage.append({"time":t,"frame":fr,"group":"crash","score":float(pc[i]),"confidence":float(1+2*pc[i])})

    tprob=tm.predict(d["tom_X"])
    for i,prob in enumerate(tprob):
        if prob<p["tom_prob"]:continue
        fr=d["tom_frames"][i];t=fr*ev.HOP/ev.SR
        close=[e for e in stage if e["group"] in ("kick","snare") and abs(e["time"]-t)<=.035]
        if close and prob<.78:continue
        stage.append({"time":t,"frame":fr,"group":"tom","score":float(prob),"confidence":float(1+2*prob)})

    # Stick/pedal split. Candidate foot hits must be on the beat grid and periodic.
    pp=pm.predict(d["pedal_X_all"]);cand_i=[];cand_t=[]
    for i,fr in enumerate(d["pedal_frames_all"]):
        t=fr*ev.HOP/ev.SR
        margin=float(d["sim"][7,fr]-d["sim"][2,fr])
        if pp[i]>=p["pedal_prob"] and margin>=p["pedal_sim_margin"] and pg.beat_distance(t,phase,d["bpm"],d["den"])<=p["pedal_grid_beats"]:
            cand_i.append(i);cand_t.append(t)
    pos={ii:k for k,ii in enumerate(cand_i)}
    split=[]
    for e in stage:
        if e["group"]!="hat":split.append(e);continue
        i=d["pedal_index"].get(e["frame"]);k=pos.get(i)
        if k is None:split.append(e);continue
        per=pg.periodic(cand_t,k,d["bpm"],d["den"])
        if per>=p["pedal_periodic"]:
            x=dict(e);x["group"]="pedal_hat";x["confidence"]=max(x["confidence"],1+2*float(pp[i])+.25*per);split.append(x)
        else:split.append(e)
    stage=split

    # Ride only re-labels remaining hand-played hats, never pedal_hat.
    if p["ride_mode"]!="off":
        rp=sm.predict(d["section_X_all"]);active=active_windows(rp,p["section_threshold"],p["section_min_windows"])
        ranges=d["section_ranges_all"];converted=[]
        for e in stage:
            if e["group"]!="hat":converted.append(e);continue
            cover=[i for i,(a,b) in enumerate(ranges) if a<=e["time"]<b and active[i]]
            sp=max([float(rp[i]) for i in cover],default=0.)
            margin=float(d["sim"][5,e["frame"]]-d["sim"][2,e["frame"]])
            if sp>=p["section_threshold"] and margin>=p["section_timbre_gate"]:
                x=dict(e);x["group"]="ride";x["confidence"]=max(x["confidence"],1+1.8*sp+.25*max(0,margin));converted.append(x)
            else:converted.append(e)
        stage=converted

    return base.enforce_two_limb(stage,p),phase

def evaluate(name,p,data,outdir):
    result={"params":p,"songs":{}};tot=Counter()
    for held in SONGS:
        tm=tom.train_tom(data,held,"rf")
        pm=ped.train(data,held,"logistic")
        cm=ml.train_fold(data,held,"rf")[0]
        sm=sec.train_section(data,held,"extra")
        pred,phase=transcribe(data[held],held,data,tm,pm,cm,sm,p)
        mid=outdir/name/f"{held}.mid";base.write_midi(mid,pred,data[held]["bpm"])
        parsed=ev.midi_events(mid);truth=ev.midi_events(data[held]["folder"]/"chart.mid")
        sc=ev.score(parsed,truth,data[held]["shift"]);cf=ev.confusion(parsed,truth,data[held]["shift"])
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);sc["two_limb_violations"]=ps.poly_violations(parsed,p["poly_window"])
        result["songs"][held]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],poly=sc["two_limb_violations"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,m=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4),"recall":round(tp/m,4),"f1":round(2*tp/(n+m),4),
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":tot["poly"],"by_group":{}}
    macro=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0;macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/len(macro),4)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(
      s["f1"]+.10*s["macro_f1"]
      +.10*s["by_group"]["pedal_hat"]["f1"]+.10*s["by_group"]["tom"]["f1"]
      +.10*s["by_group"]["crash"]["f1"]+.14*s["by_group"]["ride"]["f1"]
      -.20*ks,6)
    result["summary"]=s;return result

def prepare():
    data=anc.load();ml.build_dataset(data,True);tom.build_tom(data);ped.build(data);sec.build_windows(data,2);return data
def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data=prepare();root=ROOT/"drumscribe/experiments/generated-search-composite-v2";report={"schema":2,"taxonomy":"pedal_hat_split","cycles":[]};best=None

    # Cycle 37: human-review-worthy ride policies.
    res={}
    configs=[
      ("c37_precision","off",.82,-.05,1),
      ("c37_ride_balanced","section",.70,-.12,1),
      ("c37_ride_recall","section",.58,-.20,1)
    ]
    for name,mode,thr,gate,run in configs:
        p=params();p.update(ride_mode=mode,section_threshold=thr,section_timbre_gate=gate,section_min_windows=run)
        res[name]=evaluate(name,p,data,root/"cycle37")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":37,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    # Cycle 38: pedal conservatism around the winning ride policy.
    res={}
    for name,prob,period in [("c38_pedal_strict",.80,.50),("c38_pedal_balanced",.70,.25),("c38_pedal_recall",.62,.25)]:
        p=copy.deepcopy(best);p["pedal_prob"]=prob;p["pedal_periodic"]=period
        res[name]=evaluate(name,p,data,root/"cycle38")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":38,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    # Cycle 39: crash recall while retaining the hard measure-head rule.
    res={}
    for name,prob,w in [("c39_crash_strict",.65,.14),("c39_crash_balanced",.50,.18),("c39_crash_recall",.42,.20)]:
        p=copy.deepcopy(best);p["crash_prob"]=prob;p["crash_window_beats"]=w
        res[name]=evaluate(name,p,data,root/"cycle39")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":39,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    report["final"]={"winner":win,"summary":res[win]["summary"],"params":best}
    (ROOT/"drumscribe/experiments/results-iterative-composite-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
