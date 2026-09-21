"""Search cycles 13-15: loop-aware downbeat detection.

Uses only drums.mp3-derived candidates and known BPM for transcription.
Every candidate is written to MIDI, re-parsed, then scored against chart.mid.
"""
from __future__ import annotations
import copy, importlib.util, json, math
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".")
spec=importlib.util.spec_from_file_location("rot",ROOT/"drumscribe/experiments/iterative_search_rotation.py")
rot=importlib.util.module_from_spec(spec);spec.loader.exec_module(rot)
base=rot.base;ps=rot.anc.ps;ev=rot.ev

def wrapdist(x,period):
    x=abs(x)%period
    return min(x,period-x)

def phase_grid(d,steps=192):
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"]
    return beat,bar,[bar*i/steps for i in range(steps)]

def event_score(e,d,phase,mode):
    beat,bar,_=phase_grid(d)
    sim=d["sim"];t=e["time"];x=(t-phase)%bar
    sigma=max(.025,beat*.09)
    def pulse(center,w):
        return w*math.exp(-.5*(wrapdist(x-center,bar)/sigma)**2)
    s=0.
    if e["group"]=="kick":
        s += pulse(0,1.7)
        if d["num"]==4:s += pulse(2*beat,.45)
    elif e["group"]=="snare":
        if d["num"]==4:
            s += pulse(beat,1.2)+pulse(3*beat,1.2)-pulse(0,.35)
    elif e["group"]=="cymbal":
        crash=max(0.,float(sim[4,e["frame"]])-.16)
        s += crash*pulse(0,3.6)
        if mode=="boundary_fill":
            s += crash*pulse(0,1.0)
    return s*e["confidence"]

def fill_boundary_score(events,d,phase):
    beat,bar,_=phase_grid(d)
    score=0.
    # Reward fills just before the boundary and kick/cymbal accents at it.
    for e in events:
        x=(e["time"]-phase)%bar
        if e["group"] in ("snare","tom") and bar-.75*beat<=x<bar:
            score += .35*e["confidence"]*(1-(bar-x)/(.75*beat))
        if e["group"]=="cymbal":
            crash=max(0.,float(d["sim"][4,e["frame"]])-.16)
            if x<=.16*beat or x>=bar-.16*beat:score += 2.8*crash*e["confidence"]
        if e["group"]=="kick" and (x<=.14*beat or x>=bar-.14*beat):
            score += .8*e["confidence"]
    return score

def pattern_repeat_score(events,d,phase):
    beat,bar,_=phase_grid(d);sub=beat/4
    bars=max(1,int((d["duration"]-phase)/bar))
    if bars<3:return 0.
    vecs=[]
    for b in range(bars):
        start=phase+b*bar
        v=np.zeros((4,d["num"]*4),dtype=np.float32)
        for e in events:
            if not (start<=e["time"]<start+bar):continue
            k=min(v.shape[1]-1,max(0,int((e["time"]-start)/sub)))
            gi={"kick":0,"snare":1,"hat":2,"cymbal":3}.get(e["group"])
            if gi is not None:v[gi,k]+=min(3.,e["confidence"])
        n=np.linalg.norm(v)
        if n>0:vecs.append((v/n).ravel())
    if len(vecs)<3:return 0.
    A=np.stack(vecs)
    med=np.median(A,axis=0);norm=np.linalg.norm(med)
    if norm<=1e-8:return 0.
    med/=norm
    return float(np.median(A@med))

def estimate_phase(events,d,mode):
    beat,bar,grid=phase_grid(d);best=(-1e30,0.)
    for ph in grid:
        score=sum(event_score(e,d,ph,mode) for e in events)
        if mode in ("boundary_fill","hybrid"):
            score += fill_boundary_score(events,d,ph)
        if mode in ("repeat","hybrid"):
            score += (18. if mode=="hybrid" else 32.)*pattern_repeat_score(events,d,ph)
        if score>best[0]:best=(score,ph)
    return best[1]

def direct_ride(stage,d,p):
    return ps.split_cymbal(stage,d["band"],d["sim"],d["bpm"],d["num"],d["den"],p,p["phase"])

def transcribe(d,p):
    raw=base.raw_candidates(d["band"],d["sim"]);stage=base.ks_arbitrate(raw,d["band"],d["sim"],p)
    ph=estimate_phase(stage,d,p["loop_phase_mode"])
    pp=copy.deepcopy(p);pp["phase"]=ph
    stage=ps.split_cymbal(stage,d["band"],d["sim"],d["bpm"],d["num"],d["den"],pp,ph)
    stage=base.enforce_two_limb(stage,pp)
    return stage,ph

def true_phase(d):
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"];return d["shift"]%bar

def phase_err(ph,d):
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"]
    return round(wrapdist(ph-true_phase(d),bar)/beat,4)

