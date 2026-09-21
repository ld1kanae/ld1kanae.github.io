"""Cycles 106-108: pairwise ride consensus.

Targets the gap between:
- high-resolution ride detector: useful ride recall but too many hat->ride swaps
- strict 3-way intersection: too few ride hits

Prediction uses only audio-derived MIDI sources + BPM.
chart.mid is evaluation only after writing each MIDI.

Cycle 106: HI+OLD, HI+SECTION, HI+(OLD or SECTION)
Cycle 107: match windows 30/50/75 ms
Cycle 108: periodic support 0/0.25/0.50
"""
from __future__ import annotations
import importlib.util,json
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
HI=EXP/"generated-search-ride-hires/cycle86/c86_logistic"
OLD=EXP/"generated-search-composite/cycle28/c28_ride_recall"
SEC=EXP/"generated-search-ride-section/cycle20/c20_logistic"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def periodic(times,t,bpm):
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.065 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def dedupe(xs,w=.035):
    out=[];last=-999.
    for t in sorted(xs):
        if t-last>=w:out.append(t);last=t
    return out

def ride_candidates(song,mode,window,per_thr):
    hi=[t for t,g in rows(HI,song) if g=="ride"]
    old=[t for t,g in rows(OLD,song) if g=="ride"]
    sec=[t for t,g in rows(SEC,song) if g=="ride"]
    if mode=="hi_old":
        cand=[t for t in hi if near(old,t,window)]
    elif mode=="hi_sec":
        cand=[t for t in hi if near(sec,t,window)]
    else:
        cand=[t for t in hi if near(old,t,window) or near(sec,t,window)]
    cand=dedupe(cand,.040)
    bpm=float(meta(song)["bpm"])
    if per_thr>0:cand=[t for t in cand if periodic(cand,t,bpm)>=per_thr]
    return cand

def enforce(events):
    ded=[];mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.05,"tom":.05,"crash":.09,"ride":.04}
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0;pri={"snare":.93,"tom":.88,"crash":.84,"ride":.83,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def build(song,mode,window,per_thr,hat_replace):
    b=rows(BASE,song);rides=ride_candidates(song,mode,window,per_thr)
    out=[e for e in b if e[1]!="ride"];hats=[t for t,g in out if g=="hat"]
    for t in rides:
        hs=[x for x in hats if abs(x-t)<=hat_replace]
        if hs:
            h=min(hs,key=lambda x:abs(x-t))
            out=[e for e in out if not(e[1]=="hat" and abs(e[0]-h)<=1e-6)]
            out.append((h,"ride"))
        else:
            # Pairwise consensus is already two-detector support, so adding a
            # no-hat ride candidate is allowed.
            out.append((t,"ride"))
    return enforce(out)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,window,per_thr,hat_replace,outdir):
    result={"mode":mode,"window":window,"periodic_threshold":per_thr,"hat_replace":hat_replace,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=build(song,mode,window,per_thr,hat_replace)
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
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
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),
          "false_discovery_rate":round((b-a)/b,4) if b else 0,"miss_rate":round((c-a)/c,4) if c else 0,
          "count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):core.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"];ride=s["by_group"]["ride"];hat=s["by_group"]["hat"]
    s["selection_score"]=round(s["f1"]+.16*sum(core)/len(core)+.12*ride["f1"]+.07*ped-.05*ride["false_discovery_rate"]-.04*hat["false_discovery_rate"]-.28*ks,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-ride-pairwise";report={"schema":1,"cycles":[]}
    res={}
    for name,mode in [("c106_hi_old","hi_old"),("c106_hi_sec","hi_sec"),("c106_hi_either","hi_either")]:
        res[name]=evaluate(name,mode,.050,0,.050,root/"cycle106");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":106,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,w in [("c107_w30",.030),("c107_w50",.050),("c107_w75",.075)]:
        res[name]=evaluate(name,best["mode"],w,best["periodic_threshold"],best["hat_replace"],root/"cycle107");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":107,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,p in [("c108_per0",0),("c108_per25",.25),("c108_per50",.50)]:
        res[name]=evaluate(name,best["mode"],best["window"],p,best["hat_replace"],root/"cycle108");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":108,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"mode":res[win]["mode"],"window":res[win]["window"],"periodic_threshold":res[win]["periodic_threshold"],"hat_replace":res[win]["hat_replace"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-ride-pairwise.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
