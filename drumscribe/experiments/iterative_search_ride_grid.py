"""Cycles 100-102: latent beat-grid ride section detection.

The previous true-run experiment failed because missing ride candidates break
consecutive chains. This version tolerates missing hits: it estimates the best
quarter/eighth-note pulse phase inside sliding windows and scores how many ride
candidates lie near that latent grid.

Inputs during prediction are audio-derived ride candidates + BPM only.
chart.mid is used only after generated MIDI is written.
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

def best_grid(local,beat,tol_frac):
    """Return best fit score and fitted candidate times for 8th/quarter grids."""
    if len(local)<2:return 0.,[]
    best=(0.,[])
    for step in (beat*.5,beat):
        tol=step*tol_frac
        # Candidate-derived phases avoid using any reference timing.
        phases=[t%step for t in local]
        for ph in phases:
            good=[]
            for t in local:
                x=(t-ph)%step;d=min(x,step-x)
                if d<=tol:good.append(t)
            score=len(good)/len(local)
            if score>best[0]:best=(score,good)
    return best

def active_windows(times,bpm,window_beats,fit_thr,min_hits,contig,tol_frac):
    beat=60/float(bpm);win=window_beats*beat
    if not times:return []
    start=math.floor(min(times)/win)*win;end=max(times)+win
    ws=[];x=start
    while x<end:
        local=[t for t in times if x<=t<x+win]
        score,good=best_grid(local,beat,tol_frac)
        ws.append({"a":x,"b":x+win,"active":len(local)>=min_hits and score>=fit_thr,"good":good,"score":score,"n":len(local)})
        x+=win
    keep=[False]*len(ws)
    i=0
    while i<len(ws):
        if not ws[i]["active"]:i+=1;continue
        j=i+1
        while j<len(ws) and ws[j]["active"]:j+=1
        if j-i>=contig:
            for k in range(i,j):keep[k]=True
        i=j
    selected=[]
    for flag,w in zip(keep,ws):
        if flag:selected.extend(w["good"])
    return sorted(set(round(t,6) for t in selected))

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
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def fuse(song,fit_thr,window_beats,min_hits,contig,tol_frac):
    b=rows(BASE,song);cand=[t for t,g in rows(RIDE,song) if g=="ride"];m=meta(song)
    chosen=active_windows(cand,float(m["bpm"]),window_beats,fit_thr,min_hits,contig,tol_frac)
    # Convert only nearby hand-hat hits inside accepted ride sections.
    out=[e for e in b if e[1]!="ride"]
    out=[e for e in out if not(e[1]=="hat" and any(abs(e[0]-t)<=.045 for t in chosen))]
    out += [(t,"ride") for t in chosen]
    return enforce(out)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,fit_thr,window_beats,min_hits,contig,tol_frac,outdir):
    result={"fit_thr":fit_thr,"window_beats":window_beats,"min_hits":min_hits,"contig":contig,"tol_frac":tol_frac,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=fuse(song,fit_thr,window_beats,min_hits,contig,tol_frac);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
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
    s["selection_score"]=round(s["f1"]+.16*sum(core)/len(core)+.08*ped+.15*ride["f1"]-.06*ride["false_discovery_rate"]-.28*ks-.05*hf,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-ride-grid";report={"schema":1,"cycles":[]}
    res={}
    for name,thr in [("c100_fit50",.50),("c100_fit65",.65),("c100_fit80",.80)]:
        res[name]=evaluate(name,thr,8,3,2,.18,root/"cycle100");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":100,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,w in [("c101_win4",4),("c101_win8",8),("c101_win16",16)]:
        res[name]=evaluate(name,best["fit_thr"],w,best["min_hits"],best["contig"],best["tol_frac"],root/"cycle101");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":101,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,n in [("c102_contig1",1),("c102_contig2",2),("c102_contig3",3)]:
        res[name]=evaluate(name,best["fit_thr"],best["window_beats"],best["min_hits"],n,best["tol_frac"],root/"cycle102");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":102,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"fit_thr":res[win]["fit_thr"],"window_beats":res[win]["window_beats"],"min_hits":res[win]["min_hits"],"contig":res[win]["contig"],"tol_frac":res[win]["tol_frac"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-ride-grid.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
