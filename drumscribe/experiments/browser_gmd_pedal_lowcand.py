"""Extend the validated GMD pedal decoder to low-threshold ADTOF hat candidates.

The current browser pedal decoder only reclassifies already-emitted browser
hats. ADTOF at low hat threshold has much higher oracle onset coverage for
pedal-hat. This benchmark keeps the already validated pedal score formula
fixed and varies only:
- ADTOF hat candidate threshold,
- pedal score threshold,
- add/reclass policy.

Fixed pedal score (same as current browser):
  1.5 * log(P_GMD(pedal)/P_GMD(hat))
  - .35 * tail2 - .35 * tail3 - .25 * near8

Prediction inputs are audio, current browser output, browser BPM/bar phase, and
the external GMD train-split prior. DruMaster chart.mid is scoring-only.
Nested LOO selects only the extension thresholds/policy.
"""
from __future__ import annotations
import bisect,importlib.util,json,math
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from adtof_pytorch import calculate_n_bins,create_frame_rnn_model,get_default_weights_path,load_pytorch_weights,PeakPicker,LABELS_5
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GMD=json.loads((ROOT/"drumscribe/models/gmd-metal-prior.json").read_text())

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
dec=loadmod("dec",EXP/"browser_cymbal_decay_search.py")

def near(xs,t,w):
    if not xs:return False
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def model():
    n=calculate_n_bins();m=create_frame_rnn_model(n)
    return load_pytorch_weights(m,get_default_weights_path(),strict=False).eval()

def infer(song,m,p):
    a=p.load_audio(str(ROOT/"DruMaster/songs"/song/"drums.mp3"))
    st=p.compute_stft(a);x=p.apply_filterbank(st).T.astype(np.float32)[...,None]
    with torch.no_grad():return m(torch.from_numpy(x[None,...])).cpu().numpy()

def pick_hat(y,thr):
    pp=PeakPicker(thresholds=[.22,.24,.32,thr,.30],fps=100)
    d=pp.pick(y,labels=LABELS_5,label_offset=0)[0]
    return sorted(map(float,d.get(42,[])))

