"""Distill a DrumSep hi-hat onset teacher into a drums-only lightweight student.

Teacher:
- mdxnet-infer DrumSep 6-stem "hh" output.
- Used only on fixed, chart-independent short windows of TRAIN songs.
- Model weights are never committed.

Student inference:
- original drums.mp3 only.
- 10 ms frames, compact spectral band/context features.
- ExtraTrees predicts HH-onset probability.
- low-threshold probability peaks form an independent candidate stream.

Open-HH rescue:
- current retained open-hat events remain untouched.
- candidates within 60 ms of any current hat are removed.
- a second drums-only classifier selects which new HH candidates are Open 46.
- rescue only ADDS GM46; kick/snare/tom/ride/crash are never removed/relabelled.

Three articulation hypotheses over the same distilled candidate stream:
A acoustic_only:
  robust-normalized 26-D timbre/decay features.
B acoustic_student:
  A + student onset probability/local probability shape.
C acoustic_student_gmd:
  B model for student/context, while the acoustic submodel is additionally
  regularized by GMD128 open/closed rows; probabilities are fused.

Strict leave-one-song-out:
- held-out chart is final scoring only.
- held-out DrumSep stem is NEVER used for training or inference.
- threshold is selected by inner LOO over the four outer-training songs.
"""
from __future__ import annotations
import importlib.util,json,math,subprocess,tempfile
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import find_peaks
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
SR=44100; HOP=441; NFFT=1024
WINDOW=np.hanning(NFFT).astype(np.float32)
FREQ=np.fft.rfftfreq(NFFT,1/SR)
BASE_THRESHOLD=.575
STUDENT_CANDIDATE_THRESHOLD=.20
RESCUE_THRESHOLDS=[.45,.55,.62,.68,.74,.80,.86,.91,.95,.98,1.01]
TEACHER_SEG_SEC=18.0
TEACHER_FRACTIONS=(.28,.68)
BAND_EDGES=np.geomspace(350,20000,13)

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ov=loadmod("distill_ov",EXP/"open_hat_overlay_gmd_loo.py")
ext=ov.ext; sn=ov.sn; oh=ov.oh

def duration(song):
    s=subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration",
       "-of","default=noprint_wrappers=1:nokey=1",str(ROOT/"DruMaster/songs"/song/"drums.mp3")],text=True)
    return float(s.strip())

