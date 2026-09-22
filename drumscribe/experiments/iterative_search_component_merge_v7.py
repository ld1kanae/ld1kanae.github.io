"""Cycles 193-194: merge independently improved ride and pedal components.

Base: c183_g330.
Pedal component: pedal-refine-v3 c192_w055.
Ride component: ride-section-v2 c189_b8r3 (hat+ride pair, because that search
may reclassify a tiny number of hats into ride).

Cycle 193 compares base / pedal-only / ride-only / both.
Cycle 194 checks whether the retained crash component can be swapped without
regressing the new combined base.

chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
repair=loadmod("repair",EXP/"iterative_search_overtrigger_repair.py")
ev=repair.ev;sel=repair.sel;detail=repair.detail;base=repair.base
SONGS=repair.SONGS;GROUPS=repair.GROUPS

BASE=EXP/"generated-search-hat-gate-refine/cycle183/c183_g330"
PEDAL=EXP/"generated-search-pedal-refine-v3/cycle192/c192_w055"
RIDE=EXP/"generated-search-ride-section-v2/cycle189/c189_b8r3"
CRASH_A=EXP/"generated-search-crash-context/cycle139/c139_kick"
CRASH_B=EXP/"generated-search-crash-context/cycle141/c141_support_only"

def rows(path,song):return repair.rows(path,song)
def meta(song):return repair.meta(song)

def replace_group(events,g,path,song):
    return [e for e in events if e[1]!=g]+[e for e in rows(path,song) if e[1]==g]

def build(song,use_pedal,use_ride,crash_src="base"):
    e=rows(BASE,song)
    if use_ride:
        # Carry both groups from the ride component because it contains a small
        # number of deliberate hat->ride reclassifications.
        e=[x for x in e if x[1] not in ("hat","ride")]
        e+=[x for x in rows(RIDE,song) if x[1] in ("hat","ride")]
    if use_pedal:
        e=replace_group(e,"pedal_hat",PEDAL,song)
    if crash_src=="a":
        e=replace_group(e,"crash",CRASH_A,song)
    elif crash_src=="b":
        e=replace_group(e,"crash",CRASH_B,song)
    return repair.enforce(e)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,use_pedal,use_ride,crash_src,outdir):
    result={"use_pedal":use_pedal,"use_ride":use_ride,"crash_src":crash_src,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);events=build(song,use_pedal,use_ride,crash_src)
        p=outdir/name/f"{song}.mid";write(p,events,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,ref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":ref,"precision":tp/n if n else 0,"recall":tp/ref if ref else 0,
       "f1":2*tp/(n+ref) if n+ref else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,
          "false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,
          "worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s);return result

def choose(res,baseline,targets):
    d=sel.select(res,baseline["summary"],target_parts=targets,max_part_drop=.025,target_tolerance=.012)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-component-merge-v7";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline",False,False,"base",root/"baseline")
    res={}
    for name,p,r in [("c193_base",False,False),("c193_pedal",True,False),
                     ("c193_ride",False,True),("c193_both",True,True)]:
        res[name]=evaluate(name,p,r,"base",root/"cycle193")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],
          "pedal":res[name]["summary"]["by_group"]["pedal_hat"],
          "ride":res[name]["summary"]["by_group"]["ride"],
          "hat":res[name]["summary"]["by_group"]["hat"],
          "score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline,("pedal_hat","ride","hat"));win=d["winner"] or "c193_base";best=res[win]
    report["cycles"].append({"cycle":193,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,cs in [("c194_basecrash","base"),("c194_crashA","a"),("c194_crashB","b")]:
        res[name]=evaluate(name,best["use_pedal"],best["use_ride"],cs,root/"cycle194")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],
          "crash":res[name]["summary"]["by_group"]["crash"],
          "score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best,("crash",));win=d["winner"] or "c194_basecrash";best=res[win]
    report["cycles"].append({"cycle":194,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "use_pedal":best["use_pedal"],"use_ride":best["use_ride"],"crash_src":best["crash_src"],
      "detailed":detail.compare_dir(root/"cycle194"/win,win)["aggregate"]}
    (EXP/"results-iterative-component-merge-v7.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
