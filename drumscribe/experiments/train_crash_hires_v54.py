from __future__ import annotations
import importlib.util,json,subprocess,wave
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,ExtraTreesClassifier
from sklearn.preprocessing import StandardScaler
from scipy.signal import resample_poly

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";D=EXP/"generated-crash-diagnostics-v54"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"];SR=44100;NFFT=4096
BANDS=[(800,2500),(2500,5000),(5000,8000),(8000,12000),(12000,17000),(17000,22000)]
OFFSETS=[.012,.080,.180,.350]
FEATURE_NAMES=[]
for o in OFFSETS:
    for lo,hi in BANDS:FEATURE_NAMES.append(f"b{o:.3f}_{lo}_{hi}")
FEATURE_NAMES += ["centroid","flatness","roll85","simCrash","simClosed","simOpen","simRide"]
for a,b in [(0,.025),(.025,.060),(.060,.120),(.120,.220),(.220,.400),(.400,.650)]:FEATURE_NAMES.append(f"rms_{a}_{b}")
FEATURE_NAMES += ["tail80","tail180","tail350","lowmidTail180","highShare","bodyShare",
                  "adtofConfidence","periodic","headDistance","hatSupport"]

spec=importlib.util.spec_from_file_location("ev54",EXP/"evaluate_v2.py");ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def decode(path):
    cmd=["ffmpeg","-v","error","-i",str(path),"-ac","1","-ar",str(SR),"-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()
def load_asset(note):
    p=ROOT/"DruMaster/assets/drums"/f"{note}.wav"
    with wave.open(str(p)) as w:
        raw=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").astype(np.float32)/32768
        raw=raw.reshape(-1,w.getnchannels()).mean(axis=1);src=w.getframerate()
    if src!=SR:raw=resample_poly(raw,SR,src).astype(np.float32)
    return raw
WIN=np.hanning(NFFT).astype(np.float32);FREQ=np.fft.rfftfreq(NFFT,1/SR)
def spectrum(x,center):
    lo=int(round(center*SR))-NFFT//2
    frame=np.zeros(NFFT,np.float32)
    a=max(0,lo);b=min(len(x),lo+NFFT)
    if b>a:frame[a-lo:b-lo]=x[a:b]
    return np.abs(np.fft.rfft(frame*WIN)).astype(np.float64)+1e-12
def asset_template(note):
    x=load_asset(note); return spectrum(x,.025)
T={n:asset_template(n) for n in [49,42,46,51]}
def cosine(a,b):return float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-12))
def rms(x,t,a,b):
    lo=max(0,int((t+a)*SR));hi=min(len(x),int((t+b)*SR))
    if hi<=lo:return 1e-9
    return float(np.sqrt(np.mean(x[lo:hi]**2)+1e-12))
def hires_features(x,t,c):
    specs=[spectrum(x,t+o) for o in OFFSETS]
    onset=specs[0];total=float(onset.sum());vals=[]
    for sp in specs:
        st=float(sp.sum())
        for lo,hi in BANDS:
            vals.append(float(sp[(FREQ>=lo)&(FREQ<hi)].sum()/(st+1e-12)))
    centroid=float((FREQ*onset).sum()/(total+1e-12)/22050)
    flat=float(np.exp(np.mean(np.log(onset)))/(np.mean(onset)+1e-12))
    cs=np.cumsum(onset);roll=float(FREQ[np.searchsorted(cs,.85*cs[-1])]/22050)
    vals += [centroid,flat,roll,cosine(onset,T[49]),cosine(onset,T[42]),cosine(onset,T[46]),cosine(onset,T[51])]
    rs=[rms(x,t,a,b) for a,b in [(0,.025),(.025,.060),(.060,.120),(.120,.220),(.220,.400),(.400,.650)]]
    r0=max(rs[0],1e-9);vals += [float(np.log(max(r,1e-9)/r0)) for r in rs]
    def band_sum(sp,lo,hi):return float(sp[(FREQ>=lo)&(FREQ<hi)].sum())
    onset_hi=band_sum(onset,5000,18000)+1e-12;onset_lm=band_sum(onset,800,5000)+1e-12
    vals += [
      float(band_sum(specs[1],5000,18000)/onset_hi),
      float(band_sum(specs[2],5000,18000)/onset_hi),
      float(band_sum(specs[3],5000,18000)/onset_hi),
      float(band_sum(specs[2],800,5000)/onset_lm),
      float(band_sum(onset,5000,18000)/(band_sum(onset,800,18000)+1e-12)),
      float(band_sum(onset,800,5000)/(band_sum(onset,800,18000)+1e-12)),
      float(c.get("baseConfidence",0)),float(c.get("periodicSupport",0)),
      float(c.get("headDistance",9)),1.0 if c.get("hatSupport") else 0.0
    ]
    return np.array(vals,dtype=np.float64)