def decode_mono(song,start=None,length=None):
    cmd=["ffmpeg","-v","error"]
    if start is not None:cmd+=["-ss",str(start)]
    if length is not None:cmd+=["-t",str(length)]
    cmd+=["-i",str(ROOT/"DruMaster/songs"/song/"drums.mp3"),"-ac","1","-ar",str(SR),
          "-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

def decode_stereo(song,start,length,tmp):
    p=tmp/f"{song}-{start:.3f}.wav"
    subprocess.check_call(["ffmpeg","-v","error","-y","-ss",str(start),"-t",str(length),
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

def frame_matrix(x):
    n=max(0,1+(len(x)-NFFT)//HOP)
    out=[]
    for start in range(0,n,3000):
        ids=np.arange(start,min(n,start+3000))
        fr=np.stack([x[i*HOP:i*HOP+NFFT] for i in ids]).astype(np.float32)
        mag=np.abs(np.fft.rfft(fr*WINDOW[None,:],axis=1)).astype(np.float32)+1e-8
        logs=[]
        for lo,hi in zip(BAND_EDGES[:-1],BAND_EDGES[1:]):
            m=(FREQ>=lo)&(FREQ<hi)
            logs.append(np.log1p(mag[:,m].mean(axis=1)))
        E=np.stack(logs,axis=1)
        out.append(E)
    E=np.concatenate(out,axis=0) if out else np.zeros((0,len(BAND_EDGES)-1),np.float32)
    if not len(E):return np.zeros((0,75),np.float32)
    # song/segment internal robust normalization, available at inference.
    med=np.median(E,axis=0);q1=np.percentile(E,25,axis=0);q3=np.percentile(E,75,axis=0)
    Z=np.clip((E-med)/np.maximum(q3-q1,1e-4),-8,8).astype(np.float32)
    D=np.maximum(np.diff(Z,axis=0,prepend=Z[:1]),0).astype(np.float32)
    blocks=[]
    for off in (-2,-1,0,1,2):
        idx=np.clip(np.arange(len(Z))+off,0,len(Z)-1)
        blocks.extend([Z[idx],D[idx]])
    # 12 bands * energy/flux * 5 context = 120 dimensions.
    return np.concatenate(blocks,axis=1).astype(np.float32)

def teacher_peaks(hh):
    # RMS/log-envelope on separated HH stem. Broad onset target.
    win=882;n=max(0,1+(len(hh)-win)//HOP)
    e=np.zeros(n,np.float32)
    for i in range(n):
        z=hh[i*HOP:i*HOP+win];e[i]=np.sqrt(np.mean(z*z)+1e-12)
    le=np.log(e+1e-7);fl=np.maximum(np.diff(le,prepend=le[0]),0)
    def rz(a):
        return (a-np.median(a))/max(np.percentile(a,75)-np.percentile(a,25),1e-6)
    score=rz(fl)+.12*np.maximum(rz(le),0)
    floor=max(float(np.percentile(score,57)),.03)
    p,_=find_peaks(score,height=floor,prominence=.02,distance=max(1,round(.025*SR/HOP)))
    # Ignore separator edges.
    p=p[(p*HOP/SR>=.5)&(p*HOP/SR<=TEACHER_SEG_SEC-.6)]
    return p,score

def make_teacher_data(engine,song,tmp):
    dur=duration(song);Xs=[];ys=[];meta=[]
    for frac in TEACHER_FRACTIONS:
        center=dur*frac;start=max(0,min(dur-TEACHER_SEG_SEC,center-TEACHER_SEG_SEC/2))
        stereo=decode_stereo(song,start,TEACHER_SEG_SEC,tmp)
        stems=engine.separate(stereo,sample_rate=SR)
        hh=mono(stems["hh"])
        original=stereo.mean(axis=1)
        X=frame_matrix(original)
        peaks,score=teacher_peaks(hh)
        n=min(len(X),max(0,1+(len(hh)-882)//HOP))
        X=X[:n]
        pos=set()
        for p in peaks:
            for d in (-1,0,1):
                j=int(p+d)
                if 0<=j<n:pos.add(j)
        pos=np.asarray(sorted(pos),int)
        neg=np.asarray([i for i in range(n) if all(abs(i-p)>4 for p in peaks)],int)
        rng=np.random.default_rng(2100+SONGS.index(song)*17+int(frac*100))
        cap=max(600,5*len(pos))
        if len(neg)>cap:neg=rng.choice(neg,cap,replace=False)
        ids=np.sort(np.concatenate([pos,neg]))
        y=np.isin(ids,pos).astype(np.int8)
        Xs.append(X[ids]);ys.append(y)
        meta.append({"startSec":start,"frames":len(ids),"positive":int(y.sum()),"teacherPeaks":len(peaks)})
        print("TEACHER_SEG",song,frac,json.dumps(meta[-1]),flush=True)
    return np.concatenate(Xs),np.concatenate(ys),meta

def fit_student(teacher,songs,seed):
    X=np.concatenate([teacher[s]["X"] for s in songs]);y=np.concatenate([teacher[s]["y"] for s in songs])
    model=ExtraTreesClassifier(n_estimators=260,max_depth=13,min_samples_leaf=2,max_features="sqrt",
      class_weight="balanced",random_state=2400+seed,n_jobs=-1).fit(X,y)
    return model,{"rows":len(y),"positive":int(y.sum()),"songs":list(songs)}

def student_stream(model,x):
    X=frame_matrix(x);p=model.predict_proba(X)
    cls=list(model.classes_);prob=p[:,cls.index(1)] if 1 in cls else np.zeros(len(X))
    # Broad local maxima only; open classifier handles precision.
    peaks,_=find_peaks(prob,height=STUDENT_CANDIDATE_THRESHOLD,
      distance=max(1,round(.025*SR/HOP)),prominence=.015)
    return peaks*HOP/SR,prob,peaks

def near(xs,t,w=.080):return any(abs(t-u)<=w for u in xs)

def robust_rows(basis,rows):
    if not len(rows):return np.zeros((0,basis.shape[1]),np.float32)
    med=np.median(basis,axis=0);q1=np.percentile(basis,25,axis=0);q3=np.percentile(basis,75,axis=0)
    return np.clip((rows-med)/np.maximum(q3-q1,1e-3),-8,8).astype(np.float32)

def build_candidates(d,s,student):
    x=d[s]["audio"];times,prob,peaks=student_stream(student,x)
    # Remove existing hand-hat candidates: this stream is rescue-only.
    keep=np.asarray([not near(d[s]["hats"],t,.060) for t in times],bool)
    times=times[keep];peaks=peaks[keep]
    raw=np.stack([oh.timbre_features(x,t) for t in times]) if len(times) else np.zeros((0,26),np.float32)
    # candidate-based normalization is inference-safe.
    norm=robust_rows(raw,raw) if len(raw) else raw
    ctx=[]
    for i in peaks:
        lo=max(0,i-2);hi=min(len(prob),i+3)
        ctx.append([float(prob[i]),float(np.mean(prob[lo:hi])),float(np.max(prob[lo:hi])),
                    float(prob[max(0,i-2)]),float(prob[min(len(prob)-1,i+2)])])
    ctx=np.asarray(ctx,np.float32) if ctx else np.zeros((0,5),np.float32)
    X=np.concatenate([norm,ctx],axis=1)
    y=np.asarray([1 if near(d[s]["refs"][46],t,.080) else 0 for t in times],np.int8)
    return {"times":times,"Xa":norm,"Xc":X,"y":y,
            "counts":{"candidates":len(times),"positiveCandidateRows":int(y.sum()),
                      "distinctOpenCoverage":greedy_coverage(times,d[s]["refs"][46])}}

def greedy_coverage(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        cand=[(abs(t-u),j) for j,u in enumerate(ref) if j not in used and abs(t-u)<=w]
        if cand:
            _,j=min(cand);used.add(j);tp+=1
    return tp

def fit_open(cands,songs,variant,gmd,seed):
    XX=[];yy=[]
    for s in songs:
        c=cands[s];X=c["Xa"] if variant=="acoustic_only" else c["Xc"];y=c["y"]
        pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0)
        rng=np.random.default_rng(3100+seed+SONGS.index(s)*19)
        cap=max(300,5*len(pos))
        if len(neg)>cap:neg=rng.choice(neg,cap,replace=False)
        ids=np.sort(np.concatenate([pos,neg]))
        XX.append(X[ids]);yy.append(y[ids])
    X=np.concatenate(XX);y=np.concatenate(yy)
    model=ExtraTreesClassifier(n_estimators=340,max_depth=14,min_samples_leaf=3,max_features="sqrt",
      class_weight="balanced",random_state=3200+seed,n_jobs=-1).fit(X,y)
    gmodel=None
    if variant=="acoustic_student_gmd":
        gx,gy=gmd
        # acoustic-only auxiliary model: training candidates + retained GMD128.
        ax=[];ay=[]
        for s in songs:
            c=cands[s];pos=np.flatnonzero(c["y"]==1);neg=np.flatnonzero(c["y"]==0)
            rng=np.random.default_rng(4100+seed+SONGS.index(s))
            cap=max(300,5*len(pos))
            if len(neg)>cap:neg=rng.choice(neg,cap,replace=False)
            ids=np.sort(np.concatenate([pos,neg]))
            ax.append(c["Xa"][ids]);ay.append(c["y"][ids])
        ax.append(gx);ay.append(gy)
        gmodel=ExtraTreesClassifier(n_estimators=320,max_depth=13,min_samples_leaf=4,
          class_weight="balanced",random_state=3300+seed,n_jobs=-1).fit(np.concatenate(ax),np.concatenate(ay))
    return (model,gmodel),{"rows":len(y),"positive":int(y.sum())}

def p1(m,X):
    if not len(X):return np.zeros(0)
    p=m.predict_proba(X);cls=list(m.classes_)
    return p[:,cls.index(1)] if 1 in cls else np.zeros(len(X))

def open_prob(models,c,variant):
    m,gm=models
    if variant=="acoustic_only":return p1(m,c["Xa"])
    p=p1(m,c["Xc"])
    if variant=="acoustic_student_gmd":
        pg=p1(gm,c["Xa"])
        return .72*p+.28*pg
    return p

def fit_base(d,songs,gx,gy):
    X=np.concatenate([*(d[s]["X"]["timbre_norm"] for s in songs),gx])
    y=np.concatenate([*((d[s]["y"]==1).astype(np.int8) for s in songs),gy])
    return ExtraTreesClassifier(n_estimators=320,max_depth=13,min_samples_leaf=4,
      class_weight="balanced",random_state=560,n_jobs=-1).fit(X,y)

def score(d,s,bm,c,models,variant,th):
    hp=p1(bm,d[s]["X"]["timbre_norm"])
    bo=[t for t,p in zip(d[s]["hats"],hp) if p>=BASE_THRESHOLD]
    bc=[t for t,p in zip(d[s]["hats"],hp) if p<BASE_THRESHOLD]
    rp=open_prob(models,c,variant)
    rescue=[t for t,p in zip(c["times"],rp) if p>=th and not near(bo,t,.060)]
    met=oh.articulation_metrics(sorted(bo+rescue),bc,d[s]["refs"])
    return met,{"baseOpen":len(bo),"studentCandidates":len(rp),"rescued":len(rescue),
      "studentDistinctOpenCoverage":c["counts"]["distinctOpenCoverage"],
      "candidatePositiveRowsDiagnostic":c["counts"]["positiveCandidateRows"],
      "maxOpenProb":float(np.max(rp)) if len(rp) else 0.}

def aggregate(per):
    z=Counter()
    for m in per.values():
      for c in ("open","closed"):
        q=m[c];z[f"{c}t"]+=q["tp"];z[f"{c}p"]+=q["predicted"];z[f"{c}r"]+=q["reference"]
    out={}
    for c in ("open","closed"):
      tp,p,r=z[f"{c}t"],z[f"{c}p"],z[f"{c}r"]
      out[c]={"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,
              "recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"]);return out

def build_for_split(d,teacher,train_songs,target_songs,seed):
    sm,info=fit_student(teacher,train_songs,seed)
    c={s:build_candidates(d,s,sm) for s in target_songs}
    return sm,info,c

def choose(d,teacher,outer,gx,gy,variant):
    cache={}
    for i,val in enumerate(outer):
        tr=[s for s in outer if s!=val]
        _,sinfo,c=build_for_split(d,teacher,tr,[*tr,val],500+i)
        om,oinfo=fit_open(c,tr,variant,(gx,gy),600+i)
        bm=fit_base(d,tr,gx,gy)
        cache[val]=(bm,c[val],om,sinfo,oinfo)
    base={s:score(d,s,cache[s][0],cache[s][1],cache[s][2],variant,1.01)[0] for s in outer}
    b=aggregate(base);rows=[]
    for th in RESCUE_THRESHOLDS:
        per={}
        for s,(bm,c,om,_,_) in cache.items():per[s]=score(d,s,bm,c,om,variant,th)[0]
        a=aggregate(per)
        eligible=(a["open"]["precision"]>=b["open"]["precision"]-.025 and
                  a["open"]["f1"]>b["open"]["f1"] and a["macroF1"]>b["macroF1"])
        util=a["macroF1"]+.08*a["open"]["precision"]
        rows.append((eligible,util,th,a))
    rows.sort(key=lambda x:(x[0],x[1]),reverse=True)
    best=next((x for x in rows if x[0]),None)
    return (best[2] if best else 1.01),{"base":b,"ranking":[{"threshold":r[2],"eligible":r[0],"utility":r[1],"summary":r[3]} for r in rows]}

def evaluate(d,teacher,gx,gy,variant):
    per={};folds={}
    for oi,held in enumerate(SONGS):
        outer=[s for s in SONGS if s!=held]
        th,inner=choose(d,teacher,outer,gx,gy,variant)
        _,sinfo,c=build_for_split(d,teacher,outer,[*outer,held],700+oi)
        om,oinfo=fit_open(c,outer,variant,(gx,gy),800+oi)
        bm=fit_base(d,outer,gx,gy)
        m,diag=score(d,held,bm,c[held],om,variant,th)
        per[held]=m;folds[held]={"threshold":th,"metrics":m,"diag":diag,
           "studentTrain":sinfo,"openTrain":oinfo,"inner":inner}
        print("DISTILL_FOLD",variant,held,th,json.dumps({"open":m["open"],"diag":diag}),flush=True)
    return {"variant":variant,"summary":aggregate(per),"songs":per,"folds":folds}

def main():
    from mdxnet_infer import MDX23CInference
    d=sn.prepare()
    for s in SONGS:d[s]["audio"]=decode_mono(s)
    engine=MDX23CInference.from_pretrained("drumsep-6stem",device="cpu")
    teacher={}
    with tempfile.TemporaryDirectory() as td:
      tmp=Path(td)
      for s in SONGS:
        X,y,meta=make_teacher_data(engine,s,tmp)
        teacher[s]={"X":X,"y":y,"segments":meta}
    gx,gy,_,_,manifest=ov.gmd_collect()

    # Baseline on the exact input snapshot used by this workflow.
    base={}
    for held in SONGS:
        bm=fit_base(d,[s for s in SONGS if s!=held],gx,gy)
        hp=p1(bm,d[held]["X"]["timbre_norm"])
        bo=[t for t,p in zip(d[held]["hats"],hp) if p>=BASE_THRESHOLD]
        bc=[t for t,p in zip(d[held]["hats"],hp) if p<BASE_THRESHOLD]
        base[held]=oh.articulation_metrics(bo,bc,d[held]["refs"])
    baseline=aggregate(base)

    result={"schema":1,"description":"DrumSep HH-onset teacher distilled to drums-only student; strict nested LOO.",
      "teacher":{"model":"drumsep-6stem","segmentSec":TEACHER_SEG_SEC,"fractions":TEACHER_FRACTIONS,
                 "license":"teacher only; weights not redistributed",
                 "segments":{s:teacher[s]["segments"] for s in SONGS}},
      "studentCandidateThreshold":STUDENT_CANDIDATE_THRESHOLD,
      "baseline":baseline,"variants":{}}
    for v in ("acoustic_only","acoustic_student","acoustic_student_gmd"):
        q=evaluate(d,teacher,gx,gy,v);s=q["summary"]
        q["passesGuard"]=(s["macroF1"]>baseline["macroF1"] and s["open"]["f1"]>baseline["open"]["f1"] and
                          s["open"]["precision"]>=baseline["open"]["precision"]-.025)
        result["variants"][v]=q
        print("DISTILL_RESULT",v,json.dumps({"passes":q["passesGuard"],"summary":s}),flush=True)
    elig=[q for q in result["variants"].values() if q["passesGuard"]]
    best=max(elig,key=lambda q:(q["summary"]["macroF1"],q["summary"]["open"]["f1"])) if elig else None
    result["retained"]=best["variant"] if best else "none";result["retainedSummary"]=best["summary"] if best else baseline
    (EXP/"results-open-hat-drumsep-distill-loo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("DISTILL_RETAINED",result["retained"],json.dumps(result["retainedSummary"]),flush=True)

if __name__=="__main__":main()
