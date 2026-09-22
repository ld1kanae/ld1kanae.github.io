"""Cycles 198-200: ADTOF cymbal onset + sample-template crash/ride classifier.

Base: component-merge-v7 c194_basecrash.

ADTOF supplies broad cymbal onset candidates only. Crash-vs-ride class is
decided independently from the DruMaster reference drum samples in
DruMaster/assets/drums using the same whitened onset-spectrum similarity used
by the offline DSP evaluator. Existing crash/ride notes are preserved unless
a new onset is absent from the current cymbal stream.

This provides genuinely new acoustic evidence after the previous crash
consensus search found zero unseen candidates shared by its older sources.
chart.mid is scoring-only.
"""
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

repair=loadmod("repair",EXP/"iterative_search_overtrigger_repair.py")
ev=repair.ev
sel=repair.sel
detail=repair.detail
base=repair.base

SONGS=repair.SONGS
GROUPS=repair.GROUPS
BASE=EXP/"generated-search-component-merge-v7/cycle194/c194_basecrash"
AD={
  "precision":EXP/"generated-search-adtof/cycle163/c163_precision",
  "default":EXP/"generated-search-adtof/cycle163/c163_default",
  "recall":EXP/"generated-search-adtof/cycle163/c163_recall",
}

IDX={g:i for i,g in enumerate(ev.ORDER)}

def rows(path,song):
    return repair.rows(path,song)

def meta(song):
    return repair.meta(song)

def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)

def prepare_features():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    out={}
    for song in SONGS:
        print("FEATURES",song,flush=True)
        x=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3")
        spec=ev.spectrum(x)
        band,sim=ev.features(spec,tmpl)
        out[song]={"band":band,"sim":sim}
        del x,spec
    return out

def local_scores(feat,t,rad=.032):
    f=int(round(t*ev.SR/ev.HOP))
    rr=max(1,int(round(rad*ev.SR/ev.HOP)))
    lo=max(0,f-rr);hi=min(feat["sim"].shape[1],f+rr+1)
    if hi<=lo:
        return {"crash":0.0,"ride":0.0,"hat":0.0}
    sim=feat["sim"]
    return {
      "crash":float(np.max(sim[IDX["crash"],lo:hi])),
      "ride":float(np.max(sim[IDX["ride"],lo:hi])),
      "hat":float(np.max(sim[IDX["hat"],lo:hi])),
    }

def source_times(song,source):
    # ADTOF has a single broad cymbal class, materialized as MIDI crash.
    return [t for t,g in rows(AD[source],song) if g=="crash"]

