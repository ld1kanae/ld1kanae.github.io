#!/usr/bin/env python3
"""Held-out continuation test for GMD K/S/T priors.

For each GMD validation/test performance, infer a local expert mixture from the
FIRST HALF of the MIDI, then evaluate occupied K/S/T grid slots in the SECOND
HALF. This is closer to DrumScribe's intended use than semantic genre-name
classification: the expert labels are only provenance; rhythmic similarity is
what matters.

Compared without any DruMaster data:
  A) global GMD prior
  B) inferred primary-genre mixture
  C) inferred exact-style mixture
  D) oracle genre+beat_type prior (diagnostic upper bound, not runtime-usable)
"""

from __future__ import annotations
import argparse,csv,json,math
from collections import defaultdict
from pathlib import Path
import mido

GROUPS=("kick","snare","tom")
PITCH={36:"kick",37:"snare",38:"snare",40:"snare",
       43:"tom",45:"tom",47:"tom",48:"tom",50:"tom",58:"tom"}

def norm(xs):
    s=sum(xs); return [x/s for x in xs] if s else [0.0 for _ in xs]

def cosine(a,b):
    ab=sum(x*y for x,y in zip(a,b));aa=sum(x*x for x in a);bb=sum(y*y for y in b)
    return ab/math.sqrt(aa*bb) if aa>1e-12 and bb>1e-12 else 0.0

def signature(raw):
    try:
        a,b=str(raw).replace("/","-").split("-",1);return int(a),int(b)
    except: return 4,4

def parse_slots(path,numerator,denominator):
    mid=mido.MidiFile(path);tpq=mid.ticks_per_beat
    barq=numerator*4/denominator;slots=max(1,round(numerator*16/denominator))
    tick=0;hits=[];maxbar=0
    for msg in mido.merge_tracks(mid.tracks):
        tick+=msg.time
        if msg.type!="note_on" or getattr(msg,"velocity",0)<=0: continue
        g=PITCH.get(int(msg.note))
        if not g: continue
        q=tick/tpq;bar=math.floor((q+1e-9)/barq)
        pos=q-bar*barq;slot=round(pos*4)%slots
        hits.append((bar,slot,g));maxbar=max(maxbar,bar)
    return hits,slots,maxbar+1

def observed_profile(hits,slots,bars):
    phase={g:[0]*slots for g in GROUPS};gh={g:0 for g in GROUPS}
    for bar,slot,g in hits:
        if bar not in bars: continue
        phase[g][slot]+=1;gh[g]+=1
    return {"phase":{g:norm(phase[g]) for g in GROUPS},
            "composition":norm([gh[g] for g in GROUPS]),
            "hits":gh}

def ref_profile(agg,slots):
    phase={}
    for g in GROUPS:
        c=agg.get("phase_16th_counts",{}).get(g,{})
        phase[g]=norm([float(c.get(str(i),0)) for i in range(slots)])
    h=agg.get("hits",{})
    return {"phase":phase,"composition":norm([float(h.get(g,0)) for g in GROUPS])}

def similarity(obs,agg,slots):
    ref=ref_profile(agg,slots);scores=[]
    for g in GROUPS:
        if obs["hits"][g]>0:scores.append(cosine(obs["phase"][g],ref["phase"][g]))
    phase=sum(scores)/len(scores) if scores else 0
    return .82*phase+.18*cosine(obs["composition"],ref["composition"])

def mixture(knowledge,family,obs,slots,topk,temp=.10):
    rows=[(similarity(obs,agg,slots),key) for key,agg in knowledge["aggregates"][family].items()]
    rows.sort(reverse=True);rows=rows[:topk]
    if not rows:return {}
    mx=rows[0][0];ex=[math.exp((s-mx)/temp) for s,_ in rows];den=sum(ex) or 1
    return {key:v/den for v,(_,key) in zip(ex,rows)}

def phase_ratio(agg,g,slot,slots):
    c=agg.get("phase_16th_counts",{}).get(g,{})
    vals=[float(c.get(str(i),0)) for i in range(slots)]
    mean=sum(vals)/slots if slots else 0
    alpha=max(2.0,.12*mean)
    return (vals[slot]+alpha)/(mean+alpha) if mean+alpha else 1.0

