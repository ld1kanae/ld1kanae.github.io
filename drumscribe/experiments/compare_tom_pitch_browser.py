"""Fine-grained tom-pitch score for fresh browser output.

Tom onset matching is one-to-one at +/-80 ms, exactly like the main evaluator.
Reference chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
SONGS=("arcaround","diamondvirgin","kaiju","nanairo","ray")
TOL=.080

def tier(n):
    n=int(n)
    if n in (41,43):return 41
    if n==45:return 45
    if n in (47,48):return 47
    if n==50:return 50
    return n

def match(pred,ref,shift):
    # pred times are already converted back to audio-local coordinates.
    rr=[(t+shift,int(note)) for t,g,note in ref if g=="tom"]
    pp=[(t,int(note)) for t,g,note in pred if g=="tom"]
    used=set();pairs=[]
    for pt,pn in sorted(pp):
        choices=[i for i,(rt,rn) in enumerate(rr) if i not in used and abs(rt-pt)<=TOL]
        if not choices:continue
        j=min(choices,key=lambda i:abs(rr[i][0]-pt));used.add(j)
        rt,rn=rr[j];pairs.append((pt,pn,rt,rn))
    return pp,rr,pairs

def metrics(pairs):
    if not pairs:return {"matched":0,"exact":None,"tier4":None}
    exact=sum(pn==rn for _,pn,_,rn in pairs)/len(pairs)
    t4=sum(tier(pn)==tier(rn) for _,pn,_,rn in pairs)/len(pairs)
    conf=Counter((tier(rn),tier(pn)) for _,pn,_,rn in pairs)
    return {"matched":len(pairs),"exact":exact,"tier4":t4,
            "confusion":{f"{a}->{b}":v for (a,b),v in sorted(conf.items())}}

def main():
    out={"schema":1,"toleranceSec":TOL,"songs":{}}
    allpairs=[]
    for song in SONGS:
        folder=ROOT/"DruMaster/songs"/song
        meta=json.loads((folder/"song.json").read_text())
        side=json.loads((EXP/"generated-v2-browser"/f"{song}.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        export=float(side.get("exportOffsetSec",0) or 0)
        pred0=ev.midi_events(EXP/"generated-v2-browser"/f"{song}.mid")
        pred=[(t-export,g,n) for t,g,n in pred0]
        ref=ev.midi_events(folder/"chart.mid")
        pp,rr,pairs=match(pred,ref,shift);allpairs.extend(pairs)
        m=metrics(pairs);m.update({"predictedTom":len(pp),"referenceTom":len(rr)})
        out["songs"][song]=m
    out["summary"]=metrics(allpairs)
    out["summary"]["note45BaselineOnMatched"]=(
      sum(tier(rn)==45 for _,_,_,rn in allpairs)/len(allpairs) if allpairs else None
    )
    (EXP/"results-tom-pitch-browser.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(out["summary"],ensure_ascii=False,indent=2))

if __name__=="__main__":main()
