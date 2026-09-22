"""Restricted GMD repetition decoder: preserve pedal-hat, change only hat/ride/crash.

This isolates the useful part of the GMD repetition prior without allowing the
sequence model to overwrite the already-validated browser pedal-hat decoder.

Prediction is audio/browser output + GMD prior only. DruMaster charts are used
only for evaluation and nested leave-one-song-out hyperparameter selection.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
spec=importlib.util.spec_from_file_location("base",EXP/"browser_gmd_repetition_decoder.py")
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
METAL=("hat","pedal_hat","ride","crash")
CHANGE=("hat","ride","crash")

def decode(d,cfg):
    beam=[(0.0,tuple(),{})]
    changed=0
    for s in range(d["start"],d["end"]+1):
        pos=s%16;ctx=base.ctx_name(d["body"].get(s,set()));event=d["prim"].get(s)
        nextb=[]
        for score,hist,dec in beam:
            prev=hist[-1] if len(hist)>=1 else "none"
            prev2=hist[-2] if len(hist)>=2 else "none"
            prevbar=hist[-16] if len(hist)>=16 else "none"
            if event is None:
                labels=("none",)
            elif event[1]=="pedal_hat":
                labels=("pedal_hat",)
            else:
                labels=CHANGE
            for lab in labels:
                lp=base.lm_prob(cfg["scope"],pos,prev,prev2,prevbar,ctx,lab)
                v=score+cfg["lmWeight"]*math.log(lp)
                if event is not None:
                    cur=event[1]
                    v+=cfg["currentBias"]*(1 if lab==cur else 0)
                    if cur=="crash" and lab==cur:v+=cfg["crashKeep"]
                    if cur=="ride" and lab==cur:v+=cfg["rideKeep"]
                    if cur=="hat" and lab==cur:v+=cfg["hatKeep"]
                    v+=cfg["acousticWeight"]*d["centered"][s][lab]
                nh=(hist+(lab,))[-16:]
                nd=dec if event is None else {**dec,s:lab}
                nextb.append((v,nh,nd))
        nextb.sort(key=lambda z:z[0],reverse=True)
        uniq=[];seen=set()
        for row in nextb:
            if row[1] in seen:continue
            seen.add(row[1]);uniq.append(row)
            if len(uniq)>=cfg["beam"]:break
        beam=uniq
    best=max(beam,key=lambda z:z[0]);dec=best[2]
    pred=list(d["extras"])+list(d["secondary"])
    for s,(t,cur) in d["prim"].items():
        lab=dec.get(s,cur);pred.append((t,lab))
        changed+=lab!=cur
    pred.sort()
    return pred,changed

def aggregate(scores):
    return base.aggregate(scores)

def objective(ag):
    h=ag["by_group"]["hat"];p=ag["by_group"]["pedal_hat"];r=ag["by_group"]["ride"];c=ag["by_group"]["crash"]
    return ag["f1"]+.055*r["f1"]+.045*c["f1"]+.02*h["f1"]+.02*p["f1"]-.015*max(0,(r["count_ratio"] or 0)-1.1)

def main():
    tmpl=base.ev.templates(ROOT/"DruMaster/assets/drums")
    data={s:base.prepare(s,tmpl) for s in SONGS}
    bscore={s:base.truth_score(s,data[s]["rows"]) for s in SONGS};baseline=aggregate(bscore)

    configs=[]
    for scope in ("all","rock_family"):
      for lm in (.25,.45,.65,.85):
       for cb in (1.0,1.4,1.8,2.2,2.6):
        for aw in (0,.08,.16):
         for ck in (.1,.35,.65):
          configs.append({"scope":scope,"lmWeight":lm,"currentBias":cb,"acousticWeight":aw,
                          "crashKeep":ck,"rideKeep":.2,"hatKeep":.15,"beam":24})
    rows=[];cache={}
    for i,cfg in enumerate(configs):
        scores={};diag={}
        for s in SONGS:
            pred,ch=decode(data[s],cfg);sc=base.truth_score(s,pred);scores[s]=sc
            diag[s]={"changed":ch,"f1":sc["f1"],"metal":{g:sc["by_group"][g] for g in METAL}}
        ag=aggregate(scores);cache[i]=scores
        eligible=(ag["f1"]>=baseline["f1"]-.002 and
                  ag["by_group"]["pedal_hat"]["f1"]>=baseline["by_group"]["pedal_hat"]["f1"]-.001 and
                  ag["precision"]>=baseline["precision"]-.02)
        rows.append({"id":i,"eligible":eligible,"objective":objective(ag),"config":cfg,"summary":ag,"songs":diag})
        if i%100==0:print("CFG",i,len(configs),ag["f1"],flush=True)
    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)

    held_scores={};loo={}
    for held in SONGS:
        train=[s for s in SONGS if s!=held];rank=[]
        for row in rows:
            ag=aggregate({s:cache[row["id"]][s] for s in train})
            # enforce train guard relative to train baseline
            bag=aggregate({s:bscore[s] for s in train})
            valid=(ag["f1"]>=bag["f1"]-.002 and
                   ag["by_group"]["pedal_hat"]["f1"]>=bag["by_group"]["pedal_hat"]["f1"]-.001)
            rank.append((valid,objective(ag),ag["f1"],row["id"]))
        rank.sort(reverse=True);bid=rank[0][3];row=next(z for z in rows if z["id"]==bid)
        sc=cache[bid][held];held_scores[held]=sc
        loo[held]={"selectedId":bid,"config":row["config"],"heldF1":sc["f1"],
                   "metal":{g:sc["by_group"][g] for g in METAL}}
    loo_ag=aggregate(held_scores)

    out={"schema":1,"description":"Restricted GMD repetition decoder; pedal fixed; charts evaluation-only.",
         "baseline":baseline,"top":rows[:50],
         "nestedLOO":{"aggregate":loo_ag,"objective":objective(loo_ag),"songs":loo}}
    (EXP/"results-browser-gmd-repetition-metal-only.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    print("TOP",json.dumps(rows[:8],ensure_ascii=False),flush=True)
    print("LOO",json.dumps(out["nestedLOO"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
