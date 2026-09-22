"""Search a browser-compatible hi-hat overtrigger filter.

Input events are the latest real-Chromium DrumScribe outputs. Candidate
generation uses only predicted events, audio features, and the audio-only
estimated BPM/beat phase saved by the browser. chart.mid is scoring-only.

Search dimensions:
- absolute hat template similarity
- collision gate against kick/snare template similarity
- rhythmic periodicity rescue
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
IDX={g:i for i,g in enumerate(ev.ORDER)}

def browser_events(song):
    side=json.loads((EXP/"generated-v2-browser"/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    rows=ev.midi_events(EXP/"generated-v2-browser"/f"{song}.mid")
    return [(t-off,g,p) for t,g,p in rows],side

def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)

def rep_support(hats,t,beat,tol=.045):
    if len(hats)<3 or beat<=0:return 0
    best=0
    for step in (beat/4,beat/2,beat):
        n=0
        for k in (-2,-1,1,2):
            target=t+k*step
            if any(abs(x-target)<=tol for x in hats):n+=1
        best=max(best,n)
    return best

def prepare():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    out={}
    for song in SONGS:
        print("FEATURE",song,flush=True)
        pred,side=browser_events(song)
        x=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3")
        sp=ev.spectrum(x);band,sim=ev.features(sp,tmpl)
        hats=sorted(t for t,g,*_ in pred if g=="hat")
        kicks=sorted(t for t,g,*_ in pred if g=="kick")
        snares=sorted(t for t,g,*_ in pred if g=="snare")
        bpm=float(side["bpm"]);beat=60/bpm
        feat={}
        for t in hats:
            f=max(0,min(sim.shape[1]-1,int(round(t*ev.SR/ev.HOP))))
            hs=float(sim[IDX["hat"],f]);ks=float(sim[IDX["kick"],f]);ss=float(sim[IDX["snare"],f])
            cs=float(sim[IDX["crash"],f]);rs=float(sim[IDX["ride"],f])
            feat[t]={
              "hat":hs,"body":max(ks,ss),"kick":ks,"snare":ss,"crash":cs,"ride":rs,
              "rep":rep_support(hats,t,beat)
            }
        out[song]={"pred":pred,"side":side,"feat":feat,"kicks":kicks,"snares":snares}
    return out

def apply(song,data,abs_min,coll_ratio,rescue,window,weak_rescue):
    pred=data["pred"];feat=data["feat"];kicks=data["kicks"];snares=data["snares"]
    out=[];removed=Counter()
    for row in pred:
        t,g,*rest=row
        if g!="hat":
            out.append(row);continue
        f=feat[t]
        coll=near(kicks,t,window) or near(snares,t,window)
        if f["hat"]<abs_min and f["rep"]<weak_rescue:
            removed["absolute"]+=1;continue
        if coll and f["hat"]<coll_ratio*max(.03,f["body"]) and f["rep"]<rescue:
            removed["collision"]+=1;continue
        out.append(row)
    return out,removed

def summarize(scores):
    tot=Counter()
    for sc in scores.values():
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,r=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":r,
       "precision":tp/n if n else 0,"recall":tp/r if r else 0,
       "f1":2*tp/(n+r) if n+r else 0,"by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,
          "count_ratio":b/c if c else None}
    return s

def evaluate(cache,cfg):
    abs_min,coll_ratio,rescue,window,weak_rescue=cfg
    scores={};diag={}
    for song in SONGS:
        pred,removed=apply(song,cache[song],*cfg)
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        sc=ev.score(pred,truth,shift)
        scores[song]=sc;diag[song]={"removed":dict(removed),"hat_pred":sc["by_group"]["hat"]["predicted"],"hat_tp":sc["by_group"]["hat"]["tp"]}
    return summarize(scores),scores,diag

def main():
    cache=prepare()
    configs=[]
    for abs_min in (0,.10,.15,.20,.25,.30,.35,.40):
      for coll_ratio in (.70,.85,1.00,1.15,1.30,1.50):
       for rescue in (1,2,3,4):
        for window in (.025,.035,.045):
         for weak_rescue in (2,3,4):
          configs.append((abs_min,coll_ratio,rescue,window,weak_rescue))
    rows=[]
    baseline,_s,_d=evaluate(cache,(0,0,0,.035,0))
    base_hat=baseline["by_group"]["hat"]
    for i,cfg in enumerate(configs):
        s,songs,diag=evaluate(cache,cfg)
        h=s["by_group"]["hat"]
        # Prioritize hat F1 while preserving overall recall; reject severe
        # hat recall collapse. Score does not use per-song hardcoding.
        eligible=h["recall"]>=max(.60,base_hat["recall"]-.16)
        objective=s["f1"]+.18*h["f1"]-.03*abs((h["count_ratio"] or 1)-1)
        rows.append((eligible,objective,s["f1"],h["f1"],cfg,s,diag))
        if i%500==0:print("SEARCH",i,len(configs),flush=True)
    rows.sort(key=lambda z:(z[0],z[1],z[2],z[3]),reverse=True)
    top=[]
    for ok,obj,of1,hf1,cfg,s,diag in rows[:30]:
        top.append({"eligible":ok,"objective":obj,
          "config":{"abs_min":cfg[0],"collision_ratio":cfg[1],"periodic_rescue":cfg[2],"collision_window":cfg[3],"weak_rescue":cfg[4]},
          "summary":s,"diagnostics":diag})
    report={"schema":1,"description":"Browser hat filter search. Truth is scoring-only.",
            "baseline":baseline,"top":top}
    (EXP/"results-browser-hat-filter-search-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps({"overall":baseline["f1"],"hat":baseline["by_group"]["hat"]},ensure_ascii=False),flush=True)
    for x in top[:10]:
        print("TOP",json.dumps({"cfg":x["config"],"overall":x["summary"]["f1"],"hat":x["summary"]["by_group"]["hat"],"diag":x["diagnostics"]},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
