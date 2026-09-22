"""Cycles 49-51: separated-stem event classification.

Cycle 49: compare 3 separation front ends
  A DSP/HPSS 5-stem
  B MDX23C neural 6-stem
  C neural + DSP ensemble
Cycle 50: compare 3 event classifier families on the winning separator
Cycle 51: compare 3 probability/rhythm operating points on the winner

All evaluations are leave-one-song-out. The held-out song's chart.mid is never
used to train its classifier. Every candidate writes real MIDI, re-parses it,
then scores all songs/parts.
"""
from __future__ import annotations
import copy, importlib.util, json, math, subprocess, tempfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from drumsep import separate as dsp_separate
from mdxnet_infer import separate as mdx_separate

ROOT=Path(".")
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
ev=loadmod("ev","drumscribe/experiments/evaluate_v2.py")
detail=loadmod("detail","drumscribe/experiments/detailed_metrics.py")

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride"]
HANDS={"snare","hat","tom","crash","ride"}
PITCH={"kick":36,"snare":38,"hat":42,"pedal_hat":44,"tom":45,"crash":49,"ride":51}
MIN_DIST={"kick":.050,"snare":.040,"hat":.035,"pedal_hat":.050,"tom":.055,"crash":.100,"ride":.045}
BASE_THR={"kick":.52,"snare":.54,"hat":.58,"pedal_hat":.64,"tom":.66,"crash":.58,"ride":.58}

def vlq(n):
    out=[n&127]
    while n>>7:n>>=7;out.insert(0,(n&127)|128)
    return bytes(out)

def write_midi(path,events,bpm):
    ppq=480;tps=ppq*bpm/60;tempo=round(60_000_000/bpm)
    packets=[(0,0,bytes([255,81,3,(tempo>>16)&255,(tempo>>8)&255,tempo&255]))]
    for e in events:
        tick=max(0,round(e["time"]*tps));pitch=PITCH[e["group"]]
        vel=max(1,min(127,round(55+65*float(e.get("prob",.7)))))
        packets += [(tick,2,bytes([0x99,pitch,vel])),(tick+max(1,round(.06*tps)),1,bytes([0x89,pitch,0]))]
    packets.sort(key=lambda x:(x[0],x[1],x[2][1] if len(x[2])>1 else 0))
    body=bytearray();prev=0
    for tick,_,data in packets:body+=vlq(tick-prev)+data;prev=tick
    body+=bytes([0,255,47,0]);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b"MThd"+(6).to_bytes(4,"big")+bytes([0,0,0,1,1,224])+b"MTrk"+len(body).to_bytes(4,"big")+body)

