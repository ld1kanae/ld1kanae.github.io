"""Cycles 64-66: pedal-hi-hat component search.

Uses the completed recall-repair winner as the base and swaps only note 44.
No chart information is used to choose individual events.

Cycle 64: compare three historical pedal classifiers.
Cycle 65: source fusion (single / consensus / union).
Cycle 66: periodic-section filtering strengths.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]

SOURCES={
 "strict":EXP/"generated-search-pedal-hat/cycle32/c32_strict",
 "logistic":EXP/"generated-search-pedal-hat/cycle31/c31_logistic",
 "recall":EXP/"generated-search-pedal-hat/cycle32/c32_recall",
}

def winner_dir():
    o=json.loads((EXP/"results-iterative-recall-repair.json").read_text());w=o["final"]["winner"]
    return EXP/"generated-search-recall-repair"/"cycle63"/w,w

def rows(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]

def source_ped(src,song):
    return sorted(t for t,g in rows(SOURCES[src],song) if g=="pedal_hat")

def merge_times(a,b,mode):
    if mode=="single":return sorted(a)
    if mode=="consensus":
        return sorted(t for t in a if any(abs(t-x)<=.055 for x in b))
    xs=sorted(a+b);out=[];last=-999.
    for t in xs:
        if t-last>=.045:out.append(t);last=t
    return out

def periodic(times,t,bpm):
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.065 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def filter_section(times,bpm,thr):
    if thr<=0:return times
    out=[];beat=60/bpm
    for t in times:
        loc=sum(abs(x-t)<=beat*4 for x in times)
        if periodic(times,t,bpm)>=thr and loc>=4:out.append(t)
    return out

def replace_pedal(base_rows,ped):
    return sorted([x for x in base_rows if x[1]!="pedal_hat"]+[(t,"pedal_hat") for t in ped],key=lambda x:x[0])

def write(path,rs,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in rs],bpm)

def evaluate(name,bd,src_a,src_b,fusion,per_thr,outdir):
    result={"base":str(bd),"source_a":src_a,"source_b":src_b,"fusion":fusion,"periodic_threshold":per_thr,"songs":{}};tot=Counter()
    for song in SONGS:
        folder=ROOT/"DruMaster/songs"/song;m=json.loads((folder/"song.json").read_text());bpm=float(m["bpm"])
        a=source_ped(src_a,song);b=source_ped(src_b,song) if src_b else []
        p=merge_times(a,b,fusion);p=filter_section(p,bpm,per_thr)
        rr=replace_pedal(rows(bd,song),p);path=outdir/name/f"{song}.mid";write(path,rr,bpm)
        pred=ev.midi_events(path);truth=ev.midi_events(folder/"chart.mid");shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mref,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mref,4) if mref else 0,"f1":round(2*tp/(n+mref),4) if n+mref else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    parts=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None,
          "mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","pedal_hat","tom","crash","ride"):parts.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(s["f1"]+.20*sum(parts)/len(parts)-.25*ks,6);result["summary"]=s
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    bd,bn=winner_dir();root=EXP/"generated-search-pedal-component";report={"schema":1,"base_winner":bn,"cycles":[]}
    res={}
    for name,src in [("c64_strict","strict"),("c64_logistic","logistic"),("c64_recall","recall")]:
        res[name]=evaluate(name,bd,src,None,"single",0,root/"cycle64");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best_src=res[win]["source_a"]
    report["cycles"].append({"cycle":64,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    configs=[("c65_single",best_src,None,"single"),("c65_consensus",best_src,"logistic" if best_src!="logistic" else "strict","consensus"),("c65_union",best_src,"logistic" if best_src!="logistic" else "strict","union")]
    for name,a,b,mode in configs:
        res[name]=evaluate(name,bd,a,b,mode,0,root/"cycle65");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":65,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,thr in [("c66_no_periodic",0),("c66_periodic_025",.25),("c66_periodic_050",.50)]:
        res[name]=evaluate(name,bd,best["source_a"],best["source_b"],best["fusion"],thr,root/"cycle66");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":66,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"source_a":res[win]["source_a"],"source_b":res[win]["source_b"],"fusion":res[win]["fusion"],"periodic_threshold":res[win]["periodic_threshold"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-pedal-component.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()

# trigger-after-recall-1
