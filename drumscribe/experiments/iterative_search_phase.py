"""Search cycles 4-6: downbeat phase, crash window, then ride recovery.

Every candidate writes real MIDI and re-parses that MIDI before chart.mid scoring.
Reference MIDI is scoring/diagnostics only and is never used by transcribe_candidate().
"""
from __future__ import annotations
import copy, importlib.util, json, math
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".")
spec=importlib.util.spec_from_file_location("base",ROOT/"drumscribe/experiments/iterative_search.py")
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
ev=base.ev
SONGS=base.SONGS

def continuous_score_phase(events,bpm,num,den,mode,sim):
    beat=60/bpm*4/den;bar=beat*num
    if mode=="all":
        sigma=max(.035,beat*.11);best=(-1,0.)
        for i in range(128):
            ph=bar*i/128;score=0.
            for e in events:
                w=3.2 if e["group"]=="cymbal" else 1.8 if e["group"]=="kick" else .8 if e["group"]=="snare" else .1
                x=(e["time"]-ph)%bar;d=min(x,bar-x)
                score+=w*e["confidence"]*math.exp(-.5*(d/sigma)**2)
            if score>best[0]:best=(score,ph)
        return best[1]
    if mode=="crash_template":
        sigma=max(.035,beat*.10);best=(-1,0.)
        cym=[e for e in events if e["group"]=="cymbal"]
        for i in range(128):
            ph=bar*i/128;score=0.
            for e in cym:
                d0=(e["time"]-ph)%bar;d=min(d0,bar-d0)
                crash_like=max(0.,float(sim[4,e["frame"]])-.20)
                score+=e["confidence"]*crash_like*math.exp(-.5*(d/sigma)**2)
            if score>best[0]:best=(score,ph)
        return best[1]
    # Two-stage beat grid, then choose which beat is bar head from common
    # kick/snare/crash accent structure.
    sigma=max(.025,beat*.08);best=(-1,0.)
    for i in range(64):
        phi=beat*i/64;score=0.
        for e in events:
            if e["group"] not in ("kick","snare"):continue
            x=(e["time"]-phi)%beat;d=min(x,beat-x)
            score+=e["confidence"]*math.exp(-.5*(d/sigma)**2)
        if score>best[0]:best=(score,phi)
    beat_phase=best[1]
    best=(-1e30,beat_phase)
    for head in range(num):
        ph=(beat_phase+head*beat)%bar;score=0.
        for e in events:
            rel=(e["time"]-ph)/beat
            nearest=round(rel);d=abs(rel-nearest)*beat
            if d>beat*.20:continue
            pos=nearest%num;align=math.exp(-.5*(d/sigma)**2)
            if e["group"]=="kick":
                w=1.8 if pos==0 else .35
            elif e["group"]=="snare":
                if num==4:w=1.15 if pos in (1,3) else -.35
                else:w=.55 if pos!=0 else -.25
            elif e["group"]=="cymbal":
                crash_like=max(0.,float(sim[4,e["frame"]])-.20)
                w=(3.4 if pos==0 else -.20)*crash_like
            else:
                w=0
            score+=w*e["confidence"]*align
        if score>best[0]:best=(score,ph)
    return best[1]

def periodic(times,i,bpm):
    return base.periodic_support(times,i,bpm)

def direct_ride_candidates(band,sim,p):
    if p["ride_stream"]=="none":return []
    threshold=p["ride_stream_threshold"];distance=.075
    out=[]
    for fr in base.peaks(band[3],threshold,distance):
        rs=float(sim[5,fr]);hs=float(sim[2,fr])
        if rs<p["ride_stream_sim"] or rs<hs*p["ride_stream_vs_hat"]:continue
        out.append({"time":fr*ev.HOP/ev.SR,"frame":fr,"group":"ride_direct",
                    "score":float(band[3,fr]),
                    "confidence":float(band[3,fr]/threshold+.8*rs)})
    return out

