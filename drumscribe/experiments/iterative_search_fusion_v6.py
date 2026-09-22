"""Cycles 142-144: sixth-generation all-part fusion.

Base: fusion-v5 c129_balanced.
New retained components:
- pedal adaptive: c135_sparse060
- ride segment: c138_seed3
- crash context: c141_support_only

Cycle 142: progressively combine the three improved weak-part components.
Cycle 143: balanced / safe / high-recall snare on the integrated winner.
Cycle 144: current adaptive / cross-stem precision / pattern-consensus hi-hat.

Every candidate is written as real MIDI, re-read, then scored against chart.mid.
Prediction uses only previously generated audio-derived MIDI.
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
sel=loadmod("sel",EXP/"selection_policy.py")

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

BASE=EXP/"generated-search-fusion-v5/cycle129/c129_balanced"
PEDAL=EXP/"generated-search-pedal-adaptive/cycle135/c135_sparse060"
RIDE=EXP/"generated-search-ride-segment/cycle138/c138_seed3"
CRASH=EXP/"generated-search-crash-context/cycle141/c141_support_only"
SNARE={
 "balanced":BASE,
 "safe":EXP/"generated-search-snare-safe-fusion/cycle113/c113_k65",
 "highrecall":EXP/"generated-search-best-fusion/cycle80/c80_snare_pattern",
}
HAT={
 "adaptive":BASE,
 "crossstem":EXP/"generated-search-crossstem-hat/cycle85/c85_strict",
 "pattern":EXP/"generated-search-pattern-consensus/cycle56/c56_window2",
}

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def replace(events,g,path,song):
    return [e for e in events if e[1]!=g]+[e for e in rows(path,song) if e[1]==g]

def enforce(events):
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.045,"tom":.050,"crash":.090,"ride":.045,"other":.040}
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):ded.append((t,g));last=t
    ded.sort();out=[];i=0;pri={"snare":.93,"tom":.88,"crash":.86,"ride":.84,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j]
        ex=[e for e in c if e[1] not in HANDS]
        h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def fuse(song,use_pedal,use_crash,use_ride,snare_src="balanced",hat_src="adaptive"):
    e=rows(BASE,song)
    if use_pedal:e=replace(e,"pedal_hat",PEDAL,song)
    if use_crash:e=replace(e,"crash",CRASH,song)
    if snare_src!="balanced":e=replace(e,"snare",SNARE[snare_src],song)

    # Hat source is replaced before ride, then ride removes only its local
    # synchronous hand-hat candidates.
    if hat_src!="adaptive":e=replace(e,"hat",HAT[hat_src],song)

    if use_ride:
        e=[x for x in e if x[1]!="ride"]
        rides=[x for x in rows(RIDE,song) if x[1]=="ride"]
        rt=[t for t,_ in rides]
        e=[x for x in e if not(x[1]=="hat" and any(abs(x[0]-t)<=.030 for t in rt))]
        e+=rides
    return enforce(e)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,use_pedal,use_crash,use_ride,snare_src,hat_src,outdir):
    result={"use_pedal":use_pedal,"use_crash":use_crash,"use_ride":use_ride,"snare_src":snare_src,"hat_src":hat_src,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=fuse(song,use_pedal,use_crash,use_ride,snare_src,hat_src)
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,"precision":tp/n if n else 0,"recall":tp/mr if mr else 0,
       "f1":2*tp/(n+mr) if n+mr else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];gf=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":gf,
          "false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s);result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def decide(res,baseline,targets,max_drop=.035):
    d=sel.select(res,baseline["summary"],target_parts=targets,max_part_drop=max_drop,target_tolerance=.012)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-fusion-v6";report={"schema":1,"selection_policy":"canonical score + all-part non-regression","cycles":[]}
    baseline=evaluate("baseline",False,False,False,"balanced","adaptive",root/"baseline")

    # 142: integrate retained weak-part improvements. Keep a baseline candidate
    # in the set so an apparent improvement cannot be forced.
    res={}
    cfg=[
      ("c142_base",False,False,False),
      ("c142_pedal_crash",True,True,False),
      ("c142_pedal_ride",True,False,True),
      ("c142_all_three",True,True,True),
    ]
    for name,p,c,r in cfg:
        res[name]=evaluate(name,p,c,r,"balanced","adaptive",root/"cycle142")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=decide(res,baseline,("pedal_hat","crash","ride"),.04)
    win=d["winner"] or "c142_base";best=res[win]
    report["cycles"].append({"cycle":142,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    print("DECISION142",json.dumps(d,ensure_ascii=False),flush=True)

    # 143: snare variants on integrated winner.
    res={}
    for name,sn in [("c143_balanced","balanced"),("c143_safe","safe"),("c143_highrecall","highrecall")]:
        res[name]=evaluate(name,best["use_pedal"],best["use_crash"],best["use_ride"],sn,best["hat_src"],root/"cycle143")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=decide(res,best,("snare",),.035)
    win=d["winner"] or "c143_balanced";best=res[win]
    report["cycles"].append({"cycle":143,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    print("DECISION143",json.dumps(d,ensure_ascii=False),flush=True)

    # 144: three hat components. Ride replacement is re-applied after hat
    # replacement so hand-hat/ride conflicts remain physically plausible.
    res={}
    for name,h in [("c144_adaptive","adaptive"),("c144_crossstem","crossstem"),("c144_pattern","pattern")]:
        res[name]=evaluate(name,best["use_pedal"],best["use_crash"],best["use_ride"],best["snare_src"],h,root/"cycle144")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=decide(res,best,("hat",),.035)
    win=d["winner"] or "c144_adaptive";best=res[win]
    report["cycles"].append({"cycle":144,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    print("DECISION144",json.dumps(d,ensure_ascii=False),flush=True)

    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "use_pedal":best["use_pedal"],"use_crash":best["use_crash"],"use_ride":best["use_ride"],
      "snare_src":best["snare_src"],"hat_src":best["hat_src"],"detailed":best["detailed"]}
    (EXP/"results-iterative-fusion-v6.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
