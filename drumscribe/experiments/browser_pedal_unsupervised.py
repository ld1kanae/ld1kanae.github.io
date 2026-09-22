"""Unsupervised browser pedal-hi-hat rule search.

Base: current real-browser MIDI on drumscribe-v2-eval.
Candidates: only current hand-hat events.

Prediction features:
- fixed DruMaster reference sample templates for hand hat vs pedal hat
- high/mid spectral-flux ratio
- periodic support in the candidate pedal stream

No classifier is trained on chart.mid. chart.mid is used only after each fixed
rule has produced predictions.
"""
from __future__ import annotations

import importlib.util, json, math
from pathlib import Path
from collections import Counter
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
HIDX=ev.ORDER.index("hat");PIDX=ev.ORDER.index("pedal_hat")


def browser_rows(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")]


def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)


def periodic(times,t,bpm):
    if len(times)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.065 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best


def prepare(song,tmpl):
    side=json.loads((BASE/f"{song}.json").read_text())
    events=browser_rows(song)
    audio=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3")
    spec=ev.spectrum(audio);band,sim=ev.features(spec,tmpl)
    hats=sorted(t for t,g in events if g=="hat")
    rows=[]
    for t in hats:
        fr=max(0,min(band.shape[1]-1,int(round(t*ev.SR/ev.HOP))))
        hs=float(sim[HIDX,fr]);ps=float(sim[PIDX,fr])
        b2=float(band[2,fr]);b3=float(band[3,fr])
        rows.append({
          "t":t,"hat_sim":hs,"pedal_sim":ps,
          "margin":ps-hs,
          "ratio":ps/(abs(hs)+1e-4),
          "high_ratio":b3/(b2+1e-5),
        })
    return {
      "bpm":float(side["bpm"]),
      "events":events,
      "hats":hats,
      "features":rows
    }


def build(d,margin,ratio,high_ratio,per_thr,mode):
    prelim=[]
    for f in d["features"]:
        template_ok=f["margin"]>=margin and f["ratio"]>=ratio and f["high_ratio"]>=high_ratio
        if template_ok:prelim.append(f["t"])

    chosen=[]
    for f in d["features"]:
        t=f["t"]
        if t not in prelim:continue
        per=periodic(prelim,t,d["bpm"])
        if mode=="template":
            keep=True
        elif mode=="periodic":
            keep=per>=per_thr
        else: # adaptive: very strong template evidence bypasses moderate periodicity
            strong=f["margin"]>=margin+.10 and f["ratio"]>=ratio+.15
            keep=per>=per_thr or (strong and per>=max(0,per_thr-.25))
        if keep:chosen.append(t)

    out=[]
    for t,g in d["events"]:
        if g=="hat" and near(chosen,t,.025):out.append((t,"pedal_hat"))
        else:out.append((t,g))
    return out,chosen


def evaluate(data,cfg):
    tot=Counter();songs={}
    for song,d in data.items():
        pred,chosen=build(d,**cfg)
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        sc=ev.score([(t,g,0,0) for t,g in pred],truth,shift)
        songs[song]={
          "converted":len(chosen),
          "overall_f1":2*sc["tp"]/(sc["predicted"]+sc["reference"]) if sc["predicted"]+sc["reference"] else 0,
          "hat":sc["by_group"]["hat"],
          "pedal_hat":sc["by_group"]["pedal_hat"],
        }
        tot.update(tp=sc["tp"],pred=sc["predicted"],ref=sc["reference"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    def part(g):
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        return {"tp":a,"predicted":b,"reference":c,
                "precision":a/b if b else 0,"recall":a/c if c else 0,
                "f1":2*a/(b+c) if b+c else 0}
    return {
      "tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
      "precision":tot["tp"]/tot["pred"] if tot["pred"] else 0,
      "recall":tot["tp"]/tot["ref"] if tot["ref"] else 0,
      "f1":2*tot["tp"]/(tot["pred"]+tot["ref"]) if tot["pred"]+tot["ref"] else 0,
      "hat":part("hat"),"pedal_hat":part("pedal_hat"),
      "songs":songs
    }


def main():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    data={s:prepare(s,tmpl) for s in SONGS}
    baseline=evaluate(data,{"margin":99,"ratio":99,"high_ratio":99,"per_thr":1,"mode":"template"})
    results=[]

    for mode in ("template","periodic","adaptive"):
      for margin in (-.15,-.10,-.05,0,.05,.10,.15,.20,.25):
       for ratio in (.75,.85,.95,1.0,1.05,1.10,1.20,1.30):
        for hr in (.0,.50,.75,1.0,1.25):
         for per in ((0,) if mode=="template" else (.25,.50,.75,1.0)):
          cfg={"margin":margin,"ratio":ratio,"high_ratio":hr,"per_thr":per,"mode":mode}
          sc=evaluate(data,cfg)
          # Do not buy pedal recall by destroying the hand-hat class.
          hat_drop=baseline["hat"]["f1"]-sc["hat"]["f1"]
          eligible=hat_drop<=.035 and sc["f1"]>=baseline["f1"]-.006
          pedal=sc["pedal_hat"]
          song_pedal=[v["pedal_hat"] for v in sc["songs"].values()]
          mean_song_pedal=np.mean([
              2*x["tp"]/(x["predicted"]+x["reference"])
              if x["predicted"]+x["reference"] else 0
              for x in song_pedal
          ])
          objective=sc["f1"]+.13*pedal["f1"]+.05*float(mean_song_pedal)-.08*max(0,hat_drop)
          results.append({
            "eligible":eligible,"objective":float(objective),"config":cfg,
            "summary":sc,"hat_drop":hat_drop,
          })
    results.sort(key=lambda x:(x["eligible"],x["objective"],x["summary"]["f1"]),reverse=True)
    report={
      "schema":1,
      "description":"Unsupervised fixed-rule pedal-hat search; chart scoring-only.",
      "baseline":baseline,
      "top":results[:50],
      "feature_diagnostics":{s:{
        "hat_count":len(d["features"]),
        "margin_quantiles":{str(q):float(np.quantile([f["margin"] for f in d["features"]],q)) for q in (.1,.25,.5,.75,.9)} if d["features"] else {},
        "ratio_quantiles":{str(q):float(np.quantile([f["ratio"] for f in d["features"]],q)) for q in (.1,.25,.5,.75,.9)} if d["features"] else {},
      } for s,d in data.items()}
    }
    (EXP/"results-browser-pedal-unsupervised.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"baseline":baseline,"top":results[:12],"features":report["feature_diagnostics"]},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
