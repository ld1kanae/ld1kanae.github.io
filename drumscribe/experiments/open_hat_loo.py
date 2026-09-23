"""Open/closed hi-hat articulation experiment.

Goal: preserve the current browser hit detector and relabel only its remaining
stick hi-hat events (MIDI 42) as closed (42) or open (46).

Five-song leave-one-song-out evaluation. The held-out song's chart.mid is never
used for model fitting or threshold selection. DruMaster assets 42.wav/46.wav
are used only as acoustic template features, not as held-out labels.

Three deliberately different hypotheses:
  A decay_logistic: amplitude-decay envelope only + logistic regression.
  B timbre_extra: decay + spectral/timbre + asset-template similarity, ExtraTrees.
  C context_extra: B + browser-available rhythmic/event context, ExtraTrees.

Every held-out prediction is written to a real MIDI file and re-read before
articulation scoring.
"""
from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import wave
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"
BASE=EXP/"generated-v2-browser"
OUT=EXP/"generated-search-open-hat-loo"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
SR=44100
NFFT=2048
BANDS=[(1000,3000),(3000,6000),(6000,9000),(9000,13000),(13000,18000),(18000,22000)]
DECAY_WINDOWS=[(0,.025),(.025,.060),(.060,.120),(.120,.220),(.220,.400),(.400,.650)]
THRESHOLDS=[.35,.45,.55,.65,.75]
PITCH={"kick":36,"snare":38,"hat":42,"open_hat":46,"pedal_hat":44,"tom":45,"crash":49,"ride":51,"other":58}

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev_openhat",EXP/"evaluate_v2.py")

