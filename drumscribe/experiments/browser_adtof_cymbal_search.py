"""Search browser-available ADTOF cymbal classification policies.

Base MIDI: current real-browser output after ADTOF structural replacement.
Broad cymbal candidates: ADTOF precision stream (same model/threshold as browser;
chunk benchmark showed ~0.999 event agreement with full inference).

Prediction-time features only:
- estimated browser BPM and bar phase
- periodic support within the broad ADTOF cymbal stream
- proximity to the current browser crash/ride predictions

chart.mid is scoring-only.
"""
from __future__ import annotations

import json, math, importlib.util
from pathlib import Path
from collections import Counter
import numpy as np

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

BASE=EXP/"generated-v2-browser"
AD=EXP/"generated-search-adtof/cycle163/c163_precision"

GROUPS=ev.ORDER


def rows(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]


def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)


def circ_dist(t,phase,period):
    x=(t-phase)%period
    return min(x,period-x)


def periodic(times,t,bpm):
    if len(times)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.07 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best


def timing(song):
    j=json.loads((BASE/f"{song}.json").read_text())
    return float(j["bpm"]),float(j["barPhaseSec"])


def build(song,head_thr,ride_per,current_mode,ad_mode,margin):
    base=rows(BASE,song)
    bpm,phase=timing(song)
    beat=60/bpm;bar=4*beat

    ad=sorted(t for t,g in rows(AD,song) if g=="crash")
    cur_cr=sorted(t for t,g in base if g=="crash")
    cur_ri=sorted(t for t,g in base if g=="ride")

    out=[e for e in base if e[1] not in ("crash","ride")]
    chosen=[]

    for t in ad:
        hd=circ_dist(t,phase,bar)/beat
        per=periodic(ad,t,bpm)
        cs=near(cur_cr,t,.07)
        rs=near(cur_ri,t,.07)

        # browser-available evidence score
        cscore=(2.2 if hd<=head_thr else 0)+(0.7 if cs else 0)
        rscore=1.45*per+(0.8 if rs else 0)+(0.25 if hd>head_thr else 0)

        if ad_mode=="hard_head":
            if hd<=head_thr: g="crash"
            elif per>=ride_per: g="ride"
            else: continue
        elif ad_mode=="score":
            if max(cscore,rscore)<1.0 or abs(cscore-rscore)<margin: continue
            g="crash" if cscore>rscore else "ride"
        else: # permissive
            if hd<=head_thr: g="crash"
            elif per>=ride_per or rs: g="ride"
            elif cs: g="crash"
            else: continue

        chosen.append((t,g))

    # Current detector fallback only for events not already covered by ADTOF.
    if current_mode!="none":
        for g,arr in (("crash",cur_cr),("ride",cur_ri)):
            for t in arr:
                if any(abs(t-x)<=.07 for x,_ in chosen):continue
                hd=circ_dist(t,phase,bar)/beat
                if g=="crash":
                    keep=(current_mode=="loose" and hd<=.22) or (current_mode=="strict" and hd<=.12)
                else:
                    per=periodic(cur_ri,t,bpm)
                    keep=(current_mode=="loose" and per>=.50) or (current_mode=="strict" and per>=.75)
                if keep: chosen.append((t,g))

    chosen.sort()
    # de-dupe same cymbal family within 50 ms, prefer crash at near-identical time
    ded=[]
    for t,g in chosen:
        if ded and t-ded[-1][0]<.05:
            if g=="crash" and ded[-1][1]=="ride": ded[-1]=(t,g)
            continue
        ded.append((t,g))
    out.extend(ded)
    return sorted(out)


def summarize(candidates):
    tot=Counter()
    per_song={}
    for song,events in candidates.items():
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        # score accepts event tuples with time/group
        pred=[(t,g,0,0) for t,g in events]
        sc=ev.score(pred,truth,shift)
        per_song[song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"])
        for g,d in sc["by_group"].items():
            tot[f"{g}_tp"]+=d["tp"];tot[f"{g}_pred"]+=d["predicted"];tot[f"{g}_ref"]+=d["reference"]
    s={"tp":tot["tp"],"predicted":tot["predicted"],"reference":tot["reference"],"by_group":{}}
    s["precision"]=s["tp"]/s["predicted"] if s["predicted"] else 0
    s["recall"]=s["tp"]/s["reference"] if s["reference"] else 0
    s["f1"]=2*s["tp"]/(s["predicted"]+s["reference"]) if s["predicted"]+s["reference"] else 0
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        s["by_group"][g]={
          "tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,
          "recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,
          "count_ratio":b/c if c else None
        }
    return s,per_song


def main():
    baseline={s:rows(BASE,s) for s in SONGS}
    base_summary,_=summarize(baseline)
    report={"schema":1,"baseline":base_summary,"top":[]}

    results=[]
    for head in (.08,.12,.16,.20,.24,.30):
      for rp in (.25,.50,.75,1.0):
       for cm in ("none","strict","loose"):
        for am in ("hard_head","score","permissive"):
         for margin in ((0,.25,.5) if am=="score" else (0,)):
          cand={s:build(s,head,rp,cm,am,margin) for s in SONGS}
          summary,per_song=summarize(cand)
          cr=summary["by_group"]["crash"];ri=summary["by_group"]["ride"]
          # prioritize cymbal class quality while preserving whole-score F1
          cym_mean=.5*(cr["f1"]+ri["f1"])
          objective=summary["f1"]+.28*cym_mean-.10*max(0,cr["count_ratio"]-1 if cr["count_ratio"] else 0)-.10*max(0,ri["count_ratio"]-1 if ri["count_ratio"] else 0)
          eligible=summary["f1"]>=base_summary["f1"]-.006
          results.append({
            "eligible":eligible,"objective":objective,
            "config":{"head_thr":head,"ride_per":rp,"current_mode":cm,"ad_mode":am,"margin":margin},
            "summary":summary,
            "songs":{s:{
              "crash":per_song[s]["by_group"]["crash"],
              "ride":per_song[s]["by_group"]["ride"],
              "overall_f1":2*per_song[s]["tp"]/(per_song[s]["predicted"]+per_song[s]["reference"]) if per_song[s]["predicted"]+per_song[s]["reference"] else 0
            } for s in SONGS}
          })
    results.sort(key=lambda r:(r["eligible"],r["objective"],r["summary"]["f1"]),reverse=True)
    report["top"]=results[:30]
    (EXP/"results-browser-adtof-cymbal-search.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"baseline":base_summary,"top":report["top"][:10]},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
