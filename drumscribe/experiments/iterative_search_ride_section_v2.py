"""Cycles 187-189: section-gated ADTOF ride repair.

Base: current integrated best c183_g330.
Loose ADTOF cymbal classification has useful ride recall, especially in songs
with an existing ride stream, but raw use creates many hat->ride errors.

This search uses that loose ride stream only inside sections supported by the
current ride stream, and then tests:
- gap-only additions away from current hats,
- hat->ride reclassification when the ADTOF ride event is periodic,
- a guarded hybrid.

chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util,json,math
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
LOOSE=EXP/"generated-search-adtof-cymbal-class/cycle169/c169_loose"

def rows(path,song):return repair.rows(path,song)
def meta(song):return repair.meta(song)
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def periodic(times,t,bpm):
    if len(times)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.065 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def active(current,t,bpm,beats):
    w=beats*60.0/bpm
    return any(abs(x-t)<=w for x in current)

def replace_nearest_hat(events,t,w=.035):
    idx=[i for i,(x,g) in enumerate(events) if g=="hat" and abs(x-t)<=w]
    if not idx:return events,False
    i=min(idx,key=lambda i:abs(events[i][0]-t))
    out=list(events);out[i]=(out[i][0],"ride")
    return out,True

def build(song,mode,per_thr,section_beats,rep_thr):
    e=rows(BASE,song)
    cur=[t for t,g in e if g=="ride"]
    hats=[t for t,g in e if g=="hat"]
    src=[t for t,g in rows(LOOSE,song) if g=="ride"]
    m=meta(song);bpm=float(m["bpm"])
    _,ph,_,bar=repair.timing(song,e)
    out=list(e);added=0;reclassed=0
    for t in src:
        if near(cur,t,.045):continue
        if not active(cur,t,bpm,section_beats):continue
        per=periodic(src,t,bpm);rep=repair.rep_support(src,t,ph,bar)
        hnear=near(hats,t,.035)
        strong=per>=per_thr and rep>=rep_thr
        if mode=="gap":
            if (not hnear) and strong:
                out.append((t,"ride"));added+=1
        elif mode=="reclass":
            if hnear and strong:
                out,ok=replace_nearest_hat(out,t)
                if ok:reclassed+=1
        else: # hybrid
            if not strong:continue
            if hnear:
                out,ok=replace_nearest_hat(out,t)
                if ok:reclassed+=1
            else:
                out.append((t,"ride"));added+=1
    return repair.enforce(out),{"current":len(cur),"source":len(src),"added":added,"reclassed":reclassed}

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,per_thr,section_beats,rep_thr,outdir):
    result={"mode":mode,"per_thr":per_thr,"section_beats":section_beats,"rep_thr":rep_thr,"diag":{},"songs":{}}
    tot=Counter()
    for song in SONGS:
        m=meta(song);events,diag=build(song,mode,per_thr,section_beats,rep_thr);result["diag"][song]=diag
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
    d=sel.select(res,baseline["summary"],target_parts=("ride","hat"),max_part_drop=.025,target_tolerance=.012)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-ride-section-v2";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","gap",1.1,4,99,root/"baseline")

    res={}
    for name,mode in [("c187_gap","gap"),("c187_reclass","reclass"),("c187_hybrid","hybrid")]:
        res[name]=evaluate(name,mode,.75,4,3,root/"cycle187")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"ride":res[name]["summary"]["by_group"]["ride"],
          "hat":res[name]["summary"]["by_group"]["hat"],"diag":res[name]["diag"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    res["c187_base"]=baseline
    d=choose(res,baseline);win=d["winner"] or "c187_base";best=res[win]
    report["cycles"].append({"cycle":187,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,p in [("c188_p50",.50),("c188_p75",.75),("c188_p100",1.0)]:
        if best["mode"]=="gap" and win=="c187_base":
            mode="gap"
        else: mode=best["mode"]
        res[name]=evaluate(name,mode,p,best["section_beats"],best["rep_thr"],root/"cycle188")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"ride":res[name]["summary"]["by_group"]["ride"],
          "hat":res[name]["summary"]["by_group"]["hat"],"diag":res[name]["diag"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":188,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,b,rp in [("c189_b2r2",2,2),("c189_b4r2",4,2),("c189_b4r3",4,3),("c189_b8r3",8,3)]:
        res[name]=evaluate(name,best["mode"],best["per_thr"],b,rp,root/"cycle189")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"ride":res[name]["summary"]["by_group"]["ride"],
          "hat":res[name]["summary"]["by_group"]["hat"],"diag":res[name]["diag"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":189,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "mode":best["mode"],"per_thr":best["per_thr"],"section_beats":best["section_beats"],"rep_thr":best["rep_thr"],
      "diag":best["diag"],"detailed":detail.compare_dir(root/"cycle189"/win,win)["aggregate"]}
    (EXP/"results-iterative-ride-section-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
