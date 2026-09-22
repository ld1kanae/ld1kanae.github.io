"""Candidate-grounded tatum metal decoder using low-threshold ADTOF + GMD LM.

Prediction inputs:
- low-threshold ADTOF hat and generic-cymbal peak streams
- current browser metal events as strong observations
- current browser kick/snare/tom for simultaneous context
- browser-estimated BPM/bar phase
- GMD train/4-4 repetition-aware symbolic prior

Rules:
- decoding happens on 16th-note slots;
- a slot with no acoustic/current candidate is forced none;
- current pedal-hat events are fixed and never overwritten;
- other candidate slots choose none/hat/ride/crash;
- low-threshold ADTOF only proposes candidates; GMD LM decides whether they
  form a plausible repeated timekeeping/accent sequence.

DruMaster chart.mid is scoring-only. Global search and nested LOO are reported.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
import torch
from adtof_pytorch import calculate_n_bins,create_frame_rnn_model,get_default_weights_path,load_pytorch_weights,PeakPicker,LABELS_5
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
TOKENS=("none","hat","ride","crash")
HATS=(.04,.06)
CYMS=(.04,.08)

spec=importlib.util.spec_from_file_location("rep",EXP/"browser_gmd_repetition_decoder.py")
rep=importlib.util.module_from_spec(spec);spec.loader.exec_module(rep)

def model():
    n=calculate_n_bins();m=create_frame_rnn_model(n)
    return load_pytorch_weights(m,get_default_weights_path(),strict=False).eval()

def infer(song,m,p):
    a=p.load_audio(str(ROOT/"DruMaster/songs"/song/"drums.mp3"))
    st=p.compute_stft(a);x=p.apply_filterbank(st).T.astype(np.float32)[...,None]
    with torch.no_grad():return m(torch.from_numpy(x[None,...])).cpu().numpy()

def pick(y,ht,ct):
    pp=PeakPicker(thresholds=[.22,.24,.32,ht,ct],fps=100)
    d=pp.pick(y,labels=LABELS_5,label_offset=0)[0]
    return sorted(map(float,d.get(42,[]))),sorted(map(float,d.get(49,[])))

def browser_rows(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in rep.ev.midi_events(BASE/f"{song}.mid")],side

def score(song,pred):return rep.truth_score(song,pred)
def qslot(t,phase,step):return int(round((t-phase)/step))

def add_nearest(d,s,t,kind,scorev):
    x=d.setdefault(s,{"times":[],"hatSrc":0.,"cymSrc":0.,"current":[]})
    x["times"].append(t);x[kind]=max(x[kind],scorev)

def prepare(song,y):
    rows,side=browser_rows(song);bpm=float(side["bpm"]);phase=float(side["barPhaseSec"]);step=(60/bpm)/4
    body=defaultdict(set);current=defaultdict(list);extras=[]
    for t,g in rows:
        s=qslot(t,phase,step)
        if g in ("kick","snare","tom"):body[s].add(g)
        if g in ("hat","pedal_hat","ride","crash"):current[s].append((t,g))
        else:extras.append((t,g))
    fixed_pedal=[];current_nonped=defaultdict(list)
    for s,items in current.items():
        for t,g in items:
            if g=="pedal_hat":fixed_pedal.append((t,g))
            else:current_nonped[s].append((t,g))
    return {"song":song,"rows":rows,"side":side,"bpm":bpm,"phase":phase,"step":step,
            "body":body,"current":current_nonped,"fixedPedal":fixed_pedal,"extras":extras,"y":y}

def candidate_slots(d,ht,ct):
    hh,cy=pick(d["y"],ht,ct);slots={}
    for t in hh:
        s=qslot(t,d["phase"],d["step"]);fr=max(0,min(d["y"].shape[1]-1,int(round(t*100))))
        add_nearest(slots,s,t,"hatSrc",float(d["y"][0,fr,3]))
    for t in cy:
        s=qslot(t,d["phase"],d["step"]);fr=max(0,min(d["y"].shape[1]-1,int(round(t*100))))
        add_nearest(slots,s,t,"cymSrc",float(d["y"][0,fr,4]))
    for s,items in d["current"].items():
        x=slots.setdefault(s,{"times":[],"hatSrc":0.,"cymSrc":0.,"current":[]})
        x["current"].extend(items);x["times"].extend(t for t,g in items)
    pedslots={qslot(t,d["phase"],d["step"]) for t,g in d["fixedPedal"]}
    return slots,pedslots

def obs_time(x,lab):
    for t,g in x["current"]:
        if g==lab:return t
    return float(np.median(x["times"])) if x["times"] else 0.

def decode(d,cfg):
    slots,pedslots=candidate_slots(d,cfg["hatThr"],cfg["cymThr"])
    keys=set(slots)|set(d["body"])|pedslots
    if not keys:return list(d["rows"]),0
    start=(min(keys)//16)*16;end=max(keys)
    beam=[(0.,tuple(),{})]
    for s in range(start,end+1):
        x=slots.get(s);ctx=rep.ctx_name(d["body"].get(s,set()));pos=s%16
        nextb=[]
        for sc,hist,dec in beam:
            prev=hist[-1] if hist else "none"
            prev2=hist[-2] if len(hist)>=2 else "none"
            prevbar=hist[-16] if len(hist)>=16 else "none"
            labels=("none",) if x is None else TOKENS
            for lab in labels:
                p=rep.lm_prob(cfg["scope"],pos,prev,prev2,prevbar,ctx,lab)
                v=sc+cfg["lmWeight"]*math.log(max(p,1e-7))
                if x is not None:
                    cur=[g for t,g in x["current"]]
                    if lab in cur:v+=cfg["currentBias"]
                    elif cur and lab!="none":v-=cfg["changePenalty"]
                    if lab=="none":
                        v+=cfg["noneBias"]
                        if cur:v-=cfg["dropPenalty"]
                    elif lab=="hat":
                        v+=cfg["hatObs"]*x["hatSrc"]-cfg["hatCymPenalty"]*x["cymSrc"]
                    elif lab=="ride":
                        v+=cfg["rideHatObs"]*x["hatSrc"]+cfg["rideCymObs"]*x["cymSrc"]
                    elif lab=="crash":
                        v+=cfg["crashCymObs"]*x["cymSrc"]
                        if pos==0:v+=cfg["crashHead"]
                nh=(hist+(lab,))[-16:]
                nd=dec if x is None else {**dec,s:lab}
                nextb.append((v,nh,nd))
        nextb.sort(key=lambda z:z[0],reverse=True)
        nb=[];seen=set()
        for row in nextb:
            if row[1] in seen:continue
            seen.add(row[1]);nb.append(row)
            if len(nb)>=cfg["beam"]:break
        beam=nb
    best=max(beam,key=lambda z:z[0]);dec=best[2]
    pred=list(d["extras"])+list(d["fixedPedal"]);changed=0
    for s,x in slots.items():
        lab=dec.get(s,"none")
        if lab=="none":continue
        pred.append((obs_time(x,lab),lab))
        cur=[g for t,g in x["current"]]
        if lab not in cur:changed+=1
    pred.sort()
    return pred,changed

def aggregate(scores):return rep.aggregate(scores)

def objective(ag):
    h=ag["by_group"]["hat"];p=ag["by_group"]["pedal_hat"];r=ag["by_group"]["ride"];c=ag["by_group"]["crash"]
    return ag["f1"]+.06*r["f1"]+.05*c["f1"]+.02*p["f1"]+.01*h["f1"]-.015*max(0,(r["count_ratio"] or 0)-1.15)

def main():
    m=model();proc=create_adtof_processor();data={}
    for song in SONGS:
        print("INFER",song,flush=True);data[song]=prepare(song,infer(song,m,proc))
    baseline_scores={s:score(s,data[s]["rows"]) for s in SONGS};baseline=aggregate(baseline_scores)

    configs=[];i=0
    for ht in HATS:
      for ct in CYMS:
       for scope in ("all","rock_family"):
        for lm in (.50,.80):
         for cb in (1.5,2.1):
          configs.append({"id":i,"hatThr":ht,"cymThr":ct,"scope":scope,"lmWeight":lm,
            "currentBias":cb,"changePenalty":.15,"noneBias":.25,"dropPenalty":1.8,
            "hatObs":1.1,"hatCymPenalty":.2,"rideHatObs":.45,"rideCymObs":.85,
            "crashCymObs":1.0,"crashHead":.35,"beam":16});i+=1

    rows=[];cache={}
    for n,cfg in enumerate(configs):
        scores={};diag={}
        for s in SONGS:
            pred,ch=decode(data[s],cfg);sc=score(s,pred);scores[s]=sc
            diag[s]={"f1":sc["f1"],"changedOrAdded":ch,"metal":{g:sc["by_group"][g] for g in ("hat","pedal_hat","ride","crash")}}
        ag=aggregate(scores);cache[cfg["id"]]=scores
        eligible=(ag["precision"]>=baseline["precision"]-.035 and ag["f1"]>=baseline["f1"]-.005)
        rows.append({"id":cfg["id"],"eligible":eligible,"objective":objective(ag),"config":cfg,"summary":ag,"songs":diag})
        if n%25==0:print("CFG",n,len(configs),ag["f1"],flush=True)
    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)

    loo={};held={}
    for h in SONGS:
        tr=[s for s in SONGS if s!=h];rank=[]
        btr=aggregate({s:baseline_scores[s] for s in tr})
        for row in rows:
            ag=aggregate({s:cache[row["id"]][s] for s in tr})
            valid=ag["precision"]>=btr["precision"]-.035 and ag["f1"]>=btr["f1"]-.005
            rank.append((valid,objective(ag),ag["f1"],row["id"]))
        rank.sort(reverse=True);bid=rank[0][3];row=next(z for z in rows if z["id"]==bid)
        sc=cache[bid][h];held[h]=sc
        loo[h]={"selectedId":bid,"config":row["config"],"heldF1":sc["f1"],
                "metal":{g:sc["by_group"][g] for g in ("hat","pedal_hat","ride","crash")}}
    lag=aggregate(held)
    out={"schema":1,"description":"Fast constrained low-threshold ADTOF candidate-grounded 16th-slot GMD decoder; pedal fixed; charts scoring-only.",
         "baseline":baseline,"top":rows[:40],"nestedLOO":{"aggregate":lag,"objective":objective(lag),"songs":loo}}
    (EXP/"results-adtof-gmd-tatum-metal-decoder-fast.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    print("TOP",json.dumps(rows[:6],ensure_ascii=False),flush=True)
    print("LOO",json.dumps(out["nestedLOO"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
