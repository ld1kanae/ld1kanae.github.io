"""Search cycles 7-9: robust bar-head anchoring and ride threshold search."""
from __future__ import annotations
import copy, importlib.util, json, math
from pathlib import Path
import numpy as np

ROOT=Path(".")
spec=importlib.util.spec_from_file_location("ps",ROOT/"drumscribe/experiments/iterative_search_phase.py")
ps=importlib.util.module_from_spec(spec);spec.loader.exec_module(ps)
base=ps.base;ev=ps.ev

def grid_score(candidates,bpm,num,den,weight_fn,steps=192):
    beat=60/bpm*4/den;bar=beat*num;sigma=max(.03,beat*.085);best=(-1,0.)
    for i in range(steps):
        ph=bar*i/steps;score=0.
        for e in candidates:
            x=(e["time"]-ph)%bar;d=min(x,bar-x)
            score+=weight_fn(e)*math.exp(-.5*(d/sigma)**2)
        if score>best[0]:best=(score,ph)
    return best[1],best[0]

def phase_estimate(events,d,p):
    bpm,num,den,sim=d["bpm"],d["num"],d["den"],d["sim"];mode=p["phase_mode"]
    if mode=="all":
        return ps.continuous_score_phase(events,bpm,num,den,"all",sim)
    cym=[e for e in events if e["group"]=="cymbal"]
    if not cym:return ps.continuous_score_phase(events,bpm,num,den,"all",sim)
    def evidence(e):
        return e["confidence"]*max(0.,float(sim[4,e["frame"]])-.18)
    ranked=sorted(cym,key=evidence,reverse=True)
    if mode=="top_crash":
        n=max(12,min(80,round(d["duration"]/60*p["top_crash_per_min"])))
        chosen=ranked[:n]
        ph,_=grid_score(chosen,bpm,num,den,evidence)
        return ph
    if mode=="early_crash":
        chosen=[e for e in ranked if e["time"]<=p["early_seconds"]][:p["early_topn"]]
        if len(chosen)<2:chosen=ranked[:max(2,p["early_topn"])]
        ph,_=grid_score(chosen,bpm,num,den,evidence)
        return ph
    if mode=="section_vote":
        beat=60/bpm*4/den;bar=beat*num
        votes=[]
        section=p["section_seconds"];start=0.
        while start<d["duration"]:
            part=[e for e in cym if start<=e["time"]<start+section]
            part=sorted(part,key=evidence,reverse=True)[:p["section_topn"]]
            if part:
                ph,score=grid_score(part,bpm,num,den,evidence,96)
                votes.append((ph,max(score,1e-6)))
            start+=section
        if not votes:return ps.continuous_score_phase(events,bpm,num,den,"all",sim)
        best=(-1,0.)
        sigma=max(.04,beat*.12)
        for i in range(192):
            ph=bar*i/192;score=0.
            for v,w in votes:
                dd=abs(ph-v);dd=min(dd,bar-dd);score+=w*math.exp(-.5*(dd/sigma)**2)
            if score>best[0]:best=(score,ph)
        return best[1]
    raise ValueError(mode)

def transcribe_candidate(d,p):
    raw=base.raw_candidates(d["band"],d["sim"])
    stage=base.ks_arbitrate(raw,d["band"],d["sim"],p)
    phase=phase_estimate(stage,d,p)
    stage=ps.split_cymbal(stage,d["band"],d["sim"],d["bpm"],d["num"],d["den"],p,phase)
    stage=base.enforce_two_limb(stage,p)
    return stage,phase

def true_bar_phase(d):
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"]
    return d["shift"]%bar

def phase_err(phase,d):
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"];ref=true_bar_phase(d)
    x=abs(phase-ref)%bar;return round(min(x,bar-x)/beat,4)

