"""Cycles 184-186: sparse-regime pedal-hi-hat rescue on the current best base.

Base: generated-search-hat-gate-refine/cycle183/c183_g330.

The predictor never uses chart.mid. A song is eligible for rescue only when
the raw/recall pedal detector ratio is sparse; this is the same prediction-time
signal previously used to distinguish detector regimes. Missing pedal notes are
then proposed from the high-recall pedal stream and filtered by:
- no current hand-hat at the onset,
- periodic support,
- repeated bar-slot support,
- optional simultaneous kick/snare/tom/crash support.

This specifically tests whether arcaround/nanairo-like detector-sparse songs
can gain pedal recall without reintroducing the large false-positive streams
seen in diamondvirgin/kaiju/ray.
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
RAW=EXP/"generated-search-fusion-v5/cycle129/c129_balanced"
RECALL=EXP/"generated-search-pedal-component/cycle64/c64_recall"

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

def rescue(song,mode,sparse_thr,per_thr,rep_thr):
    e=rows(BASE,song)
    cur=[t for t,g in e if g=="pedal_hat"]
    hats=[t for t,g in e if g=="hat"]
    accents=[t for t,g in e if g in ("kick","snare","tom","crash","ride")]
    raw=[t for t,g in rows(RAW,song) if g=="pedal_hat"]
    rec=[t for t,g in rows(RECALL,song) if g=="pedal_hat"]
    ratio=len(raw)/max(1,len(rec))
    m=meta(song);bpm=float(m["bpm"])
    _,ph,_,bar=repair.timing(song,e)
    eligible=ratio<sparse_thr

    chosen=list(cur)
    added=[]
    if eligible and mode!="base":
        for t in rec:
            if near(cur,t,.040) or near(hats,t,.035):
                continue
            per=periodic(rec,t,bpm)
            rep=repair.rep_support(rec,t,ph,bar)
            accent=near(accents,t,.040)
            if mode=="periodic":
                keep=per>=per_thr and rep>=rep_thr
            elif mode=="accent":
                keep=accent and per>=max(.25,per_thr-.25) and rep>=max(2,rep_thr-1)
            elif mode=="gap_repeat":
                keep=per>=per_thr and (rep>=rep_thr or accent)
            else: # hybrid
                keep=(per>=per_thr and rep>=rep_thr) or (accent and per>=max(.25,per_thr-.25) and rep>=max(2,rep_thr-1))
            if keep:
                chosen.append(t);added.append(t)

    chosen=sorted(chosen);ded=[];last=-999.
    for t in chosen:
        if t-last>=.045:
            ded.append(t);last=t
    out=[x for x in e if x[1]!="pedal_hat"]+[(t,"pedal_hat") for t in ded]
    return repair.enforce(out),{
      "raw":len(raw),"recall":len(rec),"current":len(cur),"hat":len(hats),
      "ratio":ratio,"eligible":eligible,"added":len(added),"chosen":len(ded)
    }

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,sparse_thr,per_thr,rep_thr,outdir):
    result={"mode":mode,"sparse_thr":sparse_thr,"per_thr":per_thr,"rep_thr":rep_thr,"diagnostics":{},"songs":{}}
    tot=Counter()
    for song in SONGS:
        m=meta(song);events,diag=rescue(song,mode,sparse_thr,per_thr,rep_thr);result["diagnostics"][song]=diag
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
          "precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,
          "false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,
          "mean_song_f1":sum(sf)/len(sf) if sf else None,
          "worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s);return result

def choose(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("pedal_hat",),max_part_drop=.025,target_tolerance=.012)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-pedal-rescue-v2";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","base",.08,.50,3,root/"baseline")

    res={}
    for name,mode in [("c184_base","base"),("c184_periodic","periodic"),("c184_accent","accent"),
                      ("c184_gap_repeat","gap_repeat"),("c184_hybrid","hybrid")]:
        res[name]=evaluate(name,mode,.08,.50,3,root/"cycle184")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],
          "pedal":res[name]["summary"]["by_group"]["pedal_hat"],"diag":res[name]["diagnostics"],
          "score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline);win=d["winner"] or "c184_base";best=res[win]
    report["cycles"].append({"cycle":184,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,thr in [("c185_s04",.04),("c185_s06",.06),("c185_s08",.08),("c185_s12",.12),("c185_s18",.18)]:
        res[name]=evaluate(name,best["mode"],thr,best["per_thr"],best["rep_thr"],root/"cycle185")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],
          "pedal":res[name]["summary"]["by_group"]["pedal_hat"],"diag":res[name]["diagnostics"],
          "score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":185,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,per,rep in [("c186_loose",.25,2),("c186_mid",.50,3),("c186_strict",.75,3),("c186_rep4",.50,4)]:
        res[name]=evaluate(name,best["mode"],best["sparse_thr"],per,rep,root/"cycle186")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],
          "pedal":res[name]["summary"]["by_group"]["pedal_hat"],"diag":res[name]["diagnostics"],
          "score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":186,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "mode":best["mode"],"sparse_thr":best["sparse_thr"],"per_thr":best["per_thr"],"rep_thr":best["rep_thr"],
      "diagnostics":best["diagnostics"],"detailed":detail.compare_dir(root/"cycle186"/win,win)["aggregate"]}
    (EXP/"results-iterative-pedal-rescue-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
