"""Cycles 97-99: structural pedal-hi-hat reclassification.

Base: current best fusion-v2 cycle84.
Candidate sources: previously generated strict/recall pedal predictions.
Rules use only predictions and musical structure, never chart.mid:
- hand-supported: pedal candidate coincides with snare/tom/crash and is periodic
- poly-rescue: candidate explains an otherwise 3-hand collision / strong hand event
- gap-repeat: periodic candidate fills a repeated hat-slot gap without a hand-hat

Cycle 97: three structural rules
Cycle 98: periodic support thresholds
Cycle 99: strict / recall / union candidate source
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

BASE=EXP/"generated-search-fusion-v2/cycle84/c84_pedal75"
STRICT=EXP/"generated-search-pedal-repair/cycle76/c76_strict"
RECALL=EXP/"generated-search-pedal-repair/cycle76/c76_recall"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def source_times(song,kind):
    s=[t for t,g in rows(STRICT,song) if g=="pedal_hat"]
    r=[t for t,g in rows(RECALL,song) if g=="pedal_hat"]
    if kind=="strict":return s
    if kind=="recall":return r
    out=sorted(s+r);ded=[];last=-999.
    for t in out:
        if t-last>=.035:ded.append(t);last=t
    return ded

def phase(events,m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;sc=0.
        for t,g in events:
            if g not in ("kick","snare"):continue
            w=1.7 if g=="kick" else .8;x=(t-ph)%bar;d=min(x,bar-x)
            sc+=w*math.exp(-.5*(d/max(.025,.10*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def periodic(times,t,bpm):
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.06 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def slot(t,ph,bar):return int(round((((t-ph)%bar)/bar)*16))%16

def repeat_support(times,t,ph,bar):
    s=slot(t,ph,bar);b=math.floor((t-ph)/bar);bars=set()
    for x in times:
        bx=math.floor((x-ph)/bar)
        if abs(bx-b)<=6 and slot(x,ph,bar)==s:bars.add(bx)
    return len(bars)

def choose(song,rule,per_thr,source):
    b=rows(BASE,song);m=meta(song);bpm=float(m["bpm"]);ph,beat,bar=phase(b,m)
    cand=source_times(song,source)
    hand=[t for t,g in b if g in ("snare","tom","crash","ride")]
    hats=[t for t,g in b if g=="hat"]
    kicks=[t for t,g in b if g=="kick"]
    chosen=[]
    for t in cand:
        per=periodic(cand,t,bpm)
        hand_n=sum(abs(x-t)<=.035 for x in hand)
        kick=near(kicks,t,.035);hat=near(hats,t,.035)
        rep=repeat_support(cand,t,ph,bar)
        if rule=="hand_supported":
            keep=per>=per_thr and hand_n>=1 and not hat
        elif rule=="poly_rescue":
            keep=per>=per_thr and ((hand_n>=2) or (hand_n>=1 and kick)) and not hat
        else:
            # A repeated foot pattern may appear where no hand-hat is predicted.
            # Stronger support is required if no simultaneous hand accent exists.
            keep=(not hat) and per>=per_thr and (hand_n>=1 or rep>=3)
        if keep:chosen.append(t)
    others=[e for e in b if e[1]!="pedal_hat"]
    return sorted(others+[(t,"pedal_hat") for t in chosen])

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,rule,per_thr,source,outdir):
    result={"rule":rule,"periodic_threshold":per_thr,"source":source,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=choose(song,rule,per_thr,source);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid");shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mr,4) if mr else 0,"f1":round(2*tp/(n+mr),4) if n+mr else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    core=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,
          "f1":round(f,4),"count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):core.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"]
    # pedal gets explicit weight so the score cannot prefer deleting it.
    s["selection_score"]=round(s["f1"]+.18*sum(core)/len(core)+.12*ped-.30*ks,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-pedal-structural";report={"schema":1,"cycles":[]}
    res={}
    for name,rule in [("c97_hand","hand_supported"),("c97_poly","poly_rescue"),("c97_gap","gap_repeat")]:
        res[name]=evaluate(name,rule,.50,"recall",root/"cycle97");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":97,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,p in [("c98_per25",.25),("c98_per50",.50),("c98_per75",.75)]:
        res[name]=evaluate(name,best["rule"],p,best["source"],root/"cycle98");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":98,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for src in ("strict","recall","union"):
        name=f"c99_{src}";res[name]=evaluate(name,best["rule"],best["periodic_threshold"],src,root/"cycle99");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":99,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"rule":res[win]["rule"],"periodic_threshold":res[win]["periodic_threshold"],"source":res[win]["source"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-pedal-structural.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
