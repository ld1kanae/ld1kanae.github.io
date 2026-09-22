"""Cycles 169-171: ADTOF cymbal onset + crash/ride evidence fusion.

Base: generated-search-adtof-components/cycle168/c168_kick_tom.

ADTOF provides a strong broad cymbal onset stream but no crash/ride split.
Existing crash/ride detectors provide class evidence. This search:
  169 - adds missing ADTOF cymbal onsets, classified by multi-source votes.
  170 - reclassifies only ADTOF-supported hat events when class evidence is strong.
  171 - combines the best add/reclass policies.

chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util, json
from collections import Counter
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

repair=loadmod("repair",EXP/"iterative_search_overtrigger_repair.py")
ev=repair.ev; sel=repair.sel; detail=repair.detail; base=repair.base
SONGS=repair.SONGS; GROUPS=repair.GROUPS

BASE=EXP/"generated-search-adtof-components/cycle168/c168_kick_tom"
AD_CYM=EXP/"generated-search-adtof/cycle163/c163_precision"

CRASH_SOURCES=[
    EXP/"generated-search-crash-context/cycle139/c139_kick",
    EXP/"generated-search-crash-context/cycle141/c141_support_only",
    EXP/"generated-search-crash-consensus/cycle72/c72_head18",
    EXP/"generated-search-crash-barhead/cycle145/c145_hybrid",
]
RIDE_SOURCES=[
    EXP/"generated-search-ride-segment/cycle138/c138_seed3",
    EXP/"generated-search-ride-song-gate/cycle108/c108_per50",
    EXP/"generated-search-ride-fallback/cycle119/c119_per50",
]

def rows(path,song): return repair.rows(path,song)
def meta(song): return repair.meta(song)

def source_lists(paths,song,group):
    return [[t for t,g in rows(p,song) if g==group] for p in paths]

def features(song,events,t,ad_times):
    _,ph,beat,bar=repair.timing(song,events)
    cs=source_lists(CRASH_SOURCES,song,"crash")
    rs=source_lists(RIDE_SOURCES,song,"ride")
    current_cr=[x for x,g in events if g=="crash"]
    current_ri=[x for x,g in events if g=="ride"]
    cv=repair.source_votes(cs,t,.070)
    rv=repair.source_votes(rs,t,.070)
    ccur=repair.near(current_cr,t,.070)
    rcur=repair.near(current_ri,t,.070)
    down=repair.downbeat_strength(t,ph,beat,bar)
    # A ride stream should repeat regularly. Use the broad ADTOF cymbal stream
    # only as a periodicity clock, not as class truth.
    rep=repair.rep_support(ad_times,t,ph,bar)
    cscore=2.0*cv + (1.5 if ccur else 0.0) + 1.10*down
    rscore=2.0*rv + (1.5 if rcur else 0.0) + 0.55*min(rep,4)
    return {"cv":cv,"rv":rv,"ccur":ccur,"rcur":rcur,"down":down,"rep":rep,
            "cscore":cscore,"rscore":rscore}

def classify(f,mode):
    cs,rs=f["cscore"],f["rscore"]
    if cs>=rs:
        g="crash"; top=cs; margin=cs-rs
        votes=f["cv"]; rhythm=f["down"]
    else:
        g="ride"; top=rs; margin=rs-cs
        votes=f["rv"]; rhythm=min(1.0,f["rep"]/4.0)
    if mode=="strict":
        ok=(votes>=2 and margin>=1.0) or (top>=5.0 and margin>=1.5)
    elif mode=="balanced":
        ok=(votes>=2) or (votes>=1 and rhythm>=.65 and margin>=.4) or top>=4.5
    else:
        ok=(votes>=1) or (top>=2.2 and margin>=.2)
    return (g,ok,top,margin)

def add_cymbals(song,events,mode):
    if mode=="base": return events
    ad=sorted(t for t,g in rows(AD_CYM,song) if g=="crash")
    current=[t for t,g in events if g in ("crash","ride")]
    out=list(events)
    for t in ad:
        if repair.near(current,t,.070):
            continue
        f=features(song,events,t,ad); g,ok,_,_=classify(f,mode)
        if ok:
            out.append((t,g)); current.append(t)
    return repair.enforce(out)

def reclass_hats(song,events,mode):
    if mode=="base": return events
    ad=sorted(t for t,g in rows(AD_CYM,song) if g=="crash")
    out=[]
    for t,g in events:
        if g!="hat" or not repair.near(ad,t,.065):
            out.append((t,g)); continue
        f=features(song,events,t,ad)
        # Reclassification is more conservative than adding: require a strong
        # class margin because a legitimate hi-hat can coincide with cymbals.
        cg,ok,top,margin=classify(f,mode)
        if mode=="strict":
            change=ok and margin>=1.6 and top>=4.0
        elif mode=="balanced":
            change=ok and margin>=1.0 and top>=3.2
        else:
            change=ok and margin>=.6 and top>=2.5
        out.append((t,cg if change else "hat"))
    return repair.enforce(out)

def build(song,add_mode,reclass_mode):
    e=rows(BASE,song)
    e=add_cymbals(song,e,add_mode)
    e=reclass_hats(song,e,reclass_mode)
    return repair.enforce(e)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,add_mode,reclass_mode,outdir):
    result={"add_mode":add_mode,"reclass_mode":reclass_mode,"songs":{}}; tot=Counter()
    for song in SONGS:
        m=meta(song);events=build(song,add_mode,reclass_mode)
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
    s={"tp":tp,"predicted":n,"reference":ref,"precision":tp/n if n else 0,
       "recall":tp/ref if ref else 0,"f1":2*tp/(n+ref) if n+ref else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,
          "false_discovery_rate":(b-a)/b if b else 0,
          "miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,
          "mean_song_f1":sum(sf)/len(sf) if sf else None,
          "worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s)
    return result

def choose(res,baseline,targets,tol=.015,maxdrop=.035):
    ranking=[];guards={}
    for n,o in res.items():
        gd=sel.eligibility(o["summary"],baseline["summary"],target_parts=targets,
                           target_tolerance=tol,max_part_drop=maxdrop)
        o["guard"]=gd;guards[n]=gd
        ranking.append((gd["eligible"],o["canonical_score"]["score"],o["summary"]["f1"],n))
    ranking.sort(reverse=True)
    return {"winner":next((n for ok,_,_,n in ranking if ok),None),
            "ranking":[x[3] for x in ranking],"guards":guards}

def main():
    root=EXP/"generated-search-adtof-cymbal-class";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","base","base",root/"baseline")

    res={}
    for name,mode in [("c169_base","base"),("c169_strict","strict"),("c169_balanced","balanced"),("c169_loose","loose")]:
        res[name]=evaluate(name,mode,"base",root/"cycle169")
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],
          "crash":res[name]["summary"]["by_group"]["crash"],
          "ride":res[name]["summary"]["by_group"]["ride"],
          "score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline,("crash","ride"),.018,.04);win=d["winner"] or "c169_base";best=res[win]
    report["cycles"].append({"cycle":169,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,mode in [("c170_base","base"),("c170_strict","strict"),("c170_balanced","balanced"),("c170_loose","loose")]:
        res[name]=evaluate(name,best["add_mode"],mode,root/"cycle170")
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],
          "hat":res[name]["summary"]["by_group"]["hat"],
          "crash":res[name]["summary"]["by_group"]["crash"],
          "ride":res[name]["summary"]["by_group"]["ride"],
          "score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best,("hat","crash","ride"),.018,.04);win=d["winner"] or "c170_base";best=res[win]
    report["cycles"].append({"cycle":170,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    # Explicit combined grid, including base add/reclass options, because a
    # reclassification rule can interact with additions non-linearly.
    res={}
    cfg=[
      ("c171_base","base","base"),
      ("c171_bal_bal","balanced","balanced"),
      ("c171_bal_strict","balanced","strict"),
      ("c171_loose_strict","loose","strict"),
      ("c171_strict_bal","strict","balanced"),
    ]
    for name,a,r in cfg:
        res[name]=evaluate(name,a,r,root/"cycle171")
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],
          "hat":res[name]["summary"]["by_group"]["hat"],
          "crash":res[name]["summary"]["by_group"]["crash"],
          "ride":res[name]["summary"]["by_group"]["ride"],
          "score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best,("hat","crash","ride"),.02,.04);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":171,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],
      "guard":best["guard"],"add_mode":best["add_mode"],"reclass_mode":best["reclass_mode"],
      "detailed":detail.compare_dir(root/"cycle171"/win,win)["aggregate"]}
    (EXP/"results-iterative-adtof-cymbal-class.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
