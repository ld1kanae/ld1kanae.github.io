"""GMD-arrangement-aware hat -> crash reclassification search.

Prediction-only evidence:
- current real-browser hats and kick/snare/tom events
- browser BPM/bar phase
- fixed sample template similarities/high-band flux
- GMD general + rock-family symbolic priors
- preceding fill-like body activity

The held-out chart is scoring-only.
"""
from __future__ import annotations
import bisect,importlib.util,json,math
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GMD=json.loads((ROOT/"drumscribe/models/gmd-metal-prior.json").read_text())
STYLE=json.loads((ROOT/"drumscribe/models/gmd-metal-style-prior.json").read_text())

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
H=ev.ORDER.index("hat");C=ev.ORDER.index("crash")

def near(xs,t,w):
    if not xs:return False
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def rows(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")],side

def match(pred,truth,tol=.08):
    pred=sorted(pred);truth=sorted(truth);used=set();tp=0
    for x in pred:
        j=bisect.bisect_left(truth,x);opts=[k for k in (j-1,j,j+1) if 0<=k<len(truth) and k not in used]
        if not opts:continue
        k=min(opts,key=lambda q:abs(x-truth[q]))
        if abs(x-truth[k])<=tol:used.add(k);tp+=1
    return tp

def prepare(song,tmpl):
    rr,side=rows(song);bpm=float(side["bpm"]);phase=float(side["barPhaseSec"]);beat=60/bpm;bar=4*beat
    x=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3");sp=ev.spectrum(x);band,sim=ev.features(sp,tmpl)
    hats=sorted(t for t,g in rr if g=="hat");kicks=sorted(t for t,g in rr if g=="kick")
    snares=sorted(t for t,g in rr if g=="snare");toms=sorted(t for t,g in rr if g=="tom")
    feats=[]
    rock=STYLE["groups"]["rock_family"];allp=GMD
    for t in hats:
        fr=max(0,min(sim.shape[1]-1,int(round(t*ev.SR/ev.HOP))))
        xx=(t-phase)%bar;head=min(xx,bar-xx)/beat;slot=int(round(xx/(beat/4)))%16
        a=t-beat
        tn=sum(a<=z<t for z in toms);sn=sum(a<=z<t for z in snares)
        fill="tom" if tn>=2 else "snare" if sn>=2 else "none"
        key=("head" if slot==0 else "nonhead")+"|"+fill
        gp=allp["accent"].get(key,allp["globalProb"])
        rp=rock["slot16"].get(str(slot),rock["global"])
        # combine general fill/context and rock position prior
        odds=math.log(max(1e-6,gp.get("crash",1e-6))/max(1e-6,gp.get("hat",1e-6)))+math.log(max(1e-6,rp.get("crash",1e-6))/max(1e-6,rp.get("hat",1e-6)))
        hs=float(sim[H,fr]);cs=float(sim[C,fr])
        feats.append({"t":t,"head":head,"slot":slot,"fill":fill,"tom_n":tn,"snare_n":sn,
                      "prior_odds":odds,"crash_ratio":(cs+.04)/(hs+.04),
                      "crash_margin":cs-hs,"high":float(band[3,fr])})
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text());truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth_by={g:sorted(t+shift for t,gg,*_ in truth if gg==g) for g in ev.ORDER}
    return {"rows":rr,"feats":feats,"truth":truth_by}

def apply(d,cfg):
    chosen=[]
    for f in d["feats"]:
        if f["head"]>cfg["head"]:continue
        if f["prior_odds"]<cfg["prior"]:continue
        if f["crash_ratio"]<cfg["ratio"]:continue
        if f["high"]<cfg["high"]:continue
        if cfg["fill"]=="tom" and f["tom_n"]<1:continue
        if cfg["fill"]=="body" and f["tom_n"]+f["snare_n"]<1:continue
        chosen.append(f["t"])
    out=[]
    for t,g in d["rows"]:
        if g=="hat" and near(chosen,t,.025):out.append((t,"crash"))
        else:out.append((t,g))
    return out,chosen

def evaluate(data,cfg):
    tot=Counter();songs={}
    for song,d in data.items():
        pred,chosen=apply(d,cfg);st={};tp=pr=rf=0
        for g in ev.ORDER:
            pp=sorted(t for t,gg in pred if gg==g);tt=d["truth"][g];a=match(pp,tt)
            st[g]={"tp":a,"predicted":len(pp),"reference":len(tt)}
            tp+=a;pr+=len(pp);rf+=len(tt);tot.update({f"{g}_tp":a,f"{g}_pred":len(pp),f"{g}_ref":len(tt)})
        tot.update(tp=tp,pred=pr,ref=rf);songs[song]={"f1":2*tp/(pr+rf),"converted":len(chosen),"hat":st["hat"],"crash":st["crash"]}
    def stat(g):
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        return {"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0}
    return {"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],"precision":tot["tp"]/tot["pred"],
            "recall":tot["tp"]/tot["ref"],"f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),
            "hat":stat("hat"),"crash":stat("crash"),"songs":songs}

def main():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums");data={s:prepare(s,tmpl) for s in SONGS}
    baseline=evaluate(data,{"head":0,"prior":99,"ratio":99,"high":99,"fill":"none"})
    out=[]
    for head in (.04,.07,.10,.14,.20):
      for prior in (-4,-3,-2,-1,0):
       for ratio in (.75,.85,.95,1.05,1.15):
        for high in (0,.12,.22,.35,.55):
         for fill in ("none","body","tom"):
          cfg={"head":head,"prior":prior,"ratio":ratio,"high":high,"fill":fill}
          sc=evaluate(data,cfg);h=sc["hat"];cr=sc["crash"]
          hdrop=baseline["hat"]["f1"]-h["f1"]
          eligible=sc["f1"]>=baseline["f1"]-.0025 and hdrop<=.025
          obj=sc["f1"]+.07*cr["f1"]-.02*max(0,hdrop)
          out.append({"eligible":eligible,"objective":obj,"config":cfg,"summary":sc})
    out.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)
    report={"schema":1,"description":"GMD rock/fill-aware hat-to-crash reclass; chart scoring-only.","baseline":baseline,"top":out[:50]}
    (EXP/"results-browser-gmd-crash-reclass.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    for x in report["top"][:12]:print("TOP",json.dumps(x,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
