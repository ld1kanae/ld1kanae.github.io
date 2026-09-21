"""Cycles 34-36: pedal hi-hat beat-grid and periodicity priors."""
from __future__ import annotations
import copy, importlib.util, json, math
from collections import Counter
from pathlib import Path

ROOT=Path(".")
spec=importlib.util.spec_from_file_location("ped",ROOT/"drumscribe/experiments/iterative_search_pedal_hat.py")
ped=importlib.util.module_from_spec(spec);spec.loader.exec_module(ped)
tom=ped.tom;ml=ped.ml;anc=ped.anc;ps=ped.ps;base=ped.base;ev=ped.ev
SONGS=ped.SONGS

def params():
    p=ped.params()
    p.update({"pedal_prob":.78,"pedal_sim_margin":-.05,
              "pedal_grid_beats":.10,"pedal_periodic":.50})
    return p

def beat_distance(t,phase,bpm,den):
    beat=60/bpm*4/den
    x=(t-phase)%beat
    return min(x,beat-x)/beat

def periodic(times,i,bpm,den):
    if len(times)<3:return 0.
    beat=60/bpm*4/den;t=times[i];count=0
    for k in (-2,-1,1,2):
        target=t+k*beat
        if any(abs(x-target)<=min(.07,beat*.15) for x in times):count+=1
    return count/4

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
    candidate_indices=[]
    candidate_times=[]
    for i,fr in enumerate(d["pedal_frames_all"]):
        t=fr*ev.HOP/ev.SR
        sim_margin=float(d["sim"][7,fr]-d["sim"][2,fr])
        if pp[i]>=p["pedal_prob"] and sim_margin>=p["pedal_sim_margin"] and beat_distance(t,phase,d["bpm"],d["den"])<=p["pedal_grid_beats"]:
            candidate_indices.append(i);candidate_times.append(t)
    pos={i:k for k,i in enumerate(candidate_indices)}

    converted=[]
    for e in stage:
        if e["group"]!="hat":converted.append(e);continue
        i=d["pedal_index"].get(e["frame"])
        k=pos.get(i)
        if k is None:converted.append(e);continue
        per=periodic(candidate_times,k,d["bpm"],d["den"])
        if per>=p["pedal_periodic"]:
            x=dict(e);x["group"]="pedal_hat";x["confidence"]=max(x["confidence"],1+2*float(pp[i])+.25*per);converted.append(x)
        else:converted.append(e)
    return base.enforce_two_limb(converted,p),phase

def evaluate(name,p,data,outdir):
    result={"params":p,"songs":{}};tot=Counter()
    groups=["kick","snare","hat","pedal_hat","tom","crash","ride"]
    for held in SONGS:
        tm=tom.train_tom(data,held,"rf");pm=ped.train(data,held,"logistic")
        pred,phase=transcribe(data[held],held,data,tm,pm,p)
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
    for g in groups:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0;macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/len(macro),4)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(s["f1"]+.12*s["macro_f1"]+.14*s["by_group"]["pedal_hat"]["f1"]+.12*s["by_group"]["tom"]["f1"]+.10*s["by_group"]["crash"]["f1"]-.20*ks,6)
    result["summary"]=s;return result

def prepare():
    data=anc.load();ml.build_dataset(data,True);tom.build_tom(data);ped.build(data);return data
def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data=prepare();root=ROOT/"drumscribe/experiments/generated-search-pedal-grid";report={"schema":1,"cycles":[]};best=None
    res={}
    for name,w in [("c34_grid_006",.06),("c34_grid_010",.10),("c34_grid_016",.16)]:
        p=params();p["pedal_grid_beats"]=w;res[name]=evaluate(name,p,data,root/"cycle34")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":34,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,per in [("c35_periodic_025",.25),("c35_periodic_050",.50),("c35_periodic_075",.75)]:
        p=copy.deepcopy(best);p["pedal_periodic"]=per;res[name]=evaluate(name,p,data,root/"cycle35")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":35,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,prob in [("c36_prob_070",.70),("c36_prob_080",.80),("c36_prob_090",.90)]:
        p=copy.deepcopy(best);p["pedal_prob"]=prob;res[name]=evaluate(name,p,data,root/"cycle36")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=copy.deepcopy(res[win]["params"])
    report["cycles"].append({"cycle":36,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"params":best}
    (ROOT/"drumscribe/experiments/results-iterative-pedal-grid.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
