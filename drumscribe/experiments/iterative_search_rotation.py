"""Search cycles 10-12: rotate beat-aligned phase by musical pattern priors."""
from __future__ import annotations
import copy, importlib.util, json, math
from pathlib import Path

ROOT=Path(".")
spec=importlib.util.spec_from_file_location("anchor",ROOT/"drumscribe/experiments/iterative_search_anchor.py")
anc=importlib.util.module_from_spec(spec);spec.loader.exec_module(anc)
ps=anc.ps;base=anc.base;ev=anc.ev

def all_phase(events,d):
    return ps.continuous_score_phase(events,d["bpm"],d["num"],d["den"],"all",d["sim"])

def rotate_quality(events,d,phase,weights):
    bpm,num,den,sim=d["bpm"],d["num"],d["den"],d["sim"]
    beat=60/bpm*4/den;sigma=max(.025,beat*.085);score=0.
    for e in events:
        rel=(e["time"]-phase)/beat;nearest=round(rel);dist=abs(rel-nearest)*beat
        if dist>beat*.22:continue
        pos=nearest%num;align=math.exp(-.5*(dist/sigma)**2)
        w=0.
        if e["group"]=="kick":
            if pos==0:w=weights["kick_head"]
            elif num==4 and pos==2:w=weights["kick_mid"]
            else:w=weights["kick_other"]
        elif e["group"]=="snare":
            if num==4 and pos in (1,3):w=weights["snare_back"]
            elif pos==0:w=weights["snare_head"]
            else:w=weights["snare_other"]
        elif e["group"]=="cymbal":
            cs=max(0.,float(sim[4,e["frame"]])-.18)
            w=(weights["crash_head"] if pos==0 else weights["crash_other"])*cs
        score += w*e["confidence"]*align
    return score

WEIGHTS={
 "kick_only":{"kick_head":2.1,"kick_mid":.5,"kick_other":.15,"snare_back":1.0,"snare_head":-.55,"snare_other":.15,"crash_head":1.0,"crash_other":0},
 "balanced":{"kick_head":1.8,"kick_mid":.4,"kick_other":.1,"snare_back":1.35,"snare_head":-.45,"snare_other":.05,"crash_head":3.0,"crash_other":-.15},
 "crash_heavy":{"kick_head":1.25,"kick_mid":.3,"kick_other":.05,"snare_back":1.0,"snare_head":-.35,"snare_other":.05,"crash_head":5.0,"crash_other":-.25},
}

def phase_estimate(events,d,p):
    ph=all_phase(events,d)
    if p["rotation_mode"]=="none":return ph
    beat=60/d["bpm"]*4/d["den"];bar=beat*d["num"];w=WEIGHTS[p["rotation_mode"]]
    candidates=[(ph+k*beat)%bar for k in range(d["num"])]
    return max(candidates,key=lambda x:rotate_quality(events,d,x,w))

def transcribe(d,p):
    raw=base.raw_candidates(d["band"],d["sim"]);stage=base.ks_arbitrate(raw,d["band"],d["sim"],p)
    phase=phase_estimate(stage,d,p)
    stage=ps.split_cymbal(stage,d["band"],d["sim"],d["bpm"],d["num"],d["den"],p,phase)
    stage=base.enforce_two_limb(stage,p)
    return stage,phase

