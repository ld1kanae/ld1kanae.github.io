"""Diagnostic only: measure temporal-decay feature separability by reference class.

This does NOT define a predictor. It labels current browser plate events by the
nearest reference class only to understand whether decay features can separate
hat/ride/crash, and writes distribution summaries.
"""
from __future__ import annotations
import importlib.util,json,bisect
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

dec=loadmod("dec",EXP/"browser_cymbal_decay_search.py")
ev=dec.ev

def browser_rows(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")]

def nearest_label(t,truth,tol=.08):
    best=None
    for g in ("hat","ride","crash","pedal_hat"):
        xs=truth[g]
        i=bisect.bisect_left(xs,t)
        for k in (i-1,i):
            if 0<=k<len(xs):
                d=abs(xs[k]-t)
                if d<=tol and (best is None or d<best[0]):best=(d,g)
    return best[1] if best else "unmatched"

def stats(rows,key):
    vals=[r[key] for r in rows]
    if not vals:return {"n":0}
    return {"n":len(vals),"mean":float(np.mean(vals)),
      "q10":float(np.quantile(vals,.1)),"q25":float(np.quantile(vals,.25)),
      "q50":float(np.quantile(vals,.5)),"q75":float(np.quantile(vals,.75)),
      "q90":float(np.quantile(vals,.9))}

def main():
    report={"schema":1,"songs":{},"aggregate":{}}
    allrows={g:[] for g in ("hat","ride","crash","pedal_hat","unmatched")}
    for song in SONGS:
        audio=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3");sp=ev.spectrum(audio)
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        truthrows=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        truth={g:sorted(t+shift for t,gg,*_ in truthrows if gg==g) for g in ("hat","ride","crash","pedal_hat")}
        groups={g:[] for g in allrows}
        for t,predg in browser_rows(song):
            if predg not in ("hat","ride","crash"):continue
            f=dec.env_features(sp,t);lab=nearest_label(t,truth)
            f.update({"t":t,"pred":predg,"label":lab})
            groups[lab].append(f);allrows[lab].append(f)
        report["songs"][song]={g:{
          "tail1":stats(rs,"tail1"),"tail2":stats(rs,"tail2"),"tail3":stats(rs,"tail3"),
          "upper_tail":stats(rs,"upper_tail"),"mid_tail":stats(rs,"mid_tail")
        } for g,rs in groups.items()}
    report["aggregate"]={g:{
      "tail1":stats(rs,"tail1"),"tail2":stats(rs,"tail2"),"tail3":stats(rs,"tail3"),
      "upper_tail":stats(rs,"upper_tail"),"mid_tail":stats(rs,"mid_tail")
    } for g,rs in allrows.items()}
    (EXP/"results-cymbal-decay-diagnostic.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report["aggregate"],ensure_ascii=False,indent=2))
    print("KAJIU",json.dumps(report["songs"]["kaiju"],ensure_ascii=False,indent=2))

if __name__=="__main__":main()
