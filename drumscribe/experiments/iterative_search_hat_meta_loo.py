"""Cycles 198-200: meta-classify current hi-hat events to suppress false hits.

Base: browser/component fusion c197_merge.

Prediction features use only drums.mp3 + already predicted MIDI + browser-estimated
BPM/bar phase. chart.mid is used for labels on training songs and final scoring
only. For each held-out song, learned classifiers are trained on the other four
songs (LOSO).

Cycle 198:
  - fixed structural/acoustic heuristic
  - LOSO logistic regression
  - LOSO ExtraTrees
Cycle 199:
  - three probability thresholds for the winning learned family
Cycle 200:
  - three rescue policies for removed hats (none / repetition / off-kick)

Every candidate is written as MIDI, re-read, then compared to chart.mid.
"""
from __future__ import annotations
import importlib.util,json,math,subprocess
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}
BASE=EXP/"generated-search-browser-component-fusion/cycle197/c197_merge"
BROWSER=EXP/"generated-v2-browser"
SR=44100;NFFT=2048

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
base=loadmod("base",EXP/"iterative_search.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
sel=loadmod("sel",EXP/"selection_policy.py")

def audio(song):
    p=ROOT/"DruMaster/songs"/song/"drums.mp3"
    cmd=["ffmpeg","-v","error","-i",str(p),"-ac","1","-ar",str(SR),"-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

def rows(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]

def meta(song):
    return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def side(song):
    return json.loads((BROWSER/f"{song}.json").read_text())

def aligned_truth(song):
    m=meta(song)
    shift=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
    return [(t+shift,g) for t,g,*_ in ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")]

def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)

def nearest(xs,t):
    return min((abs(x-t) for x in xs),default=9.0)

def periodic_support(times,t,bpm):
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.060 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def spectral(x,t):
    c=int(round(t*SR))
    def win(center):
        lo=center-NFFT//2;hi=lo+NFFT
        z=np.zeros(NFFT,dtype=np.float32)
        a=max(0,lo);b=min(len(x),hi)
        if b>a:z[a-lo:b-lo]=x[a:b]
        return z*np.hanning(NFFT)
    cur=win(c);pre=win(c-int(.025*SR))
    S=np.abs(np.fft.rfft(cur))+1e-9
    P=np.abs(np.fft.rfft(pre))+1e-9
    freqs=np.fft.rfftfreq(NFFT,1/SR)
    total=float(S.sum())+1e-9
    bands=[]
    for lo,hi in [(30,180),(180,800),(800,2500),(2500,5000),(5000,10000),(10000,18000),(18000,22000)]:
        m=(freqs>=lo)&(freqs<hi)
        e=float(S[m].sum())/total
        pe=float(P[m].sum())/(float(P.sum())+1e-9)
        bands += [math.log1p(100*e),math.log1p(100*max(0,e-pe))]
    centroid=float((freqs*S).sum()/total)/22050
    flat=float(np.exp(np.mean(np.log(S)))/(np.mean(S)+1e-9))
    rms=float(np.sqrt(np.mean(cur*cur))+1e-9)
    crest=float(np.max(np.abs(cur))/(rms+1e-9))
    zc=float(np.mean(np.signbit(cur[1:])!=np.signbit(cur[:-1])))
    return bands+[centroid,flat,math.log1p(rms*1000),crest/10,zc]

def feat(song,x,t,events,sd):
    bpm=float(sd["bpm"]);phase=float(sd["barPhaseSec"]);beat=60/bpm;bar=4*beat
    by={g:sorted(tt for tt,gg in events if gg==g) for g in GROUPS}
    hats=by["hat"];i=min(range(len(hats)),key=lambda k:abs(hats[k]-t))
    prev=t-hats[i-1] if i>0 else 9.
    nxt=hats[i+1]-t if i+1<len(hats) else 9.
    xx=(t-phase)%bar
    slot=(xx/bar)*16
    slotround=round(slot)
    sloterr=abs(slot-slotround)
    head=min(xx,bar-xx)/beat
    return np.asarray(spectral(x,t)+[
      min(nearest(by["kick"],t),.25)/.25,
      min(nearest(by["snare"],t),.25)/.25,
      min(nearest(by["crash"],t),.25)/.25,
      min(nearest(by["ride"],t),.25)/.25,
      min(nearest(by["pedal_hat"],t),.25)/.25,
      float(near(by["kick"],t,.025)),float(near(by["kick"],t,.045)),float(near(by["kick"],t,.070)),
      float(near(by["snare"],t,.045)),
      min(prev,.5)/.5,min(nxt,.5)/.5,
      periodic_support(hats,t,bpm),
      min(sloterr,.5)*2,
      min(head,2)/2,
      math.sin(2*math.pi*slot/16),math.cos(2*math.pi*slot/16),
    ],dtype=np.float32)

def prepare():
    data={}
    for song in SONGS:
        print("FEATURES",song,flush=True)
        x=audio(song);rr=rows(BASE,song);sd=side(song);truth=aligned_truth(song)
        hats=sorted(t for t,g in rr if g=="hat")
        X=np.stack([feat(song,x,t,rr,sd) for t in hats]) if hats else np.zeros((0,40),dtype=np.float32)
        y=np.asarray([1 if any(g=="hat" and abs(t-tt)<=.080 for tt,g in truth) else 0 for t in hats],dtype=np.int8)
        # diagnostics only: what non-hat truth class lies near a false hat?
        cls=Counter()
        for t,yy in zip(hats,y):
            if yy:continue
            neartruth=[(abs(t-tt),g) for tt,g in truth if abs(t-tt)<=.080]
            cls[min(neartruth)[1] if neartruth else "unmatched"]+=1
        data[song]={"rows":rr,"side":sd,"hats":hats,"X":X,"y":y,"fp_truth_class":dict(cls)}
    return data

class Model:
    def __init__(self,family):
        self.family=family;self.scaler=None;self.model=None;self.constant=.5
    def fit(self,X,y):
        if not len(y) or y.min()==y.max():
            self.constant=float(y[0]) if len(y) else .5;return self
        if self.family=="logistic":
            self.scaler=StandardScaler().fit(X);X=self.scaler.transform(X)
            self.model=LogisticRegression(max_iter=800,class_weight="balanced",C=.5,solver="liblinear").fit(X,y)
        elif self.family=="extra":
            self.model=ExtraTreesClassifier(n_estimators=240,max_depth=12,min_samples_leaf=4,class_weight="balanced",random_state=198,n_jobs=-1).fit(X,y)
        return self
    def predict(self,X):
        if self.model is None:return np.full(len(X),self.constant)
        if self.scaler is not None:X=self.scaler.transform(X)
        return self.model.predict_proba(X)[:,1]

def train(data,held,family):
    X=np.concatenate([data[s]["X"] for s in SONGS if s!=held])
    y=np.concatenate([data[s]["y"] for s in SONGS if s!=held])
    return Model(family).fit(X,y)

def heuristic_keep(x):
    # Feature indices after 21 acoustic dims:
    # kick distances/collisions begin at 21.
    kick45=x[27];kick70=x[28];period=x[32];sloterr=x[33]
    # Spectral high-band features: band pairs index 8..13 roughly 5-18k.
    high=x[8]+x[10]+x[12]
    low=x[0]+x[2]+x[4]
    suspicious = kick45>0.5 and high < low*1.18 and period < .50
    # Strong repeated hats survive even on kick.
    return not suspicious

def build_pred(d,probs,threshold,rescue):
    rr=d["rows"];hats=d["hats"];bpm=float(d["side"]["bpm"])
    keep=[]
    for i,t in enumerate(hats):
        k=probs[i]>=threshold
        if not k:
            if rescue=="repeat" and periodic_support(hats,t,bpm)>=.75:k=True
            elif rescue=="offkick" and not any(abs(t-x)<=.045 for x,g in rr if g=="kick"):k=True
        if k:keep.append(t)
    out=[x for x in rr if x[1]!="hat"]+[(t,"hat") for t in keep]
    return enforce(out)

def build_heuristic(d):
    keep=[t for t,x in zip(d["hats"],d["X"]) if heuristic_keep(x)]
    return enforce([x for x in d["rows"] if x[1]!="hat"]+[(t,"hat") for t in keep])

def enforce(rows0):
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in rows0 if gg==g);last=-999.
        md=.035 if g in ("snare","hat","ride") else .05 if g in ("tom","pedal_hat") else .08 if g=="crash" else .04
        for t in arr:
            if t-last>=md:ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0;pri={"snare":.95,"tom":.88,"crash":.84,"ride":.80,"hat":.62}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[x for x in c if x[1] not in HANDS];h=[x for x in c if x[1] in HANDS]
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def write(path,rr,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in rr],bpm)

