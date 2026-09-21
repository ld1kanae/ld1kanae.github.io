"""Cycles 82-84: 44.1 kHz ride-section reclassification.

Starts from the current best all-part MIDI (best-fusion cycle81).
For each held-out song:
  - read drums.mp3 at 44.1 kHz
  - extract high-frequency spectral/periodic section features around existing
    metal/hat timing
  - train only on the other four songs' chart labels
  - classify sections as ride-dominant
  - convert only existing hat hits inside predicted ride sections to ride
Then write real MIDI and score against chart.mid.

Cycle 85: 2 / 4 / 8 beat sections
Cycle 86: logistic / random forest / extra trees
Cycle 87: strict / balanced / recall thresholds
"""
from __future__ import annotations
import importlib.util, json, math, subprocess
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
BEST=EXP/"generated-search-fusion-v2/cycle84/c84_pedal75"

def audio(song,sr=44100):
    p=ROOT/"DruMaster/songs"/song/"drums.mp3"
    cmd=["ffmpeg","-v","error","-i",str(p),"-ac","1","-ar",str(sr),"-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

def spectrum(x,sr=44100):
    nfft=4096;hop=441
    x=np.pad(x,(nfft//2,nfft//2))
    frames=np.lib.stride_tricks.sliding_window_view(x,nfft)[::hop]
    win=np.hanning(nfft).astype("f4")
    S=np.abs(np.fft.rfft(frames*win,axis=1)).astype("f4").T
    R=np.maximum(S-np.pad(S[:,:-1],((0,0),(1,0))),0)
    freqs=np.arange(S.shape[0])*sr/nfft
    return S,R,freqs,hop

def load_song(song):
    folder=ROOT/"DruMaster/songs"/song
    meta=json.loads((folder/"song.json").read_text())
    x=audio(song);S,R,freqs,hop=spectrum(x)
    def band(lo,hi,src=R):
        m=(freqs>=lo)&(freqs<hi)
        y=src[m].sum(axis=0) if np.any(m) else np.zeros(src.shape[1])
        q=np.percentile(y,98)+1e-8
        return (y/q).astype("f4")
    bands={
      "mid":band(1500,4000),
      "h4":band(4000,8000),
      "h8":band(8000,12000),
      "h12":band(12000,18000),
      "air":band(18000,22000),
      "body":band(500,1500),
    }
    metal=bands["h4"]+.85*bands["h8"]+.6*bands["h12"]
    metal=np.maximum(metal-.5*median_filter(metal,size=101),0)
    pp,_=find_peaks(metal,distance=max(1,int(.035*44100/hop)),prominence=.04)
    floor=np.maximum(.08,1.8*median_filter(metal,size=151))
    metal_times=np.asarray([i*hop/44100 for i in pp if metal[i]>=floor[i]],dtype="f4")

    pred=[(t,g) for t,g,*_ in ev.midi_events(BEST/f"{song}.mid")]
    ref0=ev.midi_events(folder/"chart.mid")
    shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
    truth=[(t+shift,g) for t,g,*_ in ref0]
    return {"meta":meta,"bands":bands,"metal_times":metal_times,"pred":pred,"truth":truth,"hop":hop}

def periodicity(times,bpm):
    if len(times)<3:return 0.,0.
    vals=[]
    for t in times:
        best=0.
        for step in (30/bpm,60/bpm,120/bpm):
            n=sum(any(abs(float(x)-(t+k*step))<=.055 for x in times) for k in (-2,-1,1,2))
            best=max(best,n/4)
        vals.append(best)
    return float(np.mean(vals)),float(np.mean(np.asarray(vals)>=.5))

def section_feature(d,a,b):
    hop=d["hop"];i0=max(0,int(a*44100/hop));i1=min(len(d["bands"]["mid"]),int(b*44100/hop)+1)
    if i1<=i0:return np.zeros(32,dtype="f4")
    vals=[]
    for key in ("body","mid","h4","h8","h12","air"):
        x=d["bands"][key][i0:i1]
        vals += [float(np.mean(x)),float(np.median(x)),float(np.percentile(x,75)),float(np.max(x))]
    mt=d["metal_times"][(d["metal_times"]>=a)&(d["metal_times"]<b)]
    bpm=float(d["meta"]["bpm"]);pmean,phalf=periodicity(mt,bpm)
    if len(mt)>=2:
        dt=np.diff(mt);med=float(np.median(dt));std=float(np.std(dt))
    else:med=std=0.
    # Existing transcription event densities in section, audio-only prediction.
    pred=d["pred"]
    hc=sum(1 for t,g in pred if g=="hat" and a<=t<b)
    pc=sum(1 for t,g in pred if g=="pedal_hat" and a<=t<b)
    cc=sum(1 for t,g in pred if g=="crash" and a<=t<b)
    dur=max(.05,b-a)
    vals += [len(mt)/dur,pmean,phalf,med,std,hc/dur,pc/dur,cc/dur]
    return np.asarray(vals,dtype="f4")

def windows(d,beats):
    bpm=float(d["meta"]["bpm"]);ts=d["meta"].get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));w=beat*beats;step=beat
    duration=len(d["bands"]["mid"])*d["hop"]/44100
    starts=np.arange(0,duration,step,dtype=float)
    ranges=[(float(s),float(s+w)) for s in starts]
    X=np.stack([section_feature(d,a,b) for a,b in ranges]) if ranges else np.zeros((0,32),dtype="f4")
    y=[]
    for a,b in ranges:
        ride=sum(1 for t,g in d["truth"] if g=="ride" and a<=t<b)
        hat=sum(1 for t,g in d["truth"] if g=="hat" and a<=t<b)
        cym=sum(1 for t,g in d["truth"] if g=="crash" and a<=t<b)
        # Label ride-dominant sections only. Crash-heavy sections are negative.
        total=ride+hat
        y.append(1 if ride>=2 and ride/max(1,total)>=.55 and ride>=cym else 0)
    return ranges,X,np.asarray(y,dtype=np.int8)

class Model:
    def __init__(self,fam):self.fam=fam;self.scaler=None;self.model=None;self.constant=0.
    def fit(self,X,y):
        if len(y)==0 or y.min()==y.max():self.constant=float(y[0]) if len(y) else 0.;return self
        pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0);rng=np.random.default_rng(211)
        cap=max(600,len(pos)*10)
        if len(neg)>cap:neg=rng.choice(neg,cap,replace=False)
        idx=np.concatenate([pos,neg]);rng.shuffle(idx);X=X[idx];y=y[idx]
        if self.fam=="logistic":
            self.scaler=StandardScaler().fit(X);X=self.scaler.transform(X)
            self.model=LogisticRegression(max_iter=700,class_weight="balanced",C=.65,solver="liblinear").fit(X,y)
        elif self.fam=="rf":
            self.model=RandomForestClassifier(n_estimators=180,max_depth=10,min_samples_leaf=3,class_weight="balanced_subsample",random_state=223,n_jobs=-1).fit(X,y)
        else:
            self.model=ExtraTreesClassifier(n_estimators=200,max_depth=11,min_samples_leaf=3,class_weight="balanced",random_state=227,n_jobs=-1).fit(X,y)
        return self
    def predict(self,X):
        if self.model is None:return np.full(len(X),self.constant)
        if self.scaler is not None:X=self.scaler.transform(X)
        return self.model.predict_proba(X)[:,1]

