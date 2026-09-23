#!/usr/bin/env python3
"""Held-out sanity evaluation for section-local GMD genre inference.

This evaluates whether the TRAIN-derived K/S/T genre profiles contain useful
style information at all. It uses official GMD validation/test MIDI as an
"oracle K/S/T profile" upper-bound test; it does not tune thresholds and it
does not use DruMaster.
"""

from __future__ import annotations
import argparse, csv, json, math
from collections import Counter, defaultdict
from pathlib import Path
import mido

GROUPS=("kick","snare","tom")
PITCH={
    36:"kick",
    37:"snare",38:"snare",40:"snare",
    43:"tom",45:"tom",47:"tom",48:"tom",50:"tom",58:"tom",
}

def norm(xs):
    s=sum(xs)
    return [x/s for x in xs] if s else [0.0 for _ in xs]

def cosine(a,b):
    ab=sum(x*y for x,y in zip(a,b))
    aa=sum(x*x for x in a); bb=sum(y*y for y in b)
    return ab/math.sqrt(aa*bb) if aa>1e-12 and bb>1e-12 else 0.0

def sig(raw):
    try:
        n,d=str(raw).replace("/","-").split("-",1)
        return int(n),int(d)
    except Exception:
        return 4,4

def midi_profile(path,numerator,denominator):
    mid=mido.MidiFile(path)
    tpq=mid.ticks_per_beat
    slots=max(1,round(numerator*16/denominator))
    barq=numerator*4/denominator
    counts={g:[0]*slots for g in GROUPS}
    hits=Counter()
    tick=0
    for msg in mido.merge_tracks(mid.tracks):
        tick+=msg.time
        if msg.type!="note_on" or getattr(msg,"velocity",0)<=0: continue
        g=PITCH.get(int(msg.note))
        if not g: continue
        q=tick/tpq
        pos=q-math.floor((q+1e-9)/barq)*barq
        slot=round(pos*4)%slots
        counts[g][slot]+=1; hits[g]+=1
    return {
        "phase":{g:norm(counts[g]) for g in GROUPS},
        "composition":norm([hits[g] for g in GROUPS]),
        "hits":sum(hits.values()),
        "slots":slots,
    }

def ref_profile(agg,slots):
    out={}
    for g in GROUPS:
        c=agg.get("phase_16th_counts",{}).get(g,{})
        out[g]=norm([float(c.get(str(i),0)) for i in range(slots)])
    h=agg.get("hits",{})
    return {
        "phase":out,
        "composition":norm([float(h.get(g,0)) for g in GROUPS]),
    }

def rank_genres(knowledge,profile):
    rows=[]
    for genre,agg in knowledge["aggregates"]["genre"].items():
        ref=ref_profile(agg,profile["slots"])
        phase_num=phase_den=0.0
        for g in GROUPS:
            observed=sum(profile["phase"][g])
            # The normalized phase sums to one when the group is present.
            raw_hits=sum(1 for x in profile["phase"][g] if x>0)
            if observed<=0: continue
            # Equal group contribution is more stable on short held-out rows.
            w=1.0 if raw_hits else 0.0
            phase_num+=w*cosine(profile["phase"][g],ref["phase"][g]); phase_den+=w
        phase=phase_num/phase_den if phase_den else 0.0
        comp=cosine(profile["composition"],ref["composition"])
        score=.82*phase+.18*comp
        rows.append((score,genre,phase,comp))
    rows.sort(reverse=True)
    return rows

def find_root(cache):
    roots=list(Path(cache).rglob("info.csv"))
    if not roots: raise SystemExit(f"info.csv not found under {cache}")
    return roots[0].parent

def evaluate(root,knowledge):
    rows=list(csv.DictReader((root/"info.csv").open(encoding="utf-8",newline="")))
    results={}
    for split in ("validation","test"):
        stats={
            "all":{"n":0,"top1":0,"top3":0},
            "4-4":{"n":0,"top1":0,"top3":0},
            "by_genre":defaultdict(lambda:{"n":0,"top1":0,"top3":0}),
            "confusion_top1":defaultdict(Counter),
        }
        for row in rows:
            if row.get("split")!=split: continue
            primary=(row.get("style") or "unknown/unknown").split("/",1)[0].lower()
            n,d=sig(row.get("time_signature") or "4-4")
            p=midi_profile(root/row["midi_filename"],n,d)
            if p["hits"]<8: continue
            ranked=rank_genres(knowledge,p)
            top=[g for _,g,_,_ in ranked[:3]]
            pred=top[0] if top else None
            buckets=["all"]+(["4-4"] if (n,d)==(4,4) else [])
            for key in buckets:
                s=stats[key];s["n"]+=1
                s["top1"]+=int(pred==primary)
                s["top3"]+=int(primary in top)
            bg=stats["by_genre"][primary];bg["n"]+=1
            bg["top1"]+=int(pred==primary);bg["top3"]+=int(primary in top)
            stats["confusion_top1"][primary][pred]+=1
        for key in ("all","4-4"):
            s=stats[key]
            s["top1_accuracy"]=s["top1"]/s["n"] if s["n"] else 0
            s["top3_accuracy"]=s["top3"]/s["n"] if s["n"] else 0
        by={}
        for g,s in sorted(stats["by_genre"].items()):
            by[g]={**s,
                "top1_accuracy":s["top1"]/s["n"] if s["n"] else 0,
                "top3_accuracy":s["top3"]/s["n"] if s["n"] else 0}
        results[split]={
            "all":stats["all"],"4-4":stats["4-4"],
            "by_genre":by,
            "confusion_top1":{g:dict(c.most_common()) for g,c in sorted(stats["confusion_top1"].items())},
        }
    return results

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cache-dir",default=".cache/gmd-kst")
    ap.add_argument("--knowledge",default="drumscribe/models/gmd-kst/knowledge-v1.json")
    ap.add_argument("--output",default="drumscribe/experiments/gmd-kst/results-gmd-genre-heldout-v1.json")
    args=ap.parse_args()
    root=find_root(args.cache_dir)
    knowledge=json.loads(Path(args.knowledge).read_text(encoding="utf-8"))
    result={
      "version":"gmd-kst-genre-heldout-v1",
      "purpose":"oracle K/S/T profile upper-bound sanity check; no threshold tuning",
      "knowledge_split":"train only",
      "evaluation_splits":["validation","test"],
      "score":".82 phase cosine + .18 K/S/T composition cosine; equal genre prior",
      "results":evaluate(root,knowledge),
    }
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__": main()
