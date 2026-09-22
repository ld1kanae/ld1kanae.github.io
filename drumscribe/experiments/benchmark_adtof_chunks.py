"""Benchmark overlap-chunked ADTOF ONNX inference against full inference.

This determines a browser-safe chunk size for the bidirectional GRU. The full
ONNX output is the reference; no chart.mid or song metadata is used.

For ray and nanairo, use the first 90 s of audio and compare:
- activation MAE / p99 / max
- event-level agreement after the official ADTOF PeakPicker
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnxruntime as ort

from adtof_pytorch import PeakPicker, FRAME_RNN_THRESHOLDS, LABELS_5
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"
MODEL=ROOT/"drumscribe/models/adtof-frame-rnn.onnx"
SONGS=["ray","nanairo"]
MAP={35:"kick",38:"snare",47:"tom",42:"hat",49:"cymbal"}


def frontend(song,seconds=90):
    p=create_adtof_processor()
    a=p.load_audio(str(ROOT/"DruMaster/songs"/song/"drums.mp3"))
    a=a[:int(seconds*p.sample_rate)]
    s=p.compute_stft(a)
    x=p.apply_filterbank(s).T.astype(np.float32)[...,None]
    return x[None,...]


def infer(sess,x):
    return sess.run(["activations"],{"input":x})[0]


def infer_chunked(sess,x,core,overlap):
    T=x.shape[1]
    y=np.zeros((1,T,5),dtype=np.float32)
    coverage=np.zeros(T,dtype=np.int16)
    for a in range(0,T,core):
        b=min(T,a+core)
        sa=max(0,a-overlap)
        sb=min(T,b+overlap)
        yy=infer(sess,x[:,sa:sb])
        ka=a-sa
        kb=ka+(b-a)
        y[:,a:b]=yy[:,ka:kb]
        coverage[a:b]+=1
    assert np.all(coverage==1)
    return y


def peak_dict(y):
    picker=PeakPicker(thresholds=FRAME_RNN_THRESHOLDS,fps=100)
    p=picker.pick(y,labels=LABELS_5,label_offset=0)[0]
    return {MAP[int(k)]:np.asarray(v,float) for k,v in p.items()}


def event_agreement(a,b,tol=.02):
    out={}
    for g in MAP.values():
        aa=list(a.get(g,[]));bb=list(b.get(g,[]))
        used=set();tp=0
        for t in aa:
            opts=[i for i,x in enumerate(bb) if i not in used and abs(x-t)<=tol]
            if opts:
                i=min(opts,key=lambda i:abs(bb[i]-t));used.add(i);tp+=1
        out[g]={
          "full":len(aa),"chunked":len(bb),"matched":tp,
          "precision":tp/len(bb) if len(bb) else 0,
          "recall":tp/len(aa) if len(aa) else 0,
          "f1":2*tp/(len(aa)+len(bb)) if len(aa)+len(bb) else 1,
        }
    return out


def main():
    sess=ort.InferenceSession(str(MODEL),providers=["CPUExecutionProvider"])
    configs=[
      (800,50),(800,100),(800,200),
      (1200,100),(1200,200),(1200,300),
      (2000,100),(2000,200),(2000,400),
      (3000,200),(3000,400),
    ]
    report={"schema":1,"seconds":90,"songs":{},"aggregate":{}}
    agg={c:[] for c in configs}
    for song in SONGS:
        print("FRONTEND",song,flush=True)
        x=frontend(song)
        print("FULL",song,x.shape,flush=True)
        full=infer(sess,x)
        fp=peak_dict(full)
        rows={}
        for core,ov in configs:
            print("CHUNK",song,core,ov,flush=True)
            y=infer_chunked(sess,x,core,ov)
            d=np.abs(full-y)
            agree=event_agreement(fp,peak_dict(y))
            mean_event_f1=float(np.mean([v["f1"] for v in agree.values()]))
            row={
              "coreFrames":core,"overlapFrames":ov,
              "coreSeconds":core/100,"overlapSeconds":ov/100,
              "mae":float(d.mean()),"p99":float(np.percentile(d,99)),
              "maxAbs":float(d.max()),
              "meanEventF1":mean_event_f1,
              "events":agree,
            }
            rows[f"c{core}_o{ov}"]=row
            agg[(core,ov)].append(row)
        report["songs"][song]={"frames":int(x.shape[1]),"configs":rows}

    for core,ov in configs:
        rs=agg[(core,ov)]
        report["aggregate"][f"c{core}_o{ov}"]={
          "coreFrames":core,"overlapFrames":ov,
          "meanMae":float(np.mean([r["mae"] for r in rs])),
          "maxP99":float(np.max([r["p99"] for r in rs])),
          "maxAbs":float(np.max([r["maxAbs"] for r in rs])),
          "meanEventF1":float(np.mean([r["meanEventF1"] for r in rs])),
          "worstClassF1":float(min(v["f1"] for r in rs for v in r["events"].values())),
        }
    ranking=sorted(report["aggregate"].items(),key=lambda kv:(kv[1]["meanEventF1"],kv[1]["worstClassF1"],-kv[1]["overlapFrames"]),reverse=True)
    report["ranking"]=[k for k,_ in ranking]
    (EXP/"results-adtof-chunk-benchmark.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"ranking":report["ranking"],"aggregate":report["aggregate"]},indent=2))


if __name__=="__main__":
    main()
