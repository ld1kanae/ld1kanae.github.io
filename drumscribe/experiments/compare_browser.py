import json
from collections import Counter
from pathlib import Path
import importlib.util

root=Path(".")
spec=importlib.util.spec_from_file_location("ev", root/"drumscribe/experiments/evaluate_v2.py")
ev=importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)

songs=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
out={"schema":1,"source":"real browser-generated MIDI","songs":{}}
tot=Counter()

for song in songs:
    folder=root/"DruMaster/songs"/song
    meta=json.loads((folder/"song.json").read_text())
    shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
    pred=ev.midi_events(root/"drumscribe/experiments/generated-v2-browser"/f"{song}.mid")
    truth=ev.midi_events(folder/"chart.mid")
    sc=ev.score(pred,truth,shift)
    cf=ev.confusion(pred,truth,shift)
    sc["count_ratio"]=ev.count_ratios(sc)
    sc["confusion"]=cf
    out["songs"][song]=sc
    tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
               kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
    for g,d in sc["by_group"].items():
        tot[f"{g}_tp"]+=d["tp"]; tot[f"{g}_pred"]+=d["predicted"]; tot[f"{g}_ref"]+=d["reference"]

tp,n,m=tot["tp"],tot["predicted"],tot["reference"]
summary={"tp":tp,"predicted":n,"reference":m,
         "precision":round(tp/n,3) if n else 0,
         "recall":round(tp/m,3) if m else 0,
         "f1":round(2*tp/(n+m),3) if n+m else 0,
         "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
         "by_group":{}}
for g in ev.ORDER:
    a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
    summary["by_group"][g]={"tp":a,"predicted":b,"reference":c,
                            "count_ratio":round(b/c,3) if c else None}
out["summary"]=summary
(root/"drumscribe/experiments/results-v2-browser.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(summary,ensure_ascii=False,indent=2))
