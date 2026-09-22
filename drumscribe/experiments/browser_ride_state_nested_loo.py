"""Nested-LOO ride recovery from low-threshold ADTOF hat+cymbal candidates.

Motivation:
- current browser ride recall is low;
- ADTOF hat+cymbal union covers many missed ride onsets, especially kaiju;
- many true rides appear in the ADTOF *hat* stream, so cymbal-only recovery is
  structurally insufficient.

For each held song:
1. infer low-threshold ADTOF hat/cymbal activations for all songs;
2. build candidate-slot features from audio/current browser output only;
3. train a ride-vs-nonride logistic classifier on the OTHER FOUR supplied
   chart.mid files;
4. choose add/reclass thresholds by inner leave-one-song-out on those four;
5. predict the held song;
6. only then score against its chart.mid.

The held chart is never used for training, threshold selection, normalization,
or feature design at runtime.
"""
from __future__ import annotations
import bisect,importlib.util,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from adtof_pytorch import (
    calculate_n_bins,create_frame_rnn_model,get_default_weights_path,
    load_pytorch_weights,PeakPicker,LABELS_5
)
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
HAT_THR=.04;CYM_THR=.04

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def model():
    n=calculate_n_bins();m=create_frame_rnn_model(n)
    return load_pytorch_weights(m,get_default_weights_path(),strict=False).eval()

def infer(song,m,p):
    a=p.load_audio(str(ROOT/"DruMaster/songs"/song/"drums.mp3"))
    st=p.compute_stft(a);x=p.apply_filterbank(st).T.astype(np.float32)[...,None]
    with torch.no_grad():return m(torch.from_numpy(x[None,...])).cpu().numpy()

def pick(y):
    pp=PeakPicker(thresholds=[.22,.24,.32,HAT_THR,CYM_THR],fps=100)
    d=pp.pick(y,labels=LABELS_5,label_offset=0)[0]
    return sorted(map(float,d.get(42,[]))),sorted(map(float,d.get(49,[])))

