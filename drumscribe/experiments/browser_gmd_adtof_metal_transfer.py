"""Evaluate frozen-GMD ADTOF embedding classifier on current browser metal events.

The classifier was trained only on GMD rock/punk train audio+MIDI and selected
before touching DruMaster charts. This benchmark asks whether it transfers to
the five supplied songs.

Conservative production candidate:
- keep pedal_hat exactly as the current validated browser decoder emits it;
- keep crash exactly as current;
- do not add any new onset;
- only allow hat <-> ride relabeling at an existing browser metal onset;
- require high external-model probability/margin before changing current label.

DruMaster chart.mid is evaluation-only. We report:
1. fixed conservative policies;
2. nested leave-one-song-out threshold selection for diagnostic generalization;
3. raw matched-event classifier accuracy / confusion on the five songs.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from adtof_pytorch import calculate_n_bins,create_frame_rnn_model,get_default_weights_path,load_pytorch_weights
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
MODEL=json.loads((ROOT/"drumscribe/models/gmd-adtof-metal-logreg.json").read_text())
OUTDIR=EXP/"generated-gmd-adtof-metal-transfer"
PITCH_OUT={"kick":36,"snare":38,"hat":42,"pedal_hat":44,"tom":45,"crash":49,"ride":51}
CLASSES=MODEL["classes"];CI={g:i for i,g in enumerate(CLASSES)}
MEAN=np.asarray(MODEL["mean"],float);SCALE=np.asarray(MODEL["scale"],float)
COEF=np.asarray(MODEL["coef"],float);INTER=np.asarray(MODEL["intercept"],float)

spec=importlib.util.spec_from_file_location("rep",EXP/"browser_gmd_repetition_decoder.py")
rep=importlib.util.module_from_spec(spec);spec.loader.exec_module(rep)

def frozen():
    n=calculate_n_bins();m=create_frame_rnn_model(n)
    return load_pytorch_weights(m,get_default_weights_path(),strict=False).eval()

def hidden_and_output(model,x_np):
    x=torch.from_numpy(x_np[None,...]).float()
    with torch.no_grad():
        B,T,F,C=x.shape
        z=x.permute(0,3,1,2)
        for block in model.cnn_blocks:z=block(z)
        z=z.permute(0,2,3,1).reshape(B,T,-1)
        if getattr(model,"context_layer",None) is not None:z=model.context_layer(z)
        for gru in model.gru_layers:z,_=gru(z)
        a=torch.sigmoid(model.output_layer(z))
    return z[0].cpu().numpy().astype(np.float32),a[0].cpu().numpy().astype(np.float32)

def feature(h,a,fr):
    fr=max(0,min(len(h)-1,fr));lo=max(0,fr-2);hi=min(len(h),fr+3)
    return np.concatenate([h[fr],a[fr],h[lo:hi].mean(0),a[lo:hi].mean(0),a[lo:hi].max(0)]).astype(np.float32)

def vlq(n):
    out=[n&127]
    while n>>7:
        n>>=7;out.insert(0,(n&127)|128)
    return bytes(out)

def write_midi(path,pred,bpm):
    ppq=480;tps=ppq*bpm/60;tempo=round(60_000_000/bpm)
    packets=[(0,0,bytes([255,81,3,(tempo>>16)&255,(tempo>>8)&255,tempo&255])),
             (0,0,bytes([255,88,4,4,2,24,8]))]
    for t,g in pred:
        if g not in PITCH_OUT:continue
        tick=max(0,round(t*tps));pitch=PITCH_OUT[g]
        packets += [(tick,2,bytes([0x99,pitch,100])),(tick+max(1,round(.06*tps)),1,bytes([0x89,pitch,0]))]
    packets.sort(key=lambda x:(x[0],x[1],x[2][1] if len(x[2])>1 else 0))
    body=bytearray();prev=0
    for tick,_,data in packets:
        body+=vlq(tick-prev)+data;prev=tick
    body+=bytes([0,255,47,0]);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b"MThd"+(6).to_bytes(4,"big")+bytes([0,0,0,1,1,224])+b"MTrk"+len(body).to_bytes(4,"big")+body)

def score_midi(song,pred,out_path,bpm):
    write_midi(out_path,pred,bpm)
    parsed=[(t,g) for t,g,*_ in rep.ev.midi_events(out_path)]
    return rep.truth_score(song,parsed)

def softmax(z):
    z=z-np.max(z);e=np.exp(z);return e/e.sum()

def prob(f):
    x=(f-MEAN)/np.maximum(SCALE,1e-8)
    p=softmax(COEF@x+INTER)
    return {g:float(p[CI[g]]) for g in CLASSES}

def browser_rows(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in rep.ev.midi_events(BASE/f"{song}.mid")],side

def truth_rows(song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    truth=rep.ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    return [(t+shift,g) for t,g,*_ in truth]

def prepare(song,model,proc):
    rows,side=browser_rows(song)
    audio=proc.load_audio(str(ROOT/"DruMaster/songs"/song/"drums.mp3"))
    st=proc.compute_stft(audio);x=proc.apply_filterbank(st).T.astype(np.float32)[...,None]
    h,a=hidden_and_output(model,x)
    items=[]
    for t,g in rows:
        if g not in ("hat","ride"):continue
        fr=max(0,min(len(h)-1,int(round(t*100))))
        items.append({"time":t,"group":g,"p":prob(feature(h,a,fr))})
    return {"rows":rows,"side":side,"items":items,"truth":truth_rows(song)}

def score(song,pred):return rep.truth_score(song,pred)
def aggregate(scores):return rep.aggregate(scores)

def relabel(d,cfg):
    idx={(round(it["time"],5),it["group"]):it for it in d["items"]}
    out=[];changed=Counter()
    for t,g in d["rows"]:
        if g not in ("hat","ride"):
            out.append((t,g));continue
        it=idx.get((round(t,5),g))
        if it is None:
            out.append((t,g));continue
        p=it["p"];ph=p["hat"];pr=p["ride"]
        if g=="hat":
            if pr>=cfg["rideProb"] and pr-ph>=cfg["rideMargin"]:
                out.append((t,"ride"));changed["hat->ride"]+=1
            else:out.append((t,g))
        else:
            if cfg["allowRideToHat"] and ph>=cfg["hatProb"] and ph-pr>=cfg["hatMargin"]:
                out.append((t,"hat"));changed["ride->hat"]+=1
            else:out.append((t,g))
    return sorted(out),dict(changed)

def objective(ag):
    r=ag["by_group"]["ride"];h=ag["by_group"]["hat"]
    return ag["f1"]+.09*r["f1"]+.02*h["f1"]-.01*max(0,(r["count_ratio"] or 0)-1.0)

def matched_confusion(d,tol=.08):
    # Greedy one-to-one matching for current hat/ride events only.
    truth=sorted((t,g) for t,g in d["truth"] if g in ("hat","ride"))
    used=set();c=Counter();matched=0
    for it in sorted(d["items"],key=lambda z:z["time"]):
        t=it["time"];cand=[]
        for j,(tt,g) in enumerate(truth):
            if j in used:continue
            dt=abs(tt-t)
            if dt<=tol:cand.append((dt,j,g))
        if not cand:continue
        _,j,gt=min(cand);used.add(j);matched+=1
        pred=max(("hat","ride"),key=lambda g:it["p"][g])
        c[(it["group"],gt,pred)]+=1
    return matched,c

def main():
    m=frozen();proc=create_adtof_processor();data={}
    for s in SONGS:
        print("INFER",s,flush=True);data[s]=prepare(s,m,proc)

    baseline_scores={s:score(s,data[s]["rows"]) for s in SONGS};baseline=aggregate(baseline_scores)

    fixed=[
      {"name":"p70_m20_keepRide","rideProb":.70,"rideMargin":.20,"allowRideToHat":False,"hatProb":.90,"hatMargin":.40},
      {"name":"p80_m25_keepRide","rideProb":.80,"rideMargin":.25,"allowRideToHat":False,"hatProb":.90,"hatMargin":.40},
      {"name":"p90_m30_keepRide","rideProb":.90,"rideMargin":.30,"allowRideToHat":False,"hatProb":.90,"hatMargin":.40},
      {"name":"p80_m25_twoWay","rideProb":.80,"rideMargin":.25,"allowRideToHat":True,"hatProb":.90,"hatMargin":.40},
    ]
    fixed_rows=[]
    for cfg in fixed:
        scores={};diag={};name=cfg["name"]
        for s in SONGS:
            pred,ch=relabel(data[s],cfg)
            sc=score_midi(s,pred,OUTDIR/"fixed"/name/f"{s}.mid",float(data[s]["side"]["bpm"]))
            scores[s]=sc;diag[s]=ch
        ag=aggregate(scores)
        fixed_rows.append({"config":cfg,"objective":objective(ag),"summary":ag,"diag":diag,
          "midiDir":str(OUTDIR/"fixed"/name),
          "songs":{s:{"f1":scores[s]["f1"],"hat":scores[s]["by_group"]["hat"],"ride":scores[s]["by_group"]["ride"]} for s in SONGS}})

    configs=[];i=0
    for rp in (.55,.65,.75,.85,.92,.96):
      for rm in (.05,.15,.25,.35,.50):
       for two in (False,True):
        for hp in ((.90,.40),(.95,.50)):
          configs.append({"id":i,"rideProb":rp,"rideMargin":rm,"allowRideToHat":two,"hatProb":hp[0],"hatMargin":hp[1]});i+=1
    rows=[];cache={}
    for cfg in configs:
        scores={};diag={}
        for s in SONGS:
            pred,ch=relabel(data[s],cfg);sc=score(s,pred);scores[s]=sc;diag[s]=ch
        ag=aggregate(scores);cache[cfg["id"]]=scores
        eligible=(ag["f1"]>=baseline["f1"]-.002 and ag["precision"]>=baseline["precision"]-.015)
        rows.append({"id":cfg["id"],"eligible":eligible,"objective":objective(ag),"config":cfg,"summary":ag,"diag":diag})
    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)

    held={};loo={}
    for h in SONGS:
        tr=[s for s in SONGS if s!=h];bag=aggregate({s:baseline_scores[s] for s in tr});rank=[]
        for z in rows:
            ag=aggregate({s:cache[z["id"]][s] for s in tr})
            valid=ag["f1"]>=bag["f1"]-.002 and ag["precision"]>=bag["precision"]-.015
            rank.append((valid,objective(ag),ag["f1"],z["id"]))
        rank.sort(reverse=True);bid=rank[0][3];z=next(x for x in rows if x["id"]==bid)
        pred,ch=relabel(data[h],z["config"])
        sc=score_midi(h,pred,OUTDIR/"nested-loo"/f"{h}.mid",float(data[h]["side"]["bpm"]))
        held[h]=sc
        loo[h]={"selectedId":bid,"config":z["config"],"heldF1":sc["f1"],
                "hat":sc["by_group"]["hat"],"ride":sc["by_group"]["ride"],"diag":ch}
    loo_ag=aggregate(held)

    mc={};tot=Counter();n=0
    for s in SONGS:
        nn,c=matched_confusion(data[s]);mc[s]={"matched":nn,"counts":{"|".join(k):v for k,v in c.items()}}
        n+=nn;tot.update(c)
    raw={"matched":n,"counts":{"|".join(k):v for k,v in tot.items()}}

    out={"schema":1,
      "description":"GMD-only frozen ADTOF embedding transfer; existing hat/ride relabel only; charts scoring-only.",
      "externalValidation":MODEL["training"],
      "baseline":baseline,
      "generatedMidiRoot":str(OUTDIR),
      "fixed":fixed_rows,
      "top":rows[:40],
      "nestedLOO":{"aggregate":loo_ag,"objective":objective(loo_ag),"songs":loo},
      "matchedDiagnostic":{"aggregate":raw,"songs":mc}}
    (EXP/"results-browser-gmd-adtof-metal-transfer.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    print("FIXED",json.dumps(fixed_rows,ensure_ascii=False),flush=True)
    print("TOP",json.dumps(rows[:8],ensure_ascii=False),flush=True)
    print("LOO",json.dumps(out["nestedLOO"],ensure_ascii=False),flush=True)
    print("MATCH",json.dumps(raw,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
