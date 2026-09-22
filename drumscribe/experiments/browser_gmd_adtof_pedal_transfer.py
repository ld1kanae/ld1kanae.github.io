"""Evaluate GMD-trained frozen ADTOF embedding model as a pedal-hat supplement.

Production-safe scope:
- current pedal_hat events are preserved exactly;
- no new onset is added;
- only current remaining hat events may become pedal_hat;
- kick/snare/tom/crash/ride are untouched.

The classifier was trained only on external GMD rock/punk audio+MIDI.
DruMaster chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from adtof_pytorch import calculate_n_bins,create_frame_rnn_model,get_default_weights_path,load_pytorch_weights
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
MODEL=json.loads((ROOT/"drumscribe/models/gmd-adtof-metal-logreg.json").read_text())
CLASSES=MODEL["classes"];CI={g:i for i,g in enumerate(CLASSES)}
MEAN=np.asarray(MODEL["mean"],float);SCALE=np.asarray(MODEL["scale"],float)
COEF=np.asarray(MODEL["coef"],float);INTER=np.asarray(MODEL["intercept"],float)

spec=importlib.util.spec_from_file_location("rep",EXP/"browser_gmd_repetition_decoder.py")
rep=importlib.util.module_from_spec(spec);spec.loader.exec_module(rep)

def model():
    n=calculate_n_bins();m=create_frame_rnn_model(n)
    return load_pytorch_weights(m,get_default_weights_path(),strict=False).eval()

def hidden(model,x_np):
    x=torch.from_numpy(x_np[None,...]).float()
    with torch.no_grad():
        B,T,F,C=x.shape;z=x.permute(0,3,1,2)
        for b in model.cnn_blocks:z=b(z)
        z=z.permute(0,2,3,1).reshape(B,T,-1)
        if getattr(model,"context_layer",None) is not None:z=model.context_layer(z)
        for g in model.gru_layers:z,_=g(z)
        a=torch.sigmoid(model.output_layer(z))
    return z[0].cpu().numpy().astype(np.float32),a[0].cpu().numpy().astype(np.float32)

def feat(h,a,fr):
    fr=max(0,min(len(h)-1,fr));lo=max(0,fr-2);hi=min(len(h),fr+3)
    return np.concatenate([h[fr],a[fr],h[lo:hi].mean(0),a[lo:hi].mean(0),a[lo:hi].max(0)])

def sm(z):
    z=z-np.max(z);e=np.exp(z);return e/e.sum()

def prob(f):
    x=(f-MEAN)/np.maximum(SCALE,1e-8);p=sm(COEF@x+INTER)
    return {g:float(p[CI[g]]) for g in CLASSES}

def browser(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in rep.ev.midi_events(BASE/f"{song}.mid")],side

def truth(song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    return [(t+shift,g) for t,g,*_ in rep.ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")]

def prep(song,m,p):
    rows,side=browser(song);a=p.load_audio(str(ROOT/"DruMaster/songs"/song/"drums.mp3"))
    st=p.compute_stft(a);x=p.apply_filterbank(st).T.astype(np.float32)[...,None]
    h,y=hidden(m,x);items={}
    for t,g in rows:
        if g!="hat":continue
        fr=max(0,min(len(h)-1,int(round(t*100))))
        items[round(t,5)]=prob(feat(h,y,fr))
    return {"rows":rows,"items":items,"truth":truth(song)}

def relabel(d,cfg):
    out=[];n=0
    for t,g in d["rows"]:
        if g!="hat":out.append((t,g));continue
        p=d["items"].get(round(t,5))
        if p and p["pedal_hat"]>=cfg["prob"] and p["pedal_hat"]-p["hat"]>=cfg["margin"] and p["pedal_hat"]-p["ride"]>=cfg["rideMargin"]:
            out.append((t,"pedal_hat"));n+=1
        else:out.append((t,g))
    return sorted(out),n

def score(song,pred):return rep.truth_score(song,pred)
def agg(s):return rep.aggregate(s)
def obj(a):
    p=a["by_group"]["pedal_hat"];h=a["by_group"]["hat"]
    return a["f1"]+.12*p["f1"]+.02*h["f1"]-.015*max(0,(p["count_ratio"] or 0)-.7)

def nearest_truth(d,t,tol=.08):
    xs=[(abs(tt-t),g) for tt,g in d["truth"] if g in ("hat","pedal_hat") and abs(tt-t)<=tol]
    return min(xs)[1] if xs else None

def main():
    m=model();p=create_adtof_processor();data={}
    for s in SONGS:
        print("INFER",s,flush=True);data[s]=prep(s,m,p)
    base={s:score(s,data[s]["rows"]) for s in SONGS};bag=agg(base)

    # Transfer diagnostic on current remaining hats.
    diag={};tot=Counter()
    for s,d in data.items():
        c=Counter()
        for t,g in d["rows"]:
            if g!="hat":continue
            gt=nearest_truth(d,t)
            if gt is None:continue
            pp=d["items"][round(t,5)]
            pred=max(("hat","pedal_hat"),key=lambda q:pp[q])
            c[(gt,pred)]+=1
        diag[s]={"|".join(k):v for k,v in c.items()};tot.update(c)

    fixed=[
      {"name":"p80_m20","prob":.80,"margin":.20,"rideMargin":.10},
      {"name":"p90_m30","prob":.90,"margin":.30,"rideMargin":.20},
      {"name":"p95_m40","prob":.95,"margin":.40,"rideMargin":.25},
    ]
    fixedout=[]
    for cfg in fixed:
        scores={};conv={}
        for s in SONGS:
            pred,n=relabel(data[s],cfg);scores[s]=score(s,pred);conv[s]=n
        a=agg(scores);fixedout.append({"config":cfg,"objective":obj(a),"summary":a,"converted":conv,
          "songs":{s:{"f1":scores[s]["f1"],"hat":scores[s]["by_group"]["hat"],"pedal_hat":scores[s]["by_group"]["pedal_hat"]} for s in SONGS}})

    cfgs=[];i=0
    for pr in (.45,.55,.65,.75,.85,.92,.96):
      for ma in (0,.10,.20,.30,.40,.55):
       for rm in (0,.10,.20,.35):
        cfgs.append({"id":i,"prob":pr,"margin":ma,"rideMargin":rm});i+=1
    rows=[];cache={}
    for cfg in cfgs:
        scores={};conv={}
        for s in SONGS:
            pred,n=relabel(data[s],cfg);scores[s]=score(s,pred);conv[s]=n
        a=agg(scores);cache[cfg["id"]]=scores
        eligible=a["f1"]>=bag["f1"]-.002 and a["precision"]>=bag["precision"]-.015
        rows.append({"id":cfg["id"],"eligible":eligible,"objective":obj(a),"config":cfg,"summary":a,"converted":conv})
    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)

    held={};loo={}
    for h in SONGS:
        tr=[s for s in SONGS if s!=h];btr=agg({s:base[s] for s in tr});rank=[]
        for z in rows:
            a=agg({s:cache[z["id"]][s] for s in tr})
            valid=a["f1"]>=btr["f1"]-.002 and a["precision"]>=btr["precision"]-.015
            rank.append((valid,obj(a),a["f1"],z["id"]))
        rank.sort(reverse=True);bid=rank[0][3];z=next(q for q in rows if q["id"]==bid)
        sc=cache[bid][h];held[h]=sc
        loo[h]={"selectedId":bid,"config":z["config"],"heldF1":sc["f1"],
                "hat":sc["by_group"]["hat"],"pedal_hat":sc["by_group"]["pedal_hat"],
                "converted":z["converted"][h]}
    la=agg(held)

    out={"schema":1,"description":"External GMD ADTOF embedding pedal supplement; no new onset; charts scoring-only.",
         "externalValidation":MODEL["training"],"baseline":bag,
         "matchedDiagnostic":{"aggregate":{"|".join(k):v for k,v in tot.items()},"songs":diag},
         "fixed":fixedout,"top":rows[:40],"nestedLOO":{"aggregate":la,"objective":obj(la),"songs":loo}}
    (EXP/"results-browser-gmd-adtof-pedal-transfer.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(bag,ensure_ascii=False),flush=True)
    print("DIAG",json.dumps(out["matchedDiagnostic"],ensure_ascii=False),flush=True)
    print("FIXED",json.dumps(fixedout,ensure_ascii=False),flush=True)
    print("TOP",json.dumps(rows[:8],ensure_ascii=False),flush=True)
    print("LOO",json.dumps(out["nestedLOO"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
