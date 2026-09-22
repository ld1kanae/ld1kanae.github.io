"""Build style- and beat/fill-conditioned metal priors from GMD.

This complements gmd-metal-prior.json:
- all-style vs rock-family symbolic distributions
- beat vs fill distributions
- onset position and preceding-fill proxies
- metal transition probabilities by style/beat_type

Only aggregate statistics are stored.
"""
from __future__ import annotations
import argparse,csv,json
from collections import Counter,defaultdict
from pathlib import Path
import mido

METAL=("hat","pedal_hat","ride","crash")
PITCH={22:"hat",26:"hat",42:"hat",46:"hat",44:"pedal_hat",
       51:"ride",53:"ride",59:"ride",49:"crash",52:"crash",55:"crash",57:"crash"}

def parse(path):
    mid=mido.MidiFile(path);tpb=mid.ticks_per_beat;tick=0;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        tick+=msg.time
        if msg.type=="note_on" and msg.velocity>0 and int(msg.note) in PITCH:
            out.append((int(round(tick/(tpb/4))),PITCH[int(msg.note)]))
    return out

def family(style):
    p=(style or "").split("/")[0]
    if p in ("rock","punk"):return "rock_family"
    if p in ("pop","soul","country"):return "pop_rock_family"
    if p in ("funk","gospel","neworleans"):return "funk_family"
    if p=="jazz":return "jazz_family"
    return "other"

def smooth(c,alpha=.75):
    z=sum(c.values())+alpha*len(METAL)
    return {g:(c.get(g,0)+alpha)/z for g in METAL}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--gmd-root",required=True);ap.add_argument("--output",required=True)
    a=ap.parse_args();root=Path(a.gmd_root);info=next(iter(root.rglob("info.csv")),None)
    if info is None:raise SystemExit("info.csv not found")
    tables=defaultdict(lambda:defaultdict(Counter));trans=defaultdict(lambda:defaultdict(Counter));counts=Counter()
    with info.open(newline="",encoding="utf-8") as f:
      for row in csv.DictReader(f):
        if row.get("split")!="train" or row.get("time_signature") not in ("4-4","4/4"):continue
        rel=row["midi_filename"];p=root/rel
        if not p.exists():
            m=list(root.rglob(Path(rel).name))
            if not m:continue
            p=m[0]
        try:ev=parse(p)
        except Exception:continue
        if not ev:continue
        fam=family(row.get("style",""));bt=row.get("beat_type","unknown")
        keys=("all",fam,f"beat_type:{bt}",f"{fam}|{bt}")
        counts["files"]+=1;counts[f"files:{fam}"]+=1;counts[f"files:{bt}"]+=1
        prev=None
        for slot,g in ev:
            pos=slot%16
            for k in keys:
                tables[k][f"slot:{pos}"][g]+=1
                tables[k]["global"][g]+=1
                if prev:
                    ps,pg=prev;delta=min(16,max(0,slot-ps))
                    trans[k][f"{pg}|d{delta}"][g]+=1
            prev=(slot,g)
    out={"schema":1,"source":"GMD v1.0.0 train, 4/4 aggregate","counts":dict(counts),"groups":{}}
    for k,tab in tables.items():
        out["groups"][k]={
          "global":smooth(tab["global"]),
          "slot16":{str(i):smooth(tab[f"slot:{i}"]) for i in range(16)},
          "transition":{kk:smooth(v) for kk,v in trans[k].items()}
        }
    op=Path(a.output);op.parent.mkdir(parents=True,exist_ok=True)
    op.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
      "counts":out["counts"],
      "all":out["groups"].get("all",{}).get("global"),
      "rock":out["groups"].get("rock_family",{}).get("global"),
      "fill":out["groups"].get("beat_type:fill",{}).get("global"),
      "beat":out["groups"].get("beat_type:beat",{}).get("global")
    },ensure_ascii=False,indent=2))
if __name__=="__main__":main()