def ffmpeg_mono(path,sr=44100):
    cmd=["ffmpeg","-v","error","-i",str(path),"-ac","1","-ar",str(sr),"-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

def stft_features(x,sr=44100):
    nfft=2048;hop=441
    x=np.pad(x,(nfft//2,nfft//2))
    frames=np.lib.stride_tricks.sliding_window_view(x,nfft)[::hop]
    S=np.abs(np.fft.rfft(frames*np.hanning(nfft),axis=1)).astype("f4").T
    R=np.maximum(S-np.pad(S[:,:-1],((0,0),(1,0))),0)
    onset=R.sum(axis=0);onset=np.maximum(onset-.55*median_filter(onset,size=101),0)
    onset/=np.percentile(onset,98)+1e-7
    freqs=np.arange(S.shape[0])*sr/nfft
    return S,R,onset,freqs,hop

def candidate_frames(onset,sr,hop,min_dist=.035):
    pp,_=find_peaks(onset,distance=max(1,int(min_dist*sr/hop)),prominence=.035)
    floor=np.maximum(.055,2.0*median_filter(onset,size=151))
    return [int(i) for i in pp if onset[i]>=floor[i]]

def feature_at(S,R,onset,freqs,fr,candidate_times,hop,sr):
    spec=S[:,fr]+1e-8;total=float(np.sum(spec))+1e-8
    bands=[]
    for lo,hi in [(20,150),(150,500),(500,2000),(2000,5000),(5000,10000),(10000,16000),(16000,22000)]:
        m=(freqs>=lo)&(freqs<hi);bands.append(float(np.sum(spec[m]))/total if np.any(m) else 0.)
    centroid=float(np.sum(freqs*spec)/total)/(freqs[-1]+1e-8)
    flat=float(np.exp(np.mean(np.log(spec)))/(np.mean(spec)+1e-8))
    local=[]
    for rad in (2,5,12):
        lo=max(0,fr-rad);hi=min(len(onset),fr+rad+1)
        local += [float(onset[fr]),float(np.mean(onset[lo:hi])),float(np.max(onset[lo:hi]))]
    t=fr*hop/sr;rec=[]
    for step in (.125,.25,.5,1.0):
        rec.append(float(any(abs(float(x)-(t-step))<.055 or abs(float(x)-(t+step))<.055 for x in candidate_times)))
    return np.asarray(local+bands+[centroid,flat]+rec,dtype="f4")

def load_stream(path):
    x=ffmpeg_mono(path);S,R,onset,freqs,hop=stft_features(x)
    frs=candidate_frames(onset,44100,hop)
    times=np.asarray(frs)*hop/44100
    feats=np.stack([feature_at(S,R,onset,freqs,fr,times,hop,44100) for fr in frs]) if frs else np.zeros((0,22),dtype="f4")
    return {"frames":frs,"times":times.astype("f4"),"X":feats,"onset":onset}

def normalize_stems(method,dsp,mdx):
    if method=="dsp":
        return {"kick":dsp["kick"],"snare":dsp["snare"],"tom":dsp["tom"],"hat":dsp["hat"],"crash":dsp["cymbal"],"ride":dsp["cymbal"]}
    if method=="mdx":
        return {"kick":mdx["kick"],"snare":mdx["snare"],"tom":mdx["tom"],"hat":mdx["hat"],"crash":mdx["crash"],"ride":mdx["ride"]}
    raise ValueError(method)

def stem_path_dsp(result,key):
    aliases={"kick":["kick"],"snare":["snare"],"tom":["tom"],"hat":["hihat","hat"],"cymbal":["cymbal"]}[key]
    for k,v in (getattr(result,"stems",{}) or {}).items():
        if any(a in str(k).lower() for a in aliases):return Path(v)
    raise KeyError((key,getattr(result,"stems",{})))

def prepare_separations(tmp):
    allsep={}
    cache=tmp/"mdx-cache";cache.mkdir(parents=True,exist_ok=True)
    for song in SONGS:
        folder=ROOT/"DruMaster/songs"/song
        dspdir=tmp/song/"dsp";mdxdir=tmp/song/"mdx";dspdir.mkdir(parents=True);mdxdir.mkdir(parents=True)
        print("DSP SEPARATE",song,flush=True)
        dr=dsp_separate(str(folder/"drums.mp3"),output_dir=str(dspdir),enhanced=True)
        dsp={k:stem_path_dsp(dr,k) for k in ("kick","snare","tom","hat","cymbal")}
        print("MDX SEPARATE",song,flush=True)
        mr=mdx_separate(str(folder/"drums.mp3"),output_dir=str(mdxdir),model_name="drumsep-6stem",device="cpu",cache_dir=cache,progress=True)
        mdx={"kick":Path(mr["kick"]),"snare":Path(mr["snare"]),"tom":Path(mr.get("toms") or mr["tom"]),
             "hat":Path(mr.get("hh") or mr.get("hihat")),"ride":Path(mr["ride"]),"crash":Path(mr["crash"])}
        allsep[song]={"dsp":dsp,"mdx":mdx}
    return allsep

def truth(song):
    folder=ROOT/"DruMaster/songs"/song;meta=json.loads((folder/"song.json").read_text())
    shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
    xs=[(t+shift,g) for t,g,*_ in ev.midi_events(folder/"chart.mid")]
    return meta,xs

def group_positive(t,g,truths):
    return any(rg==g and abs(t-rt)<=.080 for rt,rg in truths)

def build_method_dataset(allsep,method):
    data={}
    for song in SONGS:
        meta,truths=truth(song)
        streams={}
        # DSP/MDX features are loaded independently. Ensemble concatenates both
        # front-end features at matched candidate times.
        if method in ("dsp","mdx"):
            paths=normalize_stems(method,allsep[song]["dsp"],allsep[song]["mdx"])
            raw={k:load_stream(v) for k,v in paths.items()}
            for g in GROUPS:
                source="hat" if g=="pedal_hat" else g
                streams[g]=raw[source]
        else:
            dpaths=normalize_stems("dsp",allsep[song]["dsp"],allsep[song]["mdx"])
            mpaths=normalize_stems("mdx",allsep[song]["dsp"],allsep[song]["mdx"])
            dr={k:load_stream(v) for k,v in dpaths.items()};mr={k:load_stream(v) for k,v in mpaths.items()}
            for g in GROUPS:
                source="hat" if g=="pedal_hat" else g
                a,b=dr[source],mr[source]
                times=sorted(set([round(float(t),3) for t in a["times"]]+[round(float(t),3) for t in b["times"]]))
                rows=[]
                for t in times:
                    ia=np.argmin(np.abs(a["times"]-t)) if len(a["times"]) else None
                    ib=np.argmin(np.abs(b["times"]-t)) if len(b["times"]) else None
                    xa=a["X"][ia] if ia is not None and abs(float(a["times"][ia])-t)<=.06 else np.zeros(22,dtype="f4")
                    xb=b["X"][ib] if ib is not None and abs(float(b["times"][ib])-t)<=.06 else np.zeros(22,dtype="f4")
                    support=[1. if np.any(xa) else 0.,1. if np.any(xb) else 0.]
                    rows.append(np.concatenate([xa,xb,np.asarray(support,dtype="f4")]))
                streams[g]={"times":np.asarray(times,dtype="f4"),"X":np.stack(rows) if rows else np.zeros((0,46),dtype="f4")}
        labels={}
        for g,s in streams.items():
            labels[g]=np.asarray([1 if group_positive(float(t),g,truths) else 0 for t in s["times"]],dtype=np.int8)
        data[song]={"meta":meta,"truth":truths,"streams":streams,"labels":labels}
    return data

class Binary:
    def __init__(self,family):self.family=family;self.scaler=None;self.model=None;self.constant=0.
    def fit(self,X,y):
        if not len(y) or y.min()==y.max():self.constant=float(y[0]) if len(y) else 0.;return self
        pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0);rng=np.random.default_rng(109)
        cap=max(500,len(pos)*12)
        if len(neg)>cap:neg=rng.choice(neg,cap,replace=False)
        idx=np.concatenate([pos,neg]);rng.shuffle(idx);X=X[idx];y=y[idx]
        if self.family=="logistic":
            self.scaler=StandardScaler().fit(X);X=self.scaler.transform(X)
            self.model=LogisticRegression(max_iter=700,class_weight="balanced",C=.7,solver="liblinear").fit(X,y)
        elif self.family=="rf":
            self.model=RandomForestClassifier(n_estimators=160,max_depth=11,min_samples_leaf=3,class_weight="balanced_subsample",random_state=111,n_jobs=-1).fit(X,y)
        else:
            self.model=ExtraTreesClassifier(n_estimators=180,max_depth=12,min_samples_leaf=3,class_weight="balanced",random_state=113,n_jobs=-1).fit(X,y)
        return self
    def predict(self,X):
        if self.model is None:return np.full(len(X),self.constant)
        if self.scaler is not None:X=self.scaler.transform(X)
        return self.model.predict_proba(X)[:,1]

def train_models(data,held,family):
    models={}
    for g in GROUPS:
        X=np.concatenate([data[s]["streams"][g]["X"] for s in SONGS if s!=held])
        y=np.concatenate([data[s]["labels"][g] for s in SONGS if s!=held])
        models[g]=Binary(family).fit(X,y)
    return models

def estimate_phase(events,meta):
    bpm=float(meta["bpm"]);ts=meta.get("timeSignature") or {"numerator":4,"denominator":4}
    num=int(ts.get("numerator",4));den=int(ts.get("denominator",4));beat=60/bpm*4/den;bar=beat*num
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;score=0.
        for e in events:
            w=1.8 if e["group"]=="kick" else .8 if e["group"]=="snare" else 0
            if not w:continue
            x=(e["time"]-ph)%bar;d=min(x,bar-x)
            score+=w*e["prob"]*math.exp(-.5*(d/max(.03,beat*.1))**2)
        if score>best[0]:best=(score,ph)
    return best[1]

def periodic_support(times,t,bpm):
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.06 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def postprocess(events,meta,profile):
    bpm=float(meta["bpm"]);ts=meta.get("timeSignature") or {"numerator":4,"denominator":4}
    num=int(ts.get("numerator",4));den=int(ts.get("denominator",4));beat=60/bpm*4/den;bar=beat*num
    phase=estimate_phase(events,meta)
    out=[]
    by=defaultdict(list)
    for e in events:by[e["group"]].append(e)
    for g,arr in by.items():
        arr=sorted(arr,key=lambda x:x["time"]);times=[x["time"] for x in arr];last=-999.
        for e in arr:
            if e["time"]-last<MIN_DIST[g]:continue
            keep=True
            if g=="crash":
                x=(e["time"]-phase)%bar;hd=min(x,bar-x)/beat
                keep=hd<=profile["crash_head_beats"]
            elif g=="ride" and profile["rhythm"]!="none":
                keep=periodic_support(times,e["time"],bpm)>=profile["ride_periodic"]
            elif g=="hat" and profile["rhythm"]=="strict":
                keep=e["prob"]>=profile["hat_strong"] or periodic_support(times,e["time"],bpm)>=.5
            elif g=="tom" and profile["rhythm"]=="strict":
                nearby=sum(abs(x-e["time"])<=.7 for x in times)
                x=(e["time"]-phase)%bar;tohead=(bar-x)/beat if x>0 else 0
                keep=e["prob"]>=.80 or nearby>=2 or (0<tohead<=1.2)
            if keep:out.append(e);last=e["time"]
    # two-hand hard constraint; kick and pedal_hat are exempt.
    ordered=sorted(out,key=lambda e:e["time"]);final=[];i=0
    while i<len(ordered):
        start=ordered[i]["time"];j=i
        while j<len(ordered) and ordered[j]["time"]-start<=.035:j+=1
        c=ordered[i:j];ex=[e for e in c if e["group"] not in HANDS];hand=[e for e in c if e["group"] in HANDS]
        hand=sorted(hand,key=lambda e:e["prob"],reverse=True)[:2];final.extend(ex+hand);i=j
    return sorted(final,key=lambda e:(e["time"],PITCH[e["group"]]))

def predict_song(data,song,models,thresholds,profile):
    evs=[]
    for g in GROUPS:
        s=data[song]["streams"][g];p=models[g].predict(s["X"])
        for t,pr in zip(s["times"],p):
            if pr>=thresholds[g]:evs.append({"time":float(t),"group":g,"prob":float(pr)})
    return postprocess(evs,data[song]["meta"],profile)

def evaluate_candidate(name,data,family,thresholds,profile,outdir):
    result={"family":family,"thresholds":thresholds,"profile":profile,"songs":{}};tot=Counter()
    for held in SONGS:
        models=train_models(data,held,family);pred=predict_song(data,held,models,thresholds,profile)
        mid=outdir/name/f"{held}.mid";write_midi(mid,pred,float(data[held]["meta"]["bpm"]))
        parsed=ev.midi_events(mid);truth0=ev.midi_events(ROOT/"DruMaster/songs"/held/"chart.mid")
        meta=data[held]["meta"];shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
        sc=ev.score(parsed,truth0,shift);cf=ev.confusion(parsed,truth0,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][held]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,m=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4) if n else 0,"recall":round(tp/m,4) if m else 0,"f1":round(2*tp/(n+m),4) if n+m else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    robust=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        songf=[]
        for sn in SONGS:
            x=result["songs"][sn]["by_group"].get(g,{})
            rr=x.get("reference",0)
            if rr: songf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),
                          "count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(float(np.mean(songf)),4) if songf else None,"worst_song_f1":round(float(np.min(songf)),4) if songf else None}
        if g!="pedal_hat":robust.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    critical=np.mean([s["by_group"][g]["f1"] for g in ("kick","snare","hat","tom","crash","ride")])
    s["selection_score"]=round(s["f1"]+.18*critical-.25*ks,6);result["summary"]=s
    # Canonical detailed timing/false-positive metrics from the real MIDI.
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"]
    return result

