"""Evaluate tom-pitch subdivision without changing tom onset detection.

Reference chart.mid is used only here for scoring/diagnostics. Production inference
must never read chart.mid. Three deployable audio-only hypotheses are compared:
1) resonant-peak nearest asset prototype,
2) low-band spectral-profile nearest asset prototype,
3) hybrid peak + profile + centroid score.

A leave-one-song-out real-hit centroid is reported only as a research upper-bound;
it is not a production candidate.
"""
from __future__ import annotations
import importlib.util, json, math, wave
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import resample_poly

ROOT=Path(".")
SPEC=importlib.util.spec_from_file_location("ev",ROOT/"drumscribe/experiments/evaluate_v2.py")
ev=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(ev)
SR=ev.SR
FFT=1024
TOM_NOTES=(41,43,45,47,48,50)
CORE_NOTES=(41,45,47,50)
SONGS=("arcaround","diamondvirgin","kaiju","nanairo","ray")

def load_wav(path:Path):
    with wave.open(str(path)) as w:
        raw=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").astype("f4")/32768
        raw=raw.reshape(-1,w.getnchannels()).mean(axis=1)
        rate=w.getframerate()
    return resample_poly(raw,SR,rate).astype("f4")

def mag_body(x:np.ndarray,t:float,asset=False):
    # Ignore the first ~15 ms attack: tom shell/head resonance is much more
    # pitch-informative than the broadband stick transient.
    base=0 if asset else int(round(t*SR))
    start=base+int(round(.015*SR))
    offsets=(0,int(.018*SR),int(.036*SR),int(.054*SR))
    win=np.hanning(FFT).astype("f4")
    mags=[]
    for off in offsets:
        a=start+off
        frame=np.zeros(FFT,dtype="f4")
        lo=max(0,a); hi=min(len(x),a+FFT)
        if hi>lo: frame[lo-a:hi-a]=x[lo:hi]
        mags.append(np.abs(np.fft.rfft(frame*win)))
    return np.mean(mags,axis=0)

FREQ=np.fft.rfftfreq(FFT,1/SR)
MASK=(FREQ>=55)&(FREQ<=650)
PEAK_MASK=(FREQ>=60)&(FREQ<=360)
CENT_MASK=(FREQ>=55)&(FREQ<=500)

def descriptor(x,t=0.0,asset=False):
    m=mag_body(x,t,asset=asset)
    sm=gaussian_filter1d(m.astype("f8"),1.2)
    # Normalize the profile after log compression; this is robust to velocity.
    profile=np.log1p(sm[MASK])
    profile=profile-profile.mean()
    profile=profile/(np.linalg.norm(profile)+1e-9)
    pm=sm[PEAK_MASK]
    pf=FREQ[PEAK_MASK]
    peak=float(pf[int(np.argmax(pm))]) if len(pm) else 0.0
    cm=sm[CENT_MASK]**2
    cf=FREQ[CENT_MASK]
    centroid=float(np.sum(cf*cm)/(np.sum(cm)+1e-12))
    # Four broad resonance bands add robustness when a single bin is masked.
    bands=[]
    for lo,hi in ((55,105),(105,155),(155,220),(220,360)):
        z=sm[(FREQ>=lo)&(FREQ<hi)]
        bands.append(float(np.log1p(np.sum(z))))
    bands=np.asarray(bands,dtype="f8")
    bands=(bands-bands.mean())/(np.linalg.norm(bands-bands.mean())+1e-9)
    return {"profile":profile,"peak":peak,"centroid":centroid,"bands":bands}

def cos(a,b):
    return float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-12))

def predict(desc,assets,mode):
    rows=[]
    for note,a in assets.items():
        dp=abs(math.log2(max(desc["peak"],1)/max(a["peak"],1)))
        dc=abs(math.log2(max(desc["centroid"],1)/max(a["centroid"],1)))
        prof=cos(desc["profile"],a["profile"])
        band=cos(desc["bands"],a["bands"])
        if mode=="peak":
            score=-dp
        elif mode=="profile":
            score=.82*prof+.18*band
        elif mode=="hybrid":
            score=.58*prof+.14*band+.20*math.exp(-dp/.22)+.08*math.exp(-dc/.28)
        else:
            raise ValueError(mode)
        rows.append((score,note,{"dp":dp,"dc":dc,"profile":prof,"band":band}))
    rows.sort(reverse=True)
    return rows[0][1],rows

