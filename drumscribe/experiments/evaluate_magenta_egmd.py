"""Score Magenta E-GMD Onsets & Frames output against DrumScribe references.

The Magenta model is external/pretrained; chart.mid is scoring-only here.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";OUT=EXP/"generated-magenta-egmd"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def main():
    scores={};tot=Counter()
    for song in SONGS:
        candidates=[
          OUT/f"{song}.mid",
          OUT/f"{song}.midi",
          OUT/f"{song}.wav.midi",
          OUT/f"{song}.wav.mid",
        ]
        p=next((x for x in candidates if x.exists()),None)
        if p is None:raise SystemExit(f"missing Magenta output for {song}")
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        sc=ev.score(pred,truth,shift);sc["confusion"]=ev.confusion(pred,truth,shift)
        scores[song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    s={"tp":tot["tp"],"predicted":tot["predicted"],"reference":tot["reference"],
       "precision":tot["tp"]/tot["predicted"] if tot["predicted"] else 0,
       "recall":tot["tp"]/tot["reference"] if tot["reference"] else 0,
       "f1":2*tot["tp"]/(tot["predicted"]+tot["reference"]) if tot["predicted"]+tot["reference"] else 0,
       "by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    report={"schema":1,"model":"Magenta E-GMD Onsets & Frames pretrained checkpoint","summary":s,"songs":scores}
    (EXP/"results-magenta-egmd.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(s,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
