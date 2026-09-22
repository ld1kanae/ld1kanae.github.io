"""Cycles 201-203: LOSO snare candidate meta-classification on c197 base.

Candidate pool = c197 current snare union high-recall/safe audio-derived snare
streams. Features use drums.mp3 + prediction structure only. For each held-out
song the classifier is trained on the other four songs. chart.mid is training
labels only for non-held-out songs and final held-out scoring.

Cycle 201: heuristic / logistic / ExtraTrees.
Cycle 202: 3 probability thresholds on the winning learned family.
Cycle 203: 3 rescue policies for rejected base snares.

Every candidate writes real MIDI, re-reads it, then scores all parts.
"""
from __future__ import annotations
import importlib.util,json,math,subprocess
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}
BASE=EXP/"generated-search-browser-component-fusion/cycle197/c197_merge"
HIGH=EXP/"generated-search-best-fusion/cycle80/c80_snare_pattern"
SAFE=EXP/"generated-search-snare-additive/cycle114/c114_repeat3"
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

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def side(song):return json.loads((BROWSER/f"{song}.json").read_text())
def aligned_truth(song):
    m=meta(song);shift=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
    return [(t+shift,g) for t,g,*_ in ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")]
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)
def nearest(xs,t):return min((abs(x-t) for x in xs),default=9.)

def periodic(times,t,bpm):
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.06 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def spectral(x,t):
    c=int(round(t*SR))
    def frame(center):
        lo=center-NFFT//2;hi=lo+NFFT;z=np.zeros(NFFT,dtype=np.float32)
        a=max(0,lo);b=min(len(x),hi)
        if b>a:z[a-lo:b-lo]=x[a:b]
        return z*np.hanning(NFFT)
    cur=frame(c);pre=frame(c-int(.025*SR));S=np.abs(np.fft.rfft(cur))+1e-9;P=np.abs(np.fft.rfft(pre))+1e-9
    f=np.fft.rfftfreq(NFFT,1/SR);tot=float(S.sum())+1e-9;pt=float(P.sum())+1e-9
    out=[]
    for lo,hi in [(30,140),(140,500),(500,1500),(1500,3500),(3500,7000),(7000,12000),(12000,20000)]:
        m=(f>=lo)&(f<hi);e=float(S[m].sum())/tot;ep=float(P[m].sum())/pt
        out += [math.log1p(100*e),math.log1p(100*max(0,e-ep))]
    centroid=float((f*S).sum()/tot)/22050
    flat=float(np.exp(np.mean(np.log(S)))/(np.mean(S)+1e-9))
    rms=float(np.sqrt(np.mean(cur*cur))+1e-9);crest=float(np.max(np.abs(cur))/(rms+1e-9))
    return out+[centroid,flat,math.log1p(1000*rms),crest/10]

def unique_union(*seqs,w=.025):
    xs=[]
    for src,arr in enumerate(seqs):
        for t in arr:xs.append((float(t),src))
    xs.sort();groups=[];cur=[]
    for z in xs:
        if not cur or z[0]-cur[-1][0]<=w:cur.append(z)
        else:groups.append(cur);cur=[z]
    if cur:groups.append(cur)
    out=[]
    for grp in groups:
        t=sum(x[0] for x in grp)/len(grp);members={x[1] for x in grp}
        out.append((t,members))
    return out

