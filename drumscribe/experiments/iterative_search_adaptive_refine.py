"""Cycles 175-177: integrate adaptive routing and repair remaining hat/pedal overprediction.

Base: generated-search-song-adaptive-v2/cycle174/c174_recall90.

175: re-apply ADTOF-supported cymbal/hat reclassification on the adaptive base.
176: conditionally suppress kick/snare-near hat events using independent hat
     votes + rhythmic repetition, with song-level conflict-fraction gating.
177: conditionally suppress pedal-hat events that collide with hand-hat when
     pedal evidence is weak.

chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util, json
from collections import Counter
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

repair=loadmod("repair",EXP/"iterative_search_overtrigger_repair.py")
metal=loadmod("metal",EXP/"iterative_search_adtof_cymbal_class.py")
ev=repair.ev;sel=repair.sel;detail=repair.detail;base=repair.base
SONGS=repair.SONGS;GROUPS=repair.GROUPS

BASE=EXP/"generated-search-song-adaptive-v2/cycle174/c174_recall90"
HAT_SOURCES=[
    EXP/"generated-search-crossstem-hat/cycle85/c85_strict",
    EXP/"generated-search-hat-precision/cycle75/c75_repeat5",
    EXP/"generated-search-pattern-consensus/cycle56/c56_window2",
]
PEDAL_SOURCES=[
    EXP/"generated-search-fusion-v5/cycle129/c129_balanced",
    EXP/"generated-search-best-fusion/cycle81/c81_pedal_strict",
    EXP/"generated-search-best-fusion/cycle81/c81_pedal_balanced",
    EXP/"generated-search-pedal-component/cycle64/c64_recall",
]

def rows(path,song):return repair.rows(path,song)
def meta(song):return repair.meta(song)

def source_lists(paths,song,g):
    return [[t for t,gg in rows(p,song) if gg==g] for p in paths]

def timing(song,e):
    return repair.timing(song,e)

def reclass_metal(song,e,mode):
    if mode=="base":return e
    return metal.reclass_hats(song,e,mode)

def hat_filter(song,e,mode,gate):
    if mode=="base":return e,{"conflict_fraction":0.0,"active":False,"removed":0}
    hats=sorted(t for t,g in e if g=="hat")
    kicks=[t for t,g in e if g=="kick"]
    snares=[t for t,g in e if g=="snare"]
    conflict=[t for t in hats if repair.near(kicks,t,.032) or repair.near(snares,t,.032)]
    frac=len(conflict)/max(1,len(hats))
    if frac<gate:
        return e,{"conflict_fraction":frac,"active":False,"removed":0}
    _,ph,_,bar=timing(song,e)
    src=source_lists(HAT_SOURCES,song,"hat")
    keep=[];removed=0
    for t in hats:
        is_conf=repair.near(kicks,t,.032) or repair.near(snares,t,.032)
        if not is_conf:
            keep.append(t);continue
        votes=repair.source_votes(src,t,.045)
        rep=repair.rep_support(hats,t,ph,bar)
        if mode=="loose":
            ok=votes>=1 or rep>=3
        elif mode=="balanced":
            ok=votes>=2 or (votes>=1 and rep>=4)
        elif mode=="strict":
            ok=votes>=2 and rep>=2
        else: # very_strict
            ok=votes>=3 or (votes>=2 and rep>=4)
        if ok:keep.append(t)
        else:removed+=1
    out=[x for x in e if x[1]!="hat"]+[(t,"hat") for t in keep]
    return repair.enforce(out),{"conflict_fraction":frac,"active":True,"removed":removed}

def pedal_filter(song,e,mode):
    if mode=="base":return e,{"removed":0}
    pedals=sorted(t for t,g in e if g=="pedal_hat")
    hats=[t for t,g in e if g=="hat"]
    if not pedals:return e,{"removed":0}
    _,ph,_,bar=timing(song,e)
    src=source_lists(PEDAL_SOURCES,song,"pedal_hat")
    keep=[];removed=0
    for t in pedals:
        overlap=repair.near(hats,t,.030)
        if not overlap:
            keep.append(t);continue
        votes=repair.source_votes(src,t,.035)
        rep=repair.rep_support(pedals,t,ph,bar)
        if mode=="vote2":
            ok=votes>=2
        elif mode=="vote3":
            ok=votes>=3
        elif mode=="vote4":
            ok=votes>=4
        elif mode=="vote3_periodic":
            ok=votes>=3 and rep>=2
        else: # strict_periodic
            ok=votes>=4 or (votes>=3 and rep>=3)
        if ok:keep.append(t)
        else:removed+=1
    out=[x for x in e if x[1]!="pedal_hat"]+[(t,"pedal_hat") for t in keep]
    return repair.enforce(out),{"removed":removed}

def build(song,metal_mode,hat_mode,hat_gate,pedal_mode):
    e=rows(BASE,song)
    e=reclass_metal(song,e,metal_mode)
    e,hdiag=hat_filter(song,e,hat_mode,hat_gate)
    e,pdiag=pedal_filter(song,e,pedal_mode)
    return repair.enforce(e),{"hat":hdiag,"pedal":pdiag}

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,metal_mode,hat_mode,hat_gate,pedal_mode,outdir):
    result={"metal_mode":metal_mode,"hat_mode":hat_mode,"hat_gate":hat_gate,"pedal_mode":pedal_mode,"diagnostics":{},"songs":{}}
    tot=Counter()
    for song in SONGS:
        m=meta(song);events,diag=build(song,metal_mode,hat_mode,hat_gate,pedal_mode);result["diagnostics"][song]=diag
        p=outdir/name/f"{song}.mid";write(p,events,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],
                   kick_to_hat=cf["class_errors"].get("kick_to_hat",0),
                   snare_to_hat=cf["class_errors"].get("snare_to_hat",0),
                   hat_to_pedal=cf["class_errors"].get("hat_to_pedal_hat",0))
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,ref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":ref,"precision":tp/n if n else 0,"recall":tp/ref if ref else 0,
       "f1":2*tp/(n+ref) if n+ref else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "kick_to_hat":tot["kick_to_hat"],"snare_to_hat":tot["snare_to_hat"],"hat_to_pedal_hat":tot["hat_to_pedal"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,"false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    can=sel.score(s)
    href=max(1,s["by_group"]["hat"]["reference"]);pref=max(1,s["by_group"]["pedal_hat"]["reference"])
    direct=(s["kick_to_hat"]+s["snare_to_hat"])/href + .5*s["hat_to_pedal_hat"]/pref
    result["summary"]=s;result["canonical_score"]=can;result["selection_score"]=round(can["score"]-.025*direct,6)
    return result

def choose(res,baseline,targets,maxdrop=.03,tol=.012):
    ranking=[];guards={}
    for n,o in res.items():
        gd=sel.eligibility(o["summary"],baseline["summary"],target_parts=targets,max_part_drop=maxdrop,target_tolerance=tol)
        o["guard"]=gd;guards[n]=gd
        ranking.append((gd["eligible"],o["selection_score"],o["summary"]["f1"],n))
    ranking.sort(reverse=True)
    return {"winner":next((n for ok,_,_,n in ranking if ok),None),"ranking":[x[3] for x in ranking],"guards":guards}

def main():
    root=EXP/"generated-search-adaptive-refine";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","base","base",0.0,"base",root/"baseline")

    res={}
    for name,mode in [("c175_base","base"),("c175_strict","strict"),("c175_balanced","balanced"),("c175_loose","loose")]:
        res[name]=evaluate(name,mode,"base",0.0,"base",root/"cycle175")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],
          "crash":res[name]["summary"]["by_group"]["crash"],"ride":res[name]["summary"]["by_group"]["ride"],
          "score":res[name]["selection_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline,("hat","crash","ride"),.03,.015);win=d["winner"] or "c175_base";best=res[win]
    report["cycles"].append({"cycle":175,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    cfg=[
      ("c176_base","base",0.0),
      ("c176_bal20","balanced",.20),
      ("c176_bal30","balanced",.30),
      ("c176_strict20","strict",.20),
      ("c176_vstrict20","very_strict",.20),
    ]
    for name,mode,gate in cfg:
        res[name]=evaluate(name,best["metal_mode"],mode,gate,"base",root/"cycle176")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],
          "k2h":res[name]["summary"]["kick_to_hat"],"s2h":res[name]["summary"]["snare_to_hat"],
          "diag":res[name]["diagnostics"],"score":res[name]["selection_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best,("hat",),.025,.015);win=d["winner"] or "c176_base";best=res[win]
    report["cycles"].append({"cycle":176,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,mode in [
      ("c177_base","base"),("c177_vote2","vote2"),("c177_vote3","vote3"),
      ("c177_vote4","vote4"),("c177_periodic","vote3_periodic"),("c177_strict","strict_periodic")
    ]:
        res[name]=evaluate(name,best["metal_mode"],best["hat_mode"],best["hat_gate"],mode,root/"cycle177")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"pedal":res[name]["summary"]["by_group"]["pedal_hat"],
          "h2p":res[name]["summary"]["hat_to_pedal_hat"],"diag":res[name]["diagnostics"],"score":res[name]["selection_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best,("pedal_hat",),.03,.015);win=d["winner"] or "c177_base";best=res[win]
    report["cycles"].append({"cycle":177,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"selection_score":best["selection_score"],
      "guard":best["guard"],"metal_mode":best["metal_mode"],"hat_mode":best["hat_mode"],"hat_gate":best["hat_gate"],"pedal_mode":best["pedal_mode"],
      "diagnostics":best["diagnostics"],"detailed":detail.compare_dir(root/"cycle177"/win,win)["aggregate"]}
    (EXP/"results-iterative-adaptive-refine.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
