"""Cycles 76-78: pedal hi-hat component repair.

Uses historical audio-derived pedal-hat candidates and predicted rhythmic
structure only. chart.mid is used only after output MIDI generation.

Cycle 76: current / strict / recall pedal components.
Cycle 77: periodic-support thresholds.
Cycle 78: hand-hat conflict windows.
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

BASE=EXP/"generated-search-recall-repair/cycle63/c63_pedal_keep"
STRICT=EXP/"generated-search-pedal-hat/cycle32/c32_strict"
BAL=EXP/"generated-search-pedal-hat/cycle32/c32_balanced"
RECALL=EXP/"generated-search-pedal-hat/cycle32/c32_recall"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def periodic_support(times,t,bpm):
    if len(times)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.065 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def enforce(events):
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.;mind=.045 if g=="pedal_hat" else .035
        for t in arr:
            if t-last>=mind:ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0;pri={"snare":.9,"tom":.86,"crash":.82,"ride":.78,"hat":.6}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def choose(song,source,per_thr,hat_conflict):
    b=rows(BASE,song)
    src={"current":BASE,"strict":STRICT,"balanced":BAL,"recall":RECALL}[source]
    ped=[t for t,g in rows(src,song) if g=="pedal_hat"]
    bpm=float(meta(song)["bpm"])
    hats=[t for t,g in b if g=="hat"]
    if source!="current":
        kept=[]
        for t in ped:
            if per_thr>0 and periodic_support(ped,t,bpm)<per_thr:continue
            if hat_conflict>0 and near(hats,t,hat_conflict):continue
            kept.append(t)
        ped=kept
    others=[e for e in b if e[1]!="pedal_hat"]
    return enforce(others+[(t,"pedal_hat") for t in ped])

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,source,per_thr,hat_conflict,outdir):
    result={"source":source,"periodic_threshold":per_thr,"hat_conflict":hat_conflict,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=choose(song,source,per_thr,hat_conflict);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid");shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mr,4) if mr else 0,"f1":round(2*tp/(n+mr),4) if n+mr else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    parts=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),
          "count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):parts.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"]
    s["selection_score"]=round(s["f1"]+.20*sum(parts)/len(parts)+.10*ped-.32*ks,6);result["summary"]=s
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-pedal-repair";report={"schema":1,"cycles":[]}
    res={}
    for name,source in [("c76_current","current"),("c76_strict","strict"),("c76_recall","recall")]:
        res[name]=evaluate(name,source,0,0,root/"cycle76");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":76,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    src=best["source"] if best["source"]!="current" else "strict"
    res={}
    for name,p in [("c77_per25",.25),("c77_per50",.50),("c77_per75",.75)]:
        res[name]=evaluate(name,src,p,0,root/"cycle77");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win2=rr[0][0];b2=res[win2]
    report["cycles"].append({"cycle":77,"candidates":res,"ranking":[n for n,_ in rr],"winner":win2,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    if best["summary"]["selection_score"]>b2["summary"]["selection_score"]:cur=best
    else:cur=b2

    src=cur["source"] if cur["source"]!="current" else "strict";pth=cur["periodic_threshold"] if cur["source"]!="current" else .5
    res={}
    for name,w in [("c78_hat0",0),("c78_hat35",.035),("c78_hat70",.070)]:
        res[name]=evaluate(name,src,pth,w,root/"cycle78");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":78,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    final=max([best,b2,res[win]],key=lambda x:x["summary"]["selection_score"])
    report["final"]={"winner":"cross-cycle-best","summary":final["summary"],"source":final["source"],"periodic_threshold":final["periodic_threshold"],"hat_conflict":final["hat_conflict"],"detailed":final["detailed"]}
    (EXP/"results-iterative-pedal-repair.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