def browser_rows(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")],side

def slot16(t,bpm,phase):
    beat=60/bpm;bar=4*beat;x=(t-phase)%bar
    return int(round(x/(beat/4)))%16

def prepare(song,y):
    rows,side=browser_rows(song);bpm=float(side["bpm"]);phase=float(side["barPhaseSec"]);beat=60/bpm
    audio=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3");sp=ev.spectrum(audio)
    by={g:sorted(t for t,gg in rows if gg==g) for g in ev.ORDER}
    return {"song":song,"rows":rows,"side":side,"bpm":bpm,"phase":phase,"beat":beat,"sp":sp,"by":by,"y":y}

def feature_candidates(d,hat_thr):
    times=pick_hat(d["y"],hat_thr);out=[]
    kicks=d["by"]["kick"];snares=d["by"]["snare"];toms=d["by"]["tom"]
    for t in times:
        sl=slot16(t,d["bpm"],d["phase"]);ctx=[]
        if near(kicks,t,.045):ctx.append("kick")
        if near(snares,t,.045):ctx.append("snare")
        if near(toms,t,.045):ctx.append("tom")
        ck="+".join(ctx) if ctx else "none"
        prior=GMD["context"].get(f"{sl}|{ck}") or GMD["slot16"].get(str(sl)) or GMD["globalProb"]
        ph=max(1e-6,float(prior.get("hat",1e-6)));pp=max(1e-6,float(prior.get("pedal_hat",1e-6)))
        e=dec.env_features(d["sp"],t)
        others=[x for x in times if abs(x-t)>.035]
        near8=near(others,t-d["beat"]/2,.055) or near(others,t+d["beat"]/2,.055)
        score=1.5*math.log(pp/ph)-.35*min(e["tail2"],3)-.35*min(e["tail3"],3)-.25*(1 if near8 else 0)
        fr=max(0,min(d["y"].shape[1]-1,int(round(t*100))))
        out.append({"t":t,"score":score,"activation":float(d["y"][0,fr,3]),"slot":sl,"ctx":ck,
                    "tail2":float(e["tail2"]),"tail3":float(e["tail3"]),"near8":bool(near8)})
    return out

def enforce(rows):
    # only de-duplicate pedal events; preserve all other browser events exactly.
    other=[x for x in rows if x[1]!="pedal_hat"]
    ped=sorted(t for t,g in rows if g=="pedal_hat");keep=[];last=-999.
    for t in ped:
        if t-last>=.05:keep.append(t);last=t
    return sorted(other+[(t,"pedal_hat") for t in keep])

def build(d,cfg,cache):
    cands=cache[cfg["hatThr"]];out=list(d["rows"]);diag=Counter()
    current_ped=sorted(t for t,g in out if g=="pedal_hat")
    for c in cands:
        if c["score"]<cfg["scoreThr"]:continue
        t=c["t"]
        if near(current_ped,t,.045):continue
        hats=[(i,x) for i,(x,g) in enumerate(out) if g=="hat" and abs(x-t)<=cfg["hatWindow"]]
        if hats:
            if cfg["mode"] in ("reclass","both"):
                i,x=min(hats,key=lambda z:abs(z[1]-t))
                out[i]=(x,"pedal_hat");current_ped.append(x);current_ped.sort();diag["hat->pedal"]+=1
            continue
        if cfg["mode"] in ("add","both"):
            # Avoid adding on top of another current pedal only; pedal can
            # legitimately coincide with kick/snare/crash/ride.
            out.append((t,"pedal_hat"));current_ped.append(t);current_ped.sort();diag["add"]+=1
    return enforce(out),dict(diag)

def score(song,pred):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    return ev.score([(t,g,0,0) for t,g in pred],ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid"),shift)

def aggregate(scores):
    tot=Counter()
    for sc in scores.values():
        tot.update(tp=sc["tp"],pred=sc["predicted"],ref=sc["reference"])
        for g,z in sc["by_group"].items():tot.update({f"{g}_tp":z["tp"],f"{g}_p":z["predicted"],f"{g}_r":z["reference"]})
    out={"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
         "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],"f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),"by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_p"],tot[f"{g}_r"]
        out["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,
          "recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    return out

def objective(a):
    p=a["by_group"]["pedal_hat"];h=a["by_group"]["hat"]
    return a["f1"]+.10*p["f1"]+.015*h["f1"]-.015*max(0,(p["count_ratio"] or 0)-1.05)

def main():
    m=model();proc=create_adtof_processor();data={}
    for s in SONGS:
        print("INFER",s,flush=True);data[s]=prepare(s,infer(s,m,proc))
    cand={s:{thr:feature_candidates(data[s],thr) for thr in (.04,.06,.08,.10,.14,.18)} for s in SONGS}
    base={s:score(s,data[s]["rows"]) for s in SONGS};bag=aggregate(base)

    fixed=[]
    for cfg in [
      {"name":"h08_s08_both","hatThr":.08,"scoreThr":.8,"mode":"both","hatWindow":.045},
      {"name":"h10_s10_both","hatThr":.10,"scoreThr":1.0,"mode":"both","hatWindow":.045},
      {"name":"h14_s12_both","hatThr":.14,"scoreThr":1.2,"mode":"both","hatWindow":.045},
      {"name":"h10_s10_add","hatThr":.10,"scoreThr":1.0,"mode":"add","hatWindow":.045},
    ]:
        scores={};diag={}
        for s in SONGS:
            pred,dg=build(data[s],cfg,cand[s]);scores[s]=score(s,pred);diag[s]=dg
        a=aggregate(scores);fixed.append({"config":cfg,"objective":objective(a),"summary":a,"diag":diag})

    cfgs=[];i=0
    for ht in (.04,.06,.08,.10,.14,.18):
      for st in (.4,.6,.8,1.0,1.2,1.5,1.8,2.2):
       for mode in ("add","reclass","both"):
        cfgs.append({"id":i,"hatThr":ht,"scoreThr":st,"mode":mode,"hatWindow":.045});i+=1
    rows=[];cache={}
    for cfg in cfgs:
        scores={};diag={}
        for s in SONGS:
            pred,dg=build(data[s],cfg,cand[s]);scores[s]=score(s,pred);diag[s]=dg
        a=aggregate(scores);cache[cfg["id"]]=scores
        p=a["by_group"]["pedal_hat"]
        eligible=(a["f1"]>=bag["f1"]-.002 and a["precision"]>=bag["precision"]-.025 and p["precision"]>=.48)
        rows.append({"id":cfg["id"],"eligible":eligible,"objective":objective(a),"config":cfg,"summary":a,"diag":diag})
    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)

    held={};loo={}
    for h in SONGS:
        tr=[s for s in SONGS if s!=h];btr=aggregate({s:base[s] for s in tr});rank=[]
        for z in rows:
            a=aggregate({s:cache[z["id"]][s] for s in tr});p=a["by_group"]["pedal_hat"]
            valid=(a["f1"]>=btr["f1"]-.002 and a["precision"]>=btr["precision"]-.025 and p["precision"]>=.48)
            rank.append((valid,objective(a),a["f1"],z["id"]))
        rank.sort(reverse=True);bid=rank[0][3];z=next(q for q in rows if q["id"]==bid)
        sc=cache[bid][h];held[h]=sc
        loo[h]={"selectedId":bid,"config":z["config"],"heldF1":sc["f1"],
                "pedal_hat":sc["by_group"]["pedal_hat"],"hat":sc["by_group"]["hat"],"diag":z["diag"][h]}
    la=aggregate(held)
    out={"schema":1,"description":"Low-threshold ADTOF pedal candidate extension with fixed current GMD/decay score; charts scoring-only.",
         "baseline":bag,"fixed":fixed,"top":rows[:50],
         "nestedLOO":{"aggregate":la,"objective":objective(la),"songs":loo},
         "candidateCounts":{s:{str(k):len(v) for k,v in cand[s].items()} for s in SONGS}}
    (EXP/"results-browser-gmd-pedal-lowcand.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(bag,ensure_ascii=False),flush=True)
    print("FIXED",json.dumps(fixed,ensure_ascii=False),flush=True)
    print("TOP",json.dumps(rows[:10],ensure_ascii=False),flush=True)
    print("LOO",json.dumps(out["nestedLOO"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
