"""Cycles 97-99: actual periodic ride-run extraction.

Unlike the earlier 'contiguous' experiment, this operates directly on the
timestamps of an audio-derived ride candidate stream and requires consecutive
quarter/eighth-note pulse support.

Base non-ride parts come from fusion-v2 c84. Ride candidates come from the
historical high-recall c28 source. chart.mid is evaluation-only.
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
RIDE=EXP/"generated-search-composite/cycle28/c28_ride_recall"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def pulse_match(dt,beat,tol):
    for mult in (.5,1.0):
        step=beat*mult
        if abs(dt-step)<=tol*step:return True
    return False

def build_runs(times,beat,tol,min_run):
    """Return timestamps belonging to true consecutive pulse chains."""
    times=sorted(times)
    if not times:return []
    runs=[];cur=[times[0]]
    for t in times[1:]:
        dt=t-cur[-1]
        if pulse_match(dt,beat,tol):
            cur.append(t)
        else:
            if len(cur)>=min_run:runs.append(cur)
            cur=[t]
    if len(cur)>=min_run:runs.append(cur)
    return runs

def section_filter(times,beat,tol,min_run):
    """Four-beat windows; retain windows containing a pulse-consistent run."""
    if not times:return []
    win=4*beat
    start=math.floor(times[0]/win)*win
    end=times[-1]+win
    active=[]
    x=start
    while x<end:
        local=[t for t in times if x<=t<x+win]
        runs=build_runs(local,beat,tol,min_run)
        if runs:
            active.append((x,x+win))
        x+=win
    # Require neighboring active windows to reduce isolated false sections.
    joined=[]
    for i,(a,b) in enumerate(active):
        prev=i>0 and abs(active[i-1][1]-a)<1e-6
        nxt=i+1<len(active) and abs(b-active[i+1][0])<1e-6
        if prev or nxt:joined.append((a,b))
    return [t for t in times if any(a<=t<b for a,b in joined)]

def select(times,bpm,mode,min_run,tol):
    beat=60/float(bpm)
    runs=build_runs(times,beat,tol,min_run)
    direct=sorted({t for r in runs for t in r})
    if mode=="run":return direct
    section=section_filter(times,beat,tol,min_run)
    if mode=="section":return section
    return sorted(set(direct).intersection(section))

def enforce(events):
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        mind=.09 if g=="crash" else .045 if g=="pedal_hat" else .035 if g in ("snare","hat","ride") else .045
        for t in arr:
            if t-last>=mind:ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0;pri={"snare":.93,"tom":.88,"crash":.84,"ride":.83,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def fuse(song,mode,min_run,tol,replace_hat):
    b=rows(BASE,song); cand=[t for t,g in rows(RIDE,song) if g=="ride"];m=meta(song)
    chosen=select(cand,float(m["bpm"]),mode,min_run,tol)
    out=[e for e in b if e[1]!="ride"]
    if replace_hat:
        out=[e for e in out if not(e[1]=="hat" and any(abs(e[0]-t)<=.045 for t in chosen))]
    out += [(t,"ride") for t in chosen]
    return enforce(out)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,min_run,tol,replace_hat,outdir):
    result={"mode":mode,"min_run":min_run,"tol":tol,"replace_hat":replace_hat,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=fuse(song,mode,min_run,tol,replace_hat);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
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
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),
          "false_discovery_rate":round((b-a)/b,4) if b else 0,"miss_rate":round((c-a)/c,4) if c else 0,
          "count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):core.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"];hf=s["by_group"]["hat"]["false_discovery_rate"];ride=s["by_group"]["ride"]
    # Strongly reward ride precision+recall so all-off is not favored merely
    # for avoiding false positives, while still penalizing bad ride FDR.
    s["selection_score"]=round(s["f1"]+.16*sum(core)/len(core)+.08*ped+.14*ride["f1"]-.05*ride["false_discovery_rate"]-.28*ks-.05*hf,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-ride-runs";report={"schema":1,"cycles":[]}
    res={}
    for name,mode in [("c97_run","run"),("c97_section","section"),("c97_both","both")]:
        res[name]=evaluate(name,mode,5,.16,True,root/"cycle97");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":97,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,n in [("c98_run3",3),("c98_run5",5),("c98_run7",7)]:
        res[name]=evaluate(name,best["mode"],n,best["tol"],True,root/"cycle98");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":98,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,tol in [("c99_tol08",.08),("c99_tol16",.16),("c99_tol24",.24)]:
        res[name]=evaluate(name,best["mode"],best["min_run"],tol,True,root/"cycle99");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":99,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"mode":res[win]["mode"],"min_run":res[win]["min_run"],"tol":res[win]["tol"],"replace_hat":True,"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-ride-runs.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
