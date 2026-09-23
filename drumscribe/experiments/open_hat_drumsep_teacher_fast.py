"""Fast, chart-targeted DrumSep HH diagnostic.

This is intentionally NOT a generalization metric: chart.mid is used only to
choose a 35-second open-HH-dense diagnostic window. The purpose is to determine
whether the separated HH stem exposes the acoustics of missing open hats strongly
enough to justify a full teacher/distillation cycle.
"""
from __future__ import annotations
import importlib.util,json,subprocess,tempfile
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import find_peaks

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SR=44100;HOP=441;WIN=882
SONGS=["diamondvirgin","nanairo"];SEG=35.0

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
oh=loadmod("drumsep_fast_oh",EXP/"open_hat_loo.py")

def near(xs,t,w=.080):return any(abs(x-u)<=w for u in xs)

def choose_window(song):
    ro=sorted(t for t,g,p in oh.truth(song) if p==46)
    if not ro:return 0.
    best=(0,0.)
    for t in ro:
        c=sum(t<=u<t+SEG for u in ro)
        if c>best[0]:best=(c,max(0.,t-.5))
    return best[1]

def decode_segment(song,start,tmp):
    p=tmp/f"{song}.wav"
    subprocess.check_call(["ffmpeg","-v","error","-y","-ss",str(start),"-t",str(SEG),
      "-i",str(ROOT/"DruMaster/songs"/song/"drums.mp3"),"-ac","2","-ar",str(SR),str(p)])
    rate,x=wavfile.read(p)
    if x.dtype.kind in "iu":
        inf=np.iinfo(x.dtype);x=x.astype(np.float32)/max(abs(inf.min),inf.max)
    else:x=x.astype(np.float32)
    if x.ndim==1:x=np.stack([x,x],axis=1)
    return x

def mono(a):
    x=np.asarray(a,np.float32)
    if x.ndim==1:return x
    if x.shape[0] in (1,2) and x.shape[1]>x.shape[0]:x=x.T
    return x.mean(axis=1)

def env(x):
    n=max(0,1+(len(x)-WIN)//HOP);e=np.zeros(n,np.float32)
    for i in range(n):
        z=x[i*HOP:i*HOP+WIN];e[i]=np.sqrt(np.mean(z*z)+1e-12)
    l=np.log(e+1e-7);f=np.maximum(np.diff(l,prepend=l[0]),0)
    def rz(a):
        return (a-np.median(a))/max(np.percentile(a,75)-np.percentile(a,25),1e-6)
    return e,rz(l),rz(f)

def candidates(x):
    e,z,f=env(x);score=f+.12*np.maximum(z,0)
    floor=max(float(np.percentile(score,55)),.03)
    p,_=find_peaks(score,height=floor,prominence=.025,distance=max(1,round(.025*SR/HOP)))
    return p*HOP/SR,e,p

def greedy(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        cand=[(abs(t-u),j) for j,u in enumerate(ref) if j not in used and abs(t-u)<=w]
        if cand:
            _,j=min(cand);used.add(j);tp+=1
    return tp

def tail(e,peaks):
    out=[]
    for i in peaks:
        def m(a,b):
            lo=max(0,i+round(a*SR/HOP));hi=min(len(e),i+round(b*SR/HOP))
            return float(np.mean(e[lo:hi])) if hi>lo else 0.
        out.append(np.log((m(.08,.35)+1e-8)/(m(0,.05)+1e-8)))
    return np.asarray(out)

def auc(y,s):
    p=s[np.asarray(y)==1];n=s[np.asarray(y)==0]
    if not len(p) or not len(n):return None
    return float(np.mean(p[:,None]>n[None,:])+.5*np.mean(p[:,None]==n[None,:]))

def main():
    from mdxnet_infer import MDX23CInference
    engine=MDX23CInference.from_pretrained("drumsep-6stem",device="cpu")
    out={"schema":1,"diagnosticOnly":True,"segmentSec":SEG,"songs":{}}
    with tempfile.TemporaryDirectory() as td:
      tmp=Path(td)
      for song in SONGS:
        start=choose_window(song);audio=decode_segment(song,start,tmp)
        print("FAST_SEPARATE",song,start,flush=True)
        stems=engine.separate(audio,sample_rate=SR);hh=mono(stems["hh"])
        cand,e,peaks=candidates(hh);ts=tail(e,peaks)
        truth=oh.truth(song)
        ro=[t-start for t,g,p in truth if p==46 and start<=t<start+SEG]
        rc=[t-start for t,g,p in truth if p==42 and start<=t<start+SEG]
        co=greedy(cand,ro);cc=greedy(cand,rc)
        y=[];v=[]
        for t,q in zip(cand,ts):
            if near(ro,t):y.append(1);v.append(q)
            elif near(rc,t):y.append(0);v.append(q)
        q={"startSec":start,"referenceOpen":len(ro),"referenceClosed":len(rc),
           "candidateCount":len(cand),"openCoverage":co/len(ro) if ro else 0.,
           "openMatched":co,"closedCoverage":cc/len(rc) if rc else 0.,"closedMatched":cc,
           "tailAUC":auc(np.asarray(y),np.asarray(v)) if y else None,
           "matchedForAUC":{"open":int(sum(y)),"closed":int(len(y)-sum(y))}}
        out["songs"][song]=q;print("FAST_RESULT",song,json.dumps(q),flush=True)
    (EXP/"results-open-hat-drumsep-teacher-fast.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
if __name__=="__main__":main()
