"""Diagnose GMD external acoustic classifier on current browser metal events.

The classifier is trained only on GMD rock/punk audio+MIDI. DruMaster chart.mid
is used only after predictions are complete to measure classification behavior.

This diagnostic:
- evaluates current label vs GMD acoustic argmax at the SAME detected onsets;
- reports matched-truth confusion for hat/pedal/ride/crash;
- separately reports hat->ride recovery potential (especially kaiju);
- tests conservative probability/margin gates without adding/removing onsets.
"""
from __future__ import annotations
import importlib.util,json,math,bisect
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
METAL=("hat","pedal_hat","ride","crash")

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
train=loadmod("train",EXP/"train_gmd_metal_acoustic.py")
MODEL=json.loads((ROOT/"drumscribe/models/gmd-metal-acoustic-logreg.json").read_text())
CLASSES=MODEL["classes"]
MEAN=np.asarray(MODEL["mean"],float);SCALE=np.asarray(MODEL["scale"],float)
COEF=np.asarray(MODEL["coef"],float);INTER=np.asarray(MODEL["intercept"],float)

def softmax(z):
    z=z-np.max(z);e=np.exp(z);return e/e.sum()

def predict_feat(f):
    x=(f-MEAN)/np.maximum(SCALE,1e-8)
    p=softmax(COEF@x+INTER)
    return {g:float(p[i]) for i,g in enumerate(CLASSES)}

def rows(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")],side

def truth_rows(song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    return sorted((t+shift,g) for t,g,*_ in ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid") if g in METAL)

def nearest_truth(truth,t,tol=.08):
    times=[x for x,g in truth];j=bisect.bisect_left(times,t)
    opts=[k for k in (j-1,j,j+1) if 0<=k<len(truth)]
    if not opts:return None
    k=min(opts,key=lambda q:abs(truth[q][0]-t))
    return truth[k][1] if abs(truth[k][0]-t)<=tol else None

def score_same_onsets(items,label_fn):
    # One-to-one class score at existing onset times. This is not the canonical
    # transcription score; it isolates classification from onset detection.
    c=Counter()
    for x in items:
        truth=x["truth"]
        if truth is None:continue
        pred=label_fn(x)
        c["matched"]+=1;c[f"truth:{truth}"]+=1;c[f"pred:{pred}"]+=1
        if pred==truth:c["correct"]+=1;c[f"correct:{truth}"]+=1
        c[f"{truth}->{pred}"]+=1
    return c

def canonical(song,base_rows,new_labels):
    # Preserve exact onset set; replace metal class only.
    pred=[]
    mi=0
    for t,g in base_rows:
        if g in METAL:
            pred.append((t,new_labels[mi],0,0));mi+=1
        else:pred.append((t,g,0,0))
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    return ev.score(pred,truth,shift)

def main():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    all_items=[];by_song={};base_rows={}
    for song in SONGS:
        rr,_=rows(song);base_rows[song]=rr;truth=truth_rows(song)
        x=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3")
        sp=ev.spectrum(x);band,sim=ev.features(sp,tmpl)
        items=[]
        for t,g in rr:
            if g not in METAL:continue
            f=train.feature(sp,band,sim,t)
            prob=predict_feat(f)
            items.append({"song":song,"time":t,"current":g,"prob":prob,
                          "argmax":max(prob,key=prob.get),"truth":nearest_truth(truth,t)})
        by_song[song]=items;all_items+=items
        print("FEATURE",song,len(items),flush=True)

    current=score_same_onsets(all_items,lambda x:x["current"])
    raw=score_same_onsets(all_items,lambda x:x["argmax"])
    policies=[]
    for th in (.40,.50,.60,.70,.80):
      for margin in (0,.05,.10,.20,.30):
       for bias in (0,.15,.30,.50,.75):
        song_scores={};cls=Counter()
        for song,items in by_song.items():
            labs=[]
            for q in items:
                p=dict(q["prob"]);cur=q["current"]
                # current label bias in probability/log-score space
                scores={g:math.log(max(1e-8,p[g]))+(bias if g==cur else 0) for g in METAL}
                order=sorted(METAL,key=lambda g:scores[g],reverse=True)
                best,second=order[0],order[1]
                # Require acoustic confidence and a meaningful score margin.
                if p[best]>=th and scores[best]-scores[second]>=margin:lab=best
                else:lab=cur
                labs.append(lab)
                if q["truth"] is not None:
                    cls[f"{q['truth']}->{lab}"]+=1
            song_scores[song]=canonical(song,base_rows[song],labs)
        tp=sum(s["tp"] for s in song_scores.values());pn=sum(s["predicted"] for s in song_scores.values());rf=sum(s["reference"] for s in song_scores.values())
        f1=2*tp/(pn+rf)
        # explicit ride/crash matched-onset recall diagnostic
        ride_ok=sum(cls[f"ride->{g}"] for g in ("ride",) );ride_ref=sum(v for k,v in cls.items() if k.startswith("ride->"))
        crash_ok=cls["crash->crash"];crash_ref=sum(v for k,v in cls.items() if k.startswith("crash->"))
        policies.append({"config":{"threshold":th,"margin":margin,"currentBias":bias},
          "f1":f1,"tp":tp,"predicted":pn,"reference":rf,
          "matchedRideAccuracy":ride_ok/ride_ref if ride_ref else 0,
          "matchedCrashAccuracy":crash_ok/crash_ref if crash_ref else 0,
          "songs":{s:{"f1":v["f1"],"by_group":{g:v["by_group"][g] for g in METAL}} for s,v in song_scores.items()}})
    policies.sort(key=lambda z:(z["f1"],z["matchedRideAccuracy"],z["matchedCrashAccuracy"]),reverse=True)

    diag={}
    for song,items in by_song.items():
        hats=[q for q in items if q["current"]=="hat"]
        diag[song]={
          "metalEvents":len(items),
          "matched":sum(q["truth"] is not None for q in items),
          "currentMatchedAccuracy":score_same_onsets(items,lambda x:x["current"])["correct"]/max(1,score_same_onsets(items,lambda x:x["current"])["matched"]),
          "rawMatchedAccuracy":score_same_onsets(items,lambda x:x["argmax"])["correct"]/max(1,score_same_onsets(items,lambda x:x["argmax"])["matched"]),
          "currentHatTruthRide":sum(q["truth"]=="ride" for q in hats),
          "hatTruthRideArgmaxRide":sum(q["truth"]=="ride" and q["argmax"]=="ride" for q in hats),
          "hatTruthRideProbQ":([float(np.quantile([q["prob"]["ride"] for q in hats if q["truth"]=="ride"],a)) for a in (.1,.25,.5,.75,.9)] if any(q["truth"]=="ride" for q in hats) else []),
          "hatTruthHatProbQ":([float(np.quantile([q["prob"]["ride"] for q in hats if q["truth"]=="hat"],a)) for a in (.1,.25,.5,.75,.9)] if any(q["truth"]=="hat" for q in hats) else []),
        }

    def simple(c):
        return {"matched":c["matched"],"correct":c["correct"],"accuracy":c["correct"]/max(1,c["matched"]),
                "confusion":{k:v for k,v in c.items() if "->" in k}}
    report={"schema":1,"model":"GMD rock/punk external acoustic logistic classifier",
      "currentSameOnset":simple(current),"rawClassifierSameOnset":simple(raw),
      "diagnostics":diag,"topPolicies":policies[:30]}
    (EXP/"results-browser-gmd-metal-acoustic-diagnostic.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"current":simple(current),"raw":simple(raw),"diagnostics":diag,"top":policies[:8]},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