def split_cymbal(events,band,sim,bpm,num,den,p,phase):
    cym=[e for e in events if e["group"]=="cymbal"]
    rest=[dict(e) for e in events if e["group"]!="cymbal"]
    times=[e["time"] for e in cym]
    beat=60/bpm*4/den;bar=beat*num
    def head_dist(t):
        x=(t-phase)%bar;return min(x,bar-x)/beat
    for i,e in enumerate(cym):
        fr=e["frame"];dist=head_dist(e["time"]);per=periodic(times,i,bpm)
        cs=float(sim[4,fr]);rs=float(sim[5,fr]);hs=float(sim[2,fr])
        crash_ok=(dist<=p["crash_window_beats"] and e["score"]>=p["crash_score"] and cs>=p["crash_sim"])
        high=float(band[3,fr]/(band[2,fr]+1e-7))
        ride_ok=(per>=p["ride_periodic"] and high>=p["ride_high_ratio"] and e["score"]>=p["ride_score"]
                 and rs>=p["ride_sim"] and rs>=hs*p["ride_vs_hat"])
        if crash_ok and (not ride_ok or dist<=p["crash_prefer_beats"]):
            x=dict(e);x["group"]="crash";x["confidence"]*=1+.45*(1-dist/max(p["crash_window_beats"],1e-6));rest.append(x)
        elif ride_ok:
            x=dict(e);x["group"]="ride";x["confidence"]*=1+.3*per;rest.append(x)

    direct=direct_ride_candidates(band,sim,p)
    direct_times=[e["time"] for e in direct]
    existing=[e["time"] for e in rest if e["group"]=="ride"]
    for i,e in enumerate(direct):
        per=periodic(direct_times,i,bpm)
        if per<p["ride_direct_periodic"]:continue
        if any(abs(t-e["time"])<=.055 for t in existing):continue
        x=dict(e);x["group"]="ride";x["confidence"]*=1+.3*per;rest.append(x);existing.append(x["time"])
    return sorted(rest,key=lambda e:(e["time"],e["group"]))

def transcribe_candidate(d,p):
    raw=base.raw_candidates(d["band"],d["sim"])
    stage=base.ks_arbitrate(raw,d["band"],d["sim"],p)
    phase=continuous_score_phase(stage,d["bpm"],d["num"],d["den"],p["phase_mode"],d["sim"])
    stage=split_cymbal(stage,d["band"],d["sim"],d["bpm"],d["num"],d["den"],p,phase)
    stage=base.enforce_two_limb(stage,p)
    return stage,phase

def reference_crash_phase(truth,shift,bpm,num,den):
    times=[t+shift for t,g,*_ in truth if g=="crash"]
    if not times:return None
    beat=60/bpm*4/den;bar=beat*num;sigma=max(.035,beat*.10);best=(-1,0.)
    for i in range(128):
        ph=bar*i/128;score=0.
        for t in times:
            x=(t-ph)%bar;d=min(x,bar-x);score+=math.exp(-.5*(d/sigma)**2)
        if score>best[0]:best=(score,ph)
    return best[1]

def phase_error_beats(a,b,bpm,num,den):
    if b is None:return None
    beat=60/bpm*4/den;bar=beat*num
    d=abs(a-b)%bar;d=min(d,bar-d)
    return round(d/beat,4)

def poly_violations(parsed,window=.035):
    limited={"snare","hat","tom","crash","ride"};xs=sorted((t,g) for t,g,*_ in parsed if g in limited)
    v=0;i=0
    while i<len(xs):
        start=xs[i][0];j=i
        while j<len(xs) and xs[j][0]-start<=window:j+=1
        if j-i>2:v+=1
        i=j
    return v

