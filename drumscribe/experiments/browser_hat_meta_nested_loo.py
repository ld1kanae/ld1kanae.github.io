"""Nested-LOO hi-hat false-positive suppressor on the true browser baseline.

Unlike the earlier component-fusion experiment, this benchmark starts directly
from generated-v2-browser. For each outer held song:
- features use drums.mp3 + browser-predicted events + browser BPM/bar phase;
- model/threshold/rescue are chosen using only the other four songs via inner
  leave-one-song-out;
- the held chart is used only once for final scoring.

No chart is used in production features.
"""
from __future__ import annotations
import bisect,importlib.util,json,math,subprocess
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"];GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
SR=44100;NFFT=2048

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")

def audio(song):
    p=ROOT/"DruMaster/songs"/song/"drums.mp3"
    cmd=["ffmpeg","-v","error","-i",str(p),"-ac","1","-ar",str(SR),"-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

def browser(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    rr=[(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")]
    return rr,side

def truth(song):
    m=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
    return [(t+shift,g) for t,g,*_ in ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")]

def near(xs,t,w):return any(abs(x-t)<=w for x in xs)
def nearest(xs,t):return min((abs(x-t) for x in xs),default=9.)

def periodic(times,t,bpm):
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.060 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def spectral(x,t):
    c=int(round(t*SR))
    def win(center):
        lo=center-NFFT//2;hi=lo+NFFT;z=np.zeros(NFFT,dtype=np.float32)
        a=max(0,lo);b=min(len(x),hi)
        if b>a:z[a-lo:b-lo]=x[a:b]
        return z*np.hanning(NFFT)
    cur=win(c);pre=win(c-int(.025*SR));S=np.abs(np.fft.rfft(cur))+1e-9;P=np.abs(np.fft.rfft(pre))+1e-9
    f=np.fft.rfftfreq(NFFT,1/SR);tot=float(S.sum())+1e-9;pt=float(P.sum())+1e-9;v=[]
    for lo,hi in [(30,180),(180,800),(800,2500),(2500,5000),(5000,10000),(10000,18000),(18000,22000)]:
        m=(f>=lo)&(f<hi);e=float(S[m].sum())/tot;pe=float(P[m].sum())/pt
        v += [math.log1p(100*e),math.log1p(100*max(0,e-pe))]
    centroid=float((f*S).sum()/tot)/22050
    flat=float(np.exp(np.mean(np.log(S)))/(np.mean(S)+1e-9))
    rms=float(np.sqrt(np.mean(cur*cur))+1e-9);crest=float(np.max(np.abs(cur))/(rms+1e-9));zc=float(np.mean(np.signbit(cur[1:])!=np.signbit(cur[:-1])))
    return v+[centroid,flat,math.log1p(rms*1000),crest/10,zc]

def feature(x,t,rr,sd):
    bpm=float(sd["bpm"]);phase=float(sd["barPhaseSec"]);beat=60/bpm;bar=4*beat
    by={g:sorted(tt for tt,gg in rr if gg==g) for g in GROUPS};hats=by["hat"];i=min(range(len(hats)),key=lambda k:abs(hats[k]-t))
    prev=t-hats[i-1] if i>0 else 9.;nxt=hats[i+1]-t if i+1<len(hats) else 9.
    xx=(t-phase)%bar;slot=(xx/bar)*16;sloterr=abs(slot-round(slot));head=min(xx,bar-xx)/beat
    return np.asarray(spectral(x,t)+[
      min(nearest(by["kick"],t),.25)/.25,min(nearest(by["snare"],t),.25)/.25,
      min(nearest(by["crash"],t),.25)/.25,min(nearest(by["ride"],t),.25)/.25,min(nearest(by["pedal_hat"],t),.25)/.25,
      float(near(by["kick"],t,.025)),float(near(by["kick"],t,.045)),float(near(by["kick"],t,.070)),float(near(by["snare"],t,.045)),
      min(prev,.5)/.5,min(nxt,.5)/.5,periodic(hats,t,bpm),min(sloterr,.5)*2,min(head,2)/2,
      math.sin(2*math.pi*slot/16),math.cos(2*math.pi*slot/16)
    ],dtype=np.float32)

def prepare():
    out={}
    for s in SONGS:
        print("FEATURES",s,flush=True);x=audio(s);rr,sd=browser(s);tt=truth(s);h=sorted(t for t,g in rr if g=="hat")
        X=np.stack([feature(x,t,rr,sd) for t in h]) if h else np.zeros((0,37),dtype=np.float32)
        y=np.asarray([1 if any(g=="hat" and abs(t-u)<=.08 for u,g in tt) else 0 for t in h],dtype=np.int8)
        out[s]={"rows":rr,"side":sd,"hats":h,"X":X,"y":y}
    return out

class M:
    def __init__(self,fam):self.fam=fam;self.sc=None;self.m=None;self.c=.5
    def fit(self,X,y):
        if not len(y) or y.min()==y.max():self.c=float(y[0]) if len(y) else .5;return self
        if self.fam=="logistic":
            self.sc=StandardScaler().fit(X);self.m=LogisticRegression(max_iter=900,class_weight="balanced",C=.5,solver="liblinear").fit(self.sc.transform(X),y)
        else:
            self.m=ExtraTreesClassifier(n_estimators=260,max_depth=12,min_samples_leaf=4,class_weight="balanced",random_state=211,n_jobs=-1).fit(X,y)
        return self
    def pred(self,X):
        if self.m is None:return np.full(len(X),self.c)
        if self.sc is not None:X=self.sc.transform(X)
        return self.m.predict_proba(X)[:,1]

def train(data,songs,fam):
    return M(fam).fit(np.concatenate([data[s]["X"] for s in songs]),np.concatenate([data[s]["y"] for s in songs]))

def build(d,p,cfg):
    hats=d["hats"];bpm=float(d["side"]["bpm"]);keep=[]
    for i,t in enumerate(hats):
        k=p[i]>=cfg["thr"]
        if not k and cfg["rescue"]=="repeat" and periodic(hats,t,bpm)>=cfg["rep"]:k=True
        if not k and cfg["rescue"]=="offkick":
            kicks=[x for x,g in d["rows"] if g=="kick"]
            if not near(kicks,t,.045):k=True
        if k:keep.append(t)
    return sorted([e for e in d["rows"] if e[1]!="hat"]+[(t,"hat") for t in keep])

def score(song,pred):
    m=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text());shift=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
    return ev.score([(t,g,0,0) for t,g in pred],ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid"),shift)

def aggregate(sc):
    z=Counter()
    for q in sc.values():
        z.update(tp=q["tp"],p=q["predicted"],r=q["reference"])
        for g,v in q["by_group"].items():z.update({f"{g}t":v["tp"],f"{g}p":v["predicted"],f"{g}r":v["reference"]})
    o={"tp":z["tp"],"predicted":z["p"],"reference":z["r"],"precision":z["tp"]/z["p"],"recall":z["tp"]/z["r"],"f1":2*z["tp"]/(z["p"]+z["r"]),"by_group":{}}
    for g in ev.ORDER:
        a,b,c=z[f"{g}t"],z[f"{g}p"],z[f"{g}r"];o["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    return o

def objective(a):
    h=a["by_group"]["hat"];return a["f1"]+.035*h["f1"]+.01*h["precision"]

def main():
    data=prepare();base={s:score(s,data[s]["rows"]) for s in SONGS};bag=aggregate(base)
    cfgs=[];i=0
    for fam in ("logistic","extra"):
      for thr in (.25,.35,.45,.55,.65):
       for rescue in ("none","repeat","offkick"):
        for rep in (.50,.75):
         if rescue!="repeat" and rep!=.50:continue
         cfgs.append({"id":i,"family":fam,"thr":thr,"rescue":rescue,"rep":rep});i+=1

    held={};details={}
    for h in SONGS:
        outer=[s for s in SONGS if s!=h];rank=[]
        for cfg in cfgs:
            inner_scores={}
            for v in outer:
                tr=[s for s in outer if s!=v];mod=train(data,tr,cfg["family"]);p=mod.pred(data[v]["X"])
                inner_scores[v]=score(v,build(data[v],p,cfg))
            a=aggregate(inner_scores);b=aggregate({s:base[s] for s in outer})
            valid=a["f1"]>=b["f1"]-.003 and a["by_group"]["hat"]["f1"]>=b["by_group"]["hat"]["f1"]-.010
            rank.append((valid,objective(a),a["f1"],cfg["id"],a))
        rank.sort(reverse=True);valid,objv,_,bid,inner=rank[0];cfg=next(c for c in cfgs if c["id"]==bid)
        mod=train(data,outer,cfg["family"]);p=mod.pred(data[h]["X"]);pred=build(data[h],p,cfg);sc=score(h,pred);held[h]=sc
        details[h]={"config":cfg,"innerEligible":valid,"innerObjective":objv,"inner":inner,"heldF1":sc["f1"],"hat":sc["by_group"]["hat"],
                    "kept":sum(p>=cfg["thr"]),"candidates":len(p)}
        print("HELD",h,json.dumps(details[h],ensure_ascii=False),flush=True)
    ag=aggregate(held)
    out={"schema":1,"description":"Fully nested LOO hat suppressor on generated-v2-browser; charts scoring-only.",
         "baseline":bag,"nestedLOO":{"aggregate":ag,"objective":objective(ag),"songs":details}}
    (EXP/"results-browser-hat-meta-nested-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(bag,ensure_ascii=False),flush=True);print("LOO",json.dumps(out["nestedLOO"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
