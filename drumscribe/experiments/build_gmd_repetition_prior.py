"""Build a repetition-aware symbolic metal language model from GMD.

Inspired by tatum-level drum transcription with repetition-aware symbolic
language models. Uses GMD v1.0.0 train split, 4/4 only.

At every 16th-note slot, model one dominant metal token:
  none, hat, pedal_hat, ride, crash

Conditioning variables:
- slot within bar (0..15)
- previous metal token
- metal token two slots back
- same slot in previous bar (16 slots back)
- simultaneous body context: kick/snare/tom combination
- style family: all vs rock_family

Several backoff tables are stored so browser inference can interpolate rather
than rely on sparse exact keys.

No DruMaster data is read.
"""
from __future__ import annotations
import argparse,csv,json
from collections import Counter,defaultdict
from pathlib import Path
import mido

TOKENS=("none","hat","pedal_hat","ride","crash")
METAL_PITCH={
  22:"hat",26:"hat",42:"hat",46:"hat",
  44:"pedal_hat",
  51:"ride",53:"ride",59:"ride",
  49:"crash",52:"crash",55:"crash",57:"crash",
}
KICK={35,36};SNARE={37,38,39,40};TOM={41,43,45,47,48,50,58}

def family(style):
    p=(style or "").split("/")[0]
    return "rock_family" if p in ("rock","punk") else "other"

def token_of(gs):
    # Structural cymbals have priority if simultaneous. Such collisions are
    # uncommon but this yields a single-state LM without losing accents.
    for g in ("crash","ride","pedal_hat","hat"):
        if g in gs:return g
    return "none"

def ctx_of(gs):
    xs=[]
    if "kick" in gs:xs.append("kick")
    if "snare" in gs:xs.append("snare")
    if "tom" in gs:xs.append("tom")
    return "+".join(xs) if xs else "none"

def parse(path):
    mid=mido.MidiFile(path);tpb=mid.ticks_per_beat;tick=0;at=defaultdict(set);maxslot=0
    for msg in mido.merge_tracks(mid.tracks):
        tick+=msg.time
        if msg.type!="note_on" or msg.velocity<=0:continue
        slot=max(0,int(round(tick/(tpb/4))));p=int(msg.note);maxslot=max(maxslot,slot)
        if p in METAL_PITCH:at[slot].add(METAL_PITCH[p])
        elif p in KICK:at[slot].add("kick")
        elif p in SNARE:at[slot].add("snare")
        elif p in TOM:at[slot].add("tom")
    return at,maxslot

def smooth(c,alpha=.35):
    z=sum(c.values())+alpha*len(TOKENS)
    return {t:(c.get(t,0)+alpha)/z for t in TOKENS}

def keep_tables(raw,min_count=3):
    out={}
    for k,c in raw.items():
        if sum(c.values())>=min_count:
            out[k]={"n":sum(c.values()),"p":smooth(c)}
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--gmd-root",required=True);ap.add_argument("--output",required=True)
    a=ap.parse_args();root=Path(a.gmd_root);info=next(iter(root.rglob("info.csv")),None)
    if info is None:raise SystemExit("info.csv not found")

    names=("full","prevbar_ctx","prev_ctx","prev2_ctx","prevbar","prev","ctx","slot","global")
    tabs={scope:{name:defaultdict(Counter) for name in names} for scope in ("all","rock_family")}
    file_counts=Counter();slot_counts=Counter()

    with info.open(newline="",encoding="utf-8") as f:
      for row in csv.DictReader(f):
        if row.get("split")!="train" or row.get("time_signature") not in ("4-4","4/4"):continue
        rel=row.get("midi_filename","");p=root/rel
        if not p.exists():
            m=list(root.rglob(Path(rel).name))
            if not m:continue
            p=m[0]
        try:at,maxslot=parse(p)
        except Exception:continue
        fam=family(row.get("style",""));scopes=["all"]+(["rock_family"] if fam=="rock_family" else [])
        file_counts["all"]+=1
        if fam=="rock_family":file_counts["rock_family"]+=1
        hist=[]
        for s in range(maxslot+1):
            tok=token_of(at.get(s,set()));ctx=ctx_of(at.get(s,set()));pos=s%16
            prev=hist[-1] if len(hist)>=1 else "none"
            prev2=hist[-2] if len(hist)>=2 else "none"
            prevbar=hist[-16] if len(hist)>=16 else "none"
            for scope in scopes:
                T=tabs[scope]
                T["full"][f"{pos}|{prev}|{prev2}|{prevbar}|{ctx}"][tok]+=1
                T["prevbar_ctx"][f"{pos}|{prevbar}|{ctx}"][tok]+=1
                T["prev_ctx"][f"{pos}|{prev}|{ctx}"][tok]+=1
                T["prev2_ctx"][f"{pos}|{prev}|{prev2}|{ctx}"][tok]+=1
                T["prevbar"][f"{pos}|{prevbar}"][tok]+=1
                T["prev"][f"{pos}|{prev}"][tok]+=1
                T["ctx"][f"{pos}|{ctx}"][tok]+=1
                T["slot"][str(pos)][tok]+=1
                T["global"]["all"][tok]+=1
                slot_counts[f"{scope}:{tok}"]+=1
            hist.append(tok)

    out={"schema":1,
         "source":{"dataset":"Groove MIDI Dataset v1.0.0","split":"train","timeSignature":"4/4","license":"CC BY 4.0"},
         "tokens":list(TOKENS),"fileCounts":dict(file_counts),"slotCounts":dict(slot_counts),"scopes":{}}
    for scope,T in tabs.items():
        out["scopes"][scope]={}
        for name,d in T.items():
            out["scopes"][scope][name]=keep_tables(d,1 if name in ("slot","global") else 3)
    op=Path(a.output);op.parent.mkdir(parents=True,exist_ok=True)
    op.write_text(json.dumps(out,ensure_ascii=False,separators=(",",":"))+"\n")
    # concise diagnostics
    def p(scope,name,key):
        return out["scopes"][scope][name].get(key,{}).get("p",{})
    print(json.dumps({
      "fileCounts":out["fileCounts"],
      "allGlobal":p("all","global","all"),
      "rockGlobal":p("rock_family","global","all"),
      "allSlot0PrevBarCrash":p("all","prevbar","0|crash"),
      "rockSlot0PrevBarHat":p("rock_family","prevbar","0|hat"),
      "tableSizes":{scope:{n:len(v) for n,v in out["scopes"][scope].items()} for scope in out["scopes"]}
    },ensure_ascii=False,indent=2))

if __name__=="__main__":main()