def evaluate(name,p,data,outdir):
    from collections import Counter
    result={"params":p,"songs":{}};total=Counter()
    for song,d in data.items():
        pred,phase=transcribe(d,p);mid=outdir/name/f"{song}.mid";base.write_midi(mid,pred,d["bpm"])
        parsed=ev.midi_events(mid);truth=ev.midi_events(d["folder"]/"chart.mid")
        sc=ev.score(parsed,truth,d["shift"]);cf=ev.confusion(parsed,truth,d["shift"])
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);sc["phase_error_vs_midi_bar_beats"]=anc.phase_err(phase,d)
        sc["two_limb_violations"]=ps.poly_violations(parsed,p["poly_window"]);result["songs"][song]=sc
        total.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],poly=sc["two_limb_violations"])
        for g,x in sc["by_group"].items():
            total[f"{g}_tp"]+=x["tp"];total[f"{g}_pred"]+=x["predicted"];total[f"{g}_ref"]+=x["reference"]
    tp,n,m=total["tp"],total["predicted"],total["reference"];s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4),"recall":round(tp/m,4),"f1":round(2*tp/(n+m),4),"kick_to_snare":total["kick_to_snare"],"snare_to_kick":total["snare_to_kick"],"two_limb_violations":total["poly"],"by_group":{}}
    macro=[]
    for g in ["kick","snare","hat","tom","crash","ride"]:
        a,b,c=total[f"{g}_tp"],total[f"{g}_pred"],total[f"{g}_ref"];f=2*a/(b+c) if b+c else 0;macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/6,4);cym=(s["by_group"]["crash"]["f1"]+s["by_group"]["ride"]["f1"])/2;ks=total["kick_to_snare"]/max(1,total["kick_ref"])
    s["selection_score"]=round(s["f1"]+.15*s["macro_f1"]+.12*cym-.20*ks,6);result["summary"]=s;return result

def start():
    p=ps.starting()
    p.update({"snare_ratio":1.65,"snare_margin":.22,"crash_window_beats":.05,"crash_prefer_beats":.0275,
      "ride_stream":"direct","ride_stream_threshold":.32,"ride_stream_sim":.34,"ride_stream_vs_hat":1.08,"ride_direct_periodic":.70,
      "rotation_mode":"none"})
    return p

def cycle10():
    b=start();out={}
    for name,m in [("c10_no_rotation","none"),("c10_kick_rotation","kick_only"),("c10_balanced_rotation","balanced"),("c10_crash_rotation","crash_heavy")]:
        x=copy.deepcopy(b);x["rotation_mode"]=m;out[name]=x
    return out

def cycle11(best):
    out={}
    # Keep winner and vary crash head width without changing its phase selector.
    for name,w in [("c11_head_005",.05),("c11_head_010",.10),("c11_head_015",.15)]:
        x=copy.deepcopy(best);x["crash_window_beats"]=w;x["crash_prefer_beats"]=min(.05,w*.55);out[name]=x
    return out

def cycle12(best):
    out={}
    for name,thr,sim,vs,per in [
      ("c12_ride_strict",.32,.34,1.08,.70),
      ("c12_ride_medium",.28,.31,1.03,.62),
      ("c12_ride_recall",.25,.29,1.00,.55)]:
        x=copy.deepcopy(best);x.update(ride_stream="direct",ride_stream_threshold=thr,ride_stream_sim=sim,ride_stream_vs_hat=vs,ride_direct_periodic=per);out[name]=x
    return out

def rank(r):return sorted(r.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data=anc.load();root=ROOT/"drumscribe/experiments/generated-search-rotation";report={"schema":1,"cycles":[]};best=None
    for cycle in (10,11,12):
        variants=cycle10() if cycle==10 else cycle11(best) if cycle==11 else cycle12(best);results={}
        for name,p in variants.items():
            print("EVAL",cycle,name,flush=True);results[name]=evaluate(name,p,data,root/f"cycle{cycle}")
            print("SUMMARY",name,json.dumps(results[name]["summary"],ensure_ascii=False),flush=True)
            print("PHASE",name,{s:m["phase_error_vs_midi_bar_beats"] for s,m in results[name]["songs"].items()},flush=True)
        rr=rank(results);winner=rr[0][0];best=copy.deepcopy(results[winner]["params"]);close=[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]
        report["cycles"].append({"cycle":cycle,"candidates":results,"ranking":[n for n,_ in rr],"winner":winner,"carried_close":close})
    report["final"]={"winner":report["cycles"][-1]["winner"],"summary":report["cycles"][-1]["candidates"][report["cycles"][-1]["winner"]]["summary"],"params":best}
    (ROOT/"drumscribe/experiments/results-iterative-rotation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
