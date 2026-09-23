#!/usr/bin/env python3
"""Build a genre-aware GMD hi-hat articulation prior.

Input is the original Groove MIDI Dataset MIDI-only tree. Raw GMD files are not
copied into this repository; only aggregate statistics are emitted.

The model distinguishes:
  open:   46 / 26
  closed: 42 / 22
  pedal:  44
and keeps ride/crash counts as arrangement/metal context.

Prediction-time chart.mid files from DruMaster are never read here.
"""
from __future__ import annotations
import argparse, csv, json, math
from collections import Counter, defaultdict
from pathlib import Path
import mido

OPEN={46,26}; CLOSED={42,22}; PEDAL={44}
RIDE={51,59,53}; CRASH={49,57,55,52}
ART={"open","closed","pedal"}
FAMILIES={
    "rock_pop": {"rock","pop","punk","country"},
    "funk_soul_hiphop": {"funk","soul","hiphop","gospel"},
    "jazz_neworleans": {"jazz","neworleans"},
    "latin_world": {"latin","afrocuban","afrobeat","highlife","middleeastern"},
    "dance_reggae": {"dance","reggae"},
}
ALPHA=2.0

def cls(note:int):
    if note in OPEN:return "open"
    if note in CLOSED:return "closed"
    if note in PEDAL:return "pedal"
    if note in RIDE:return "ride"
    if note in CRASH:return "crash"
    return None

def family_for(genre:str):
    for name,members in FAMILIES.items():
        if genre in members:return name
    return "other"

def new_stats():
    return {
        "files":0,"bars":0,"cc4Files":0,
        "global":Counter(),"slot16":[Counter() for _ in range(16)],
        "transitions":defaultdict(Counter),"patterns":Counter(),
        "crashBeat":[0,0,0,0],"adjacentPairs":0,"adjacentF1Sum":0.0,
    }

def note_events(path:Path):
    mid=mido.MidiFile(path,clip=True)
    tick=0; out=[]; cc4=False
    for msg in mido.merge_tracks(mid.tracks):
        tick+=msg.time
        if msg.type=="note_on" and msg.velocity>0:
            c=cls(msg.note)
            if c:out.append((tick,msg.note,msg.velocity,c))
        elif msg.type=="control_change" and msg.control==4:
            cc4=True
    out.sort(key=lambda x:(x[0],x[1]))
    return mid.ticks_per_beat,out,cc4

def f1_bits(a,b):
    aa=sum(a);bb=sum(b);inter=sum(int(x and y) for x,y in zip(a,b))
    return 2*inter/(aa+bb) if aa+bb else 1.0

def pattern_type(arts):
    if not arts:return "empty"
    o=sum(x=="open" for x in arts); c=len(arts)-o
    if o and not c:return "open_only"
    if not o:return "closed_only"
    if o/len(arts)>=.70:return "open_dominant"
    alt=sum((arts[i]=="open")!=(arts[i-1]=="open") for i in range(1,len(arts)))
    if len(arts)>1 and alt/(len(arts)-1)>=.65:return "alternating"
    return "mixed"

def add_file(S,tpq,events,cc4):
    S["files"]+=1
    if cc4:S["cc4Files"]+=1
    arts=[e for e in events if e[3] in ART]
    for tick,note,vel,c in events:
        S["global"][c]+=1
        q=tick/tpq
        slot=int(round(q*4))%16
        S["slot16"][slot][c]+=1
        if c=="crash":
            S["crashBeat"][int(round(q))%4]+=1
    for i in range(len(arts)-1):
        t0,_,_,c0=arts[i];t1,_,_,c1=arts[i+1]
        d=max(0,min(32,int(round((t1-t0)/tpq*4))))
        S["transitions"][f"{c0}|d{d}"][c1]+=1
    max_tick=max((e[0] for e in events),default=0)
    bars=max(1,math.ceil((max_tick+1)/(4*tpq)))
    barseq=[]
    for bi in range(bars):
        lo=bi*4*tpq;hi=(bi+1)*4*tpq
        seq=[0]*16; lab=[]
        for tick,_,_,c in arts:
            if lo<=tick<hi:
                slot=max(0,min(15,int(round((tick-lo)/tpq*4))))
                seq[slot]=1;lab.append(c)
        S["bars"]+=1;S["patterns"][pattern_type(lab)]+=1;barseq.append(seq)
    for a,b in zip(barseq,barseq[1:]):
        S["adjacentPairs"]+=1;S["adjacentF1Sum"]+=f1_bits(a,b)

