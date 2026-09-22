"""Reclassify current browser hand-hat events to ride/crash using audio-only cues.

Base: current generated-v2-browser MIDI.
Prediction features only:
- fixed reference sample template similarities
- browser-estimated BPM/bar phase
- periodic support and local section density of current hats
- spectral high/mid ratios

chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util,json,bisect,math
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
H=ev.ORDER.index("hat");C=ev.ORDER.index("crash");R=ev.ORDER.index("ride")

def near(xs,t,w):
    if not xs:return False
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def browser_rows(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")]

def periodic(times,t,bpm,w=.06):
    if len(times)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(near(times,t+k*step,w) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def head_dist(t,bpm,phase):
    beat=60/bpm;bar=4*beat
    x=(t-phase)%bar
    return min(x,bar-x)/beat

def match(pred,truth,tol=.08):
    pred=sorted(pred);truth=sorted(truth);used=set();tp=0
    for x in pred:
        j=bisect.bisect_left(truth,x)
        opts=[k for k in (j-1,j,j+1) if 0<=k<len(truth) and k not in used]
        if not opts:continue
        k=min(opts,key=lambda q:abs(x-truth[q]))
        if abs(x-truth[k])<=tol:used.add(k);tp+=1
    return tp

def prepare(song,tmpl):
    side=json.loads((BASE/f"{song}.json").read_text())
    bpm=float(side["bpm"]);phase=float(side["barPhaseSec"])
    events=browser_rows(song)
    audio=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3")
    sp=ev.spectrum(audio);band,sim=ev.features(sp,tmpl)
    hats=sorted(t for t,g in events if g=="hat")
    rows=[]
    beat=60/bpm
    for t in hats:
        fr=max(0,min(band.shape[1]-1,int(round(t*ev.SR/ev.HOP))))
        hs=float(sim[H,fr]);cs=float(sim[C,fr]);rs=float(sim[R,fr])
        b2,b3=float(band[2,fr]),float(band[3,fr])
        local=sum(abs(x-t)<=4*beat for x in hats)
        rows.append({
          "t":t,"frame":fr,
          "ride_ratio":rs/(abs(hs)+1e-4),"crash_ratio":cs/(abs(hs)+1e-4),
          "ride_margin":rs-hs,"crash_margin":cs-hs,
          "high_mid":b3/(b2+.04),"high":b3,
          "periodic":periodic(hats,t,bpm),
          "local":local,
          "head":head_dist(t,bpm,phase)
        })
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth_by={g:sorted(t+shift for t,gg,*_ in truth if gg==g) for g in ev.ORDER}
    fixed={}
    for g in ev.ORDER:
        if g=="hat":continue
        fixed[g]=sorted(t for t,gg in events if gg==g)
    return dict(song=song,bpm=bpm,phase=phase,events=events,hats=hats,rows=rows,truth=truth_by,fixed=fixed)

def classify(d,cfg):
    ride=[];crash=[]
    for r in d["rows"]:
        if (r["ride_ratio"]>=cfg["ride_ratio"] and r["periodic"]>=cfg["ride_per"]
            and r["local"]>=cfg["ride_local"] and r["high_mid"]>=cfg["ride_hm"]
            and r["head"]>=cfg["ride_head_min"]):
            ride.append(r["t"]);continue
        if (r["crash_ratio"]>=cfg["crash_ratio"] and r["head"]<=cfg["crash_head"]
            and r["high"]>=cfg["crash_high"]):
            crash.append(r["t"])
    return ride,crash

def evaluate(data,cfg):
    tot=Counter();songs={}
    for song,d in data.items():
        ride,crash=classify(d,cfg)
        hand=[t for t in d["hats"] if not near(ride,t,.025) and not near(crash,t,.025)]
        pred={g:list(v) for g,v in d["fixed"].items()}
        pred["hat"]=hand
        pred["ride"]=sorted(pred.get("ride",[])+ride)
        pred["crash"]=sorted(pred.get("crash",[])+crash)
        # dedupe per class
        for g in ("ride","crash"):
            xs=pred[g];ded=[];last=-999.
            for t in xs:
                if t-last>=.04:ded.append(t);last=t
            pred[g]=ded
        st={};tp=pr=rf=0
        for g in ev.ORDER:
            pp=pred.get(g,[]);tt=d["truth"][g]
            a=match(pp,tt);st[g]={"tp":a,"predicted":len(pp),"reference":len(tt)}
            tp+=a;pr+=len(pp);rf+=len(tt)
            tot.update({f"{g}_tp":a,f"{g}_pred":len(pp),f"{g}_ref":len(tt)})
        songs[song]={"f1":2*tp/(pr+rf),"converted_ride":len(ride),"converted_crash":len(crash),
                     "ride":st["ride"],"crash":st["crash"],"hat":st["hat"]}
        tot.update(tp=tp,pred=pr,ref=rf)
    def stat(g):
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        return {"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,
                "recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0}
    return {"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
      "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],
      "f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),
      "hat":stat("hat"),"ride":stat("ride"),"crash":stat("crash"),"songs":songs}

def main():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    data={s:prepare(s,tmpl) for s in SONGS}
    basecfg={"ride_ratio":99,"ride_per":1,"ride_local":999,"ride_hm":99,"ride_head_min":0,
             "crash_ratio":99,"crash_head":0,"crash_high":99}
    baseline=evaluate(data,basecfg)
    results=[]
    # Stage A ride grid, crash disabled.
    for rr in (.85,.95,1.05,1.15,1.30):
      for per in (.50,.75,1.0):
       for loc in (3,5,8,12):
        for hm in (.45,.65,.85,1.10):
         for hmin in (0,.10,.20,.35):
          cfg={**basecfg,"ride_ratio":rr,"ride_per":per,"ride_local":loc,"ride_hm":hm,"ride_head_min":hmin}
          sc=evaluate(data,cfg)
          hatdrop=baseline["hat"]["f1"]-sc["hat"]["f1"]
          eligible=sc["f1"]>=baseline["f1"]-.004 and hatdrop<=.04
          obj=sc["f1"]+.055*sc["ride"]["f1"]-.03*max(0,hatdrop)
          results.append({"stage":"ride","eligible":eligible,"objective":obj,"config":cfg,"summary":sc})
    results.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)
    bestRide=results[0]["config"]

    crashres=[]
    for cr in (.85,.95,1.05,1.15,1.30):
      for hd in (.06,.10,.14,.20,.28):
       for hi in (.15,.25,.40,.60):
        cfg={**bestRide,"crash_ratio":cr,"crash_head":hd,"crash_high":hi}
        sc=evaluate(data,cfg)
        hatdrop=baseline["hat"]["f1"]-sc["hat"]["f1"]
        eligible=sc["f1"]>=baseline["f1"]-.004 and hatdrop<=.05
        obj=sc["f1"]+.04*sc["ride"]["f1"]+.045*sc["crash"]["f1"]-.025*max(0,hatdrop)
        crashres.append({"stage":"combined","eligible":eligible,"objective":obj,"config":cfg,"summary":sc})
    crashres.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)
    report={"schema":1,"description":"Audio-only hat->ride/crash reclassification search; chart scoring-only.",
            "baseline":baseline,"ride_top":results[:30],"combined_top":crashres[:50],
            "diagnostics":{s:{
              "hat_count":len(d["rows"]),
              "ride_ratio_q":[float(np.quantile([r["ride_ratio"] for r in d["rows"]],q)) for q in (.25,.5,.75,.9)] if d["rows"] else [],
              "periodic_q":[float(np.quantile([r["periodic"] for r in d["rows"]],q)) for q in (.25,.5,.75,.9)] if d["rows"] else []
            } for s,d in data.items()}}
    (EXP/"results-browser-hat-cymbal-reclass-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    for x in report["ride_top"][:10]:print("RIDE",json.dumps(x,ensure_ascii=False),flush=True)
    for x in report["combined_top"][:10]:print("COMBINED",json.dumps(x,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
