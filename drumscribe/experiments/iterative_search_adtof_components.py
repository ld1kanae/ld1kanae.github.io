"""Cycles 166-168: integrate strong ADTOF kick/snare/tom components.

Base: ADTOF fusion c165_loose.
Cycle 166: replace snare with ADTOF recall/default/precision components.
Cycle 167: apply dynamic short-gap collapse to the selected ADTOF snare,
           preserving the user-requested anti-retrigger behavior.
Cycle 168: test ADTOF kick, tom, and kick+tom replacement on the winning snare.

All candidates are materialized as MIDI, re-read, and scored. chart.mid is
scoring-only.
"""
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

repair=loadmod("repair",EXP/"iterative_search_overtrigger_repair.py")
ev=repair.ev; sel=repair.sel; detail=repair.detail; base=repair.base

SONGS=repair.SONGS; GROUPS=repair.GROUPS
BASE=EXP/"generated-search-adtof/cycle165/c165_loose"
ADTOF={
 "recall":EXP/"generated-search-adtof/cycle163/c163_recall",
 "default":EXP/"generated-search-adtof/cycle163/c163_default",
 "precision":EXP/"generated-search-adtof/cycle163/c163_precision",
}

def rows(path,song):return repair.rows(path,song)
def meta(song):return repair.meta(song)

def replace(events,group,path,song):
    return [e for e in events if e[1]!=group]+[e for e in rows(path,song) if e[1]==group]

def collapse_snare(song,events,mode):
    if mode=="none":return repair.enforce(events)
    _,ph,beat,bar=repair.timing(song,events)
    arr=sorted(t for t,g in events if g=="snare")
    if mode=="gap12":gap=repair.clamp(.12*beat,.040,.080)
    elif mode=="gap16":gap=repair.clamp(.16*beat,.050,.100)
    else:gap=repair.clamp(.20*beat,.055,.120)
    src=[ [t for t,g in rows(ADTOF[k],song) if g=="snare"] for k in ("recall","default","precision") ]
    clusters=[];cur=[]
    for t in arr:
        if not cur or t-cur[-1]<=gap:cur.append(t)
        else:clusters.append(cur);cur=[t]
    if cur:clusters.append(cur)
    keep=[]
    for c in clusters:
        if len(c)==1:keep.extend(c);continue
        scored=[]
        for t in c:
            votes=repair.source_votes(src,t,.035)
            rep=repair.rep_support(arr,t,ph,bar)
            scored.append((2*votes+.25*min(rep,4),-t,t))
        keep.append(max(scored)[-1])
    return repair.enforce([e for e in events if e[1]!="snare"]+[(t,"snare") for t in keep])

def build(song,snare_src,snare_collapse,kick_adtof,tom_adtof):
    e=rows(BASE,song)
    if snare_src!="base":e=replace(e,"snare",ADTOF[snare_src],song)
    e=collapse_snare(song,e,snare_collapse)
    if kick_adtof:e=replace(e,"kick",ADTOF["precision"],song)
    if tom_adtof:e=replace(e,"tom",ADTOF["precision"],song)
    return repair.enforce(e)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,snare_src,snare_collapse,kick_adtof,tom_adtof,outdir):
    result={"snare_src":snare_src,"snare_collapse":snare_collapse,"kick_adtof":kick_adtof,"tom_adtof":tom_adtof,"songs":{}}
    tot=Counter()
    for song in SONGS:
        m=meta(song);events=build(song,snare_src,snare_collapse,kick_adtof,tom_adtof)
        p=outdir/name/f"{song}.mid";write(p,events,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc)
        _,_,beat,_=repair.timing(song,events)
        sr=repair.retrigger_stat(pred,truth,shift,"snare",repair.clamp(.12*beat,.040,.080))
        sc["snare_retrigger"]=sr;result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],
                   snare_pairs=sr["pairs"],snare_retrigger_fp=sr["unsupported"])
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
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,"false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    s["retrigger"]={"snare_short_gap_pairs":tot["snare_pairs"],"snare_retrigger_fp":tot["snare_retrigger_fp"],
                    "snare_retrigger_fp_rate":tot["snare_retrigger_fp"]/max(1,s["by_group"]["snare"]["predicted"])}
    result["summary"]=s;result["canonical_score"]=sel.score(s)
    result["selection_score"]=round(result["canonical_score"]["score"]-.10*s["retrigger"]["snare_retrigger_fp_rate"],6)
    return result

def choose(res,baseline,targets,max_drop=.035,tol=.012):
    ranking=[];guards={}
    for n,o in res.items():
        guard=sel.eligibility(o["summary"],baseline["summary"],target_parts=targets,max_part_drop=max_drop,target_tolerance=tol)
        o["guard"]=guard;guards[n]=guard
        ranking.append((guard["eligible"],o["selection_score"],o["summary"]["f1"],n))
    ranking.sort(reverse=True)
    winner=next((n for ok,_,_,n in ranking if ok),None)
    return {"winner":winner,"ranking":[x[3] for x in ranking],"guards":guards}

def main():
    root=EXP/"generated-search-adtof-components";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","base","none",False,False,root/"baseline")

    res={}
    for name,src in [("c166_base","base"),("c166_recall","recall"),("c166_default","default"),("c166_precision","precision")]:
        res[name]=evaluate(name,src,"none",False,False,root/"cycle166")
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],"snare":res[name]["summary"]["by_group"]["snare"],
          "retrigger":res[name]["summary"]["retrigger"],"score":res[name]["selection_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline,("snare",),.03,.012);win=d["winner"] or "c166_base";best=res[win]
    report["cycles"].append({"cycle":166,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,mode in [("c167_none","none"),("c167_gap12","gap12"),("c167_gap16","gap16"),("c167_gap20","gap20")]:
        res[name]=evaluate(name,best["snare_src"],mode,False,False,root/"cycle167")
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],"snare":res[name]["summary"]["by_group"]["snare"],
          "retrigger":res[name]["summary"]["retrigger"],"score":res[name]["selection_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best,("snare",),.025,.012);win=d["winner"] or "c167_none";best=res[win]
    report["cycles"].append({"cycle":167,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    cfg=[("c168_base",False,False),("c168_kick",True,False),("c168_tom",False,True),("c168_kick_tom",True,True)]
    for name,k,t in cfg:
        res[name]=evaluate(name,best["snare_src"],best["snare_collapse"],k,t,root/"cycle168")
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],"kick":res[name]["summary"]["by_group"]["kick"],
          "tom":res[name]["summary"]["by_group"]["tom"],"snare":res[name]["summary"]["by_group"]["snare"],
          "score":res[name]["selection_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best,("kick","tom"),.03,.012);win=d["winner"] or "c168_base";best=res[win]
    report["cycles"].append({"cycle":168,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"selection_score":best["selection_score"],
      "guard":best["guard"],"snare_src":best["snare_src"],"snare_collapse":best["snare_collapse"],"kick_adtof":best["kick_adtof"],"tom_adtof":best["tom_adtof"],
      "detailed":detail.compare_dir(root/"cycle168"/win,win)["aggregate"]}
    (EXP/"results-iterative-adtof-components.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
