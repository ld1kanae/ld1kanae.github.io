"""Cycles 190-192: pedal rescue cleanup and pedal->hat correction.

Base: current integrated best c183_g330.

Cycle 190:
- rescue only detector-sparse songs that already contain at least one current
  pedal event; this avoids adding unsupported pedal hits to a completely silent
  pedal stream.

Cycle 191:
- reclassify current pedal hits back to hand-hat when ADTOF hand-hat support is
  present but independent pedal detector support is weak.

Cycle 192:
- tune the reclassification time window on the best combined policy.

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
RAW=EXP/"generated-search-fusion-v5/cycle129/c129_balanced"
STRICT=EXP/"generated-search-best-fusion/cycle81/c81_pedal_strict"
BAL=EXP/"generated-search-best-fusion/cycle81/c81_pedal_balanced"
RECALL=EXP/"generated-search-pedal-component/cycle64/c64_recall"
ADHAT=EXP/"generated-search-adtof/cycle163/c163_precision"

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

def pedal_votes(song,t,w=.035):
    streams=[]
    for p in (RAW,STRICT,BAL,RECALL):
        streams.append([x for x,g in rows(p,song) if g=="pedal_hat"])
    return sum(near(xs,t,w) for xs in streams)

def rescue_nonempty(song,events,rep_thr=3,per_thr=.50,sparse_thr=.18):
    cur=[t for t,g in events if g=="pedal_hat"]
    hats=[t for t,g in events if g=="hat"]
    raw=[t for t,g in rows(RAW,song) if g=="pedal_hat"]
    rec=[t for t,g in rows(RECALL,song) if g=="pedal_hat"]
    ratio=len(raw)/max(1,len(rec))
    eligible=bool(cur) and ratio<sparse_thr
    if not eligible:return events,{"ratio":ratio,"eligible":False,"added":0,"current":len(cur)}
    m=meta(song);bpm=float(m["bpm"]);_,ph,_,bar=repair.timing(song,events)
    chosen=list(cur);added=0
    for t in rec:
        if near(cur,t,.040) or near(hats,t,.035):continue
        per=periodic(rec,t,bpm);rep=repair.rep_support(rec,t,ph,bar)
        if per>=per_thr and rep>=rep_thr:
            chosen.append(t);added+=1
    chosen=sorted(chosen);ded=[];last=-999.
    for t in chosen:
        if t-last>=.045:ded.append(t);last=t
    out=[e for e in events if e[1]!="pedal_hat"]+[(t,"pedal_hat") for t in ded]
    return repair.enforce(out),{"ratio":ratio,"eligible":True,"added":added,"current":len(cur),"chosen":len(ded)}

def pedal_to_hat(song,events,mode,window):
    if mode=="base":return events,{"reclassed":0}
    adh=[t for t,g in rows(ADHAT,song) if g=="hat"]
    existing_hat=[t for t,g in events if g=="hat"]
    out=[];reclassed=0
    for t,g in events:
        if g!="pedal_hat":
            out.append((t,g));continue
        hv=near(adh,t,window)
        pv=pedal_votes(song,t,window)
        if mode=="weak1":switch=hv and pv<=1
        elif mode=="weak2":switch=hv and pv<=2
        elif mode=="not_strict":
            strict=[x for x,gg in rows(STRICT,song) if gg=="pedal_hat"]
            switch=hv and not near(strict,t,window)
        else: # consensus
            switch=hv and pv<=2 and not near(existing_hat,t,.025)
        if switch:
            out.append((t,"hat"));reclassed+=1
        else:
            out.append((t,g))
    return repair.enforce(out),{"reclassed":reclassed}

def build(song,rescue_rep,rescue_per,rescue_sparse,reclass_mode,window):
    e=rows(BASE,song)
    e,rdiag=rescue_nonempty(song,e,rescue_rep,rescue_per,rescue_sparse)
    e,hdiag=pedal_to_hat(song,e,reclass_mode,window)
    return repair.enforce(e),{"rescue":rdiag,"reclass":hdiag}

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,rescue_rep,rescue_per,rescue_sparse,reclass_mode,window,outdir):
    result={"rescue_rep":rescue_rep,"rescue_per":rescue_per,"rescue_sparse":rescue_sparse,
            "reclass_mode":reclass_mode,"window":window,"diag":{},"songs":{}}
    tot=Counter()
    for song in SONGS:
        m=meta(song);events,diag=build(song,rescue_rep,rescue_per,rescue_sparse,reclass_mode,window);result["diag"][song]=diag
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

def choose(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("pedal_hat","hat"),max_part_drop=.025,target_tolerance=.012)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-pedal-refine-v3";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline",99,1.1,0,"base",.035,root/"baseline")

    res={}
    for name,rep,per in [("c190_base",99,1.1),("c190_r3",3,.50),("c190_r4",4,.50),("c190_loose",2,.25)]:
        res[name]=evaluate(name,rep,per,.18,"base",.035,root/"cycle190")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],
          "pedal":res[name]["summary"]["by_group"]["pedal_hat"],"hat":res[name]["summary"]["by_group"]["hat"],
          "diag":res[name]["diag"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline);win=d["winner"] or "c190_base";best=res[win]
    report["cycles"].append({"cycle":190,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,mode in [("c191_base","base"),("c191_weak1","weak1"),("c191_weak2","weak2"),
                      ("c191_not_strict","not_strict"),("c191_consensus","consensus")]:
        res[name]=evaluate(name,best["rescue_rep"],best["rescue_per"],best["rescue_sparse"],mode,.035,root/"cycle191")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],
          "pedal":res[name]["summary"]["by_group"]["pedal_hat"],"hat":res[name]["summary"]["by_group"]["hat"],
          "diag":res[name]["diag"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or "c191_base";best=res[win]
    report["cycles"].append({"cycle":191,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,w in [("c192_w020",.020),("c192_w030",.030),("c192_w040",.040),("c192_w055",.055)]:
        res[name]=evaluate(name,best["rescue_rep"],best["rescue_per"],best["rescue_sparse"],best["reclass_mode"],w,root/"cycle192")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],
          "pedal":res[name]["summary"]["by_group"]["pedal_hat"],"hat":res[name]["summary"]["by_group"]["hat"],
          "diag":res[name]["diag"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":192,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "rescue_rep":best["rescue_rep"],"rescue_per":best["rescue_per"],"rescue_sparse":best["rescue_sparse"],
      "reclass_mode":best["reclass_mode"],"window":best["window"],"diag":best["diag"],
      "detailed":detail.compare_dir(root/"cycle192"/win,win)["aggregate"]}
    (EXP/"results-iterative-pedal-refine-v3.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