def evaluate(name,data,family,threshold,rescue,outdir):
    result={"family":family,"threshold":threshold,"rescue":rescue,"songs":{},"diagnostic":{}};tot=Counter()
    for held in SONGS:
        if family=="heuristic":
            predrows=build_heuristic(data[held])
        else:
            m=train(data,held,family);p=m.predict(data[held]["X"]);predrows=build_pred(data[held],p,threshold,rescue)
        result["diagnostic"][held]={"hatCandidates":len(data[held]["hats"]),"truthPositive":int(data[held]["y"].sum()),"fpTruthClass":data[held]["fp_truth_class"]}
        path=outdir/name/f"{held}.mid";write(path,predrows,float(data[held]["side"]["bpm"]))
        pred=ev.midi_events(path);truth=ev.midi_events(ROOT/"DruMaster/songs"/held/"chart.mid")
        mta=meta(held);shift=float(mta["playback"]["stemOffsetSec"])+float(mta["playback"].get("midiOffsetSec",0))
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][held]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,r=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":r,"precision":tp/n if n else 0,"recall":tp/r if r else 0,
       "f1":2*tp/(n+r) if n+r else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for song in SONGS:
            z=result["songs"][song]["by_group"].get(g,{});rr=z.get("reference",0)
            if rr:sf.append(2*z.get("tp",0)/(z.get("predicted",0)+rr) if z.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,
          "false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,
          "worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s);result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"]
    return result