def train(data,held,beats,fam):
    X=[];y=[]
    for s in SONGS:
        if s==held:continue
        _,xx,yy=windows(data[s],beats);X.append(xx);y.append(yy)
    return Model(fam).fit(np.concatenate(X),np.concatenate(y))

def convert(d,model,beats,thr,run_need):
    ranges,X,_=windows(d,beats);p=model.predict(X)
    raw=p>=thr;active=np.zeros(len(raw),dtype=bool);i=0
    while i<len(raw):
        if not raw[i]:i+=1;continue
        j=i+1
        while j<len(raw) and raw[j]:j+=1
        if j-i>=run_need:active[i:j]=True
        i=j
    pred=list(d["pred"]);hats=[(i,t) for i,(t,g) in enumerate(pred) if g=="hat"]
    out=list(pred)
    for idx,t in hats:
        cover=[k for k,(a,b) in enumerate(ranges) if active[k] and a<=t<b]
        if cover:
            # Require local metal periodicity too, so a single cymbal tail cannot
            # convert an isolated hat into ride.
            local=d["metal_times"][(d["metal_times"]>=t-2)&(d["metal_times"]<=t+2)]
            pm,ph=periodicity(local,float(d["meta"]["bpm"]))
            if pm>=.35:
                out[idx]=(t,"ride")
    return out

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,data,beats,fam,thr,run_need,outdir):
    result={"beats":beats,"family":fam,"threshold":thr,"run_need":run_need,"songs":{}};tot=Counter()
    for held in SONGS:
        model=train(data,held,beats,fam);predrows=convert(data[held],model,beats,thr,run_need)
        p=outdir/name/f"{held}.mid";write(p,predrows,float(data[held]["meta"]["bpm"]))
        pred=ev.midi_events(p);truth0=ev.midi_events(ROOT/"DruMaster/songs"/held/"chart.mid")
        m=data[held]["meta"];shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth0,shift);cf=ev.confusion(pred,truth0,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][held]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mref,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mref,4) if mref else 0,"f1":round(2*tp/(n+mref),4) if n+mref else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    parts=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None,
          "mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):parts.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"]
    # Extra ride weight prevents the no-ride baseline from winning by silence.
    s["selection_score"]=round(s["f1"]+.18*sum(parts)/len(parts)+.10*s["by_group"]["ride"]["f1"]+.04*ped-.30*ks,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    data={s:load_song(s) for s in SONGS};root=EXP/"generated-search-ride-hires";report={"schema":1,"cycles":[]}
    res={}
    for beats in (2,4,8):
        name=f"c85_{beats}beat";res[name]=evaluate(name,data,beats,"extra",.65,2,root/"cycle85");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":85,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for fam in ("logistic","rf","extra"):
        name=f"c86_{fam}";res[name]=evaluate(name,data,best["beats"],fam,best["threshold"],best["run_need"],root/"cycle86");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":86,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,thr,run in [("c87_strict",.78,2),("c87_balanced",.64,2),("c87_recall",.52,1)]:
        res[name]=evaluate(name,data,best["beats"],best["family"],thr,run,root/"cycle87");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":87,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"beats":res[win]["beats"],"family":res[win]["family"],"threshold":res[win]["threshold"],"run_need":res[win]["run_need"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-ride-hires.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
