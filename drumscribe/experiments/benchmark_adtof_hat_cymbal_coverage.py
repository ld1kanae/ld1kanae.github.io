"""Benchmark low-threshold ADTOF hat+cymbal onset coverage.

Inference is audio-only. References are scoring-only.

For each song and threshold pair:
- low-threshold ADTOF hat candidates
- low-threshold ADTOF generic cymbal candidates
- union of both + current browser metal onsets
- recall against reference hat/pedal/ride/crash separately
- candidate pressure

Goal: determine whether missing kaiju ride hits are absent from ADTOF cymbal
but present in the hat activation stream.
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
HAT_T=[.04,.06,.08,.10,.12,.16,.22]
CYM_T=[.04,.06,.08,.10,.14,.20,.30]
GROUPS=("hat","pedal_hat","ride","crash")

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def model():
    n=calculate_n_bins();m=create_frame_rnn_model(n)
    return load_pytorch_weights(m,get_default_weights_path(),strict=False).eval()

def infer(song,m,p):
    a=p.load_audio(str(ROOT/"DruMaster/songs"/song/"drums.mp3"))
    st=p.compute_stft(a);x=p.apply_filterbank(st).T.astype(np.float32)[...,None]
    with torch.no_grad():return m(torch.from_numpy(x[None,...])).cpu().numpy()

def pick(y,hat_t,cym_t):
    pp=PeakPicker(thresholds=[.22,.24,.32,hat_t,cym_t],fps=100)
    out=pp.pick(y,labels=LABELS_5,label_offset=0)[0]
    return sorted(map(float,out.get(42,[]))),sorted(map(float,out.get(49,[])))

def browser_metal(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    return sorted(t-off for t,g,*_ in ev.midi_events(BASE/f"{song}.mid") if g in GROUPS)

def truth(song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    rows=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    return {g:sorted(t+shift for t,gg,*_ in rows if gg==g) for g in GROUPS}

def match(pred,ref,tol=.08):
    pred=sorted(pred);ref=sorted(ref);used=set();tp=0
    for t in pred:
        if not ref:break
        j=int(np.searchsorted(ref,t))
        opts=[k for k in (j-1,j,j+1) if 0<=k<len(ref) and k not in used]
        if not opts:continue
        k=min(opts,key=lambda z:abs(ref[z]-t))
        if abs(ref[k]-t)<=tol:used.add(k);tp+=1
    return tp

def union(*seqs,w=.035):
    xs=sorted(x for s in seqs for x in s);out=[]
    for t in xs:
        if not out or t-out[-1]>w:out.append(t)
    return out

def main():
    m=model();p=create_adtof_processor()
    report={"schema":1,"hatThresholds":HAT_T,"cymbalThresholds":CYM_T,"songs":{}}
    agg=defaultdict(Counter)
    for song in SONGS:
        print("INFER",song,flush=True);y=infer(song,m,p);br=browser_metal(song);tr=truth(song)
        rows={}
        for ht in HAT_T:
          for ct in CYM_T:
            hh,cy=pick(y,ht,ct);hc=union(hh,cy);u=union(hh,cy,br)
            key=f"h{ht:.2f}_c{ct:.2f}"
            row={"hatCandidates":len(hh),"cymCandidates":len(cy),"hcUnion":len(hc),"withBrowser":len(u),"groups":{}}
            for g in GROUPS:
                ref=tr[g]
                row["groups"][g]={
                  "ref":len(ref),
                  "hatRecall":match(hh,ref)/len(ref) if ref else None,
                  "cymRecall":match(cy,ref)/len(ref) if ref else None,
                  "hcRecall":match(hc,ref)/len(ref) if ref else None,
                  "unionRecall":match(u,ref)/len(ref) if ref else None,
                }
                a=agg[key]
                a[f"{g}_ref"]+=len(ref);a[f"{g}_hc"]+=match(hc,ref);a[f"{g}_u"]+=match(u,ref)
            a=agg[key];a["hatCand"]+=len(hh);a["cymCand"]+=len(cy);a["hc"]+=len(hc)
            rows[key]=row
        report["songs"][song]=rows
        # print only most relevant kaiju subset to keep logs manageable
        if song=="kaiju":
            best=sorted(rows.items(),key=lambda kv:(kv[1]["groups"]["ride"]["unionRecall"],-kv[1]["hcUnion"]),reverse=True)[:15]
            print("KAIJU_TOP",json.dumps(best,ensure_ascii=False),flush=True)
    report["aggregate"]={}
    for key,a in agg.items():
        d={"hatCandidates":a["hatCand"],"cymCandidates":a["cymCand"],"hcUnion":a["hc"],"groups":{}}
        for g in GROUPS:
            rr=a[f"{g}_ref"]
            d["groups"][g]={
              "ref":rr,
              "hcRecall":a[f"{g}_hc"]/rr if rr else None,
              "unionRecall":a[f"{g}_u"]/rr if rr else None,
            }
        report["aggregate"][key]=d
    report["ranking"]=sorted(report["aggregate"],key=lambda k:(
        report["aggregate"][k]["groups"]["ride"]["unionRecall"] or 0,
        report["aggregate"][k]["groups"]["crash"]["unionRecall"] or 0,
        -report["aggregate"][k]["hcUnion"]),reverse=True)
    (EXP/"results-adtof-hat-cymbal-coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("TOP",json.dumps([{k:report["aggregate"][k]} for k in report["ranking"][:15]],ensure_ascii=False),flush=True)

if __name__=="__main__":
    from collections import defaultdict
    main()