def p_open_counts(C,alpha=ALPHA):
    o=C.get("open",0);n=o+C.get("closed",0)+C.get("pedal",0)
    return (o+alpha)/(n+2*alpha) if n else None

def finish(S):
    glob={k:int(S["global"].get(k,0)) for k in ("open","closed","pedal","ride","crash")}
    pglob=p_open_counts(S["global"])
    slots=[]
    total_art=sum(glob[k] for k in ("open","closed","pedal")) or 1
    for i,C in enumerate(S["slot16"]):
        cnt={k:int(C.get(k,0)) for k in ("open","closed","pedal","ride","crash")}
        art=sum(cnt[k] for k in ("open","closed","pedal"))
        slots.append({"slot":i,"counts":cnt,"openProbability":p_open_counts(C),
                      "articulationShare":art/total_art})
    trans={}
    for k,C in S["transitions"].items():
        cnt={x:int(C.get(x,0)) for x in ("open","closed","pedal")}
        trans[k]={"counts":cnt,"openProbability":p_open_counts(C)}
    crash=S["crashBeat"]
    tail=sum(crash[1:])/3
    return {
        "files":S["files"],"bars":S["bars"],"cc4Files":S["cc4Files"],
        "global":glob,"globalOpenProbability":pglob,
        "slot16":slots,"transitions":trans,"patterns":dict(S["patterns"]),
        "adjacentBarPatternF1":S["adjacentF1Sum"]/S["adjacentPairs"] if S["adjacentPairs"] else None,
        "adjacentBarPairs":S["adjacentPairs"],
        "crashBeatCounts":crash,
        "crashBeat1Lift":crash[0]/tail if tail else None,
    }

def prob_from_group(G,slot,prev=None,d=None):
    ps=G["slot16"][slot]["openProbability"]
    if ps is None:ps=G["globalOpenProbability"] or .1
    pt=None
    if prev is not None and d is not None:
        rec=G["transitions"].get(f"{prev}|d{d}")
        if rec:pt=rec["openProbability"]
    return ps,pt

def nll(y,p):
    p=min(.999999,max(.000001,p))
    return -(math.log(p) if y else math.log(1-p))

