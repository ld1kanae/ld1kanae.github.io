"""GMD repetition-aware beam decoder for current browser metal events.

No DruMaster chart is used by prediction. The held-out references are used
only for evaluation and leave-one-song-out hyperparameter selection.

Sequence:
- 16th-note slots from estimated browser BPM/bar phase
- empty slots are forced none
- slots with a current metal onset choose hat/pedal_hat/ride/crash
- GMD repetition prior conditions on previous 1/2 slots, same slot previous
  bar, body context and bar position
- current browser label is a strong observation
- GMD acoustic classifier is used only as song-centered relative evidence to
  reduce kit/domain mismatch

The search reports both global exploratory ranking and nested LOO evaluation.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
METAL=("hat","pedal_hat","ride","crash");TOKENS=("none",)+METAL

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
train=loadmod("train",EXP/"train_gmd_metal_acoustic.py")
PRIOR=json.loads((ROOT/"drumscribe/models/gmd-metal-repetition-prior.json").read_text())
MODEL=json.loads((ROOT/"drumscribe/models/gmd-metal-acoustic-logreg.json").read_text())
CLASSES=MODEL["classes"];MEAN=np.asarray(MODEL["mean"],float);SCALE=np.asarray(MODEL["scale"],float)
COEF=np.asarray(MODEL["coef"],float);INTER=np.asarray(MODEL["intercept"],float)
CLASS_I={g:i for i,g in enumerate(CLASSES)}

def softmax(z):
    z=z-np.max(z);e=np.exp(z);return e/e.sum()

def acoustic_prob(f):
    x=(f-MEAN)/np.maximum(SCALE,1e-8);p=softmax(COEF@x+INTER)
    return {g:float(p[CLASS_I[g]]) for g in METAL}

def browser_rows(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")],side

def truth_score(song,pred):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    return ev.score([(t,g,0,0) for t,g in pred],truth,shift)

def quant_slot(t,phase,step):
    return int(round((t-phase)/step))

def ctx_name(groups):
    xs=[g for g in ("kick","snare","tom") if g in groups]
    return "+".join(xs) if xs else "none"

def prepare(song,tmpl):
    rows,side=browser_rows(song);bpm=float(side["bpm"]);phase=float(side["barPhaseSec"])
    step=(60/bpm)/4
    x=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3");sp=ev.spectrum(x);band,sim=ev.features(sp,tmpl)

    body=defaultdict(set);metal=defaultdict(list);extras=[]
    for t,g in rows:
        s=quant_slot(t,phase,step)
        if g in ("kick","snare","tom"):body[s].add(g)
        if g in METAL:metal[s].append((t,g))
        else:extras.append((t,g))

    priority={"crash":4,"ride":3,"pedal_hat":2,"hat":1}
    prim={};secondary=[]
    for s,items in metal.items():
        items=sorted(items,key=lambda z:priority[z[1]],reverse=True)
        prim[s]=items[0]
        secondary.extend(items[1:])

    probs={}
    logs_by_label={g:[] for g in METAL}
    for s,(t,g) in prim.items():
        f=train.feature(sp,band,sim,t);p=acoustic_prob(f);probs[s]=p
        for lab in METAL:logs_by_label[lab].append(math.log(max(1e-7,p[lab])))
    med={g:(float(np.median(v)) if v else 0.) for g,v in logs_by_label.items()}
    centered={s:{g:math.log(max(1e-7,p[g]))-med[g] for g in METAL} for s,p in probs.items()}

    if prim:
        minslot=min(min(prim),min(body) if body else min(prim));maxslot=max(max(prim),max(body) if body else max(prim))
    else:minslot=maxslot=0
    start=(minslot//16)*16;end=maxslot
    return {"song":song,"rows":rows,"bpm":bpm,"phase":phase,"step":step,
            "body":body,"prim":prim,"secondary":secondary,"extras":extras,
            "centered":centered,"start":start,"end":end}

def table_entry(scope,name,key):
    return PRIOR["scopes"][scope][name].get(key)

def lm_prob(scope,pos,prev,prev2,prevbar,ctx,label):
    keys=[
      ("full",f"{pos}|{prev}|{prev2}|{prevbar}|{ctx}",10),
      ("prevbar_ctx",f"{pos}|{prevbar}|{ctx}",8),
      ("prev2_ctx",f"{pos}|{prev}|{prev2}|{ctx}",8),
      ("prev_ctx",f"{pos}|{prev}|{ctx}",6),
      ("prevbar",f"{pos}|{prevbar}",5),
      ("prev",f"{pos}|{prev}",5),
      ("ctx",f"{pos}|{ctx}",5),
      ("slot",str(pos),1),
      ("global","all",1),
    ]
    for name,key,minn in keys:
        e=table_entry(scope,name,key)
        if e and e.get("n",0)>=minn:return max(1e-7,float(e["p"].get(label,1e-7)))
    return .2

def decode(d,cfg):
    beam=[(0.0,tuple(),{})]
    changed=0
    for s in range(d["start"],d["end"]+1):
        pos=s%16;ctx=ctx_name(d["body"].get(s,set()));event=d["prim"].get(s)
        nextb=[]
        for score,hist,dec in beam:
            prev=hist[-1] if len(hist)>=1 else "none"
            prev2=hist[-2] if len(hist)>=2 else "none"
            prevbar=hist[-16] if len(hist)>=16 else "none"
            labels=("none",) if event is None else METAL
            for lab in labels:
                lp=lm_prob(cfg["scope"],pos,prev,prev2,prevbar,ctx,lab)
                v=score+cfg["lmWeight"]*math.log(lp)
                if event is not None:
                    cur=event[1]
                    v+=cfg["currentBias"]*(1 if lab==cur else 0)
                    if cur=="pedal_hat" and lab==cur:v+=.45
                    if cur=="crash" and lab==cur:v+=.30
                    if cur=="ride" and lab==cur:v+=.20
                    v+=cfg["acousticWeight"]*d["centered"][s][lab]
                nh=(hist+(lab,))[-16:]
                if event is None:nd=dec
                else:
                    nd=dec.copy();nd[s]=lab
                nextb.append((v,nh,nd))
        nextb.sort(key=lambda z:z[0],reverse=True)
        uniq=[];seen=set()
        for row in nextb:
            k=row[1]
            if k in seen:continue
            seen.add(k);uniq.append(row)
            if len(uniq)>=cfg["beam"]:break
        beam=uniq
    best=max(beam,key=lambda z:z[0]);dec=best[2]
    pred=list(d["extras"])+list(d["secondary"])
    for s,(t,cur) in d["prim"].items():
        lab=dec.get(s,cur);pred.append((t,lab))
        if lab!=cur:changed+=1
    pred.sort()
    return pred,changed

def aggregate(scores):
    tot=Counter()
    for sc in scores.values():
        tot.update(tp=sc["tp"],pred=sc["predicted"],ref=sc["reference"])
        for g,x in sc["by_group"].items():
            tot.update({f"{g}_tp":x["tp"],f"{g}_pred":x["predicted"],f"{g}_ref":x["reference"]})
    out={"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
         "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],
         "f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),"by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        out["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    return out

def objective(ag):
    h=ag["by_group"]["hat"]["f1"];p=ag["by_group"]["pedal_hat"]["f1"]
    r=ag["by_group"]["ride"]["f1"];c=ag["by_group"]["crash"]["f1"]
    return ag["f1"]+.05*r+.035*c+.025*p+.015*h

def main():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums");data={s:prepare(s,tmpl) for s in SONGS}
    baseline_scores={s:truth_score(s,data[s]["rows"]) for s in SONGS};baseline=aggregate(baseline_scores)
    configs=[]
    for scope in ("all","rock_family"):
      for lm in (.35,.60,.90):
       for cb in (1.25,1.75,2.25):
        for aw in (0,.12,.25):
         configs.append({"scope":scope,"lmWeight":lm,"currentBias":cb,"acousticWeight":aw,"beam":24})
    rows=[];per_cfg_song={}
    for i,cfg in enumerate(configs):
        scores={};diag={}
        for s in SONGS:
            pred,changed=decode(data[s],cfg);sc=truth_score(s,pred);scores[s]=sc
            diag[s]={"changed":changed,"f1":sc["f1"],"metal":{g:sc["by_group"][g] for g in METAL}}
        ag=aggregate(scores)
        eligible=ag["f1"]>=baseline["f1"]-.003 and ag["precision"]>=baseline["precision"]-.025
        row={"id":i,"eligible":eligible,"objective":objective(ag),"config":cfg,"summary":ag,"songs":diag}
        rows.append(row);per_cfg_song[i]=scores
        print("CFG",i,json.dumps({"cfg":cfg,"f1":ag["f1"],"obj":row["objective"],"ride":ag["by_group"]["ride"],"crash":ag["by_group"]["crash"]}),flush=True)
    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)

    loo={};held_scores={}
    for held in SONGS:
        train_s=[s for s in SONGS if s!=held];ranked=[]
        for row in rows:
            ag=aggregate({s:per_cfg_song[row["id"]][s] for s in train_s})
            ranked.append((objective(ag),ag["f1"],row["id"]))
        ranked.sort(reverse=True);bestid=ranked[0][2]
        best=next(x for x in rows if x["id"]==bestid)
        sc=per_cfg_song[bestid][held];held_scores[held]=sc
        loo[held]={"selectedId":bestid,"config":best["config"],"heldF1":sc["f1"],
                   "heldMetal":{g:sc["by_group"][g] for g in METAL}}
    loo_ag=aggregate(held_scores)

    report={"schema":1,
      "description":"GMD repetition-aware beam decoder; acoustic evidence song-centered; charts evaluation-only.",
      "baseline":baseline,"top":rows[:30],
      "nestedLOO":{"songs":loo,"aggregate":loo_ag,"objective":objective(loo_ag)}}
    (EXP/"results-browser-gmd-repetition-decoder.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    print("LOO",json.dumps(report["nestedLOO"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