def evaluate_candidate(name,p,data,outdir):
    result={"params":p,"songs":{}};total=Counter()
    for song,d in data.items():
        pred,phase=transcribe_candidate(d,p)
        mid=outdir/name/f"{song}.mid";base.write_midi(mid,pred,d["bpm"])
        parsed=ev.midi_events(mid);truth=ev.midi_events(d["folder"]/"chart.mid")
        sc=ev.score(parsed,truth,d["shift"]);cf=ev.confusion(parsed,truth,d["shift"])
        refph=reference_crash_phase(truth,d["shift"],d["bpm"],d["num"],d["den"])
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc)
        sc["phase_estimate_sec"]=round(phase,5)
        sc["phase_error_beats_posthoc"]=phase_error_beats(phase,refph,d["bpm"],d["num"],d["den"])
        sc["two_limb_violations"]=poly_violations(parsed,p["poly_window"])
        result["songs"][song]=sc
        total.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                     kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],
                     poly=sc["two_limb_violations"])
        for g,x in sc["by_group"].items():
            total[f"{g}_tp"]+=x["tp"];total[f"{g}_pred"]+=x["predicted"];total[f"{g}_ref"]+=x["reference"]
    tp,n,m=total["tp"],total["predicted"],total["reference"]
    s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4),"recall":round(tp/m,4),
       "f1":round(2*tp/(n+m),4),"kick_to_snare":total["kick_to_snare"],"snare_to_kick":total["snare_to_kick"],
       "two_limb_violations":total["poly"],"by_group":{}}
    macro=[]
    for g in ["kick","snare","hat","tom","crash","ride"]:
        a,b,c=total[f"{g}_tp"],total[f"{g}_pred"],total[f"{g}_ref"];f=2*a/(b+c) if b+c else 0;macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,
                          "recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/6,4)
    cym=(s["by_group"]["crash"]["f1"]+s["by_group"]["ride"]["f1"])/2
    ks_rate=total["kick_to_snare"]/max(1,total["kick_ref"])
    s["selection_score"]=round(s["f1"]+.15*s["macro_f1"]+.10*cym-.20*ks_rate,6)
    result["summary"]=s
    return result

def starting():
    p=base.base_params()
    p.update({"snare_ratio":1.65,"snare_margin":.22,"crash_window_beats":.06,"crash_prefer_beats":.045,
              "crash_score":1.1,"crash_sim":.34,"ride_periodic":.80,"ride_high_ratio":.60,
              "ride_score":1.0,"ride_sim":.36,"ride_vs_hat":1.08,"poly_window":.033,
              "phase_mode":"all","ride_stream":"none","ride_stream_threshold":.30,
              "ride_stream_sim":.32,"ride_stream_vs_hat":1.06,"ride_direct_periodic":.65})
    return p

def phase_variants():
    b=starting();out={}
    for name,mode in [("c4_all_phase","all"),("c4_crash_phase","crash_template"),("c4_backbeat_phase","backbeat")]:
        x=copy.deepcopy(b);x["phase_mode"]=mode;out[name]=x
    return out

def window_variants(best):
    out={}
    for name,w in [("c5_tight_head",.055),("c5_medium_head",.10),("c5_wide_head",.16)]:
        x=copy.deepcopy(best);x["crash_window_beats"]=w;x["crash_prefer_beats"]=min(.05,w*.55);out[name]=x
    return out

def ride_variants(best):
    out={}
    a=copy.deepcopy(best);a.update(ride_stream="none");out["c6_no_direct_ride"]=a
    a=copy.deepcopy(best);a.update(ride_stream="direct",ride_stream_threshold=.34,ride_stream_sim=.36,ride_stream_vs_hat=1.10,ride_direct_periodic=.75);out["c6_direct_precision"]=a
    a=copy.deepcopy(best);a.update(ride_stream="direct",ride_stream_threshold=.24,ride_stream_sim=.28,ride_stream_vs_hat=.98,ride_direct_periodic=.50);out["c6_direct_recall"]=a
    return out

def rank(results):
    return sorted(results.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data=base.load_data();root=ROOT/"drumscribe/experiments/generated-search-phase"
    report={"schema":1,"search_stage":"cycles 4-6","cycles":[]};best=None
    for cycle,variants_fn in [(4,phase_variants),(5,None),(6,None)]:
        variants=phase_variants() if cycle==4 else window_variants(best) if cycle==5 else ride_variants(best)
        results={}
        for name,p in variants.items():
            print("EVAL",cycle,name,flush=True)
            results[name]=evaluate_candidate(name,p,data,root/f"cycle{cycle}")
            print("SUMMARY",name,json.dumps(results[name]["summary"],ensure_ascii=False),flush=True)
        ranked=rank(results);winner=ranked[0][0];best=copy.deepcopy(results[winner]["params"])
        close=[n for n,r in ranked if ranked[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]
        report["cycles"].append({"cycle":cycle,"candidates":results,"ranking":[n for n,_ in ranked],"winner":winner,"carried_close":close})
    report["final"]={"winner":report["cycles"][-1]["winner"],"summary":report["cycles"][-1]["candidates"][report["cycles"][-1]["winner"]]["summary"],"params":best}
    path=ROOT/"drumscribe/experiments/results-iterative-phase.json";path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
