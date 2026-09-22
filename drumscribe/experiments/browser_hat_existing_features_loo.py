"""Fully nested LOO hat suppressor using only features already available in transcribe.js.

No additional 44.1-kHz FFT is used. Features are derived from the existing
11.025-kHz / 1024 FFT browser analysis:
- 4 normalized band fluxes
- 8 template similarities
- local means/maxima of high bands
- template/band relationships
- predicted-event collision distances
- hat periodic support
- bar slot/head features from browser BPM/bar phase

For each held song all model fitting and threshold choice use only the other
four songs. chart.mid is labels/scoring only.
"""
from __future__ import annotations
import bisect,importlib.util,json,math
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def near(xs,t,w):
    i=bisect.bisect_left(xs,t-w);return i<len(xs) and xs[i]<=t+w
def nearest(xs,t):return min((abs(x-t) for x in xs),default=9.)

def browser(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    rr=[(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")]
    return rr,side

def truth(song):
    m=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
    return [(t+shift,g) for t,g,*_ in ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")]

def periodic(times,t,bpm):
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(near(times,t+k*step,.060) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def loc(arr,fr,r):
    a=max(0,fr-r);b=min(arr.shape[-1],fr+r+1);z=arr[a:b]
    return (float(np.mean(z)) if len(z) else 0.,float(np.max(z)) if len(z) else 0.)

def feature(band,sim,t,rr,side):
    fr=max(0,min(band.shape[1]-1,int(round(t*ev.SR/ev.HOP))))
    by={g:sorted(x for x,gg in rr if gg==g) for g in ev.ORDER};hats=by["hat"]
    i=bisect.bisect_left(hats,t);idx=min(range(max(0,i-1),min(len(hats),i+2)),key=lambda k:abs(hats[k]-t)) if hats else 0
    prev=t-hats[idx-1] if idx>0 else 9.;nxt=hats[idx+1]-t if idx+1<len(hats) else 9.
    bpm=float(side["bpm"]);phase=float(side["barPhaseSec"]);beat=60/bpm;bar=4*beat
    xx=(t-phase)%bar;slot=xx/bar*16;serr=abs(slot-round(slot));head=min(xx,bar-xx)/beat
    vals=[float(band[k,fr]) for k in range(4)]
    vals += [float(sim[k,fr]) for k in range(sim.shape[0])]
    # Local statistics already derivable from browser band arrays.
    for r in (2,5,10):
        for bi in (2,3):vals += list(loc(band[bi],fr,r))
    hs=float(sim[ev.ORDER.index("hat"),fr]);ks=float(sim[ev.ORDER.index("kick"),fr]);ss=float(sim[ev.ORDER.index("snare"),fr])
    cs=float(sim[ev.ORDER.index("crash"),fr]);rs=float(sim[ev.ORDER.index("ride"),fr]);ps=float(sim[ev.ORDER.index("pedal_hat"),fr])
    vals += [hs-ks,hs-ss,cs-hs,rs-hs,ps-hs,
             hs/(abs(ks)+1e-4),hs/(abs(ss)+1e-4),
             float(band[3,fr]/(band[2,fr]+1e-4))]
    vals += [
      min(nearest(by["kick"],t),.25)/.25,min(nearest(by["snare"],t),.25)/.25,
      min(nearest(by["crash"],t),.25)/.25,min(nearest(by["ride"],t),.25)/.25,
      min(nearest(by["pedal_hat"],t),.25)/.25,
      float(near(by["kick"],t,.025)),float(near(by["kick"],t,.045)),float(near(by["kick"],t,.070)),
      float(near(by["snare"],t,.045)),
      min(prev,.5)/.5,min(nxt,.5)/.5,periodic(hats,t,bpm),
      min(serr,.5)*2,min(head,2)/2,
      math.sin(2*math.pi*slot/16),math.cos(2*math.pi*slot/16)
    ]
    return np.asarray(vals,dtype=np.float32)

def prepare():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums");out={}
    for s in SONGS:
        print("FEATURES",s,flush=True);rr,side=browser(s);tt=truth(s)
        x=ev.audio(ROOT/"DruMaster/songs"/s/"drums.mp3");sp=ev.spectrum(x);band,sim=ev.features(sp,tmpl)
        hats=sorted(t for t,g in rr if g=="hat")
        X=np.stack([feature(band,sim,t,rr,side) for t in hats])
        y=np.asarray([1 if any(g=="hat" and abs(t-u)<=.08 for u,g in tt) else 0 for t in hats],dtype=np.int8)
        out[s]={"rows":rr,"side":side,"hats":hats,"X":X,"y":y}
    return out

def train(data,songs,variant):
    X=np.concatenate([data[s]["X"] for s in songs]);y=np.concatenate([data[s]["y"] for s in songs])
    pars={
      "tiny":dict(n_estimators=64,max_depth=8,min_samples_leaf=7),
      "small":dict(n_estimators=96,max_depth=10,min_samples_leaf=5),
      "medium":dict(n_estimators=160,max_depth=12,min_samples_leaf=4),
    }[variant]
    return ExtraTreesClassifier(**pars,class_weight="balanced",random_state=431,n_jobs=-1).fit(X,y)

def build(d,p,thr,rep):
    hats=d["hats"];bpm=float(d["side"]["bpm"]);keep=[]
    for i,t in enumerate(hats):
        if p[i]>=thr or periodic(hats,t,bpm)>=rep:keep.append(t)
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
    results={}
    for variant in ("tiny","small","medium"):
        held={};detail={}
        for h in SONGS:
            outer=[s for s in SONGS if s!=h];cache={}
            for v in outer:
                tr=[s for s in outer if s!=v];m=train(data,tr,variant);cache[v]=m.predict_proba(data[v]["X"])[:,1]
            rank=[];bouter=aggregate({s:base[s] for s in outer})
            for thr in (.35,.45,.55,.65):
              for rep in (.50,.75,1.0):
                sc={v:score(v,build(data[v],cache[v],thr,rep)) for v in outer};a=aggregate(sc)
                valid=a["f1"]>=bouter["f1"]-.003 and a["by_group"]["hat"]["f1"]>=bouter["by_group"]["hat"]["f1"]-.012
                rank.append((valid,objective(a),a["f1"],thr,rep,a))
            rank.sort(reverse=True);valid,objv,_,thr,rep,inner=rank[0]
            m=train(data,outer,variant);p=m.predict_proba(data[h]["X"])[:,1];sc=score(h,build(data[h],p,thr,rep));held[h]=sc
            detail[h]={"threshold":thr,"repeat":rep,"innerEligible":bool(valid),"innerObjective":float(objv),"heldF1":float(sc["f1"]),"hat":sc["by_group"]["hat"]}
        a=aggregate(held);results[variant]={"aggregate":a,"objective":objective(a),"songs":detail}
        print("VARIANT",variant,json.dumps(results[variant],ensure_ascii=False),flush=True)
    out={"schema":1,"description":"Nested LOO hat suppressor using only existing browser band/template/rhythm features.","baseline":bag,"variants":results}
    (EXP/"results-browser-hat-existing-features-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(bag,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