def periodic(times,t,bpm):
    if len(times)<3:return 0.0
    best=0.0
    for step in (30.0/bpm,60.0/bpm,120.0/bpm):
        n=sum(any(abs(x-(t+k*step))<=.065 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4.0)
    return best

def dedup_times(xs,w=.045):
    xs=sorted(xs);out=[];cluster=[]
    for t in xs:
        if not cluster or t-cluster[-1]<=w:
            cluster.append(t)
        else:
            out.append(float(np.median(cluster)));cluster=[t]
    if cluster:out.append(float(np.median(cluster)))
    return out

def classify_new(song,t,source_all,feat,margin,strength,hat_ratio,context):
    s=local_scores(feat,t)
    cs,rs,hs=s["crash"],s["ride"],s["hat"]
    mx=max(cs,rs)
    if mx<strength or mx<hat_ratio*hs:
        return None,s,"weak"

    ratio=(cs+1e-4)/(rs+1e-4)
    if ratio>=margin:
        return "crash",s,"ratio_crash"
    if ratio<=1.0/margin:
        return "ride",s,"ratio_ride"

    if context=="ratio_only":
        return None,s,"ambiguous"

    e=rows(BASE,song)
    m=meta(song);bpm=float(m["bpm"])
    _,ph,beat,bar=repair.timing(song,e)
    kicks=[x for x,g in e if g=="kick"]
    down=repair.downbeat_strength(t,ph,beat,bar)
    rep=periodic(source_all,t,bpm)

    # Context is only a tie-breaker inside the ambiguous spectral band.
    # Keep a weak class-preference requirement so context alone cannot turn
    # a hi-hat-like onset into a cymbal note.
    if (near(kicks,t,.050) or down>=.72) and cs>=.88*rs:
        return "crash",s,"context_crash"
    if rep>=.75 and rs>=.88*cs:
        return "ride",s,"context_ride"
    return None,s,"ambiguous"

def build(song,features,source,margin,strength,hat_ratio,context):
    e=rows(BASE,song)
    current=[t for t,g in e if g in ("crash","ride")]
    raw=dedup_times(source_times(song,source),.045)
    added=[]
    diag={"source":len(raw),"current":len(current),"added_crash":0,"added_ride":0,
          "weak":0,"ambiguous":0,"ratio_crash":0,"ratio_ride":0,
          "context_crash":0,"context_ride":0}
    for t in raw:
        if near(current,t,.060):
            continue
        g,s,reason=classify_new(song,t,raw,features[song],margin,strength,hat_ratio,context)
        diag[reason]=diag.get(reason,0)+1
        if g is None:
            continue
        # Avoid new sustain/retrigger events around any already accepted cymbal.
        accepted=current+[x for x,_ in added]
        min_gap=.095 if g=="crash" else .050
        if near(accepted,t,min_gap):
            continue
        added.append((t,g));diag["added_"+g]+=1
    return repair.enforce(e+added),diag

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,features,source,margin,strength,hat_ratio,context,outdir):
    result={"source":source,"margin":margin,"strength":strength,"hat_ratio":hat_ratio,
            "context":context,"diagnostics":{},"songs":{}}
    tot=Counter()
    for song in SONGS:
        m=meta(song)
        events,diag=build(song,features,source,margin,strength,hat_ratio,context)
        result["diagnostics"][song]=diag
        p=outdir/name/f"{song}.mid"
        write(p,events,float(m["bpm"]))
        pred=ev.midi_events(p)
        truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc)
        result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]

    tp,n,ref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":ref,
       "precision":tp/n if n else 0,"recall":tp/ref if ref else 0,
       "f1":2*tp/(n+ref) if n+ref else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{})
            rr=x.get("reference",0)
            if rr:
                sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={
          "tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,
          "false_discovery_rate":(b-a)/b if b else 0,
          "miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,
          "mean_song_f1":sum(sf)/len(sf) if sf else None,
          "worst_song_f1":min(sf) if sf else None}
    result["summary"]=s
    result["canonical_score"]=sel.score(s)
    return result

def choose(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("crash","ride","hat"),
                 max_part_drop=.025,target_tolerance=.012)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-cymbal-template-v2"
    report={"schema":1,"description":"Cycles 198-200: ADTOF cymbal onsets classified by DruMaster sample-template similarity.","cycles":[]}
    features=prepare_features()
    baseline=evaluate("baseline",features,"precision",99.0,99.0,99.0,"ratio_only",root/"baseline")

    res={"c198_base":baseline}
    for name,source in [("c198_precision","precision"),("c198_default","default"),("c198_recall","recall")]:
        res[name]=evaluate(name,features,source,1.50,.39,.90,"context",root/"cycle198")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],
          "crash":res[name]["summary"]["by_group"]["crash"],"ride":res[name]["summary"]["by_group"]["ride"],
          "hat":res[name]["summary"]["by_group"]["hat"],"diag":res[name]["diagnostics"],
          "score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline);win=d["winner"] or "c198_base";best=res[win]
    report["cycles"].append({"cycle":198,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,margin in [("c199_m115",1.15),("c199_m135",1.35),("c199_m155",1.55),("c199_m180",1.80)]:
        res[name]=evaluate(name,features,best["source"],margin,best["strength"],best["hat_ratio"],best["context"],root/"cycle199")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],
          "crash":res[name]["summary"]["by_group"]["crash"],"ride":res[name]["summary"]["by_group"]["ride"],
          "diag":res[name]["diagnostics"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":199,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    cfg=[
      ("c200_s30h80",.30,.80),
      ("c200_s35h85",.35,.85),
      ("c200_s39h90",.39,.90),
      ("c200_s45h95",.45,.95),
      ("c200_s50h100",.50,1.00),
    ]
    for name,strength,hr in cfg:
        res[name]=evaluate(name,features,best["source"],best["margin"],strength,hr,best["context"],root/"cycle200")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],
          "crash":res[name]["summary"]["by_group"]["crash"],"ride":res[name]["summary"]["by_group"]["ride"],
          "hat":res[name]["summary"]["by_group"]["hat"],"diag":res[name]["diagnostics"],
          "score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":200,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "source":best["source"],"margin":best["margin"],"strength":best["strength"],"hat_ratio":best["hat_ratio"],
      "context":best["context"],"diagnostics":best["diagnostics"],
      "detailed":detail.compare_dir(root/"cycle200"/win,win)["aggregate"]}
    (EXP/"results-iterative-cymbal-template-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    main()