def feature(x,t,members,base_rows,candidates,sd):
    bpm=float(sd["bpm"]);phase=float(sd["barPhaseSec"]);beat=60/bpm;bar=4*beat
    by={g:sorted(tt for tt,gg in base_rows if gg==g) for g in GROUPS}
    stimes=[q[0] for q in candidates]
    i=min(range(len(stimes)),key=lambda k:abs(stimes[k]-t))
    prev=t-stimes[i-1] if i>0 else 9.;nxt=stimes[i+1]-t if i+1<len(stimes) else 9.
    pos=((t-phase)%bar)/bar*16;err=abs(pos-round(pos));slot=int(round(pos))%16
    return np.asarray(spectral(x,t)+[
      float(0 in members),float(1 in members),float(2 in members),
      float(len(members)>=2),float(len(members)==3),
      min(nearest(by["kick"],t),.25)/.25,float(near(by["kick"],t,.025)),float(near(by["kick"],t,.045)),float(near(by["kick"],t,.070)),
      min(nearest(by["hat"],t),.25)/.25,min(nearest(by["tom"],t),.25)/.25,
      min(prev,.5)/.5,min(nxt,.5)/.5,periodic(stimes,t,bpm),
      min(err,.5)*2,min(min((t-phase)%bar,bar-(t-phase)%bar)/beat,2)/2,
      float(slot in (4,12)),float(slot in (0,4,8,12)),
      math.sin(2*math.pi*pos/16),math.cos(2*math.pi*pos/16)
    ],dtype=np.float32)

def prepare():
    data={}
    for song in SONGS:
        print("FEATURES",song,flush=True);x=audio(song);b=rows(BASE,song);sd=side(song);truth=aligned_truth(song)
        bs=[t for t,g in b if g=="snare"];hi=[t for t,g in rows(HIGH,song) if g=="snare"];sf=[t for t,g in rows(SAFE,song) if g=="snare"]
        cand=unique_union(bs,hi,sf)
        X=np.stack([feature(x,t,mem,b,cand,sd) for t,mem in cand]) if cand else np.zeros((0,42),np.float32)
        y=np.asarray([1 if any(g=="snare" and abs(t-tt)<=.080 for tt,g in truth) else 0 for t,mem in cand],dtype=np.int8)
        diag=Counter()
        for (t,mem),yy in zip(cand,y):
            if yy:continue
            nt=[(abs(t-tt),g) for tt,g in truth if abs(t-tt)<=.080]
            diag[min(nt)[1] if nt else "unmatched"]+=1
        data[song]={"rows":b,"side":sd,"cand":cand,"X":X,"y":y,"fpTruthClass":dict(diag)}
    return data

class Model:
    def __init__(self,fam):self.fam=fam;self.scaler=None;self.model=None;self.constant=.5
    def fit(self,X,y):
        if not len(y) or y.min()==y.max():self.constant=float(y[0]) if len(y) else .5;return self
        if self.fam=="logistic":
            self.scaler=StandardScaler().fit(X);X=self.scaler.transform(X)
            self.model=LogisticRegression(max_iter=900,class_weight="balanced",C=.6,solver="liblinear").fit(X,y)
        else:
            self.model=ExtraTreesClassifier(n_estimators=260,max_depth=13,min_samples_leaf=3,class_weight="balanced",random_state=201,n_jobs=-1).fit(X,y)
        return self
    def predict(self,X):
        if self.model is None:return np.full(len(X),self.constant)
        if self.scaler is not None:X=self.scaler.transform(X)
        return self.model.predict_proba(X)[:,1]

def train(data,held,fam):
    X=np.concatenate([data[s]["X"] for s in SONGS if s!=held]);y=np.concatenate([data[s]["y"] for s in SONGS if s!=held])
    return Model(fam).fit(X,y)

def heuristic(x):
    # Membership features begin after 18 acoustic dims.
    base_mem=x[18];high_mem=x[19];safe_mem=x[20];agree=x[21]
    kick45=x[26];rep=x[32];backbeat=x[35]
    if safe_mem and not kick45:return True
    if base_mem and (backbeat or rep>=.50):return True
    if agree and not kick45:return True
    return False

