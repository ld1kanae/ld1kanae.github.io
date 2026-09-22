"""Temporal-decay cymbal reclassification for the current browser output.

Motivation: crash/ride cymbals have longer temporal envelopes than closed
hi-hats. Prediction uses only the drum audio, current browser MIDI, estimated
BPM/bar phase, and fixed timing rules. chart.mid is scoring-only.

Stage 1 relabels existing hat/crash/ride events using post-onset decay.
Stage 2 optionally adds long-decay high-band onsets not already represented.
"""
from __future__ import annotations
import importlib.util,json,bisect,math
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.signal import find_peaks

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

specm=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(specm);specm.loader.exec_module(ev)

def near(xs,t,w):
    if not xs:return False
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def rows(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")],side

def periodic(times,t,bpm,w=.06):
    if len(times)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(near(times,t+k*step,w) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def head(t,bpm,phase):
    beat=60/bpm;bar=4*beat;x=(t-phase)%bar
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

def env_features(spec,t):
    freqs=np.arange(spec.shape[0])*ev.SR/ev.FFT
    high=spec[(freqs>=1800)&(freqs<=5400)].sum(axis=0)
    upper=spec[(freqs>=3200)&(freqs<=5400)].sum(axis=0)
    mid=spec[(freqs>=500)&(freqs<1800)].sum(axis=0)
    fr=int(round(t*ev.SR/ev.HOP));n=len(high)
    def mean(a,b,x=high):
        aa=max(0,fr+a);bb=min(n,fr+b)
        return float(np.mean(x[aa:bb])) if bb>aa else 0.
    def mx(a,b,x=high):
        aa=max(0,fr+a);bb=min(n,fr+b)
        return float(np.max(x[aa:bb])) if bb>aa else 0.
    pre=mean(-12,-3);on=mx(-1,3)
    amp=max(on-pre,1e-7)
    tail1=max(0,mean(4,11)-pre)/amp      # 40-110 ms
    tail2=max(0,mean(11,21)-pre)/amp     # 110-210 ms
    tail3=max(0,mean(21,36)-pre)/amp     # 210-360 ms
    upper_on=mx(-1,3,upper);upper_pre=mean(-12,-3,upper)
    upper_tail=max(0,mean(11,26,upper)-upper_pre)/max(upper_on-upper_pre,1e-7)
    mid_on=mx(-1,3,mid);mid_pre=mean(-12,-3,mid)
    mid_tail=max(0,mean(11,26,mid)-mid_pre)/max(mid_on-mid_pre,1e-7)
    return {"tail1":tail1,"tail2":tail2,"tail3":tail3,
            "upper_tail":upper_tail,"mid_tail":mid_tail,
            "onset":on,"pre":pre}

def prepare(song):
    pred,side=rows(song);bpm=float(side["bpm"]);phase=float(side["barPhaseSec"])
    audio=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3");sp=ev.spectrum(audio)
    plates=sorted((t,g) for t,g in pred if g in ("hat","ride","crash"))
    times=[t for t,_ in plates]
    feats=[]
    for t,g in plates:
        f=env_features(sp,t)
        f.update({"t":t,"orig":g,"periodic":periodic(times,t,bpm),"head":head(t,bpm,phase)})
        feats.append(f)
    # loose raw high-energy onset pool for stage2
    freqs=np.arange(sp.shape[0])*ev.SR/ev.FFT
    hi=sp[(freqs>=1800)&(freqs<=5400)].sum(axis=0)
    # novelty using 2-frame difference then local normalization
    rise=np.maximum(hi-np.pad(hi[:-2],(2,0)),0)
    q=float(np.percentile(rise,92))
    p,_=find_peaks(rise,distance=max(1,int(.045*ev.SR/ev.HOP)),prominence=max(1e-9,q*.08))
    raw=[]
    for fr in p:
        if rise[fr]<q*.35:continue
        t=fr*ev.HOP/ev.SR
        if near(times,t,.04):continue
        f=env_features(sp,t);f.update({"t":t,"periodic":0.,"head":head(t,bpm,phase),"novelty":float(rise[fr]/(q+1e-9))})
        raw.append(f)
    rt=[r["t"] for r in raw]
    for f in raw:f["periodic"]=periodic(rt,f["t"],bpm)

    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth_by={g:sorted(t+shift for t,gg,*_ in truth if gg==g) for g in ev.ORDER}
    fixed={g:sorted(t for t,gg in pred if gg==g) for g in ev.ORDER if g not in ("hat","ride","crash")}
    return {"bpm":bpm,"phase":phase,"pred":pred,"plates":feats,"raw":raw,"truth":truth_by,"fixed":fixed}

def classify_plate(f,cfg):
    # crash wins only near a bar head; otherwise long periodic tails are ride.
    long=max(f["tail2"],f["tail3"],.7*f["upper_tail"])
    if f["head"]<=cfg["crash_head"] and long>=cfg["crash_tail"] and f["tail1"]>=cfg["crash_t1"]:
        return "crash"
    if long>=cfg["ride_tail"] and f["tail1"]>=cfg["ride_t1"] and f["periodic"]>=cfg["ride_per"]:
        return "ride"
    return "hat"

def build(d,cfg):
    pred={g:list(v) for g,v in d["fixed"].items()}
    pred.update({"hat":[],"ride":[],"crash":[]})
    for f in d["plates"]:
        g=classify_plate(f,cfg)
        pred[g].append(f["t"])
    added={"ride":0,"crash":0}
    if cfg["raw_add"]:
        for f in d["raw"]:
            long=max(f["tail2"],f["tail3"],.7*f["upper_tail"])
            g=None
            if f["head"]<=cfg["raw_crash_head"] and long>=cfg["raw_crash_tail"] and f["novelty"]>=cfg["raw_novelty"]:
                g="crash"
            elif long>=cfg["raw_ride_tail"] and f["periodic"]>=cfg["raw_ride_per"] and f["novelty"]>=cfg["raw_novelty"]:
                g="ride"
            if g:
                pred[g].append(f["t"]);added[g]+=1
    for g in ("hat","ride","crash"):
        xs=sorted(pred[g]);ded=[];last=-999.
        for t in xs:
            if t-last>=.04:ded.append(t);last=t
        pred[g]=ded
    return pred,added

def evaluate(data,cfg):
    tot=Counter();songs={}
    for song,d in data.items():
        pred,added=build(d,cfg)
        st={};tp=pr=rf=0
        for g in ev.ORDER:
            pp=pred.get(g,[]);tt=d["truth"][g];a=match(pp,tt)
            st[g]={"tp":a,"predicted":len(pp),"reference":len(tt)}
            tot.update({f"{g}_tp":a,f"{g}_pred":len(pp),f"{g}_ref":len(tt)})
            tp+=a;pr+=len(pp);rf+=len(tt)
        songs[song]={"f1":2*tp/(pr+rf),"added":added,
                     "hat":st["hat"],"ride":st["ride"],"crash":st["crash"]}
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
    data={s:prepare(s) for s in SONGS}
    # Baseline-like policy: thresholds so high that every existing plate becomes hat
    # would destroy current crash/ride. Instead baseline is scored directly.
    base_tot=Counter();base_songs={}
    for song,d in data.items():
        pp={g:sorted(t for t,gg in d["pred"] if gg==g) for g in ev.ORDER}
        tp=pr=rf=0;st={}
        for g in ev.ORDER:
            a=match(pp[g],d["truth"][g]);st[g]={"tp":a,"predicted":len(pp[g]),"reference":len(d["truth"][g])}
            base_tot.update({f"{g}_tp":a,f"{g}_pred":len(pp[g]),f"{g}_ref":len(d["truth"][g])})
            tp+=a;pr+=len(pp[g]);rf+=len(d["truth"][g])
        base_tot.update(tp=tp,pred=pr,ref=rf);base_songs[song]={"f1":2*tp/(pr+rf),**{g:st[g] for g in ("hat","ride","crash")}}
    def bstat(g):
        a,b,c=base_tot[f"{g}_tp"],base_tot[f"{g}_pred"],base_tot[f"{g}_ref"]
        return {"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0}
    baseline={"f1":2*base_tot["tp"]/(base_tot["pred"]+base_tot["ref"]),
              "hat":bstat("hat"),"ride":bstat("ride"),"crash":bstat("crash"),"songs":base_songs}

    stage1=[]
    for rt in (.06,.10,.15,.22,.32,.45):
      for r1 in (.08,.15,.25,.40):
       for rp in (.50,.75,1.0):
        for ct in (.08,.14,.22,.32,.45):
         for c1 in (.10,.20,.35):
          for ch in (.06,.10,.15,.22):
           cfg={"ride_tail":rt,"ride_t1":r1,"ride_per":rp,
                "crash_tail":ct,"crash_t1":c1,"crash_head":ch,
                "raw_add":False,"raw_ride_tail":99,"raw_ride_per":1,
                "raw_crash_tail":99,"raw_crash_head":0,"raw_novelty":99}
           sc=evaluate(data,cfg)
           hatdrop=baseline["hat"]["f1"]-sc["hat"]["f1"]
           eligible=sc["f1"]>=baseline["f1"]-.004 and hatdrop<=.05
           obj=sc["f1"]+.04*sc["ride"]["f1"]+.04*sc["crash"]["f1"]-.025*max(0,hatdrop)
           stage1.append({"eligible":eligible,"objective":obj,"config":cfg,"summary":sc})
    stage1.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)
    best=stage1[0]["config"]

    stage2=[]
    for rtail in (.08,.14,.22,.32,.45):
      for rper in (.50,.75,1.0):
       for ctail in (.10,.18,.28,.40):
        for chead in (.06,.10,.16):
         for nov in (.5,.8,1.1,1.5):
          cfg={**best,"raw_add":True,"raw_ride_tail":rtail,"raw_ride_per":rper,
               "raw_crash_tail":ctail,"raw_crash_head":chead,"raw_novelty":nov}
          sc=evaluate(data,cfg)
          hatdrop=baseline["hat"]["f1"]-sc["hat"]["f1"]
          eligible=sc["f1"]>=baseline["f1"]-.004 and hatdrop<=.05
          obj=sc["f1"]+.04*sc["ride"]["f1"]+.04*sc["crash"]["f1"]-.025*max(0,hatdrop)
          stage2.append({"eligible":eligible,"objective":obj,"config":cfg,"summary":sc})
    stage2.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)

    report={"schema":1,"description":"Temporal-decay cymbal search; chart scoring-only.",
      "baseline":baseline,"relabel_top":stage1[:40],"raw_add_top":stage2[:40],
      "feature_quantiles":{s:{
        "tail2":[float(np.quantile([f["tail2"] for f in d["plates"]],q)) for q in (.25,.5,.75,.9)],
        "tail3":[float(np.quantile([f["tail3"] for f in d["plates"]],q)) for q in (.25,.5,.75,.9)],
        "raw_count":len(d["raw"])
      } for s,d in data.items()}}
    (EXP/"results-browser-cymbal-decay.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    for x in report["relabel_top"][:10]:print("RELABEL",json.dumps(x,ensure_ascii=False),flush=True)
    for x in report["raw_add_top"][:10]:print("RAW",json.dumps(x,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