def build_assets():
    out={}
    for note in TOM_NOTES:
        x=load_wav(ROOT/f"DruMaster/assets/drums/{note}.wav")
        out[note]=descriptor(x,0,asset=True)
    return out

def tier(note):
    # Practical 4-tom mapping used by the five-song gold set.
    if note in (41,43): return 41
    if note==45: return 45
    if note in (47,48): return 47
    return 50

def metrics(rows,key):
    total=len(rows); exact=sum(r[key]==r["truth"] for r in rows)
    t4=sum(tier(r[key])==tier(r["truth"]) for r in rows)
    conf=Counter((r["truth"],r[key]) for r in rows)
    by_song={}
    for song in sorted(set(r["song"] for r in rows)):
        xs=[r for r in rows if r["song"]==song]
        by_song[song]={
            "n":len(xs),
            "exact":sum(r[key]==r["truth"] for r in xs)/len(xs) if xs else None,
            "tier4":sum(tier(r[key])==tier(r["truth"]) for r in xs)/len(xs) if xs else None,
        }
    by_truth={}
    for n in TOM_NOTES:
        xs=[r for r in rows if r["truth"]==n]
        if xs:
            by_truth[str(n)]={"n":len(xs),"exact":sum(r[key]==n for r in xs)/len(xs)}
    return {
        "n":total,
        "exact_accuracy":exact/total if total else None,
        "tier4_accuracy":t4/total if total else None,
        "by_song":by_song,
        "by_truth":by_truth,
        "confusion":{f"{a}->{b}":v for (a,b),v in sorted(conf.items())},
    }


def optimal1d(values,k):
    order=sorted(range(len(values)),key=lambda i:(values[i],i))
    x=[values[i] for i in order];n=len(x)
    p=[0.0]*(n+1);p2=[0.0]*(n+1)
    for i,v in enumerate(x):
        p[i+1]=p[i]+v;p2[i+1]=p2[i]+v*v
    dp=[[float("inf")]*(n+1) for _ in range(k+1)]
    prev=[[-1]*(n+1) for _ in range(k+1)]
    dp[0][0]=0.0
    def cost(i,j):
        nn=j-i;ss=p[j]-p[i];ss2=p2[j]-p2[i]
        return ss2-ss*ss/max(1,nn)
    for c in range(1,k+1):
        for j in range(c,n+1):
            for i in range(c-1,j):
                z=dp[c-1][i]+cost(i,j)
                if z<dp[c][j]:
                    dp[c][j]=z;prev[c][j]=i
    bounds=[];j=n
    for c in range(k,0,-1):
        i=prev[c][j];bounds.append((i,j));j=i
    bounds.reverse()
    labels=[0]*n;centers=[]
    for c,(a,b) in enumerate(bounds):
        centers.append(float(np.median(x[a:b])))
        for z in range(a,b): labels[z]=c
    orig=[0]*n
    for sorted_i,orig_i in enumerate(order): orig[orig_i]=labels[sorted_i]
    return orig,centers

def silhouette1d(values,labels,k):
    groups=[[i for i,l in enumerate(labels) if l==g] for g in range(k)]
    total=0.0
    for i,v in enumerate(values):
        own=groups[labels[i]]
        if len(own)<=1: continue
        a=sum(abs(v-values[j]) for j in own if j!=i)/(len(own)-1)
        bs=[]
        for g in range(k):
            if g==labels[i] or not groups[g]: continue
            bs.append(sum(abs(v-values[j]) for j in groups[g])/len(groups[g]))
        b=min(bs) if bs else 0.0
        total+=(b-a)/max(a,b,1e-9)
    return total/len(values) if values else 0.0

