"""Cycles 109-111: seed-expand ride recovery.

Combine a high-precision ride seed stream with an older high-recall ride pool.
No chart data is used during prediction. Each candidate writes real MIDI and is
then scored against chart.mid.

Cycle 109: ride-section expansion radius 2 / 4 / 8 beats.
Cycle 110: periodicity threshold 0.25 / 0.50 / 0.75.
Cycle 111: minimum seed support 1 / 2 / 3 within an active section.
"""
from __future__ import annotations
import importlib.util, json, math
from collections import Counter
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

BASE=EXP/"generated-search-tom-fusion/cycle105/c105_cluster2"
SEED=EXP/"generated-search-ride-song-gate/cycle108/c108_per50"
POOL=EXP/"generated-search-composite/cycle28/c28_ride_recall"

def rows(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]

def meta(song):
    return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)

def periodic(times,t,bpm):
    if len(times)<3:return 0.0
    best=0.0
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.07 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def cluster_seed_count(seeds,t,radius_s):
    return sum(abs(x-t)<=radius_s for x in seeds)

def enforce(events):
    # Deduplicate same-class hits.
    ded=[]
    mind={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.05,"tom":.05,"crash":.10,"ride":.045,"other":.04}
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mind.get(g,.04):
                ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0
    pri={"snare":.92,"tom":.86,"crash":.84,"ride":.82,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[x for x in c if x[1] not in HANDS];h=[x for x in c if x[1] in HANDS]
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def predict(song,radius_beats,per_thr,min_seeds):
    b=rows(BASE,song)
    seed=[t for t,g in rows(SEED,song) if g=="ride"]
    pool=[t for t,g in rows(POOL,song) if g=="ride"]
    m=meta(song);bpm=float(m["bpm"]);beat=60/bpm
    radius=radius_beats*beat

    chosen=list(seed)
    for t in pool:
        if near(chosen,t,.04):continue
        if cluster_seed_count(seed,t,radius)<min_seeds:continue
        if periodic(pool,t,bpm)<per_thr:continue
        chosen.append(t)

    # Ride and hand-open hat compete for the same hand/cymbal role. Replace only
    # hats at nearly identical times, not the whole local hat pattern.
    events=[e for e in b if e[1]!="ride"]
    for t in sorted(chosen):
        events=[e for e in events if not(e[1]=="hat" and abs(e[0]-t)<=.050)]
        events.append((t,"ride"))
    return enforce(events)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,radius,per_thr,min_seeds,outdir):
    result={"radius_beats":radius,"periodic_threshold":per_thr,"min_seeds":min_seeds,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=predict(song,radius,per_thr,min_seeds)
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]

    tp,n,mref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mref,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mref,4) if mref else 0,
       "f1":round(2*tp/(n+mref),4) if n+mref else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    parts=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),
          "count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):parts.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"]
    # Ride has extra weight because zero-ride candidates must not win simply by
    # avoiding false positives, while all other parts remain in the score.
    s["selection_score"]=round(s["f1"]+.18*sum(parts)/len(parts)+.10*s["by_group"]["ride"]["f1"]+.05*ped-.25*ks,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):
    return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-ride-seed-expand";report={"schema":1,"cycles":[]}

    res={}
    for name,r in [("c109_radius2",2),("c109_radius4",4),("c109_radius8",8)]:
        res[name]=evaluate(name,r,.50,1,root/"cycle109");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":109,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,p in [("c110_per25",.25),("c110_per50",.50),("c110_per75",.75)]:
        res[name]=evaluate(name,best["radius_beats"],p,best["min_seeds"],root/"cycle110");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":110,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,n in [("c111_seed1",1),("c111_seed2",2),("c111_seed3",3)]:
        res[name]=evaluate(name,best["radius_beats"],best["periodic_threshold"],n,root/"cycle111");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":111,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"radius_beats":res[win]["radius_beats"],"periodic_threshold":res[win]["periodic_threshold"],"min_seeds":res[win]["min_seeds"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-ride-seed-expand.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
