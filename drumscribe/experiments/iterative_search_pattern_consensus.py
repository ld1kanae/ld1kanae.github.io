"""Cycles 55-57: rhythm repetition consensus on the hybrid winner.

Runs only after results-iterative-component-hybrid.json exists.
No chart information is used to filter events. Reference MIDI is consulted only
after the new MIDI is written for canonical evaluation.

Cycle 55: three repetition models
Cycle 56: three local context lengths
Cycle 57: three support thresholds
"""
from __future__ import annotations
import importlib.util, json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]

def source_dir():
    obj=json.loads((EXP/"results-iterative-component-hybrid.json").read_text())
    winner=obj["final"]["winner"]
    return EXP/"generated-search-component-hybrid"/"cycle54"/winner,winner

def phase(events,meta):
    bpm=float(meta["bpm"]);ts=meta.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(128):
        ph=bar*q/128;score=0.
        for t,g,*_ in events:
            if g not in ("kick","snare"):continue
            w=1.7 if g=="kick" else .8
            x=(t-ph)%bar;d=min(x,bar-x)
            score+=w*math.exp(-.5*(d/max(.025,.10*beat))**2)
        if score>best[0]:best=(score,ph)
    return best[1],beat,bar

def annotate(events,meta):
    ph,beat,bar=phase(events,meta)
    rows=[]
    for e in events:
        t,g,*rest=e
        rel=t-ph
        b=math.floor(rel/bar)
        x=(rel-b*bar)/bar
        slot=int(round(x*16))%16
        micro=(x*16-round(x*16))*bar/16
        rows.append({"time":t,"group":g,"bar":b,"slot":slot,"micro":micro})
    return rows,ph,beat,bar

def fill_bars(rows):
    by=Counter(r["bar"] for r in rows)
    tom=Counter(r["bar"] for r in rows if r["group"]=="tom")
    vals=list(by.values()) or [0];med=statistics.median(vals)
    return {b for b,n in by.items() if tom[b]>=2 or n>=med+5}

def support(rows,r,window):
    bars=range(r["bar"]-window,r["bar"]+window+1)
    hits={x["bar"] for x in rows if x["group"]==r["group"] and x["slot"]==r["slot"] and x["bar"] in bars}
    return len(hits)

def global_frequency(rows,r):
    bars={x["bar"] for x in rows}
    if not bars:return 0
    hits={x["bar"] for x in rows if x["group"]==r["group"] and x["slot"]==r["slot"]}
    return len(hits)/len(bars)

def apply(rows,mode,window,min_support,bar):
    fills=fill_bars(rows);out=[]
    for r in rows:
        g=r["group"];keep=True
        if g=="crash":
            # Hybrid crash source already has acoustic evidence; still reject
            # obvious non-head events to honor the product rule.
            keep=r["slot"] in (0,15)
        elif g in ("tom","ride","pedal_hat"):
            # These are sparse/structural; do not erase them via common-pattern
            # consensus. Their own dedicated classifiers remain responsible.
            keep=True
        elif mode=="global":
            threshold={"kick":.08,"snare":.10,"hat":.10}.get(g,.06)
            keep=global_frequency(rows,r)>=threshold or r["bar"] in fills
        elif mode=="local":
            keep=support(rows,r,window)>=min_support or r["bar"] in fills
        elif mode=="multires":
            s=support(rows,r,window)
            # Strong 8th-note lattice gets easier support; off-grid 16ths need
            # more evidence except inside fills.
            need=max(1,min_support-1) if r["slot"]%2==0 else min_support
            keep=s>=need or r["bar"] in fills
            if g=="snare" and r["slot"] in (4,12): keep=True
        if keep:out.append((r["time"],g))
    return out

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,src,mode,window,min_support,outdir):
    result={"mode":mode,"window":window,"min_support":min_support,"source":str(src),"songs":{}};tot=Counter()
    for song in SONGS:
        folder=ROOT/"DruMaster/songs"/song;meta=json.loads((folder/"song.json").read_text())
        pred0=ev.midi_events(src/f"{song}.mid")
        rows,ph,beat,bar=annotate(pred0,meta)
        pred=apply(rows,mode,window,min_support,bar)
        path=outdir/name/f"{song}.mid";write(path,pred,float(meta["bpm"]))
        parsed=ev.midi_events(path);truth=ev.midi_events(folder/"chart.mid")
        shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
        sc=ev.score(parsed,truth,shift);cf=ev.confusion(parsed,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,m=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4) if n else 0,"recall":round(tp/m,4) if m else 0,"f1":round(2*tp/(n+m),4) if n+m else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    parts=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{})
            rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None,
          "mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):parts.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(s["f1"]+.20*sum(parts)/len(parts)-.25*ks,6);result["summary"]=s
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"]
    return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    src,srcname=source_dir();root=EXP/"generated-search-pattern-consensus";report={"schema":1,"source_winner":srcname,"cycles":[]}
    res={}
    for name,mode,w,sup in [
      ("c55_global","global",8,2),
      ("c55_local","local",4,2),
      ("c55_multires","multires",4,2),
    ]:
        res[name]=evaluate(name,src,mode,w,sup,root/"cycle55")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":55,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,w in [("c56_window2",2),("c56_window4",4),("c56_window8",8)]:
        res[name]=evaluate(name,src,best["mode"],w,best["min_support"],root/"cycle56")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":56,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,sup in [("c57_support1",1),("c57_support2",2),("c57_support3",3)]:
        res[name]=evaluate(name,src,best["mode"],best["window"],sup,root/"cycle57")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":57,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"mode":res[win]["mode"],"window":res[win]["window"],"min_support":res[win]["min_support"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-pattern-consensus.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()

# trigger-after-hybrid-1
