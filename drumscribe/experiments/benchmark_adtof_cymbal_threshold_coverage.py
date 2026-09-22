"""Benchmark broad ADTOF cymbal onset coverage vs threshold.

ADTOF inference is run once per song. Only the cymbal activation threshold is
swept afterwards. Prediction never reads chart.mid; reference is scoring-only.

Reports:
- broad cymbal candidate count
- crash/ride onset recall of cymbal stream
- union recall after adding current browser hat/pedal/ride/crash onset times
- false-candidate pressure (candidate count / crash+ride references)

This determines whether missing cymbals are a candidate-generation problem.
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
from collections import Counter

import numpy as np
import torch
from adtof_pytorch import (
    calculate_n_bins,create_frame_rnn_model,get_default_weights_path,
    load_pytorch_weights,PeakPicker,LABELS_5
)
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
THRESHOLDS=[.04,.06,.08,.10,.12,.14,.16,.18,.20,.22,.24,.26,.28,.30,.32,.35]

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def model():
    n=calculate_n_bins();m=create_frame_rnn_model(n)
    m=load_pytorch_weights(m,get_default_weights_path(),strict=False)
    return m.eval()

def infer(song,m,p):
    a=p.load_audio(str(ROOT/"DruMaster/songs"/song/"drums.mp3"))
    st=p.compute_stft(a);x=p.apply_filterbank(st).T.astype(np.float32)[...,None]
    with torch.no_grad():
        y=m(torch.from_numpy(x[None,...])).cpu().numpy()
    return y

def pick_cym(y,thr):
    # Preserve official other thresholds but only consume MIDI 49 generic cymbal.
    pp=PeakPicker(thresholds=[.22,.24,.32,.22,thr],fps=100)
    out=pp.pick(y,labels=LABELS_5,label_offset=0)[0]
    return sorted(float(x) for x in out.get(49,[]))

def browser_metal(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    return sorted(t-off for t,g,*_ in ev.midi_events(BASE/f"{song}.mid") if g in ("hat","pedal_hat","ride","crash"))

def truth(song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    rows=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    return {g:sorted(t+shift for t,gg,*_ in rows if gg==g) for g in ("crash","ride")}

def match_count(pred,ref,tol=.08):
    pred=sorted(pred);ref=sorted(ref);used=set();tp=0
    for t in pred:
        if not ref:break
        j=int(np.searchsorted(ref,t));opts=[k for k in (j-1,j,j+1) if 0<=k<len(ref) and k not in used]
        if not opts:continue
        k=min(opts,key=lambda z:abs(ref[z]-t))
        if abs(ref[k]-t)<=tol:used.add(k);tp+=1
    return tp

def union_times(a,b,w=.035):
    xs=sorted(a+b);out=[]
    for t in xs:
        if not out or t-out[-1]>w:out.append(t)
        elif t<out[-1]:out[-1]=t
    return out

def main():
    m=model();p=create_adtof_processor()
    report={"schema":1,"thresholds":THRESHOLDS,"songs":{},"aggregate":{}}
    aggregate={th:Counter() for th in THRESHOLDS}
    for song in SONGS:
        print("INFER",song,flush=True);y=infer(song,m,p);br=browser_metal(song);tr=truth(song)
        rows={}
        for th in THRESHOLDS:
            cy=pick_cym(y,th);u=union_times(cy,br)
            ct=match_count(cy,tr["crash"]);rt=match_count(cy,tr["ride"])
            uct=match_count(u,tr["crash"]);urt=match_count(u,tr["ride"])
            refc=len(tr["crash"]);refr=len(tr["ride"]);ref=refc+refr
            row={"candidates":len(cy),"browserMetal":len(br),"union":len(u),
                 "crash":{"tp":ct,"ref":refc,"recall":ct/refc if refc else None},
                 "ride":{"tp":rt,"ref":refr,"recall":rt/refr if refr else None},
                 "metalRecall":(ct+rt)/ref if ref else None,
                 "unionCrashRecall":uct/refc if refc else None,
                 "unionRideRecall":urt/refr if refr else None,
                 "unionMetalRecall":(uct+urt)/ref if ref else None,
                 "candidateRatio":len(cy)/ref if ref else None}
            rows[str(th)]=row
            a=aggregate[th];a["cand"]+=len(cy);a["ct"]+=ct;a["rt"]+=rt;a["uct"]+=uct;a["urt"]+=urt;a["cr"]+=refc;a["rr"]+=refr
        report["songs"][song]=rows
        print("SONG",song,json.dumps(rows,ensure_ascii=False),flush=True)
    for th,a in aggregate.items():
        ref=a["cr"]+a["rr"]
        report["aggregate"][str(th)]={
          "candidates":a["cand"],"crashRecall":a["ct"]/a["cr"],"rideRecall":a["rt"]/a["rr"],
          "metalRecall":(a["ct"]+a["rt"])/ref,
          "unionCrashRecall":a["uct"]/a["cr"],"unionRideRecall":a["urt"]/a["rr"],
          "unionMetalRecall":(a["uct"]+a["urt"])/ref,
          "candidateRatio":a["cand"]/ref
        }
    (EXP/"results-adtof-cymbal-threshold-coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("AGG",json.dumps(report["aggregate"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
