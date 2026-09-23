"""Exploratory MDX23C DrumSep hi-hat teacher diagnostic.

Uses the community DrumSep 6-stem model through mdxnet-infer at workflow runtime.
Weights are NOT committed to this repository. Their original license is not
formally documented, so this experiment is teacher/diagnostic only.

Stage 1 deliberately runs two contrasting songs:
- diamondvirgin: current open-HH candidate bottleneck
- nanairo: current open-HH candidate coverage is already high

If the separated HH stem materially raises audio-only open-HH candidate coverage
for diamondvirgin without destroying nanairo, expand to all songs and distill a
browser-safe student in a later cycle.
"""
from __future__ import annotations
import importlib.util,json,subprocess,tempfile
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import find_peaks

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["diamondvirgin","nanairo"]
SR=44100;HOP=441;WIN=882

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
oh=loadmod("drumsep_teacher_oh",EXP/"open_hat_loo.py")

def stereo_wav(song,tmp):
    p=tmp/f"{song}.wav"
    subprocess.check_call(["ffmpeg","-v","error","-y","-i",str(ROOT/"DruMaster/songs"/song/"drums.mp3"),
                           "-ac","2","-ar",str(SR),str(p)])
    rate,x=wavfile.read(p)
    if x.dtype.kind in "iu":
        info=np.iinfo(x.dtype);x=x.astype(np.float32)/max(abs(info.min),info.max)
    else:x=x.astype(np.float32)
    if x.ndim==1:x=np.stack([x,x],axis=1)
    return x

def mono_stem(a):
    x=np.asarray(a,dtype=np.float32)
    if x.ndim==1:return x
    if x.shape[0] in (1,2) and x.shape[1]>x.shape[0]:x=x.T
    return x.mean(axis=1)

def envelope(x):
    n=max(0,1+(len(x)-WIN)//HOP)
    e=np.zeros(n,np.float32)
    for k in range(n):
        z=x[k*HOP:k*HOP+WIN]
        e[k]=np.sqrt(np.mean(z*z)+1e-12)
    le=np.log(e+1e-7)
    med=np.median(le);iq=max(np.percentile(le,75)-np.percentile(le,25),1e-5)
    z=(le-med)/iq
    flux=np.maximum(np.diff(le,prepend=le[0]),0)
    fm=np.median(flux);fi=max(np.percentile(flux,75)-np.percentile(flux,25),1e-6)
    fz=(flux-fm)/fi
    return e,z,fz

def candidates(x):
    e,z,fz=envelope(x)
    score=fz+.12*np.maximum(z,0)
    floor=max(float(np.percentile(score,58)),.05)
    peaks,_=find_peaks(score,height=floor,distance=max(1,round(.028*SR/HOP)),prominence=.03)
    # keep broad candidate pool, strongest first if pathological
    if len(peaks)>5000:
        peaks=peaks[np.argsort(score[peaks])[-5000:]]
        peaks=np.sort(peaks)
    return peaks*HOP/SR,e,score,peaks

def near(xs,t,w=.080):
    return any(abs(x-t)<=w for x in xs)

def greedy_coverage(cand,ref,w=.080):
    used=set();tp=0
    for t in cand:
        best=None
        for j,u in enumerate(ref):
            if j in used:continue
            d=abs(t-u)
            if d<=w and (best is None or d<best[0]):best=(d,j)
        if best is not None:
            used.add(best[1]);tp+=1
    return tp

def tail_score(e,peaks):
    out=[]
    for i in peaks:
        def mean(a,b):
            lo=max(0,i+round(a*SR/HOP));hi=min(len(e),i+round(b*SR/HOP))
            return float(np.mean(e[lo:hi])) if hi>lo else 0.
        attack=mean(0,.05)+1e-8
        tail=(mean(.08,.18)+mean(.18,.35)+mean(.35,.55))/3
        out.append(np.log((tail+1e-8)/attack))
    return np.asarray(out,float)

def auc_rank(y,s):
    y=np.asarray(y);s=np.asarray(s);p=s[y==1];n=s[y==0]
    if not len(p) or not len(n):return None
    # Mann-Whitney AUC
    return float(np.mean(p[:,None]>n[None,:])+.5*np.mean(p[:,None]==n[None,:]))

def main():
    from mdxnet_infer import MDX23CInference
    engine=MDX23CInference.from_pretrained("drumsep-6stem",device="cpu")
    out={"schema":1,"model":"mdxnet-infer drumsep-6stem","teacherOnly":True,
         "licenseNote":"checkpoint original license not formally documented; weights not redistributed","songs":{}}
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td)
        for song in SONGS:
            print("SEPARATE",song,flush=True)
            audio=stereo_wav(song,tmp)
            stems=engine.separate(audio,sample_rate=SR)
            if "hh" not in stems:raise RuntimeError(f"hh stem missing: {list(stems)}")
            hh=mono_stem(stems["hh"])
            cand,e,score,peaks=candidates(hh)
            truth=oh.truth(song)
            ro=sorted(t for t,g,p in truth if p==46);rc=sorted(t for t,g,p in truth if p==42)
            co=greedy_coverage(cand,ro);cc=greedy_coverage(cand,rc)
            ts=tail_score(e,peaks)
            labels=[];vals=[]
            for t,v in zip(cand,ts):
                if near(ro,t,.080):labels.append(1);vals.append(v)
                elif near(rc,t,.080):labels.append(0);vals.append(v)
            result={
              "candidateCount":len(cand),
              "open":{"covered":co,"reference":len(ro),"recall":co/len(ro) if ro else 0.},
              "closed":{"covered":cc,"reference":len(rc),"recall":cc/len(rc) if rc else 0.},
              "tailAUCOnMatchedArticulations":auc_rank(labels,vals),
              "matchedForAUC":{"open":int(sum(labels)),"closed":int(len(labels)-sum(labels))},
              "stemRms":float(np.sqrt(np.mean(hh*hh)+1e-12))
            }
            out["songs"][song]=result
            print("TEACHER_RESULT",song,json.dumps(result),flush=True)
    (EXP/"results-open-hat-drumsep-teacher.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
