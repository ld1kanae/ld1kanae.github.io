"""Cycles 124-126: adaptive hi-hat source switching.

Use disagreement between two audio-derived hi-hat predictors to detect songs
where the high-recall hat stream is likely flooding. No chart data is used to
select the source.

BASE: current balanced high-recall hat.
PAT2/PAT8: repetition-consensus precision-oriented hats.

Cycle 124: disagreement threshold 0.12 / 0.17 / 0.20.
Cycle 125: flagged-song source PAT2 / PAT8 / intersection.
Cycle 126: threshold refinement 0.18 / 0.20 / 0.22.
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
BASE=EXP/"generated-search-tom-consensus/cycle105/c105_density7"
PAT2=EXP/"generated-search-pattern-consensus/cycle56/c56_window2"
PAT8=EXP/"generated-search-pattern-consensus/cycle56/c56_window8"

def rows(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]

def meta(song):
    return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def near(xs,t,w=.040):
    return any(abs(x-t)<=w for x in xs)

def enforce(events):
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.05,"tom":.05,"crash":.09,"ride":.045,"other":.04}
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):
                ded.append((t,g));last=t
    ded.sort();out=[];i=0
    pri={"snare":.93,"tom":.88,"crash":.85,"ride":.82,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[x for x in c if x[1] not in HANDS];h=[x for x in c if x[1] in HANDS]
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def choose_hats(song,threshold,source):
    b=rows(BASE,song)
    bh=[t for t,g in b if g=="hat"]
    p2=[t for t,g in rows(PAT2,song) if g=="hat"]
    p8=[t for t,g in rows(PAT8,song) if g=="hat"]
    # Fraction of balanced hits not supported by the precision predictor.
    unsupported=sum(not near(p2,t) for t in bh)
    disagreement=unsupported/max(1,len(bh))
    flagged=disagreement>=threshold
    if not flagged:
        chosen=bh;mode="balanced"
    elif source=="pat2":
        chosen=p2;mode="pat2"
    elif source=="pat8":
        chosen=p8;mode="pat8"
    else:
        chosen=[t for t in p2 if near(p8,t)];mode="intersection"
    out=[e for e in b if e[1]!="hat"]+[(t,"hat") for t in chosen]
    return enforce(out),{"balanced":len(bh),"pat2":len(p2),"pat8":len(p8),"unsupported_ratio":disagreement,"flagged":flagged,"mode":mode,"chosen":len(chosen)}

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,threshold,source,outdir):
    result={"disagreement_threshold":threshold,"flagged_source":source,"song_decisions":{},"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr,d=choose_hats(song,threshold,source);result["song_decisions"][song]=d
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,"precision":tp/n if n else 0,"recall":tp/mr if mr else 0,"f1":2*tp/(n+mr) if n+mr else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];gf=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":gf,
          "false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(res):
    # Explicitly optimize all-part F1 plus hat quality and worst-song hat.
    def score(v):
        h=v["summary"]["by_group"]["hat"]
        return v["summary"]["f1"]+.12*h["f1"]+.08*(h["worst_song_f1"] or 0)-.05*h["false_discovery_rate"]
    return sorted(res.items(),key=lambda kv:(score(kv[1]),kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-hat-adaptive";report={"schema":1,"cycles":[]}
    res={}
    for name,t in [("c124_t12",.12),("c124_t17",.17),("c124_t20",.20)]:
        res[name]=evaluate(name,t,"pat2",root/"cycle124");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":124,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[]})

    res={}
    for name,src in [("c125_pat2","pat2"),("c125_pat8","pat8"),("c125_intersection","intersection")]:
        res[name]=evaluate(name,best["disagreement_threshold"],src,root/"cycle125");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":125,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[]})

    res={}
    for name,t in [("c126_t18",.18),("c126_t20",.20),("c126_t22",.22)]:
        res[name]=evaluate(name,t,best["flagged_source"],root/"cycle126");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":126,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"disagreement_threshold":res[win]["disagreement_threshold"],"flagged_source":res[win]["flagged_source"],"song_decisions":res[win]["song_decisions"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-hat-adaptive.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