def enforce(rr):
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in rr if gg==g);last=-999.;md=.038 if g=="snare" else .035 if g in ("hat","ride") else .05 if g in ("tom","pedal_hat") else .08 if g=="crash" else .04
        for t in arr:
            if t-last>=md:ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0;pri={"snare":.95,"tom":.88,"crash":.84,"ride":.80,"hat":.62}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[z for z in c if z[1] not in HANDS];h=[z for z in c if z[1] in HANDS]
        h=sorted(h,key=lambda z:pri.get(z[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def build(d,prob,thr,rescue):
    keep=[]
    for i,(t,mem) in enumerate(d["cand"]):
        k=prob[i]>=thr
        if not k:
            x=d["X"][i]
            base_mem=(0 in mem);rep=x[32];backbeat=x[35]
            if rescue=="base_all" and base_mem:k=True
            elif rescue=="base_struct" and base_mem and (rep>=.5 or backbeat):k=True
        if k:keep.append(t)
    return enforce([z for z in d["rows"] if z[1]!="snare"]+[(t,"snare") for t in keep])

def build_heur(d):
    keep=[t for (t,mem),x in zip(d["cand"],d["X"]) if heuristic(x)]
    return enforce([z for z in d["rows"] if z[1]!="snare"]+[(t,"snare") for t in keep])

def write(path,rr,bpm):base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in rr],bpm)

def evaluate(name,data,fam,thr,rescue,outdir):
    result={"family":fam,"threshold":thr,"rescue":rescue,"songs":{},"diagnostic":{}};tot=Counter()
    for held in SONGS:
        if fam=="heuristic":pr=build_heur(data[held])
        else:
            mod=train(data,held,fam);prob=mod.predict(data[held]["X"]);pr=build(data[held],prob,thr,rescue)
        result["diagnostic"][held]={"candidateCount":len(data[held]["cand"]),"truthPositive":int(data[held]["y"].sum()),"fpTruthClass":data[held]["fpTruthClass"]}
        p=outdir/name/f"{held}.mid";write(p,pr,float(data[held]["side"]["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/held/"chart.mid");m=meta(held);shift=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][held]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,z in sc["by_group"].items():tot[f"{g}_tp"]+=z["tp"];tot[f"{g}_pred"]+=z["predicted"];tot[f"{g}_ref"]+=z["reference"]
    tp,n,r=tot["tp"],tot["predicted"],tot["reference"];s={"tp":tp,"predicted":n,"reference":r,"precision":tp/n if n else 0,"recall":tp/r if r else 0,"f1":2*tp/(n+r) if n+r else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for song in SONGS:
            z=result["songs"][song]["by_group"].get(g,{});rr=z.get("reference",0)
            if rr:sf.append(2*z.get("tp",0)/(z.get("predicted",0)+rr) if z.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,"false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,"count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s);result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def choose(res,basecand):
    d=sel.select(res,basecand["summary"],target_parts=("snare",),max_part_drop=.018,target_tolerance=.008)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    data=prepare();root=EXP/"generated-search-snare-meta-loo";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline",data,"logistic",0.0,"base_all",root/"baseline")
    res={}
    for name,fam in [("c201_heuristic","heuristic"),("c201_logistic","logistic"),("c201_extra","extra")]:
        res[name]=evaluate(name,data,fam,.50,"none",root/"cycle201");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"snare":res[name]["summary"]["by_group"]["snare"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline);win=d["winner"] or "c201_logistic";best=res[win];report["cycles"].append({"cycle":201,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    fam=best["family"] if best["family"]!="heuristic" else "logistic";res={}
    for name,t in [("c202_t35",.35),("c202_t50",.50),("c202_t65",.65)]:
        res[name]=evaluate(name,data,fam,t,"none",root/"cycle202");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"snare":res[name]["summary"]["by_group"]["snare"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or "c202_t50";best=res[win];report["cycles"].append({"cycle":202,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for name,rsc in [("c203_none","none"),("c203_base_struct","base_struct"),("c203_base_all","base_all")]:
        res[name]=evaluate(name,data,fam,best["threshold"],rsc,root/"cycle203");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"snare":res[name]["summary"]["by_group"]["snare"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or "c203_none";best=res[win];report["cycles"].append({"cycle":203,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    report["baseline"]=baseline;report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"family":best["family"],"threshold":best["threshold"],"rescue":best["rescue"],"diagnostic":best["diagnostic"],"detailed":best["detailed"]}
    (EXP/"results-iterative-snare-meta-loo.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
