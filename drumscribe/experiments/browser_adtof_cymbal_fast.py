"""Fast browser ADTOF cymbal policy search.

Equivalent feature grid to browser_adtof_cymbal_search.py, but precomputes all
non-cymbal scores and matches only crash/ride per candidate. This makes a dense
threshold search cheap enough for repeated PDCA.
"""
from __future__ import annotations

import json, math, importlib.util
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
BASE=EXP/"generated-v2-browser"
AD=EXP/"generated-search-adtof/cycle163/c163_precision"

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)


def rows(path,song):
    rr=[(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
    # Browser MIDI is exported in musical/bar-aligned coordinates. All search
    # features and reference scoring operate on the original audio timeline,
    # so restore only generated-v2-browser events by undoing exportOffsetSec.
    if path == BASE:
        side=json.loads((BASE/f"{song}.json").read_text())
        off=float(side.get("exportOffsetSec",0) or 0)
        rr=[(t-off,g) for t,g in rr]
    return rr


def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)


def circ(t,phase,p):
    x=(t-phase)%p
    return min(x,p-x)


def periodic(times,t,bpm):
    if len(times)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.07 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best


def match(pred,truth,tol=.08):
    pred=sorted(pred);truth=sorted(truth);used=set();tp=0
    for x in pred:
        j=np.searchsorted(truth,x)
        opts=[k for k in (j-1,j,j+1) if 0<=k<len(truth) and k not in used]
        if not opts:continue
        k=min(opts,key=lambda q:abs(x-truth[q]))
        if abs(x-truth[k])<=tol:
            used.add(k);tp+=1
    return tp


def prepare_song(song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    side=json.loads((BASE/f"{song}.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    b=rows(BASE,song)
    ad=sorted(t for t,g in rows(AD,song) if g=="crash")
    cur_cr=sorted(t for t,g in b if g=="crash")
    cur_ri=sorted(t for t,g in b if g=="ride")
    truth_cr=sorted(t+shift for t,g,*_ in truth if g=="crash")
    truth_ri=sorted(t+shift for t,g,*_ in truth if g=="ride")

    # fixed non-cymbal counts/tp
    fixed_tp=fixed_pred=fixed_ref=0
    for g in ev.ORDER:
        if g in ("crash","ride"):continue
        pp=sorted(t for t,gg in b if gg==g)
        tt=sorted(t+shift for t,gg,*_ in truth if gg==g)
        fixed_tp+=match(pp,tt);fixed_pred+=len(pp);fixed_ref+=len(tt)
    return {
      "bpm":float(side["bpm"]),"phase":float(side["barPhaseSec"]),
      "ad":ad,"cur_cr":cur_cr,"cur_ri":cur_ri,
      "truth_cr":truth_cr,"truth_ri":truth_ri,
      "fixed_tp":fixed_tp,"fixed_pred":fixed_pred,"fixed_ref":fixed_ref,
    }


def predict(d,head,rp,cm,am,margin):
    bpm=d["bpm"];phase=d["phase"];beat=60/bpm;bar=4*beat
    chosen=[]
    for t in d["ad"]:
        hd=circ(t,phase,bar)/beat
        per=periodic(d["ad"],t,bpm)
        cs=near(d["cur_cr"],t,.07);rs=near(d["cur_ri"],t,.07)
        cscore=(2.2 if hd<=head else 0)+(0.7 if cs else 0)
        rscore=1.45*per+(0.8 if rs else 0)+(0.25 if hd>head else 0)
        if am=="hard_head":
            if hd<=head:g="crash"
            elif per>=rp:g="ride"
            else:continue
        elif am=="score":
            if max(cscore,rscore)<1.0 or abs(cscore-rscore)<margin:continue
            g="crash" if cscore>rscore else "ride"
        else:
            if hd<=head:g="crash"
            elif per>=rp or rs:g="ride"
            elif cs:g="crash"
            else:continue
        chosen.append((t,g))

    if cm!="none":
        for g,arr in (("crash",d["cur_cr"]),("ride",d["cur_ri"])):
            for t in arr:
                if any(abs(t-x)<=.07 for x,_ in chosen):continue
                hd=circ(t,phase,bar)/beat
                if g=="crash":
                    keep=(cm=="loose" and hd<=.22) or (cm=="strict" and hd<=.12)
                else:
                    per=periodic(d["cur_ri"],t,bpm)
                    keep=(cm=="loose" and per>=.50) or (cm=="strict" and per>=.75)
                if keep:chosen.append((t,g))
    chosen.sort()
    ded=[]
    for t,g in chosen:
        if ded and t-ded[-1][0]<.05:
            if g=="crash" and ded[-1][1]=="ride":ded[-1]=(t,g)
            continue
        ded.append((t,g))
    return [t for t,g in ded if g=="crash"],[t for t,g in ded if g=="ride"]


def main():
    data={s:prepare_song(s) for s in SONGS}
    total_ref=sum(d["fixed_ref"]+len(d["truth_cr"])+len(d["truth_ri"]) for d in data.values())

    results=[]
    for head in (.06,.08,.10,.12,.14,.16,.18,.20,.24,.30):
      for rp in (.25,.50,.75,1.0):
       for cm in ("none","strict","loose"):
        for am in ("hard_head","score","permissive"):
         for margin in ((0,.15,.25,.4,.6) if am=="score" else (0,)):
          tp=predn=0
          ctp=cp=cr=rtp=rp_n=rr=0
          songs={}
          for song,d in data.items():
            crp,rip=predict(d,head,rp,cm,am,margin)
            a=match(crp,d["truth_cr"]);b=match(rip,d["truth_ri"])
            stp=d["fixed_tp"]+a+b;sp=d["fixed_pred"]+len(crp)+len(rip);sr=d["fixed_ref"]+len(d["truth_cr"])+len(d["truth_ri"])
            tp+=stp;predn+=sp
            ctp+=a;cp+=len(crp);cr+=len(d["truth_cr"])
            rtp+=b;rp_n+=len(rip);rr+=len(d["truth_ri"])
            songs[song]={
              "crash":{"tp":a,"predicted":len(crp),"reference":len(d["truth_cr"])},
              "ride":{"tp":b,"predicted":len(rip),"reference":len(d["truth_ri"])},
              "overall_f1":2*stp/(sp+sr) if sp+sr else 0
            }
          f1=2*tp/(predn+total_ref)
          cf1=2*ctp/(cp+cr) if cp+cr else 0
          rf1=2*rtp/(rp_n+rr) if rp_n+rr else 0
          cprec=ctp/cp if cp else 0;rprec=rtp/rp_n if rp_n else 0
          objective=f1+.30*.5*(cf1+rf1)+.04*.5*(cprec+rprec)
          results.append({
            "objective":objective,
            "config":{"head_thr":head,"ride_per":rp,"current_mode":cm,"ad_mode":am,"margin":margin},
            "summary":{
              "tp":tp,"predicted":predn,"reference":total_ref,
              "precision":tp/predn if predn else 0,
              "recall":tp/total_ref if total_ref else 0,
              "f1":f1,
              "crash":{"tp":ctp,"predicted":cp,"reference":cr,"precision":cprec,"recall":ctp/cr if cr else 0,"f1":cf1},
              "ride":{"tp":rtp,"predicted":rp_n,"reference":rr,"precision":rprec,"recall":rtp/rr if rr else 0,"f1":rf1},
            },
            "songs":songs
          })
    results.sort(key=lambda x:(x["objective"],x["summary"]["f1"]),reverse=True)
    report={"schema":2,"top":results[:50]}
    (EXP/"results-browser-adtof-cymbal-fast.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"top":results[:10]},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
