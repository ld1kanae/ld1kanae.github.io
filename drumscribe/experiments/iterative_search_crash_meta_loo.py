"""Cycles 204-206: LOO crash reclassification of existing metal events.

Base: c197_merge. Candidate pool contains existing crash plus hat/ride/pedal-hat
events near the browser-estimated bar head. No new onset is invented.

Features use drums.mp3 + predicted structure only. For each held-out song,
logistic/ExtraTrees are trained on the other four songs. chart.mid is labels
only for non-held-out songs and final held-out scoring.

Cycle 204: fixed structural heuristic / logistic / ExtraTrees.
Cycle 205: probability thresholds.
Cycle 206: bar-head candidate windows.

Every candidate writes MIDI, re-reads it, then scores all parts.
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
BROWSER=EXP/"generated-v2-browser";SR=44100;NFFT=2048

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py");base=loadmod("base",EXP/"iterative_search.py")
detail=loadmod("detail",EXP/"detailed_metrics.py");sel=loadmod("sel",EXP/"selection_policy.py")

def audio(song):
    cmd=["ffmpeg","-v","error","-i",str(ROOT/"DruMaster/songs"/song/"drums.mp3"),"-ac","1","-ar",str(SR),"-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()
def rows(song):return [(t,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")]
def side(song):return json.loads((BROWSER/f"{song}.json").read_text())
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def truth(song):
    m=meta(song);sh=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
    return [(t+sh,g) for t,g,*_ in ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")]
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)
def nearest(xs,t):return min((abs(x-t) for x in xs),default=9.)

def spectral(x,t):
    c=int(round(t*SR))
    def fw(center):
        lo=center-NFFT//2;hi=lo+NFFT;z=np.zeros(NFFT,np.float32);a=max(0,lo);b=min(len(x),hi)
        if b>a:z[a-lo:b-lo]=x[a:b]
        return z*np.hanning(NFFT)
    cur=fw(c);pre=fw(c-int(.025*SR));S=np.abs(np.fft.rfft(cur))+1e-9;P=np.abs(np.fft.rfft(pre))+1e-9
    f=np.fft.rfftfreq(NFFT,1/SR);tot=float(S.sum())+1e-9;pt=float(P.sum())+1e-9;out=[]
    for lo,hi in [(30,180),(180,800),(800,2500),(2500,5000),(5000,10000),(10000,18000),(18000,22000)]:
        m=(f>=lo)&(f<hi);e=float(S[m].sum())/tot;pe=float(P[m].sum())/pt
        out += [math.log1p(100*e),math.log1p(100*max(0,e-pe))]
    centroid=float((f*S).sum()/tot)/22050;flat=float(np.exp(np.mean(np.log(S)))/(np.mean(S)+1e-9))
    rms=float(np.sqrt(np.mean(cur*cur))+1e-9);crest=float(np.max(np.abs(cur))/(rms+1e-9))
    return out+[centroid,flat,math.log1p(1000*rms),crest/10]

def candidate_data(song,x,rr,sd,max_head=.35):
    bpm=float(sd["bpm"]);phase=float(sd["barPhaseSec"]);beat=60/bpm;bar=4*beat
    by={g:sorted(t for t,gg in rr if gg==g) for g in GROUPS}
    cand=[]
    for t,g in rr:
        if g not in ("hat","pedal_hat","ride","crash"):continue
        xx=(t-phase)%bar;hd=min(xx,bar-xx)/beat
        if g=="crash" or hd<=max_head:
            cand.append((t,g,hd))
    tr=truth(song);X=[];y=[]
    for t,g,hd in cand:
        feat=spectral(x,t)+[
          float(g=="crash"),float(g=="hat"),float(g=="ride"),float(g=="pedal_hat"),
          min(hd,.5)*2,
          min(nearest(by["kick"],t),.25)/.25,min(nearest(by["snare"],t),.25)/.25,min(nearest(by["tom"],t),.25)/.25,
          float(near(by["kick"],t,.045)),float(near(by["kick"],t,.075)),
          float(near(by["snare"],t,.060)),float(near(by["tom"],t,.10)),
          math.sin(2*math.pi*((t-phase)%bar)/bar),math.cos(2*math.pi*((t-phase)%bar)/bar),
        ]
        X.append(feat);y.append(1 if any(gg=="crash" and abs(t-tt)<=.080 for tt,gg in tr) else 0)
    return cand,np.asarray(X,np.float32),np.asarray(y,np.int8)

def prepare():
    d={}
    for s in SONGS:
        print("FEATURES",s,flush=True);x=audio(s);rr=rows(s);sd=side(s);cand,X,y=candidate_data(s,x,rr,sd)
        cls=Counter()
        tr=truth(s)
        for (t,g,hd),yy in zip(cand,y):
            if yy:continue
            nt=[(abs(t-tt),gg) for tt,gg in tr if abs(t-tt)<=.080]
            cls[min(nt)[1] if nt else "unmatched"]+=1
        d[s]={"rows":rr,"side":sd,"cand":cand,"X":X,"y":y,"fpTruthClass":dict(cls)}
    return d

class Model:
    def __init__(self,fam):self.fam=fam;self.scaler=None;self.model=None;self.constant=.5
    def fit(self,X,y):
        if not len(y) or y.min()==y.max():self.constant=float(y[0]) if len(y) else .5;return self
        if self.fam=="logistic":
            self.scaler=StandardScaler().fit(X);X=self.scaler.transform(X)
            self.model=LogisticRegression(max_iter=900,class_weight="balanced",C=.55,solver="liblinear").fit(X,y)
        else:
            self.model=ExtraTreesClassifier(n_estimators=260,max_depth=12,min_samples_leaf=3,class_weight="balanced",random_state=204,n_jobs=-1).fit(X,y)
        return self
    def predict(self,X):
        if self.model is None:return np.full(len(X),self.constant)
        if self.scaler is not None:X=self.scaler.transform(X)
        return self.model.predict_proba(X)[:,1]

def train(d,held,fam):
    X=np.concatenate([d[s]["X"] for s in SONGS if s!=held]);y=np.concatenate([d[s]["y"] for s in SONGS if s!=held])
    return Model(fam).fit(X,y)

def heuristic(x):
    # acoustic features 18; class flags begin at 18, head dist index22
    is_crash=x[18];hd=x[22];kick45=x[26];tom=x[29]
    high=x[8]+x[10]+x[12];mid=x[4]+x[6]
    if is_crash:return True
    return hd<=.22 and kick45>0.5 and high>=.80*mid

def enforce(rr):
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in rr if gg==g);last=-999.;md=.035 if g in ("snare","hat","ride") else .05 if g in ("tom","pedal_hat") else .08 if g=="crash" else .04
        for t in arr:
            if t-last>=md:ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0;pri={"snare":.95,"tom":.88,"crash":.90,"ride":.80,"hat":.62}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        cc=ded[i:j];ex=[z for z in cc if z[1] not in HANDS];h=[z for z in cc if z[1] in HANDS]
        h=sorted(h,key=lambda z:pri.get(z[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def build(d,p,thr,head_window,rescue):
    selected=[]
    for i,(t,g,hd) in enumerate(d["cand"]):
        k=(p[i]>=thr and (g=="crash" or hd<=head_window))
        if not k and g=="crash" and rescue=="keep_base":k=True
        if k:selected.append((t,g))
    sel_times=[t for t,g in selected]
    out=[]
    for t,g in d["rows"]:
        # Existing metal event chosen as crash is reclassified, not duplicated.
        if g in ("hat","ride","pedal_hat","crash") and near(sel_times,t,.025):
            continue
        out.append((t,g))
    out += [(t,"crash") for t,g in selected]
    return enforce(out)

def build_heur(d,head_window):
    p=np.asarray([1. if heuristic(x) else 0. for x in d["X"]])
    return build(d,p,.5,head_window,"keep_base")

def write(path,rr,bpm):base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in rr],bpm)

def evaluate(name,d,fam,thr,head_window,rescue,outdir):
    result={"family":fam,"threshold":thr,"head_window":head_window,"rescue":rescue,"songs":{},"diagnostic":{}};tot=Counter()
    for held in SONGS:
        if fam=="heuristic":pr=build_heur(d[held],head_window)
        else:
            mod=train(d,held,fam);pp=mod.predict(d[held]["X"]);pr=build(d[held],pp,thr,head_window,rescue)
        result["diagnostic"][held]={"candidates":len(d[held]["cand"]),"positive":int(d[held]["y"].sum()),"fpTruthClass":d[held]["fpTruthClass"]}
        p=outdir/name/f"{held}.mid";write(p,pr,float(d[held]["side"]["bpm"]))
        pred=ev.midi_events(p);tr=ev.midi_events(ROOT/"DruMaster/songs"/held/"chart.mid");m=meta(held);sh=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
        sc=ev.score(pred,tr,sh);cf=ev.confusion(pred,tr,sh);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][held]=sc
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

def choose(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("crash","hat"),max_part_drop=.018,target_tolerance=.008)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    d=prepare();root=EXP/"generated-search-crash-meta-loo";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline",d,"logistic",0.0,.35,"keep_base",root/"baseline")
    res={}
    for name,fam in [("c204_heuristic","heuristic"),("c204_logistic","logistic"),("c204_extra","extra")]:
        res[name]=evaluate(name,d,fam,.50,.35,"keep_base",root/"cycle204");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"crash":res[name]["summary"]["by_group"]["crash"],"hat":res[name]["summary"]["by_group"]["hat"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    z=choose(res,baseline);win=z["winner"] or "c204_logistic";best=res[win];report["cycles"].append({"cycle":204,"candidates":res,"winner":win,"ranking":z["ranking"],"guards":z["guards"]})

    fam=best["family"] if best["family"]!="heuristic" else "logistic";res={}
    for name,t in [("c205_t35",.35),("c205_t50",.50),("c205_t65",.65)]:
        res[name]=evaluate(name,d,fam,t,.35,"keep_base",root/"cycle205");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"crash":res[name]["summary"]["by_group"]["crash"],"hat":res[name]["summary"]["by_group"]["hat"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    z=choose(res,best);win=z["winner"] or "c205_t50";best=res[win];report["cycles"].append({"cycle":205,"candidates":res,"winner":win,"ranking":z["ranking"],"guards":z["guards"]})

    res={}
    for name,w in [("c206_h10",.10),("c206_h20",.20),("c206_h35",.35)]:
        res[name]=evaluate(name,d,fam,best["threshold"],w,"keep_base",root/"cycle206");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"crash":res[name]["summary"]["by_group"]["crash"],"hat":res[name]["summary"]["by_group"]["hat"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    z=choose(res,best);win=z["winner"] or "c206_h20";best=res[win];report["cycles"].append({"cycle":206,"candidates":res,"winner":win,"ranking":z["ranking"],"guards":z["guards"]})
    report["baseline"]=baseline;report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"family":best["family"],"threshold":best["threshold"],"head_window":best["head_window"],"diagnostic":best["diagnostic"],"detailed":best["detailed"]}
    (EXP/"results-iterative-crash-meta-loo.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
