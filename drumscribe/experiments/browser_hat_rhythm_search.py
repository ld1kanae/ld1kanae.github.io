"""Fast browser-only hi-hat rhythm filter search.

Uses only the real browser predicted MIDI plus its audio-only BPM. No audio
features or song-specific branches. chart.mid is scoring-only.

The filter targets hats coincident with predicted kick/snare, but rescues
events that participate in a repeating beat/2 or beat/4 pattern.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def load(song):
    side=json.loads((EXP/"generated-v2-browser"/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    pred=[(t-off,g,p) for t,g,p in ev.midi_events(EXP/"generated-v2-browser"/f"{song}.mid")]
    return pred,side

def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def support(hats,t,beat,tol=.04):
    best=0
    for step in (beat/4,beat/2,beat):
        n=0
        for k in (-2,-1,1,2):
            target=t+k*step
            if near(hats,target,tol):n+=1
        best=max(best,n)
    return best

def filt(pred,side,scope,window,gate,rescue,tol):
    hats=sorted(t for t,g,*_ in pred if g=="hat")
    kicks=sorted(t for t,g,*_ in pred if g=="kick")
    snares=sorted(t for t,g,*_ in pred if g=="snare")
    beat=60/float(side["bpm"])
    conflicts=[]
    for t in hats:
        c=near(kicks,t,window) or (scope=="both" and near(snares,t,window))
        if c:conflicts.append(t)
    frac=len(conflicts)/max(1,len(hats))
    active=frac>=gate
    out=[];removed=0;rescued=0
    for row in pred:
        t,g,*_=row
        if g!="hat" or not active:
            out.append(row);continue
        c=near(kicks,t,window) or (scope=="both" and near(snares,t,window))
        if not c:
            out.append(row);continue
        rep=support(hats,t,beat,tol)
        if rep>=rescue:
            out.append(row);rescued+=1
        else:
            removed+=1
    return out,{"hat_count":len(hats),"conflicts":len(conflicts),"conflict_fraction":frac,"active":active,"removed":removed,"rescued":rescued}

def summary(scores):
    tot=Counter()
    for sc in scores.values():
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,r=tot["tp"],tot["predicted"],tot["reference"]
    out={"tp":tp,"predicted":n,"reference":r,"precision":tp/n if n else 0,"recall":tp/r if r else 0,
         "f1":2*tp/(n+r) if n+r else 0,"by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        out["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,
          "recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    return out

def evaluate(cache,cfg):
    scope,window,gate,rescue,tol=cfg
    scores={};diag={}
    for song,(pred,side) in cache.items():
        p,d=filt(pred,side,*cfg);diag[song]=d
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        scores[song]=ev.score(p,truth,shift)
    return summary(scores),diag

def main():
    cache={s:load(s) for s in SONGS}
    baseline,_=evaluate(cache,("kick",.02,2.0,99,.04))
    bh=baseline["by_group"]["hat"]
    rows=[]
    for scope in ("kick","both"):
      for window in (.015,.020,.025,.030,.035,.045):
       for gate in (0,.20,.25,.30,.33,.36,.40,.45,.50,.60):
        for rescue in (1,2,3,4):
         for tol in (.025,.035,.045,.055):
          cfg=(scope,window,gate,rescue,tol)
          s,d=evaluate(cache,cfg);h=s["by_group"]["hat"]
          eligible=h["recall"]>=max(.60,bh["recall"]-.16)
          objective=s["f1"]+.20*h["f1"]-.025*abs((h["count_ratio"] or 1)-1)
          rows.append((eligible,objective,s["f1"],h["f1"],cfg,s,d))
    rows.sort(key=lambda x:(x[0],x[1],x[2],x[3]),reverse=True)
    top=[]
    for ok,obj,of1,hf1,cfg,s,d in rows[:40]:
        top.append({"eligible":ok,"objective":obj,
          "config":{"scope":cfg[0],"window":cfg[1],"song_gate":cfg[2],"rescue":cfg[3],"support_tolerance":cfg[4]},
          "summary":s,"diagnostics":d})
    out={"schema":1,"baseline":baseline,"top":top}
    (EXP/"results-browser-hat-rhythm-search.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps({"overall":baseline["f1"],"hat":bh},ensure_ascii=False),flush=True)
    for x in top[:12]:
        print("TOP",json.dumps({"cfg":x["config"],"overall":x["summary"]["f1"],"hat":x["summary"]["by_group"]["hat"],"diag":x["diagnostics"]},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