def choose(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("hat",),max_part_drop=.018,target_tolerance=.008)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    data=prepare();root=EXP/"generated-search-hat-meta-loo";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline",data,"logistic",0.0,"repeat",root/"baseline")
    # threshold=0 keeps all hats; learned model output is irrelevant.
    res={}
    for name,fam in [("c198_heuristic","heuristic"),("c198_logistic","logistic"),("c198_extra","extra")]:
        res[name]=evaluate(name,data,fam,.50,"none",root/"cycle198")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline);win=d["winner"] or "c198_logistic";best=res[win]
    report["cycles"].append({"cycle":198,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    fam=best["family"] if best["family"]!="heuristic" else "logistic"
    res={}
    for name,thr in [("c199_t35",.35),("c199_t50",.50),("c199_t65",.65)]:
        res[name]=evaluate(name,data,fam,thr,"none",root/"cycle199")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or "c199_t50";best=res[win]
    report["cycles"].append({"cycle":199,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,rescue in [("c200_none","none"),("c200_repeat","repeat"),("c200_offkick","offkick")]:
        res[name]=evaluate(name,data,fam,best["threshold"],rescue,root/"cycle200")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or "c200_none";best=res[win]
    report["cycles"].append({"cycle":200,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    report["baseline"]=baseline
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],
      "family":best["family"],"threshold":best["threshold"],"rescue":best["rescue"],
      "diagnostic":best["diagnostic"],"detailed":best["detailed"]}
    (EXP/"results-iterative-hat-meta-loo.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
