"""Cycles 207-209: adaptive activation of the c200 LOSO hat filter.

c200 lowers hat false positives on dense-hat songs, but hurts low-density songs.
This search chooses BASE (c197_merge) versus FILTER (c200_repeat) using only
prediction density, never chart data.

Cycle 207: whole-song hat/kick ratio threshold 1.2 / 1.5 / 1.8.
Cycle 208: local 8-bar hat/kick ratio threshold 1.4 / 1.8 / 2.2.
Cycle 209: local block size 4 / 8 / 16 bars at the winning threshold.

Every candidate is written to MIDI, re-read, then scored against chart.mid.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
BASE=EXP/"generated-search-browser-component-fusion/cycle197/c197_merge"
FILTER=EXP/"generated-search-hat-meta-loo/cycle200/c200_repeat"
BROWSER=EXP/"generated-v2-browser"

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py");base=loadmod("base",EXP/"iterative_search.py")
detail=loadmod("detail",EXP/"detailed_metrics.py");sel=loadmod("sel",EXP/"selection_policy.py")

def rows(path,s):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{s}.mid")]
def side(s):return json.loads((BROWSER/f"{s}.json").read_text())
def meta(s):return json.loads((ROOT/"DruMaster/songs"/s/"song.json").read_text())

def whole(song,thr):
    b=rows(BASE,song);f=rows(FILTER,song)
    h=sum(g=="hat" for _,g in b);k=sum(g=="kick" for _,g in b);ratio=h/max(1,k)
    return (f if ratio>=thr else b),{"ratio":ratio,"filtered":ratio>=thr}

def local(song,thr,bars_per):
    b=rows(BASE,song);f=rows(FILTER,song);sd=side(song)
    bpm=float(sd["bpm"]);phase=float(sd["barPhaseSec"]);bar=4*60/bpm
    bh=[t for t,g in b if g=="hat"];bk=[t for t,g in b if g=="kick"];fh=[t for t,g in f if g=="hat"]
    blocks=defaultdict(lambda:{"h":[],"k":[]})
    for t in bh:blocks[math.floor(((t-phase)/bar)/bars_per)]["h"].append(t)
    for t in bk:blocks[math.floor(((t-phase)/bar)/bars_per)]["k"].append(t)
    active={q:len(z["h"])/max(1,len(z["k"]))>=thr for q,z in blocks.items()}
    keep=[]
    for t in bh:
        q=math.floor(((t-phase)/bar)/bars_per)
        if not active.get(q,False) or any(abs(t-x)<=.025 for x in fh):keep.append(t)
    out=[x for x in b if x[1]!="hat"]+[(t,"hat") for t in keep]
    diag={str(q):{"ratio":len(z["h"])/max(1,len(z["k"])),"filtered":active[q]} for q,z in blocks.items()}
    return sorted(out),{"barsPer":bars_per,"blocks":diag}

def write(path,rr,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in rr],bpm)

def evaluate(name,mode,thr,bars_per,outdir):
    result={"mode":mode,"threshold":thr,"bars_per":bars_per,"songs":{},"diagnostic":{}};tot=Counter()
    for s in SONGS:
        rr,d=(whole(s,thr) if mode=="whole" else local(s,thr,bars_per))
        result["diagnostic"][s]=d;p=outdir/name/f"{s}.mid";write(p,rr,float(side(s)["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/s/"chart.mid")
        mt=meta(s);sh=float(mt["playback"]["stemOffsetSec"])+float(mt["playback"].get("midiOffsetSec",0))
        sc=ev.score(pred,truth,sh);cf=ev.confusion(pred,truth,sh);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][s]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,z in sc["by_group"].items():tot[f"{g}_tp"]+=z["tp"];tot[f"{g}_pred"]+=z["predicted"];tot[f"{g}_ref"]+=z["reference"]
    tp,n,r=tot["tp"],tot["predicted"],tot["reference"]
    sm={"tp":tp,"predicted":n,"reference":r,"precision":tp/n if n else 0,"recall":tp/r if r else 0,"f1":2*tp/(n+r) if n+r else 0,
        "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for s in SONGS:
            z=result["songs"][s]["by_group"].get(g,{});rr=z.get("reference",0)
            if rr:sf.append(2*z.get("tp",0)/(z.get("predicted",0)+rr) if z.get("predicted",0)+rr else 0)
        sm["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,
            "f1":2*a/(b+c) if b+c else 0,"false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
            "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=sm;result["canonical_score"]=sel.score(sm);result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def choose(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("hat",),max_part_drop=.010,target_tolerance=.006)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-hat-adaptive-v2";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","whole",99,8,root/"baseline")

    res={}
    for name,t in [("c207_r12",1.2),("c207_r15",1.5),("c207_r18",1.8)]:
        res[name]=evaluate(name,"whole",t,8,root/"cycle207")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],"diag":res[name]["diagnostic"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline);w=d["winner"] or "c207_r15";b1=res[w]
    report["cycles"].append({"cycle":207,"candidates":res,"winner":w,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,t in [("c208_l14",1.4),("c208_l18",1.8),("c208_l22",2.2)]:
        res[name]=evaluate(name,"local",t,8,root/"cycle208")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,b1);w=d["winner"] or "c208_l18";b2=res[w]
    report["cycles"].append({"cycle":208,"candidates":res,"winner":w,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    thr=b2["threshold"]
    for name,bp in [("c209_b4",4),("c209_b8",8),("c209_b16",16)]:
        res[name]=evaluate(name,"local",thr,bp,root/"cycle209")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,b2);w=d["winner"] or "c209_b8";b3=res[w]
    report["cycles"].append({"cycle":209,"candidates":res,"winner":w,"ranking":d["ranking"],"guards":d["guards"]})
    best=max([baseline,b1,b2,b3],key=lambda z:z["canonical_score"]["score"])
    report["baseline"]=baseline;report["final"]={"winner":"cross-cycle-best","summary":best["summary"],"canonical_score":best["canonical_score"],
       "mode":best["mode"],"threshold":best["threshold"],"bars_per":best["bars_per"],"diagnostic":best["diagnostic"],"detailed":best["detailed"]}
    (EXP/"results-iterative-hat-adaptive-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
