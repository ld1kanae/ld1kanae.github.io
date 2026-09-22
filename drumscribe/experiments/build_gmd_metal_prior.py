"""Build a compact symbolic metal-arrangement prior from Groove MIDI Dataset.

Training source:
  Google Magenta Groove MIDI Dataset v1.0.0, train split only, 4/4 only.
  License: CC BY 4.0.

No DruMaster chart.mid is read here. This creates a general symbolic prior for:
- metal class by 16th-note bar position
- metal class conditioned on concurrent kick/snare/tom
- continuation / switching of time-keeping state (hat vs ride)
- crash accent relation to downbeat and preceding tom/snare density
- pedal-hat relation to neighboring hand-hat pattern

The output contains only aggregate counts/probabilities, never source MIDI.
"""
from __future__ import annotations

import argparse,csv,json,math
from collections import Counter,defaultdict
from pathlib import Path
import mido

CLASSES=("hat","pedal_hat","ride","crash")
PITCH={
  22:"hat",26:"hat",42:"hat",46:"hat",
  44:"pedal_hat",
  51:"ride",53:"ride",59:"ride",
  49:"crash",52:"crash",55:"crash",57:"crash",
}
KICK={35,36};SNARE={37,38,39,40};TOM={41,43,45,47,48,50,58}

def add_nested(d,key,cls,w=1):
    if key not in d:d[key]=Counter()
    d[key][cls]+=w

def smooth(counter,alpha=.8):
    z=sum(counter.values())+alpha*len(CLASSES)
    return {c:(counter.get(c,0)+alpha)/z for c in CLASSES}

def dominant_bar(events,bar):
    c=Counter(g for slot,g in events if slot//16==bar and g in ("hat","ride"))
    if not c:return "none"
    a,b=c.most_common(1)[0]
    return a if b>=2 else "none"

def parse_midi(path):
    mid=mido.MidiFile(path)
    tpb=mid.ticks_per_beat
    events=[];tick=0
    merged=mido.merge_tracks(mid.tracks)
    for msg in merged:
        tick+=msg.time
        if msg.type!="note_on" or msg.velocity<=0:continue
        p=int(msg.note)
        slot=int(round(tick/(tpb/4)))
        if p in PITCH:events.append((slot,PITCH[p],p))
        elif p in KICK:events.append((slot,"kick",p))
        elif p in SNARE:events.append((slot,"snare",p))
        elif p in TOM:events.append((slot,"tom",p))
    return events

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--gmd-root",required=True)
    ap.add_argument("--output",default="drumscribe/models/gmd-metal-prior.json")
    args=ap.parse_args()
    root=Path(args.gmd_root)
    info=next(iter(root.rglob("info.csv")),None)
    if info is None:raise SystemExit("info.csv not found")

    slot=defaultdict(Counter);context=defaultdict(Counter);prev_state=defaultdict(Counter)
    transition=defaultdict(Counter);accent=defaultdict(Counter);pedal=defaultdict(Counter)
    global_c=Counter();styles=Counter();files=0;hits=0

    with info.open(newline="",encoding="utf-8") as f:
      for row in csv.DictReader(f):
        if row.get("split")!="train":continue
        if row.get("time_signature") not in ("4-4","4/4"):continue
        rel=row.get("midi_filename","")
        p=root/rel
        if not p.exists():
            matches=list(root.rglob(Path(rel).name))
            if not matches:continue
            p=matches[0]
        try:ev=parse_midi(p)
        except Exception:continue
        if not ev:continue
        files+=1;styles[row.get("style","unknown")]+=1

        # Presence maps at quantized 16th slots.
        at=defaultdict(set)
        metal=[]
        for s,g,_ in ev:
            at[s].add(g)
            if g in CLASSES:metal.append((s,g))
        if not metal:continue

        bars=max(s for s,_ in metal)//16+1
        states=[dominant_bar(metal,b) for b in range(bars)]

        prev_metal=None
        for s,g in metal:
            hits+=1;global_c[g]+=1
            pos=s%16;bar=s//16
            add_nested(slot,str(pos),g)

            ctx=[]
            for name in ("kick","snare","tom"):
                if name in at[s]:ctx.append(name)
            ctxkey="+".join(ctx) if ctx else "none"
            add_nested(context,f"{pos}|{ctxkey}",g)

            ps=states[bar-1] if bar>0 else "none"
            add_nested(prev_state,ps,g)

            if prev_metal is not None:
                pslt,pg=prev_metal
                delta=min(16,max(0,s-pslt))
                add_nested(transition,f"{pg}|d{delta}",g)
            prev_metal=(s,g)

            # Structural accent features: preceding 1 beat activity.
            prior=[x for q in range(max(0,s-4),s) for x in at.get(q,set())]
            tom_n=sum(x=="tom" for x in prior)
            sn_n=sum(x=="snare" for x in prior)
            fillish=("tom" if tom_n>=2 else "snare" if sn_n>=2 else "none")
            head="head" if pos==0 else "nonhead"
            add_nested(accent,f"{head}|{fillish}",g)

            # Pedal relation to hand-hat around +/- eighth note.
            if g=="pedal_hat":
                near_hat=any("hat" in at.get(q,set()) for q in (s-2,s-1,s+1,s+2))
                same_hat="hat" in at[s]
                add_nested(pedal,f"near{int(near_hat)}|same{int(same_hat)}",g)
            elif g=="hat":
                near_ped=any("pedal_hat" in at.get(q,set()) for q in (s-2,s-1,s+1,s+2))
                add_nested(pedal,f"near{int(near_ped)}|same{int('pedal_hat' in at[s])}",g)

    out={
      "schema":1,
      "source":{
        "name":"Groove MIDI Dataset v1.0.0",
        "split":"train",
        "timeSignature":"4/4",
        "license":"CC BY 4.0",
        "url":"https://magenta.tensorflow.org/datasets/groove"
      },
      "classes":list(CLASSES),
      "files":files,"metalHits":hits,
      "globalCounts":dict(global_c),
      "globalProb":smooth(global_c),
      "styleFileCounts":dict(styles),
      "slot16":{k:smooth(v) for k,v in sorted(slot.items(),key=lambda kv:int(kv[0]))},
      "context":{k:smooth(v) for k,v in context.items()},
      "previousBarState":{k:smooth(v) for k,v in prev_state.items()},
      "transition":{k:smooth(v) for k,v in transition.items()},
      "accent":{k:smooth(v) for k,v in accent.items()},
      "pedalRelation":{k:smooth(v) for k,v in pedal.items()},
    }
    op=Path(args.output);op.parent.mkdir(parents=True,exist_ok=True)
    op.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
      "files":files,"metalHits":hits,"globalCounts":dict(global_c),
      "slot0":out["slot16"].get("0"),"prevHat":out["previousBarState"].get("hat"),
      "prevRide":out["previousBarState"].get("ride"),
      "accentHeadTom":out["accent"].get("head|tom"),
    },ensure_ascii=False,indent=2))

if __name__=="__main__":main()