def evaluate(name,p,data,outdir):
    result={"params":p,"songs":{}};total=Counter()
    for song,d in data.items():
        pred,ph=transcribe(d,p);mid=outdir/name/f"{song}.mid";base.write_midi(mid,pred,d["bpm"])
        parsed=ev.midi_events(mid);truth=ev.midi_events(d["folder"]/"chart.mid")
        sc=ev.score(parsed,truth,d["shift"]);cf=ev.confusion(parsed,truth,d["shift"])
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);sc["phase_error_vs_midi_bar_beats"]=phase_err(ph,d)
        sc["two_limb_violations"]=ps.poly_violations(parsed,p["poly_window"]);result["songs"][song]=sc
        total.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],poly=sc["two_limb_violations"])
        for g,x in sc["by_group"].items():
            total[f"{g}_tp"]+=x["tp"];total[f"{g}_pred"]+=x["predicted"];total[f"{g}_ref"]+=x["reference"]
    tp,n,m=total["tp"],total["predicted"],total["reference"]
    s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4),"recall":round(tp/m,4),"f1":round(2*tp/(n+m),4),
       "kick_to_snare":total["kick_to_snare"],"snare_to_kick":total["snare_to_kick"],"two_limb_violations":total["poly"],"by_group":{}}
    macro=[]
    for g in ["kick","snare","hat","tom","crash","ride"]:
        a,b,c=total[f"{g}_tp"],total[f"{g}_pred"],total[f"{g}_ref"];f=2*a/(b+c) if b+c else 0;macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/6,4);cym=(s["by_group"]["crash"]["f1"]+s["by_group"]["ride"]["f1"])/2;ks=total["kick_to_snare"]/max(1,total["kick_ref"])
    s["selection_score"]=round(s["f1"]+.15*s["macro_f1"]+.15*cym-.20*ks,6);result["summary"]=s;return result

def load():
    data=rot.anc.load()
    for d in data.values():
        meta=json.loads((d["folder"]/"song.json").read_text());d["duration"]=float(meta["duration"])
    return data

def start():
    p=ps.starting()
    p.update({"snare_ratio":1.65,"snare_margin":.22,"crash_window_beats":.05,"crash_prefer_beats":.0275,
      "ride_stream":"direct","ride_stream_threshold":.28,"ride_stream_sim":.31,"ride_stream_vs_hat":1.03,"ride_direct_periodic":.62,
      "loop_phase_mode":"boundary_fill"})
    return p

def cycle13():
    b=start();out={}
    for name,m in [("c13_accent","accent"),("c13_boundary_fill","boundary_fill"),("c13_repeat","repeat"),("c13_hybrid","hybrid")]:
        x=copy.deepcopy(b);x["loop_phase_mode"]=m;out[name]=x
    return out

def cycle14(best):
    out={}
    for name,w in [("c14_head_005",.05),("c14_head_010",.10),("c14_head_015",.15)]:
        x=copy.deepcopy(best);x["crash_window_beats"]=w;x["crash_prefer_beats"]=min(.05,w*.55);out[name]=x
    return out

def cycle15(best):
    out={}
    for name,thr,rs,vs,per in [
      ("c15_ride_strict",.32,.34,1.08,.70),
      ("c15_ride_medium",.28,.31,1.03,.62),
      ("c15_ride_recall",.25,.29,1.00,.55)]:
        x=copy.deepcopy(best);x.update(ride_stream="direct",ride_stream_threshold=thr,ride_stream_sim=rs,ride_stream_vs_hat=vs,ride_direct_periodic=per);out[name]=x
    return out

def rank(r):return sorted(r.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data=load();root=ROOT/"drumscribe/experiments/generated-search-loop";report={"schema":1,"cycles":[]};best=None
    for cycle in (13,14,15):
        variants=cycle13() if cycle==13 else cycle14(best) if cycle==14 else cycle15(best);results={}
        for name,p in variants.items():
            print("EVAL",cycle,name,flush=True);results[name]=evaluate(name,p,data,root/f"cycle{cycle}")
            print("SUMMARY",name,json.dumps(results[name]["summary"],ensure_ascii=False),flush=True)
            print("PHASE",name,{s:m["phase_error_vs_midi_bar_beats"] for s,m in results[name]["songs"].items()},flush=True)
        rr=rank(results);winner=rr[0][0];best=copy.deepcopy(results[winner]["params"]);close=[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]
        report["cycles"].append({"cycle":cycle,"candidates":results,"ranking":[n for n,_ in rr],"winner":winner,"carried_close":close})
    report["final"]={"winner":report["cycles"][-1]["winner"],"summary":report["cycles"][-1]["candidates"][report["cycles"][-1]["winner"]]["summary"],"params":best}
    (ROOT/"drumscribe/experiments/results-iterative-loop.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