def current_cluster_predict(song_rows):
    hz=[max(40.0,float(r["peak_hz"])) for r in song_rows]
    loghz=[math.log(v) for v in hz]
    chosen=None
    if len(song_rows)>=4:
        distinct=len(set(round(v,6) for v in hz))
        for k in range(2,min(4,distinct,len(song_rows)-1)+1):
            labels,centers=optimal1d(loghz,k)
            sil=silhouette1d(loghz,labels,k)
            if chosen is None or sil>chosen["silhouette"]:
                chosen={"labels":labels,"centers":centers,"k":k,"silhouette":sil}
    if chosen is None or chosen["silhouette"]<.35:
        def fallback(v):
            return 41 if v<110 else 45 if v<145 else 47 if v<190 else 50
        return [fallback(v) for v in hz],{"method":"absolute","silhouette":chosen["silhouette"] if chosen else 0}
    targets={2:[41,45],3:[41,45,50],4:[41,45,47,50]}[chosen["k"]]
    order=sorted(range(chosen["k"]),key=lambda i:chosen["centers"][i])
    cmap={cluster:targets[rank] for rank,cluster in enumerate(order)}
    return [cmap[l] for l in chosen["labels"]],{"method":"cluster","silhouette":chosen["silhouette"],"k":chosen["k"]}

def main():
    assets=build_assets()
    rows=[]
    per_song_desc=defaultdict(list)
    for song in SONGS:
        folder=ROOT/"DruMaster/songs"/song
        meta=json.loads((folder/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        x=ev.audio(folder/"drums.mp3")
        truth=[e for e in ev.midi_events(folder/"chart.mid") if e[1]=="tom"]
        for t,_,note in truth:
            at=t+shift
            if at<0 or at>=len(x)/SR: continue
            d=descriptor(x,at)
            row={"song":song,"time":at,"truth":int(note),"peak_hz":d["peak"],"centroid_hz":d["centroid"]}
            for mode,key in (("peak","pred_peak"),("profile","pred_profile"),("hybrid","pred_hybrid")):
                p,_=predict(d,assets,mode);row[key]=int(p)
            row["_desc"]=d
            rows.append(row);per_song_desc[song].append(row)
    # Current production-style song-relative resonant-peak clustering, applied only
    # to reference tom onset times for isolated pitch-subdivision evaluation.
    current_cluster_info={}
    for song,xs in per_song_desc.items():
        preds,ci=current_cluster_predict(xs);current_cluster_info[song]=ci
        for r,p in zip(xs,preds):r["pred_current_cluster"]=int(p)

    # Research-only LOO real-hit nearest centroid. Never production.
    for song,xs in per_song_desc.items():
        train=[r for s,ys in per_song_desc.items() if s!=song for r in ys]
        prot={}
        for note in TOM_NOTES:
            ds=[r["_desc"] for r in train if r["truth"]==note]
            if not ds: continue
            v=np.mean([d["profile"] for d in ds],axis=0);v/=np.linalg.norm(v)+1e-9
            prot[note]=v
        for r in xs:
            if prot:
                r["pred_loo"]=int(max(prot,key=lambda n:cos(r["_desc"]["profile"],prot[n])))
            else:r["pred_loo"]=45
    clean=[]
    for r in rows:
        clean.append({k:v for k,v in r.items() if k!="_desc"})
    result={
        "schema":1,
        "purpose":"tom pitch subdivision; chart.mid is scoring-only",
        "asset_prototypes":{str(n):{"peak_hz":assets[n]["peak"],"centroid_hz":assets[n]["centroid"]} for n in TOM_NOTES},
        "reference_counts":dict(Counter(str(r["truth"]) for r in rows)),
        "current_cluster_info":current_cluster_info,
        "candidates":{
            "asset_peak":metrics(rows,"pred_peak"),
            "asset_profile":metrics(rows,"pred_profile"),
            "asset_hybrid":metrics(rows,"pred_hybrid"),
            "current_song_relative_cluster":metrics(rows,"pred_current_cluster"),
            "loo_real_profile_research_only":metrics(rows,"pred_loo"),
        },
        "events":clean,
    }
    out=ROOT/"drumscribe/experiments/results-tom-pitch-v69.json"
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="events"},ensure_ascii=False,indent=2))

if __name__=="__main__":main()

# trigger v69 evaluation workflow