def evaluate(name,p,data,outdir):
    result={"params":p,"songs":{}};tot={}
    from collections import Counter
    total=Counter()
    for song,d in data.items():
        pred,phase=transcribe_candidate(d,p)
        mid=outdir/name/f"{song}.mid";base.write_midi(mid,pred,d["bpm"])
        parsed=ev.midi_events(mid);truth=ev.midi_events(d["folder"]/"chart.mid")
        sc=ev.score(parsed,truth,d["shift"]);cf=ev.confusion(parsed,truth,d["shift"])
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);sc["phase_error_vs_midi_bar_beats"]=phase_err(phase,d)
        sc["two_limb_violations"]=ps.poly_violations(parsed,p["poly_window"]);result["songs"][song]=sc
        total.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                     kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],poly=sc["two_limb_violations"])
        for g,x in sc["by_group"].items():
            total[f"{g}_tp"]+=x["tp"];total[f"{g}_pred"]+=x["predicted"];total[f"{g}_ref"]+=x["reference"]
    tp,n,m=total["tp"],total["predicted"],total["reference"]
    s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4),"recall":round(tp/m,4),"f1":round(2*tp/(n+m),4),
       "kick_to_snare":total["kick_to_snare"],"snare_to_kick":total["snare_to_kick"],"two_limb_violations":total["poly"],"by_group":{}}
    macro=[]
    for g in ["kick","snare","hat","tom","crash","ride"]:
        a,b,c=total[f"{g}_tp"],total[f"{g}_pred"],total[f"{g}_ref"];f=2*a/(b+c) if b+c else 0;macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/6,4);cym=(s["by_group"]["crash"]["f1"]+s["by_group"]["ride"]["f1"])/2
    ks=total["kick_to_snare"]/max(1,total["kick_ref"])
    s["selection_score"]=round(s["f1"]+.15*s["macro_f1"]+.12*cym-.20*ks,6);result["summary"]=s
    return result

def load():
    data=base.load_data()
    for d in data.values():
        # Duration is needed only by internal phase strategies.
        meta=json.loads((d["folder"]/"song.json").read_text());d["duration"]=float(meta["duration"])
    return data

def start():
    p=ps.starting()
    p.update({"crash_window_beats":.055,"crash_prefer_beats":.03025,"phase_mode":"all",
              "top_crash_per_min":16,"early_seconds":45.,"early_topn":10,"section_seconds":24.,"section_topn":6})
    return p

def cycle7():
    b=start();out={}
    for name,mode in [("c7_all","all"),("c7_top_crash","top_crash"),("c7_early_crash","early_crash"),("c7_section_vote","section_vote")]:
        x=copy.deepcopy(b);x["phase_mode"]=mode;out[name]=x
    return out

def cycle8(best):
    out={}
    for name,w in [("c8_head_005",.05),("c8_head_010",.10),("c8_head_015",.15)]:
        x=copy.deepcopy(best);x["crash_window_beats"]=w;x["crash_prefer_beats"]=min(.05,w*.55);out[name]=x
    return out

def cycle9(best):
    out={}
    a=copy.deepcopy(best);a.update(ride_stream="direct",ride_stream_threshold=.32,ride_stream_sim=.34,ride_stream_vs_hat=1.08,ride_direct_periodic=.70);out["c9_ride_strict"]=a
    a=copy.deepcopy(best);a.update(ride_stream="direct",ride_stream_threshold=.28,ride_stream_sim=.31,ride_stream_vs_hat=1.03,ride_direct_periodic=.62);out["c9_ride_medium"]=a
    a=copy.deepcopy(best);a.update(ride_stream="direct",ride_stream_threshold=.25,ride_stream_sim=.29,ride_stream_vs_hat=1.00,ride_direct_periodic=.55);out["c9_ride_recall"]=a
    return out

def rank(res):
    return sorted(res.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data=load();root=ROOT/"drumscribe/experiments/generated-search-anchor";report={"schema":1,"cycles":[]};best=None
    for cycle in (7,8,9):
        variants=cycle7() if cycle==7 else cycle8(best) if cycle==8 else cycle9(best)
        results={}
        for name,p in variants.items():
            print("EVAL",cycle,name,flush=True);results[name]=evaluate(name,p,data,root/f"cycle{cycle}")
            print("SUMMARY",name,json.dumps(results[name]["summary"],ensure_ascii=False),flush=True)
            print("PHASE",name,{s:m["phase_error_vs_midi_bar_beats"] for s,m in results[name]["songs"].items()},flush=True)
        ranked=rank(results);winner=ranked[0][0];best=copy.deepcopy(results[winner]["params"])
        close=[n for n,r in ranked if ranked[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]
        report["cycles"].append({"cycle":cycle,"candidates":results,"ranking":[n for n,_ in ranked],"winner":winner,"carried_close":close})
    report["final"]={"winner":report["cycles"][-1]["winner"],"summary":report["cycles"][-1]["candidates"][report["cycles"][-1]["winner"]]["summary"],"params":best}
    path=ROOT/"drumscribe/experiments/results-iterative-anchor.json";path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