def refs(song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text());shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    return sorted(t+shift for t,g,n in ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid") if n in {49,52,55,57})
def labels(times,truth,w=.080):
    used=set();out=[0]*len(times)
    for i in sorted(range(len(times)),key=lambda i:times[i]):
        c=[(abs(times[i]-u),j) for j,u in enumerate(truth) if j not in used and abs(times[i]-u)<=w]
        if c:_,j=min(c);used.add(j);out[i]=1
    return out

data={}
for song in SONGS:
    side=json.loads((D/f"{song}.json").read_text());cand=side["adtofInfo"]["cymbalPolicy"].get("crashCandidates",[])
    truth=refs(song);ys=labels([float(c["time"]) for c in cand],truth);audio=decode(ROOT/"DruMaster/songs"/song/"drums.mp3")
    rows=[]
    for c,y in zip(cand,ys):
        eligible=float(c.get("headDistance",9))<=.30 and not bool(c.get("crashSupport"))
        rows.append({"y":int(y),"eligible":eligible,"x":hires_features(audio,float(c["time"]),c)})
    data[song]={"rows":rows,"refs":len(truth)}

def score(song,keep):
    rows=data[song]["rows"];tp=sum(r["y"] for r,k in zip(rows,keep) if k);p=sum(keep);ref=data[song]["refs"]
    return {"tp":int(tp),"predicted":int(p),"reference":int(ref),"precision":tp/p if p else 0.,"recall":tp/ref if ref else 0.,"f1":2*tp/(p+ref) if p+ref else 0.,"falsePositive":int(p-tp)}
def agg(ss):
    tp=sum(s["tp"] for s in ss);p=sum(s["predicted"] for s in ss);r=sum(s["reference"] for s in ss)
    return {"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,"recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.,"falsePositive":p-tp}
baseline=agg([score(s,[True]*len(data[s]["rows"])) for s in SONGS])

def all_train(train):
    rows=[r for s in train for r in data[s]["rows"] if r["eligible"]]
    X=np.stack([r["x"] for r in rows]);y=np.array([r["y"] for r in rows],int)
    return X,y
def threshold_grid(probs):
    u=np.unique(np.round(probs,8));return np.r_[0,(u[:-1]+u[1:])/2,u,1.0000001]
def pick_threshold(train,probfn):
    probs={s:probfn(s) for s in train};best=None
    vals=np.concatenate([probs[s] for s in train if len(probs[s])])
    for th in threshold_grid(vals):
        scores=[]
        for s in train:
            it=iter(probs[s]);keep=[]
            for r in data[s]["rows"]:keep.append(True if not r["eligible"] else next(it)>=th)
            scores.append(score(s,keep))
        a=agg(scores);rank=(a["f1"],a["precision"],a["recall"])
        if best is None or rank>best[0]:best=(rank,float(th))
    return best[1]

def fit_model(kind,train):
    X,y=all_train(train)
    scaler=None
    if kind=="logistic":
        scaler=StandardScaler().fit(X);model=LogisticRegression(C=.5,class_weight="balanced",max_iter=3000,random_state=0).fit(scaler.transform(X),y)
    elif kind=="rf":
        model=RandomForestClassifier(n_estimators=320,max_depth=6,min_samples_leaf=2,max_features=.65,class_weight="balanced",random_state=0,n_jobs=-1).fit(X,y)
    else:
        model=ExtraTreesClassifier(n_estimators=320,max_depth=7,min_samples_leaf=2,max_features=.8,class_weight="balanced",random_state=0,n_jobs=-1).fit(X,y)
    def prob_song(s):
        Xs=np.stack([r["x"] for r in data[s]["rows"] if r["eligible"]]) if any(r["eligible"] for r in data[s]["rows"]) else np.empty((0,len(FEATURE_NAMES)))
        if len(Xs)==0:return np.array([])
        return model.predict_proba(scaler.transform(Xs) if scaler is not None else Xs)[:,1]
    th=pick_threshold(train,prob_song)
    return scaler,model,th,prob_song

methods={}
for kind in ["logistic","rf","extra_trees"]:
    folds=[]
    for held in SONGS:
        train=[s for s in SONGS if s!=held];scaler,model,th,pfn=fit_model(kind,train);pp=pfn(held);it=iter(pp)
        keep=[True if not r["eligible"] else next(it)>=th for r in data[held]["rows"]]
        folds.append({"held":held,"threshold":th,"score":score(held,keep)})
    methods[kind]={"folds":folds,"aggregate":agg([f["score"] for f in folds])}

best=max(methods,key=lambda k:(methods[k]["aggregate"]["f1"],methods[k]["aggregate"]["precision"]))
out={"schema":1,"date":"2026-09-23","experiment":"44.1k crash guard v54","baseline":baseline,"methods":methods,"best":best,
     "features":FEATURE_NAMES,"candidateCounts":{s:{"predicted":len(data[s]["rows"]),"eligible":sum(r["eligible"] for r in data[s]["rows"]),"reference":data[s]["refs"]} for s in SONGS},
     "referencePolicy":"fresh browser candidates first; chart.mid only labels after prediction; each LOO held song excluded from model and threshold fitting."}
(EXP/"results-crash-hires-v54.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False,indent=2))