def browser_rows(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")],side

def near(xs,t,w):
    if not xs:return False
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def match(pred,truth,tol=.08):
    pred=sorted(pred);truth=sorted(truth);used=set();tp=0
    for x in pred:
        j=bisect.bisect_left(truth,x)
        opts=[k for k in (j-1,j,j+1) if 0<=k<len(truth) and k not in used]
        if not opts:continue
        k=min(opts,key=lambda q:abs(x-truth[q]))
        if abs(x-truth[k])<=tol:used.add(k);tp+=1
    return tp

def truth_by(song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    return {g:sorted(t+shift for t,gg,*_ in truth if gg==g) for g in ev.ORDER}

def periodic(xs,t,step,w=.055):
    if len(xs)<3:return 0.
    best=0
    for mul in (1,2,4):
        s=step*mul
        n=sum(near(xs,t+k*s,w) for k in (-2,-1,1,2))
        best=max(best,n)
    return best/4

def qslot(t,phase,step):return int(round((t-phase)/step))

def prepare(song,y):
    rows,side=browser_rows(song);bpm=float(side["bpm"]);phase=float(side["barPhaseSec"])
    beat=60/bpm;step=beat/4;bar=4*beat
    hh,cy=pick(y)
    current={g:sorted(t for t,gg in rows if gg==g) for g in ev.ORDER}
    # merge low-threshold ADTOF candidate events by 16th slot
    slots={}
    def add(t,kind):
        s=qslot(t,phase,step);fr=max(0,min(y.shape[1]-1,int(round(t*100))))
        x=slots.setdefault(s,{"times":[],"hatAct":0.,"cymAct":0.})
        x["times"].append(t)
        if kind=="hat":x["hatAct"]=max(x["hatAct"],float(y[0,fr,3]))
        else:x["cymAct"]=max(x["cymAct"],float(y[0,fr,4]))
    for t in hh:add(t,"hat")
    for t in cy:add(t,"cym")
    # ensure every existing current metal event is represented
    for g in ("hat","ride","crash"):
        for t in current[g]:add(t,"hat" if g=="hat" else "cym")

    times=sorted(np.median(x["times"]) for x in slots.values())
    # bar aggregate features computed without truth
    bars=defaultdict(lambda:Counter())
    for s,x in slots.items():
        b=math.floor(s/16)
        bars[b]["cand"]+=1
        bars[b]["hatAct"]+=x["hatAct"];bars[b]["cymAct"]+=x["cymAct"]
    for g in ("hat","ride","crash","kick","snare","tom"):
        for t in current[g]:
            b=math.floor(qslot(t,phase,step)/16);bars[b][g]+=1

    feat=[];meta=[]
    for s,x in sorted(slots.items()):
        t=float(np.median(x["times"]));pos=s%16;b=math.floor(s/16);bc=bars[b]
        curhat=near(current["hat"],t,.045);curri=near(current["ride"],t,.045);curcr=near(current["crash"],t,.045)
        curped=near(current["pedal_hat"],t,.045)
        ctxk=near(current["kick"],t,.055);ctxs=near(current["snare"],t,.055);ctxt=near(current["tom"],t,.055)
        p=periodic(times,t,step)
        v=[
          x["hatAct"],x["cymAct"],x["cymAct"]-x["hatAct"],
          math.log((x["cymAct"]+.02)/(x["hatAct"]+.02)),
          float(curhat),float(curri),float(curcr),float(curped),
          float(ctxk),float(ctxs),float(ctxt),
          p,
          math.sin(2*math.pi*pos/16),math.cos(2*math.pi*pos/16),
          min(2.,bc["cand"]/16),min(2.,bc["hat"]/8),min(2.,bc["ride"]/8),min(2.,bc["crash"]/4),
          min(2.,bc["kick"]/8),min(2.,bc["snare"]/8),min(2.,bc["tom"]/8),
          bc["cymAct"]/max(1,bc["cand"]),bc["hatAct"]/max(1,bc["cand"]),
        ]
        feat.append(v);meta.append({"time":t,"slot":s,"currentHat":curhat,"currentRide":curri,"currentCrash":curcr,"currentPedal":curped})
    return {"song":song,"rows":rows,"current":current,"side":side,"bpm":bpm,"phase":phase,"step":step,
            "X":np.asarray(feat,float),"meta":meta,"truth":truth_by(song)}

def labels(d):
    y=[]
    for m in d["meta"]:
        t=m["time"];y.append(1 if near(d["truth"]["ride"],t,.08) else 0)
    return np.asarray(y,int)

def train_model(data,songs,C=1.0):
    X=np.concatenate([data[s]["X"] for s in songs]);y=np.concatenate([labels(data[s]) for s in songs])
    scaler=StandardScaler().fit(X);Xs=scaler.transform(X)
    clf=LogisticRegression(C=C,class_weight="balanced",max_iter=2000,solver="liblinear").fit(Xs,y)
    return scaler,clf

def probs(model,d):
    sc,clf=model
    return clf.predict_proba(sc.transform(d["X"]))[:,1]

def predict(d,p,add_thr,reclass_thr,veto_thr):
    # Start with current browser output. Pedal is fixed. Existing ride can be
    # removed only under very low ride probability; hats may be reclassified;
    # candidate-only slots may add ride at the stricter threshold.
    out=[]
    ride_times=[]
    # classify candidate metadata by nearest current event
    for row in d["rows"]:
        t,g=row
        if g=="ride":
            j=min(range(len(d["meta"])),key=lambda i:abs(d["meta"][i]["time"]-t)) if len(d["meta"]) else None
            if j is not None and abs(d["meta"][j]["time"]-t)<=.06 and p[j]<veto_thr:
                continue
            ride_times.append(t);out.append(row)
        elif g=="hat":
            j=min(range(len(d["meta"])),key=lambda i:abs(d["meta"][i]["time"]-t)) if len(d["meta"]) else None
            if j is not None and abs(d["meta"][j]["time"]-t)<=.06 and p[j]>=reclass_thr:
                out.append((t,"ride"));ride_times.append(t)
            else:out.append(row)
        else:out.append(row)
    metal_now=sorted(t for t,g in out if g in ("hat","pedal_hat","ride","crash"))
    for i,m in enumerate(d["meta"]):
        t=m["time"]
        if p[i]<add_thr:continue
        if near(metal_now,t,.045):continue
        out.append((t,"ride"));ride_times.append(t);metal_now.append(t);metal_now.sort()
    out.sort()
    return out

def score(song,pred):
    dtruth=truth_by(song)
    st={};tp=pr=rf=0
    for g in ev.ORDER:
        pp=sorted(t for t,gg in pred if gg==g);tt=dtruth[g];a=match(pp,tt)
        st[g]={"tp":a,"predicted":len(pp),"reference":len(tt)}
        tp+=a;pr+=len(pp);rf+=len(tt)
    return {"tp":tp,"predicted":pr,"reference":rf,"f1":2*tp/(pr+rf),"by_group":st}

def aggregate(scores):
    tot=Counter()
    for sc in scores.values():
        tot.update(tp=sc["tp"],pred=sc["predicted"],ref=sc["reference"])
        for g,x in sc["by_group"].items():tot.update({f"{g}_tp":x["tp"],f"{g}_p":x["predicted"],f"{g}_r":x["reference"]})
    o={"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
       "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],
       "f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),"by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_p"],tot[f"{g}_r"]
        o["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,
          "recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    return o

def objective(ag):
    r=ag["by_group"]["ride"];h=ag["by_group"]["hat"];c=ag["by_group"]["crash"]
    return ag["f1"]+.10*r["f1"]+.015*h["f1"]+.01*c["f1"]-.02*max(0,(r["count_ratio"] or 0)-1.0)

def select_inner(data,train_s,C):
    # Train once on all outer-training songs, but choose thresholds by
    # leave-one-song-out predictions inside that set.
    combos=[]
    for add in (.55,.65,.75,.85,.92):
      for re in (.45,.55,.65,.75,.85):
       for veto in (.02,.05,.10,.18):
        if add<re:continue
        held={}
        for v in train_s:
            tr=[s for s in train_s if s!=v]
            if not tr:continue
            m=train_model(data,tr,C);p=probs(m,data[v]);held[v]=score(v,predict(data[v],p,add,re,veto))
        ag=aggregate(held)
        combos.append((objective(ag),ag["f1"],add,re,veto,ag))
    combos.sort(reverse=True)
    return combos[0]

def main():
    m=model();proc=create_adtof_processor();data={}
    for s in SONGS:
        print("INFER",s,flush=True);data[s]=prepare(s,infer(s,m,proc))
    baseline={s:score(s,data[s]["rows"]) for s in SONGS};baseag=aggregate(baseline)

    held={};details={}
    for h in SONGS:
        tr=[s for s in SONGS if s!=h]
        choices=[]
        for C in (.15,.4,1.0,2.5):
            inn=select_inner(data,tr,C);choices.append((inn[0],inn[1],C,inn))
        choices.sort(reverse=True);_,_,C,best=choices[0]
        _,innerf,add,re,veto,innerag=best
        mod=train_model(data,tr,C);p=probs(mod,data[h]);pred=predict(data[h],p,add,re,veto);sc=score(h,pred);held[h]=sc
        details[h]={"C":C,"addThr":add,"reclassThr":re,"vetoThr":veto,"innerF1":innerf,
          "inner":innerag,"heldF1":sc["f1"],"ride":sc["by_group"]["ride"],"hat":sc["by_group"]["hat"],
          "probQ":[float(np.quantile(p,q)) for q in (.5,.75,.9,.95,.99)]}
        print("HELD",h,json.dumps(details[h],ensure_ascii=False),flush=True)
    ag=aggregate(held)
    out={"schema":1,"description":"Nested LOO ride recovery from low-threshold ADTOF hat+cymbal candidates and bar context.",
      "baseline":baseag,"nestedLOO":{"aggregate":ag,"objective":objective(ag),"songs":details}}
    (EXP/"results-browser-ride-state-nested-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseag,ensure_ascii=False),flush=True)
    print("LOO",json.dumps(out["nestedLOO"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