def mixed_score(knowledge,family,weights,g,slot,slots):
    log=0;den=0
    for key,w in weights.items():
        agg=knowledge["aggregates"][family].get(key)
        if not agg:continue
        log+=w*math.log(max(.05,phase_ratio(agg,g,slot,slots)));den+=w
    return math.exp(log/den) if den else 1.0

def auc(rows):
    # Mann-Whitney AUC with average rank for ties.
    rows=sorted(rows,key=lambda x:x[0])
    n0=sum(1 for _,y in rows if not y);n1=len(rows)-n0
    if not n0 or not n1:return None
    rank_sum=0;i=0
    while i<len(rows):
        j=i+1
        while j<len(rows) and abs(rows[j][0]-rows[i][0])<1e-12:j+=1
        avg_rank=((i+1)+j)/2
        rank_sum+=avg_rank*sum(1 for _,y in rows[i:j] if y)
        i=j
    return (rank_sum-n1*(n1+1)/2)/(n1*n0)

def evaluate(root,knowledge):
    rows=list(csv.DictReader((root/"info.csv").open(encoding="utf-8",newline="")))
    out={}
    for split in ("validation","test"):
        scores={m:{g:[] for g in GROUPS} for m in ("global","genre_mix","style_mix","oracle_genre_beat")}
        used=0
        for row in rows:
            if row.get("split")!=split:continue
            n,d=signature(row.get("time_signature") or "4-4")
            if (n,d)!=(4,4):continue
            hits,slots,nbar=parse_slots(root/row["midi_filename"],n,d)
            if nbar<4:continue
            cut=max(2,nbar//2)
            first=set(range(0,cut));second=set(range(cut,nbar))
            obs=observed_profile(hits,slots,first)
            if sum(obs["hits"].values())<8:continue
            genre_w=mixture(knowledge,"genre",obs,slots,4)
            style_w=mixture(knowledge,"style",obs,slots,8)
            primary=(row.get("style") or "unknown/unknown").split("/",1)[0].lower()
            bt=(row.get("beat_type") or "unknown").lower()
            oracle=knowledge["aggregates"]["genre_beat_type"].get(f"{primary}|{bt}")
            global_agg=knowledge["aggregates"]["global"]["all"]
            truth={(bar,slot,g) for bar,slot,g in hits if bar in second}
            for bar in second:
                for slot in range(slots):
                    for g in GROUPS:
                        y=(bar,slot,g) in truth
                        scores["global"][g].append((phase_ratio(global_agg,g,slot,slots),y))
                        scores["genre_mix"][g].append((mixed_score(knowledge,"genre",genre_w,g,slot,slots),y))
                        scores["style_mix"][g].append((mixed_score(knowledge,"style",style_w,g,slot,slots),y))
                        o=phase_ratio(oracle,g,slot,slots) if oracle else 1.0
                        scores["oracle_genre_beat"][g].append((o,y))
            used+=1
        metrics={}
        for model,groups in scores.items():
            metrics[model]={g:{"auc":auc(rs),"examples":len(rs),"positives":sum(y for _,y in rs)} for g,rs in groups.items()}
            vals=[metrics[model][g]["auc"] for g in GROUPS if metrics[model][g]["auc"] is not None]
            metrics[model]["macro_auc"]=sum(vals)/len(vals) if vals else None
        out[split]={"performances":used,"metrics":metrics}
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cache-dir",default=".cache/gmd-kst")
    ap.add_argument("--knowledge",default="drumscribe/models/gmd-kst/knowledge-v1.json")
    ap.add_argument("--output",default="drumscribe/experiments/gmd-kst/results-gmd-prior-heldout-v1.json")
    args=ap.parse_args()
    infos=list(Path(args.cache_dir).rglob("info.csv"))
    if not infos:raise SystemExit("GMD info.csv not found")
    root=infos[0].parent
    knowledge=json.loads(Path(args.knowledge).read_text(encoding="utf-8"))
    result={
      "version":"gmd-kst-prior-heldout-v1",
      "method":"first-half similarity -> second-half occupied-slot AUC",
      "knowledge_split":"train only",
      "druMaster_used":False,
      "note":"oracle_genre_beat is diagnostic only; runtime candidates are global/genre_mix/style_mix",
      "results":evaluate(root,knowledge),
    }
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__":main()
