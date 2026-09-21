"""Cycles 118-120: zero-seed ride fallback.

Starts from adaptive ride logic. For songs with zero tight ride seeds, a
high-recall ride pool can be enabled only when its candidate density relative to
current hi-hat activity is high. No chart data is used for prediction.

Cycle 118: fallback activation ratio 0.10 / 0.15 / 0.20.
Cycle 119: fallback periodic threshold 0.50 / 0.75 / 1.00.
Cycle 120: fallback local density 3 / 5 / 7 candidates within +/-2 beats.
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
HANDS={"snare","hat","tom","crash","ride"}

BASE=EXP/"generated-search-tom-consensus/cycle105/c105_density7"
TIGHT=EXP/"generated-search-ride-song-gate/cycle108/c108_per50"
EXPAND=EXP/"generated-search-composite/cycle28/c28_ride_recall"

def rows(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]

def meta(song):
    return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def periodic(times,t,bpm):
    if len(times)<3:return 0.0
    best=0.0
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.07 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def local_density(times,t,span):
    return sum(abs(x-t)<=span for x in times)

def enforce(events):
    ded=[]
    mind={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.05,"tom":.05,"crash":.10,"ride":.045,"other":.04}
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mind.get(g,.04):ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0
    pri={"snare":.92,"tom":.86,"crash":.84,"ride":.82,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[x for x in c if x[1] not in HANDS];h=[x for x in c if x[1] in HANDS]
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def predict(song,ratio_thr,per_thr,density_need):
    b=rows(BASE,song); tight=[t for t,g in rows(TIGHT,song) if g=="ride"]; pool=[t for t,g in rows(EXPAND,song) if g=="ride"]
    hats=sum(1 for _,g in b if g=="hat");m=meta(song);bpm=float(m["bpm"]);beat=60/bpm
    seed_ratio=len(tight)/max(1,hats);fallback_ratio=len(pool)/max(1,hats)
    if tight:
        if seed_ratio>=.03:
            chosen=tight;mode="tight"
        else:
            chosen=pool;mode="expand"
    elif fallback_ratio>=ratio_thr:
        chosen=[t for t in pool if periodic(pool,t,bpm)>=per_thr and local_density(pool,t,2*beat)>=density_need]
        mode="fallback"
    else:
        chosen=[];mode="off"
    events=[e for e in b if e[1]!="ride"]
    for t in chosen:
        events=[e for e in events if not(e[1]=="hat" and abs(e[0]-t)<=.03)]
        events.append((t,"ride"))
    return enforce(events),{"seed_count":len(tight),"pool_count":len(pool),"hat_count":hats,"seed_ratio":seed_ratio,"fallback_ratio":fallback_ratio,"mode":mode,"ride_count":len(chosen)}

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,ratio_thr,per_thr,density_need,outdir):
    result={"fallback_ratio_threshold":ratio_thr,"periodic_threshold":per_thr,"density_need":density_need,"song_decisions":{},"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr,dec=predict(song,ratio_thr,per_thr,density_need);result["song_decisions"][song]=dec
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mref,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mref,4) if mref else 0,
       "f1":round(2*tp/(n+mref),4) if n+mref else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    parts=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];gf=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});r=x.get("reference",0)
            if r:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+r) if x.get("predicted",0)+r else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,
          "f1":round(gf,4),"count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):parts.append(gf)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"]
    s["selection_score"]=round(s["f1"]+.18*sum(parts)/len(parts)+.12*s["by_group"]["ride"]["f1"]+.05*ped-.25*ks,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-ride-fallback";report={"schema":1,"cycles":[]}
    res={}
    for name,t in [("c118_ratio10",.10),("c118_ratio15",.15),("c118_ratio20",.20)]:
        res[name]=evaluate(name,t,.75,5,root/"cycle118");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":118,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    res={}
    for name,t in [("c119_per50",.50),("c119_per75",.75),("c119_per100",1.00)]:
        res[name]=evaluate(name,best["fallback_ratio_threshold"],t,best["density_need"],root/"cycle119");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":119,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    res={}
    for name,n in [("c120_density3",3),("c120_density5",5),("c120_density7",7)]:
        res[name]=evaluate(name,best["fallback_ratio_threshold"],best["periodic_threshold"],n,root/"cycle120");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":120,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"fallback_ratio_threshold":res[win]["fallback_ratio_threshold"],"periodic_threshold":res[win]["periodic_threshold"],"density_need":res[win]["density_need"],"song_decisions":res[win]["song_decisions"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-ride-fallback.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