def rank(x):
    return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=ROOT/"drumscribe/experiments/generated-search-neural-separation";report={"schema":1,"cycles":[]}
    thresholds=dict(BASE_THR)
    baseprof={"rhythm":"moderate","crash_head_beats":.15,"ride_periodic":.55,"hat_strong":.82}
    with tempfile.TemporaryDirectory(prefix="drumscribe-sep-") as td:
        allsep=prepare_separations(Path(td))
        datasets={m:build_method_dataset(allsep,m) for m in ("dsp","mdx","ensemble")}

        # Cycle 49: separation front end.
        res={}
        for method in ("dsp","mdx","ensemble"):
            name="c49_"+method
            print("EVAL",name,flush=True)
            res[name]=evaluate_candidate(name,datasets[method],"extra",thresholds,baseprof,root/"cycle49")
            res[name]["separation_method"]=method
            print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
        rr=rank(res);win=rr[0][0];best_method=res[win]["separation_method"]
        report["cycles"].append({"cycle":49,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

        # Cycle 50: classifier family.
        data=datasets[best_method];res={}
        for fam in ("logistic","rf","extra"):
            name="c50_"+fam;res[name]=evaluate_candidate(name,data,fam,thresholds,baseprof,root/"cycle50");res[name]["separation_method"]=best_method
            print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
        rr=rank(res);win=rr[0][0];best_family=res[win]["family"]
        report["cycles"].append({"cycle":50,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

        # Cycle 51: operating point / rhythm strategy.
        res={}
        configs=[
          ("c51_precision",1.10,{"rhythm":"strict","crash_head_beats":.12,"ride_periodic":.75,"hat_strong":.86}),
          ("c51_balanced",1.00,{"rhythm":"moderate","crash_head_beats":.15,"ride_periodic":.55,"hat_strong":.82}),
          ("c51_recall",.90,{"rhythm":"none","crash_head_beats":.18,"ride_periodic":.40,"hat_strong":.78}),
        ]
        for name,mult,prof in configs:
            th={g:min(.95,max(.25,v*mult)) for g,v in thresholds.items()}
            res[name]=evaluate_candidate(name,data,best_family,th,prof,root/"cycle51");res[name]["separation_method"]=best_method
            print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
        rr=rank(res);win=rr[0][0]
        report["cycles"].append({"cycle":51,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
        report["final"]={"winner":win,"separation_method":best_method,"classifier":best_family,"summary":res[win]["summary"],"thresholds":res[win]["thresholds"],"profile":res[win]["profile"],"detailed":res[win]["detailed"]}
        (ROOT/"drumscribe/experiments/results-iterative-neural-separation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
