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
        "candidates":{
            "asset_peak":metrics(rows,"pred_peak"),
            "asset_profile":metrics(rows,"pred_profile"),
            "asset_hybrid":metrics(rows,"pred_hybrid"),
            "loo_real_profile_research_only":metrics(rows,"pred_loo"),
        },
        "events":clean,
    }
    out=ROOT/"drumscribe/experiments/results-tom-pitch-v69.json"
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="events"},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
