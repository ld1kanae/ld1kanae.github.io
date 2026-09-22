"""Cycles 195-197: consensus crash supplementation.

Base: component-merge-v7 c194_basecrash.

Supplemental crash candidates must be absent from the current crash stream and
supported by BOTH:
- the retained kick/context crash component (c139_kick), and
- the loose ADTOF cymbal crash stream (c169_loose).

We then test kick/downbeat contextual gates. This is designed to increase crash
recall without paying the large false-positive cost of wholesale crash-source
replacement. chart.mid is scoring-only.
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

BASE=EXP/"generated-search-component-merge-v7/cycle194/c194_basecrash"
CTX=EXP/"generated-search-crash-context/cycle139/c139_kick"
AD=EXP/"generated-search-adtof-cymbal-class/cycle169/c169_loose"

def rows(path,song):return repair.rows(path,song)
def meta(song):return repair.meta(song)
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def build(song,mode,agree_w,down_thr):
    e=rows(BASE,song)
    cur=[t for t,g in e if g=="crash"]
    ctx=[t for t,g in rows(CTX,song) if g=="crash"]
    ad=[t for t,g in rows(AD,song) if g=="crash"]
    kicks=[t for t,g in e if g=="kick"]
    m=meta(song);_,ph,beat,bar=repair.timing(song,e)
    add=[]
    for t in ctx:
        if near(cur,t,.050):continue
        if not near(ad,t,agree_w):continue
        down=repair.downbeat_strength(t,ph,beat,bar)
        kick=near(kicks,t,.045)
        if mode=="consensus":keep=True
        elif mode=="kick":keep=kick
        elif mode=="down":keep=down>=down_thr
        else:keep=kick and down>=down_thr
        if keep:add.append(t)
    out=e+[(t,"crash") for t in add]
    return repair.enforce(out),{"current":len(cur),"ctx":len(ctx),"ad":len(ad),"added":len(add)}

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,agree_w,down_thr,outdir):
    result={"mode":mode,"agree_w":agree_w,"down_thr":down_thr,"diag":{},"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);events,diag=build(song,mode,agree_w,down_thr);result["diag"][song]=diag
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
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,"false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s);return result

def choose(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("crash",),max_part_drop=.025,target_tolerance=.012)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-crash-consensus-v2";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","both",.001,2.0,root/"baseline")
    res={"c195_base":baseline}
    for name,mode in [("c195_consensus","consensus"),("c195_kick","kick"),("c195_down","down"),("c195_both","both")]:
        res[name]=evaluate(name,mode,.055,.60,root/"cycle195")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"crash":res[name]["summary"]["by_group"]["crash"],
          "diag":res[name]["diag"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline);win=d["winner"] or "c195_base";best=res[win]
    report["cycles"].append({"cycle":195,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,w in [("c196_w030",.030),("c196_w045",.045),("c196_w060",.060),("c196_w080",.080)]:
        res[name]=evaluate(name,best["mode"],w,best["down_thr"],root/"cycle196")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"crash":res[name]["summary"]["by_group"]["crash"],
          "diag":res[name]["diag"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":196,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,dn in [("c197_d40",.40),("c197_d55",.55),("c197_d70",.70),("c197_d85",.85)]:
        res[name]=evaluate(name,best["mode"],best["agree_w"],dn,root/"cycle197")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"crash":res[name]["summary"]["by_group"]["crash"],
          "diag":res[name]["diag"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":197,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "mode":best["mode"],"agree_w":best["agree_w"],"down_thr":best["down_thr"],"diag":best["diag"],
      "detailed":detail.compare_dir(root/"cycle197"/win,win)["aggregate"]}
    (EXP/"results-iterative-crash-consensus-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