def audio(song):
    cmd=["ffmpeg","-v","error","-i",str(ROOT/"DruMaster/songs"/song/"drums.mp3"),
         "-ac","1","-ar",str(SR),"-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

def read_wav(path):
    with wave.open(str(path)) as w:
        raw=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").astype(np.float32)/32768
        raw=raw.reshape(-1,w.getnchannels()).mean(axis=1)
        rate=w.getframerate()
    if rate!=SR:
        from scipy.signal import resample_poly
        raw=resample_poly(raw,SR,rate).astype(np.float32)
    return raw

def onset_align(x):
    if not len(x): return x
    peak=float(np.max(np.abs(x)))+1e-12
    idx=np.flatnonzero(np.abs(x)>=.02*peak)
    start=max(0,int(idx[0])-64) if len(idx) else 0
    return x[start:]

def asset_template(pitch):
    x=onset_align(read_wav(ROOT/"DruMaster/assets/drums"/f"{pitch}.wav"))
    # Mean of three early spectra makes the feature less dependent on one FFT phase.
    mags=[]
    for off in (0,.020,.050):
        c=int(off*SR)+NFFT//2
        z=np.zeros(NFFT,np.float32);lo=c-NFFT//2;hi=lo+NFFT
        a=max(0,lo);b=min(len(x),hi)
        if b>a:z[a-lo:b-lo]=x[a:b]
        mags.append(np.abs(np.fft.rfft(z*np.hanning(NFFT)))+1e-9)
    m=np.mean(mags,axis=0);return m/(np.linalg.norm(m)+1e-12)

ASSET42=asset_template(42)
ASSET46=asset_template(46)
FREQ=np.fft.rfftfreq(NFFT,1/SR)
WINDOW=np.hanning(NFFT).astype(np.float32)

def meta(song):
    return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def browser(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    rows=[(t-off,g,p) for t,g,p in ev.midi_events(BASE/f"{song}.mid")]
    return rows,side

def truth(song):
    m=meta(song)
    shift=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
    return [(t+shift,g,p) for t,g,p in ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")]

def rms_window(x,t,a,b):
    i=max(0,int((t+a)*SR));j=min(len(x),int((t+b)*SR))
    if j<=i:return 1e-8
    z=x[i:j]
    return float(np.sqrt(np.mean(z*z)+1e-12))

def frame_mag(x,t,offset=0.015):
    c=int(round((t+offset)*SR));lo=c-NFFT//2;hi=lo+NFFT
    z=np.zeros(NFFT,np.float32);a=max(0,lo);b=min(len(x),hi)
    if b>a:z[a-lo:b-lo]=x[a:b]
    return np.abs(np.fft.rfft(z*WINDOW))+1e-9

def cosine(a,b):
    return float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-12))

def decay_features(x,t):
    floor=rms_window(x,t,-.100,-.025)
    env=[]
    for a,b in DECAY_WINDOWS:
        r=rms_window(x,t,a,b)
        env.append(math.sqrt(max(r*r-floor*floor,1e-12)))
    e0=max(env[0],1e-8)
    logrel=[math.log(max(e,1e-8)/e0) for e in env]
    centers=np.array([(a+b)/2 for a,b in DECAY_WINDOWS],dtype=float)
    yy=np.array(logrel,dtype=float)
    slope=float(np.polyfit(centers,yy,1)[0])
    weights=np.maximum(np.array(env)-floor,0)
    tcent=float(np.sum(centers*weights)/(np.sum(weights)+1e-12))
    tail=float((env[3]+env[4]+env[5])/(3*e0+1e-12))
    late=float(env[-1]/(e0+1e-12))
    pre=float(floor/e0)
    # Open hats should usually retain substantially more energy after 100-400 ms.
    return np.asarray(logrel+[slope,tcent,tail,late,pre],dtype=np.float32)

def timbre_features(x,t):
    d=decay_features(x,t)
    m=frame_mag(x,t)
    tot=float(m.sum())+1e-12
    band=[]
    for lo,hi in BANDS:
        z=float(m[(FREQ>=lo)&(FREQ<hi)].sum())/tot
        band.append(math.log1p(100*z))
    centroid=float(np.sum(FREQ*m)/tot)/22050
    flat=float(np.exp(np.mean(np.log(m)))/(np.mean(m)+1e-12))
    cs=np.cumsum(m);roll=float(FREQ[min(len(FREQ)-1,int(np.searchsorted(cs,.85*cs[-1])))])/22050
    mn=m/(np.linalg.norm(m)+1e-12)
    sim42=cosine(mn,ASSET42);sim46=cosine(mn,ASSET46)
    # Spectral persistence at later offsets complements amplitude decay.
    persist=[]
    onset_hf=float(m[FREQ>=5000].sum())+1e-12
    for off in (.080,.180,.350):
        mm=frame_mag(x,t,off)
        persist.append(math.log1p(float(mm[FREQ>=5000].sum())/onset_hf))
    return np.concatenate([d,np.asarray(band+[centroid,flat,roll,sim42,sim46,sim46-sim42]+persist,dtype=np.float32)])

def near(xs,t,w):
    return any(abs(v-t)<=w for v in xs)

def nearest(xs,t):
    return min((abs(v-t) for v in xs),default=9.)

def periodic(xs,t,bpm):
    best=0.
    if bpm<=0:return 0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(near(xs,t+k*step,.060) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def context_features(x,t,rows,side):
    a=timbre_features(x,t)
    by={}
    for g in ("kick","snare","hat","pedal_hat","tom","crash","ride"):
        by[g]=sorted(q for q,gg,_ in rows if gg==g)
    hats=by["hat"];i=min(range(len(hats)),key=lambda k:abs(hats[k]-t)) if hats else 0
    prev=t-hats[i-1] if hats and i>0 else 9.
    nxt=hats[i+1]-t if hats and i+1<len(hats) else 9.
    bpm=float(side.get("bpm") or 0);phase=float(side.get("barPhaseSec") or 0)
    beat=60/bpm if bpm>0 else 1.;bar=4*beat
    xx=(t-phase)%bar;slot=xx/bar*16
    c=[
      min(prev,.8)/.8,min(nxt,.8)/.8,periodic(hats,t,bpm),
      min(nearest(by["kick"],t),.25)/.25,min(nearest(by["snare"],t),.25)/.25,
      float(near(by["kick"],t,.045)),float(near(by["snare"],t,.045)),
      min(abs(slot-round(slot)),.5)*2,
      math.sin(2*math.pi*slot/16),math.cos(2*math.pi*slot/16)
    ]
    return np.concatenate([a,np.asarray(c,dtype=np.float32)])

def label_candidate(t,tt):
    z=[(abs(t-u),p) for u,g,p in tt if p in (42,46) and abs(t-u)<=.080]
    if not z:return None
    return min(z,key=lambda q:q[0])[1]

def prepare():
    out={}
    for s in SONGS:
        print("FEATURES",s,flush=True)
        x=audio(s);rows,side=browser(s);tt=truth(s)
        hats=sorted(t for t,g,p in rows if g=="hat")
        labels=[label_candidate(t,tt) for t in hats]
        keep=[i for i,p in enumerate(labels) if p in (42,46)]
        feats={
          "decay":np.stack([decay_features(x,t) for t in hats]) if hats else np.zeros((0,11),np.float32),
          "timbre":np.stack([timbre_features(x,t) for t in hats]) if hats else np.zeros((0,30),np.float32),
          "context":np.stack([context_features(x,t,rows,side) for t in hats]) if hats else np.zeros((0,40),np.float32),
        }
        y=np.asarray([1 if p==46 else 0 if p==42 else -1 for p in labels],dtype=np.int8)
        refs={42:sorted(t for t,g,p in tt if p==42),46:sorted(t for t,g,p in tt if p==46)}
        out[s]={"rows":rows,"side":side,"hats":hats,"X":feats,"y":y,"trainIdx":np.asarray(keep,dtype=int),"refs":refs,
                "counts":{"candidateHats":len(hats),"matched":len(keep),"matchedClosed":sum(labels[i]==42 for i in keep),"matchedOpen":sum(labels[i]==46 for i in keep),
                          "refClosed":len(refs[42]),"refOpen":len(refs[46])}}
        print("COUNTS",s,json.dumps(out[s]["counts"]),flush=True)
    return out

class Model:
    def __init__(self,family):
        self.family=family;self.scaler=None;self.model=None
    def fit(self,X,y):
        if self.family=="decay_logistic":
            self.scaler=StandardScaler().fit(X);XX=self.scaler.transform(X)
            self.model=LogisticRegression(max_iter=1200,class_weight="balanced",C=.7,solver="lbfgs").fit(XX,y)
        else:
            depth=12 if self.family=="timbre_extra" else 14
            leaf=4 if self.family=="timbre_extra" else 3
            self.model=ExtraTreesClassifier(n_estimators=240,max_depth=depth,min_samples_leaf=leaf,
                    class_weight="balanced",random_state=246 if self.family=="timbre_extra" else 346,n_jobs=-1).fit(X,y)
        return self
    def prob(self,X):
        if self.scaler is not None:X=self.scaler.transform(X)
        p=self.model.predict_proba(X)
        j=list(self.model.classes_).index(1)
        return p[:,j]

def key_for(family):
    return "decay" if family=="decay_logistic" else "timbre" if family=="timbre_extra" else "context"

def train(data,songs,family):
    key=key_for(family);XX=[];yy=[]
    for s in songs:
        ii=data[s]["trainIdx"]
        if len(ii):XX.append(data[s]["X"][key][ii]);yy.append(data[s]["y"][ii])
    return Model(family).fit(np.concatenate(XX),np.concatenate(yy))

def candidate_macro(data,songs,probs,thr):
    cm=Counter()
    for s in songs:
        y=data[s]["y"]
        for i,p in enumerate(probs[s]):
            if y[i]<0:continue
            pred=1 if p>=thr else 0;ref=int(y[i])
            cm[(ref,pred)]+=1
    def f(cls):
        tp=cm[(cls,cls)];pred=cm[(0,cls)]+cm[(1,cls)];ref=cm[(cls,0)]+cm[(cls,1)]
        return 2*tp/(pred+ref) if pred+ref else 0.
    return .5*(f(0)+f(1)),{"closedF1":f(0),"openF1":f(1),
        "closedToOpen":cm[(0,1)],"openToClosed":cm[(1,0)]}

def select_threshold(data,outer,family):
    # Nested LOO inside the four training songs.
    probs={}
    for val in outer:
        tr=[s for s in outer if s!=val]
        m=train(data,tr,family);probs[val]=m.prob(data[val]["X"][key_for(family)])
    rows=[]
    for th in THRESHOLDS:
        score,diag=candidate_macro(data,outer,probs,th)
        rows.append((score,-abs(th-.55),th,diag))
    rows.sort(reverse=True)
    return rows[0][2],{"ranking":[{"threshold":r[2],"macroF1":r[0],**r[3]} for r in rows]}

def greedy(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        cand=[(abs(t-u),j) for j,u in enumerate(ref) if j not in used and abs(t-u)<=w]
        if cand:
            _,j=min(cand);used.add(j);tp+=1
    return tp

def articulation_metrics(open_pred,closed_pred,refs):
    out={}
    for name,pred,pitch in (("open",open_pred,46),("closed",closed_pred,42)):
        ref=refs[pitch];tp=greedy(pred,ref);n=len(pred);r=len(ref)
        out[name]={"tp":tp,"predicted":n,"reference":r,
                   "precision":tp/n if n else 0.,"recall":tp/r if r else 0.,"f1":2*tp/(n+r) if n+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"])
    return out

def vlq(n):
    out=[n&127]
    while n>>7:n>>=7;out.insert(0,(n&127)|128)
    return bytes(out)

def write_midi(path,rows,bpm):
    ppq=480;tps=ppq*bpm/60;tempo=round(60_000_000/bpm)
    packets=[(0,0,bytes([255,81,3,(tempo>>16)&255,(tempo>>8)&255,tempo&255]))]
    for t,g,p0 in rows:
        pitch=PITCH.get(g,p0);tick=max(0,round(t*tps));vel=88
        packets += [(tick,2,bytes([0x99,pitch,vel])),(tick+max(1,round(.07*tps)),1,bytes([0x89,pitch,0]))]
    packets.sort(key=lambda q:(q[0],q[1],q[2][1] if len(q[2])>1 else 0))
    body=bytearray();prev=0
    for tick,_,b in packets:body+=vlq(tick-prev)+b;prev=tick
    body+=bytes([0,255,47,0]);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b"MThd"+(6).to_bytes(4,"big")+bytes([0,0,0,1,1,224])+b"MTrk"+len(body).to_bytes(4,"big")+body)

def relabel_rows(d,p,thr):
    open_times={d["hats"][i] for i,v in enumerate(p) if v>=thr}
    out=[]
    for t,g,pitch in d["rows"]:
        if g=="hat" and t in open_times:out.append((t,"open_hat",46))
        else:out.append((t,g,pitch))
    return out,sorted(open_times),sorted(t for t in d["hats"] if t not in open_times)

def reread_articulation(path):
    z=ev.midi_events(path)
    return {"open":sorted(t for t,g,p in z if p==46),"closed":sorted(t for t,g,p in z if p==42),"count":len(z)}

def baseline(data):
    per={};agg=Counter()
    for s in SONGS:
        d=data[s];m=articulation_metrics([],d["hats"],d["refs"]);per[s]=m
        for cls in ("open","closed"):
            z=m[cls];agg[f"{cls}_tp"]+=z["tp"];agg[f"{cls}_p"]+=z["predicted"];agg[f"{cls}_r"]+=z["reference"]
    return aggregate_counts(agg,per)

def aggregate_counts(agg,per):
    out={"songs":per}
    for cls in ("open","closed"):
        tp=agg[f"{cls}_tp"];p=agg[f"{cls}_p"];r=agg[f"{cls}_r"]
        out[cls]={"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,"recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"])
    return out

def evaluate_family(data,family):
    per={};fold={};agg=Counter()
    for held in SONGS:
        outer=[s for s in SONGS if s!=held]
        thr,inner=select_threshold(data,outer,family)
        model=train(data,outer,family);key=key_for(family)
        p=model.prob(data[held]["X"][key])
        rows,open_pred,closed_pred=relabel_rows(data[held],p,thr)
        path=OUT/family/f"{held}.mid";write_midi(path,rows,float(data[held]["side"]["bpm"]))
        rr=reread_articulation(path)
        # MIDI round-trip is authoritative for the scored prediction.
        m=articulation_metrics(rr["open"],rr["closed"],data[held]["refs"])
        cand,_diag=candidate_macro(data,[held],{held:p},thr)
        fold[held]={"threshold":thr,"inner":inner,"candidateMatchedMacroF1":cand,
                    "openPredictions":len(rr["open"]),"closedPredictions":len(rr["closed"]),"midiNotes":rr["count"],
                    "metrics":m}
        per[held]=m
        for cls in ("open","closed"):
            z=m[cls];agg[f"{cls}_tp"]+=z["tp"];agg[f"{cls}_p"]+=z["predicted"];agg[f"{cls}_r"]+=z["reference"]
    summary=aggregate_counts(agg,per)
    return {"family":family,"featureSet":key_for(family),"folds":fold,"summary":summary}

def main():
    data=prepare()
    result={"schema":1,
      "description":"Held-out open/closed hi-hat relabeling of current browser hat candidates. No onset times are added or removed.",
      "referenceCounts":{s:data[s]["counts"] for s in SONGS},
      "assets":{"closed":"DruMaster/assets/drums/42.wav","open":"DruMaster/assets/drums/46.wav","use":"template-similarity features only"},
      "baselineAllClosed":baseline(data),"variants":{}}
    for fam in ("decay_logistic","timbre_extra","context_extra"):
        q=evaluate_family(data,fam);result["variants"][fam]=q
        print("VARIANT",fam,json.dumps(q["summary"],ensure_ascii=False),flush=True)
    winner=max(result["variants"],key=lambda k:result["variants"][k]["summary"]["macroF1"])
    result["winner"]=winner;result["final"]=result["variants"][winner]["summary"]
    result["guard"]={
      "onsetTimesChanged":False,
      "eventCountsChanged":False,
      "otherDrumClassesChanged":False,
      "note":"Only existing MIDI-42 hat events are relabeled to MIDI 46."
    }
    (EXP/"results-open-hat-loo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",winner,json.dumps(result["final"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
