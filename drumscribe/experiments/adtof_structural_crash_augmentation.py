"""Targeted structural crash augmentation from low-threshold ADTOF cymbal peaks.

Prediction-only features:
- low-threshold ADTOF generic cymbal activation
- browser-estimated BPM/bar phase
- current kick/snare/tom/crash/ride/hat events
- preceding one-beat fill density
- distance to detected bar head

Only candidates near a bar head are considered. Existing metal hits are
preserved. The candidate must satisfy a fixed structural rule (head, kick,
fill, or combinations). chart.mid is scoring-only; nested LOO selects the
fixed policy without held-song leakage.
"""
from __future__ import annotations
import importlib.util,json,math,bisect
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from adtof_pytorch import calculate_n_bins,create_frame_rnn_model,get_default_weights_path,load_pytorch_weights,PeakPicker,LABELS_5
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
CYM_T=.04

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
    pp=PeakPicker(thresholds=[.22,.24,.32,.22,CYM_T],fps=100)
    d=pp.pick(y,labels=LABELS_5,label_offset=0)[0]
    return sorted(map(float,d.get(49,[])))

def browser(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")],side

def near(xs,t,w):
    if not xs:return False
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def score(song,pred):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    return ev.score([(t,g,0,0) for t,g in pred],ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid"),shift)

def prepare(song,y):
    rr,side=browser(song);bpm=float(side["bpm"]);phase=float(side["barPhaseSec"]);beat=60/bpm;bar=4*beat
    by={g:sorted(t for t,gg in rr if gg==g) for g in ev.ORDER}
    cands=[]
    for t in pick(y):
        fr=max(0,min(y.shape[1]-1,int(round(t*100))))
        x=(t-phase)%bar;head=min(x,bar-x)/beat
        a=t-beat
        tom=sum(a<=v<t for v in by["tom"]);sn=sum(a<=v<t for v in by["snare"])
        cands.append({"t":t,"act":float(y[0,fr,4]),"head":head,
                      "kick":near(by["kick"],t,.07),"tomFill":tom,"snareFill":sn,
                      "nearMetal":near(sorted(by["hat"]+by["pedal_hat"]+by["ride"]+by["crash"]),t,.055),
                      "nearCrash":near(by["crash"],t,.10)})
    return {"rows":rr,"side":side,"by":by,"beat":beat,"bar":bar,"phase":phase,"candidates":cands}

def keep(c,cfg):
    if c["head"]>cfg["head"]:return False
    if c["act"]<cfg["activation"]:return False
    if c["nearCrash"]:return False
    fill=c["tomFill"]>=cfg["tomFill"] or c["snareFill"]>=cfg["snareFill"]
    if cfg["mode"]=="head":return True
    if cfg["mode"]=="kick":return c["kick"]
    if cfg["mode"]=="fill":return fill
    if cfg["mode"]=="kick_or_fill":return c["kick"] or fill
    if cfg["mode"]=="kick_and_fill":return c["kick"] and fill
    return False

def build(d,cfg):
    out=list(d["rows"]);adds=[];metal=sorted(t for t,g in out if g in ("hat","pedal_hat","ride","crash"))
    for c in d["candidates"]:
        if not keep(c,cfg):continue
        t=c["t"]
        if near(metal,t,cfg["metalWindow"]):
            # allow replacing a current hat at the same structural crash onset
            hats=[(i,x) for i,(x,g) in enumerate(out) if g=="hat" and abs(x-t)<=cfg["metalWindow"]]
            if cfg["reclassHat"] and hats:
                i,x=min(hats,key=lambda z:abs(z[1]-t));out[i]=(x,"crash");adds.append(("hat->crash",x));metal.append(x);metal.sort()
            continue
        out.append((t,"crash"));adds.append(("add",t));metal.append(t);metal.sort()
    # de-dup crashes
    final=[]
    for g in ev.ORDER:
        xs=sorted(t for t,gg in out if gg==g);last=-999.;mind=.055 if g=="crash" else .035
        for t in xs:
            if t-last>=mind:final.append((t,g));last=t
    return sorted(final),Counter(k for k,t in adds)

def aggregate(scores):
    tot=Counter()
    for sc in scores.values():
        tot.update(tp=sc["tp"],pred=sc["predicted"],ref=sc["reference"])
        for g,z in sc["by_group"].items():tot.update({f"{g}_tp":z["tp"],f"{g}_p":z["predicted"],f"{g}_r":z["reference"]})
    o={"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
       "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],"f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),"by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_p"],tot[f"{g}_r"]
        o["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    return o

def objective(s):
    c=s["by_group"]["crash"];return s["f1"]+.09*c["f1"]+.015*min(1,c["precision"])

def main():
    m=model();p=create_adtof_processor();data={}
    for s in SONGS:
        print("INFER",s,flush=True);data[s]=prepare(s,infer(s,m,p))
    base={s:score(s,data[s]["rows"]) for s in SONGS};baseag=aggregate(base)
    cfgs=[];i=0
    for head in (.06,.10,.16,.22,.30):
     for act in (.04,.06,.08,.12,.18):
      for mode in ("head","kick","fill","kick_or_fill","kick_and_fill"):
       for tf in (1,2,3):
        for sf in (1,2,3):
         for re in (False,True):
          cfgs.append({"id":i,"head":head,"activation":act,"mode":mode,"tomFill":tf,"snareFill":sf,
                       "metalWindow":.055,"reclassHat":re});i+=1
    rows=[];cache={}
    for j,cfg in enumerate(cfgs):
        scores={};diag={}
        for s in SONGS:
            pred,dg=build(data[s],cfg);sc=score(s,pred);scores[s]=sc;diag[s]=dict(dg)
        ag=aggregate(scores);cache[cfg["id"]]=scores
        cr=ag["by_group"]["crash"]
        eligible=(ag["f1"]>=baseag["f1"]-.002 and cr["precision"]>=.58)
        rows.append({"id":cfg["id"],"eligible":eligible,"objective":objective(ag),"config":cfg,
                     "summary":ag,"diag":diag,
                     "songs":{s:{"f1":scores[s]["f1"],"crash":scores[s]["by_group"]["crash"]} for s in SONGS}})
        if j%500==0:print("CFG",j,len(cfgs),ag["f1"],flush=True)
    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)

    held={};loo={}
    for h in SONGS:
        tr=[s for s in SONGS if s!=h];btr=aggregate({s:base[s] for s in tr});rank=[]
        for z in rows:
            ag=aggregate({s:cache[z["id"]][s] for s in tr});cr=ag["by_group"]["crash"]
            valid=ag["f1"]>=btr["f1"]-.002 and cr["precision"]>=.58
            rank.append((valid,objective(ag),ag["f1"],z["id"]))
        rank.sort(reverse=True);bid=rank[0][3];z=next(x for x in rows if x["id"]==bid)
        sc=cache[bid][h];held[h]=sc
        loo[h]={"selectedId":bid,"config":z["config"],"heldF1":sc["f1"],"crash":sc["by_group"]["crash"],"diag":z["diag"][h]}
    lag=aggregate(held)
    out={"schema":1,"description":"Targeted structural crash augmentation; chart scoring-only.",
         "baseline":baseag,"top":rows[:60],"nestedLOO":{"aggregate":lag,"objective":objective(lag),"songs":loo}}
    (EXP/"results-adtof-structural-crash-augmentation.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseag,ensure_ascii=False),flush=True)
    print("TOP",json.dumps(rows[:12],ensure_ascii=False),flush=True)
    print("LOO",json.dumps(out["nestedLOO"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