def evaluate(rows,root,groups,blend):
    out={"n":0,"open":0,"globalNll":0.0,"genreSlotNll":0.0,"genreSlotTransitionNll":0.0}
    Gall=groups["all"]
    pg=Gall["globalOpenProbability"] or .1
    for row in rows:
        if row["time_signature"]!="4-4":continue
        genre=row["style"].split("/")[0]
        G=groups.get(f"genre:{genre}",Gall)
        tpq,events,_=note_events(root/row["midi_filename"])
        arts=[e for e in events if e[3] in ART]
        prev=None
        for tick,_,_,c in arts:
            y=int(c=="open");slot=int(round((tick/tpq)*4))%16
            ps,pt=prob_from_group(G,slot,prev[1] if prev else None,
                                  max(0,min(32,int(round((tick-prev[0])/tpq*4)))) if prev else None)
            pc=(1-blend)*ps+blend*(pt if pt is not None else ps)
            out["n"]+=1;out["open"]+=y
            out["globalNll"]+=nll(y,pg)
            out["genreSlotNll"]+=nll(y,ps)
            out["genreSlotTransitionNll"]+=nll(y,pc)
            prev=(tick,c)
    if out["n"]:
        for k in ("globalNll","genreSlotNll","genreSlotTransitionNll"):out[k]/=out["n"]
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--groove-root",type=Path,required=True)
    ap.add_argument("--model-out",type=Path,required=True)
    ap.add_argument("--results-out",type=Path,required=True)
    args=ap.parse_args()
    root=args.groove_root
    rows=list(csv.DictReader((root/"info.csv").open(newline="",encoding="utf-8")))
    train=[r for r in rows if r["split"]=="train" and r["time_signature"]=="4-4"]
    valid=[r for r in rows if r["split"]=="validation" and r["time_signature"]=="4-4"]
    test=[r for r in rows if r["split"]=="test" and r["time_signature"]=="4-4"]
    raw=defaultdict(new_stats)
    for i,row in enumerate(train,1):
        genre=row["style"].split("/")[0];fam=family_for(genre)
        tpq,events,cc4=note_events(root/row["midi_filename"])
        for key in ("all",f"genre:{genre}",f"family:{fam}"):
            add_file(raw[key],tpq,events,cc4)
        if i%100==0:print("train",i,"/",len(train))
    groups={k:finish(v) for k,v in raw.items()}
    candidates=[0.0,0.15,0.30,0.45,0.60]
    val_scores=[]
    for w in candidates:
        e=evaluate(valid,root,groups,w);val_scores.append((e["genreSlotTransitionNll"],w,e))
    val_scores.sort()
    best_w=val_scores[0][1]
    test_eval=evaluate(test,root,groups,best_w)
    allg=groups["all"]
    model={
      "schema":1,
      "name":"gmd-hat-articulation-prior-v1",
      "source":{
        "dataset":"Groove MIDI Dataset v1.0.0 MIDI-only",
        "url":"https://magenta.tensorflow.org/datasets/groove",
        "split":"train",
        "timeSignature":"4-4",
        "files":len(train),
        "license":"CC BY 4.0",
      },
      "noteMapping":{"open":[46,26],"closed":[42,22],"pedal":[44],
                     "ride":[51,59,53],"crash":[49,57,55,52]},
      "policy":{
        "alpha":ALPHA,
        "transitionBlend":best_w,
        "genreInference":"slot-articulation-density cosine; fallback all",
        "runtimeUse":"borderline acoustic open/closed rescoring only",
      },
      "groups":groups,
      "evidence":{
        "gmdHasSemanticArrangementSections":False,
        "sectionBoundaryCaveat":"GMD has style/beat/fill metadata, not A-melody/B-melody/chorus boundary labels. crashBeat1Lift is a bar-head statistic, not a section-head statistic.",
        "allTrainAdjacentBarPatternF1":allg["adjacentBarPatternF1"],
        "allTrainCrashBeat1Lift":allg["crashBeat1Lift"],
      },
      "heldout":{
        "validationCandidates":[{"transitionBlend":w,**e} for _,w,e in val_scores],
        "chosenTransitionBlend":best_w,
        "test":test_eval,
      },
    }
    results={
      "schema":1,"experiment":"GMD hi-hat articulation symbolic prior v40",
      "train4_4Files":len(train),"validation4_4Files":len(valid),"test4_4Files":len(test),
      "genres":{k.split(":",1)[1]:{"files":v["files"],"global":v["global"],
               "globalOpenProbability":v["globalOpenProbability"],"patterns":v["patterns"],
               "adjacentBarPatternF1":v["adjacentBarPatternF1"],"crashBeat1Lift":v["crashBeat1Lift"]}
               for k,v in groups.items() if k.startswith("genre:")},
      "all":{"global":allg["global"],"patterns":allg["patterns"],
             "adjacentBarPatternF1":allg["adjacentBarPatternF1"],
             "crashBeat1Lift":allg["crashBeat1Lift"],"cc4Files":allg["cc4Files"]},
      "heldout":model["heldout"],
      "interpretation":{
        "globalVsGenreSlot":"Compare heldout NLL; lower is better.",
        "transition":"Weight chosen on validation, then reported once on test.",
        "arrangement":"No semantic section-boundary claim is made from GMD."
      }
    }
    args.model_out.parent.mkdir(parents=True,exist_ok=True)
    args.results_out.parent.mkdir(parents=True,exist_ok=True)
    args.model_out.write_text(json.dumps(model,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    args.results_out.write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"train":len(train),"validation":len(valid),"test":len(test),
                      "blend":best_w,"test":test_eval,
                      "adjacentF1":allg["adjacentBarPatternF1"],
                      "crashBeat1Lift":allg["crashBeat1Lift"]},indent=2))

if __name__=="__main__":main()
