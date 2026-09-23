"""Build kick/snare/tom symbolic priors from Magenta Groove MIDI Dataset.

Uses only the official GMD train split and stores aggregate statistics.
Source MIDI files are not committed.
"""
from __future__ import annotations
import argparse,csv,json
from collections import Counter,defaultdict
from pathlib import Path
import mido

GROUPS=("kick","snare","tom")
PITCH={}
for n in (35,36): PITCH[n]="kick"
for n in (37,38,39,40): PITCH[n]="snare"
for n in (41,43,45,47,48,50): PITCH[n]="tom"

def family(style):
    p=(style or "").split("/")[0].lower()
    if p in ("rock","punk"): return "rock_family"
    if p in ("pop","soul","country"): return "pop_rock_family"
    if p in ("funk","gospel","neworleans"): return "funk_family"
    if p=="jazz": return "jazz_family"
    return "other"

def parse_slots(path):
    mid=mido.MidiFile(path)
    tpb=mid.ticks_per_beat
    tick=0
    slots=defaultdict(set)
    last_tick=0
    for msg in mido.merge_tracks(mid.tracks):
        tick += msg.time
        last_tick=max(last_tick,tick)
        if msg.type=="note_on" and msg.velocity>0 and int(msg.note) in PITCH:
            q=int(round(tick/(tpb/4)))
            bar=q//16
            slot=q%16
            slots[(bar,slot)].add(PITCH[int(msg.note)])
    bars=max(1,int(last_tick//(tpb*4))+1)
    return slots,bars

def prob(num,den,alpha=.5):
    return (num+alpha)/(den+2*alpha) if den>=0 else 0.0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--gmd-root",required=True)
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    root=Path(a.gmd_root)
    info=next(iter(root.rglob("info.csv")),None)
    if info is None: raise SystemExit("info.csv not found")

    denom=defaultdict(Counter)
    present=defaultdict(lambda:defaultdict(Counter))
    cond_den=defaultdict(lambda:defaultdict(Counter))
    cond_num=defaultdict(lambda:defaultdict(lambda:defaultdict(Counter)))
    combos=defaultdict(Counter)
    counts=Counter()

    with info.open(newline="",encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("split")!="train": continue
            if row.get("time_signature") not in ("4-4","4/4"): continue
            rel=row.get("midi_filename","")
            p=root/rel
            if not p.exists():
                hits=list(root.rglob(Path(rel).name))
                if not hits: continue
                p=hits[0]
            try:
                slots,bars=parse_slots(p)
            except Exception:
                continue
            fam=family(row.get("style",""))
            bt=row.get("beat_type","unknown")
            keys=("all",fam,f"beat_type:{bt}",f"{fam}|{bt}")
            counts["files"]+=1
            counts["bars"]+=bars
            counts[f"files:{fam}"]+=1
            counts[f"files:{bt}"]+=1
            for key in keys:
                for slot in range(16):
                    denom[key][slot]+=bars
            for (bar,slot),gs in slots.items():
                combo="+".join(g for g in GROUPS if g in gs) or "none"
                for key in keys:
                    combos[key][combo]+=1
                    for g in gs:
                        present[key][g][slot]+=1
                    for given in GROUPS:
                        if given not in gs: continue
                        cond_den[key][given][slot]+=1
                        for target in GROUPS:
                            if target in gs:
                                cond_num[key][given][target][slot]+=1

    groups={}
    for key in sorted(denom):
        slot16={}
        conditional={}
        for slot in range(16):
            d=denom[key][slot]
            slot16[str(slot)]={g:prob(present[key][g][slot],d) for g in GROUPS}
        for given in GROUPS:
            conditional[given]={}
            for slot in range(16):
                d=cond_den[key][given][slot]
                conditional[given][str(slot)]={t:prob(cond_num[key][given][t][slot],d) for t in GROUPS}
        groups[key]={
            "slot16":slot16,
            "conditional":conditional,
            "combos":dict(combos[key]),
            "bars":int(sum(denom[key].values())//16)
        }

    out={
      "schema":1,
      "source":{
        "name":"Groove MIDI Dataset v1.0.0",
        "split":"train",
        "timeSignature":"4/4",
        "license":"CC BY 4.0",
        "url":"https://magenta.tensorflow.org/datasets/groove"
      },
      "classes":list(GROUPS),
      "counts":dict(counts),
      "groups":groups
    }
    op=Path(a.output);op.parent.mkdir(parents=True,exist_ok=True)
    op.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    summary={
      "counts":out["counts"],
      "all_combos":groups.get("all",{}).get("combos",{}),
      "rock_combos":groups.get("rock_family",{}).get("combos",{})
    }
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
