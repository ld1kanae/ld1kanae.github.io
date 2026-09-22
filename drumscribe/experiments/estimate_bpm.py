"""Audio-only BPM estimation benchmark for DrumScribe.

The estimator never reads song.json until after it has produced a BPM.
song.json is used only to score the estimate.

Three independent candidates:
A) global onset-envelope autocorrelation
B) inter-onset interval histogram
C) segment-wise autocorrelation consensus

All candidates are octave-resolved by an audio-only beat-grid consistency score.
"""
from __future__ import annotations

import json, math, subprocess
from pathlib import Path
from collections import Counter
import importlib.util
import numpy as np
from scipy.signal import find_peaks

ROOT = Path(".")
EXP = ROOT / "drumscribe/experiments"
SONGS = ["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec = importlib.util.spec_from_file_location("ev", EXP / "evaluate_v2.py")
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)
FPS = ev.SR / ev.HOP


def onset_envelope(path: Path):
    x = ev.audio(path)
    s = ev.spectrum(x)
    # No templates / chart / metadata: purely spectral positive flux.
    rise = np.maximum(s - np.pad(s[:, :-2], ((0,0),(2,0))), 0)
    freqs = np.arange(s.shape[0]) * ev.SR / ev.FFT
    ranges = [(35,140),(140,900),(900,3000),(3000,5500),(5500,9000)]
    flux=[]
    for lo,hi in ranges:
        y=rise[(freqs>=lo)&(freqs<hi)].sum(axis=0)
        # robust local baseline via evaluate_v2's median filter utility
        from scipy.ndimage import median_filter
        y=np.maximum(y-.55*median_filter(y,size=101),0)
        scale=np.percentile(y,98)+1e-9
        flux.append(np.minimum(y/scale,5.0))
    b=np.stack(flux)
    # Body bands dominate pulse; highs still contribute cymbal/hat timing.
    env=1.55*b[0]+1.25*b[1]+.55*b[2]+.45*b[3]+.20*b[4]
    env=np.maximum(env-np.percentile(env,35),0)
    env=np.convolve(env,np.array([.15,.35,.35,.15]),mode="same")
    env/=np.percentile(env,99)+1e-9
    env=np.minimum(env,4.0)
    return env.astype(np.float64), b


def autocorr_fft(x):
    x=np.asarray(x,float)
    x=x-np.mean(x)
    n=1
    while n<2*len(x): n*=2
    z=np.fft.rfft(x,n)
    ac=np.fft.irfft(z*np.conj(z),n)[:len(x)]
    denom=np.arange(len(x),0,-1)
    return ac/np.maximum(1,denom)


def candidate_periods_from_ac(env, lo=55, hi=220, top=10):
    ac=autocorr_fft(env)
    minlag=max(2,int(FPS*60/hi))
    maxlag=min(len(ac)-2,int(FPS*60/lo))
    seg=ac[minlag:maxlag+1].copy()
    # Normalize local scale and mildly prefer central practical tempi without
    # forcing 120 BPM. This only stabilizes weak/noisy envelopes.
    lags=np.arange(minlag,maxlag+1)
    bpms=60*FPS/lags
    prior=np.exp(-0.5*(np.log2(bpms/120)/1.35)**2)
    score=seg*prior
    pk,_=find_peaks(score,distance=max(1,int(FPS*60/hi*.35)))
    if not len(pk): pk=np.arange(len(score))
    order=pk[np.argsort(score[pk])[::-1][:top]]
    return [(float(bpms[i]),float(score[i]),int(lags[i])) for i in order], ac


def peak_times(env):
    floor=np.percentile(env,72)
    p,_=find_peaks(env,height=floor,distance=max(1,int(.055*FPS)),prominence=.06)
    # Keep enough onsets for rhythmic evidence, but trim weakest tail.
    if len(p)>2500:
        idx=np.argsort(env[p])[-2500:]
        p=np.sort(p[idx])
    return p/FPS, env[p]


def interval_candidates(env, lo=55, hi=220, top=10):
    times,strength=peak_times(env)
    bins=np.linspace(lo,hi,661)
    hist=np.zeros(len(bins)-1)
    for i,t in enumerate(times):
        # Intervals up to about 2 seconds; use several multiples so sparse
        # kick/snare patterns can still imply the quarter-note tempo.
        for j in range(i+1,min(len(times),i+18)):
            dt=times[j]-t
            if dt>2.2: break
            if dt<.15: continue
            w=math.sqrt(max(1e-6,strength[i]*strength[j]))/(j-i)**.45
            raw=60/dt
            for mult in (1,2,3,4):
                bpm=raw*mult
                if lo<=bpm<=hi:
                    k=np.searchsorted(bins,bpm)-1
                    if 0<=k<len(hist): hist[k]+=w/(mult**.35)
    pk,_=find_peaks(hist,distance=8)
    if not len(pk):pk=np.arange(len(hist))
    centers=(bins[:-1]+bins[1:])/2
    order=pk[np.argsort(hist[pk])[::-1][:top]]
    return [(float(centers[i]),float(hist[i])) for i in order]


def segment_candidates(env, lo=55, hi=220):
    win=max(1,int(10*FPS)); hop=max(1,int(5*FPS))
    votes=[]
    for a in range(0,max(1,len(env)-win+1),hop):
        y=env[a:a+win]
        if len(y)<win*.6 or np.max(y)<.12: continue
        c,_=candidate_periods_from_ac(y,lo,hi,top=3)
        if c: votes.append(c[0][:2])
    if not votes:
        return []
    grid=np.arange(lo,hi+.25,.25)
    score=np.zeros_like(grid,dtype=float)
    for bpm,w in votes:
        # vote also allows small local tempo jitter
        score += max(0,w)*np.exp(-.5*((grid-bpm)/1.2)**2)
    pk,_=find_peaks(score,distance=8)
    if not len(pk):pk=np.arange(len(score))
    order=pk[np.argsort(score[pk])[::-1][:10]]
    return [(float(grid[i]),float(score[i])) for i in order]


def pulse_score(env, bands, bpm):
    if not (45<=bpm<=260): return -1e9,0.0
    period=FPS*60/bpm
    nphase=max(16,min(160,int(round(period))))
    # Search phase at sub-frame resolution through phase bins.
    best=(-1e18,0.0)
    for q in range(nphase):
        phase=period*q/nphase
        # soft comb around beat locations; score body and full onset envelope
        idx=np.arange(phase,len(env),period)
        if len(idx)<4:continue
        ids=np.clip(np.rint(idx).astype(int),0,len(env)-1)
        body=1.6*bands[0,ids]+1.15*bands[1,ids]
        full=env[ids]
        vals=.62*full+.38*body
        # Reward sustained beat support, not a few giant transients.
        med=float(np.median(vals)); mean=float(np.mean(np.minimum(vals,2.5)))
        hit=float(np.mean(vals>np.percentile(env,70)))
        score=mean+.28*med+.18*hit
        if score>best[0]:best=(score,phase/FPS)
    return best


def octave_family(bpm):
    out=[]
    for x in (bpm/2,bpm,bpm*2):
        if 55<=x<=220: out.append(x)
    return out


def resolve(candidates, env, bands):
    pool=[]
    for item in candidates:
        bpm=float(item[0]); raw=float(item[1])
        for b in octave_family(bpm):
            p,ph=pulse_score(env,bands,b)
            # normalize external candidate confidence only lightly; pulse
            # consistency is the principal octave resolver.
            pool.append((p,b,ph,raw))
    if not pool:return {"bpm":0.0,"phase":0.0,"pulse_score":0.0}
    # De-duplicate near-equal candidates.
    pool.sort(reverse=True)
    kept=[]
    for row in pool:
        if any(abs(row[1]-x[1])<.7 for x in kept): continue
        kept.append(row)
    p,b,ph,raw=max(kept,key=lambda z:z[0])
    return {"bpm":b,"phase":ph,"pulse_score":p,"raw_score":raw,
            "alternatives":[{"bpm":x[1],"pulse_score":x[0],"phase":x[2]} for x in kept[:8]]}


def ensemble(a,b,c,env,bands):
    seeds=[a["bpm"],b["bpm"],c["bpm"]]
    pool=[]
    for seed in seeds:
        for x in octave_family(seed):
            # consensus in log2-tempo space, allowing tiny tolerance
            agree=sum(math.exp(-.5*(math.log2(max(x,1e-6)/max(s,1e-6))/.035)**2) for s in seeds if s>0)
            ps,ph=pulse_score(env,bands,x)
            pool.append((ps+.18*agree,x,ph,ps,agree))
    score,bpm,ph,ps,agree=max(pool)
    return {"bpm":bpm,"phase":ph,"score":score,"pulse_score":ps,"agreement":agree}


def relative_tempo_error(est,truth):
    # exact BPM error plus octave-equivalence diagnostic
    abs_pct=abs(est-truth)/truth*100
    octave=min(abs(est-truth),abs(est*2-truth),abs(est/2-truth))/truth*100
    ratio=est/truth if truth else None
    return abs_pct,octave,ratio


def main():
    report={"schema":1,"description":"Audio-only BPM estimation benchmark; song.json used for scoring only.","songs":{}}
    methods={"A":[],"B":[],"C":[],"ensemble":[]}
    for song in SONGS:
        env,bands=onset_envelope(ROOT/"DruMaster/songs"/song/"drums.mp3")
        ca,_=candidate_periods_from_ac(env)
        cb=interval_candidates(env)
        cc=segment_candidates(env)
        A=resolve(ca,env,bands)
        B=resolve(cb,env,bands)
        C=resolve(cc,env,bands)
        E=ensemble(A,B,C,env,bands)
        # Truth loaded only after estimates are finished.
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        truth=float(meta["bpm"])
        row={"truth_bpm":truth,"A_global_ac":A,"B_interval":B,"C_segment_ac":C,"ensemble":E}
        for label,obj in [("A",A),("B",B),("C",C),("ensemble",E)]:
            ae,oe,ratio=relative_tempo_error(obj["bpm"],truth)
            row[label+"_error"]={"absolute_percent":ae,"octave_equiv_percent":oe,"ratio":ratio}
            methods[label].append((ae,oe))
        report["songs"][song]=row
        print("BPM",song,json.dumps(row,ensure_ascii=False),flush=True)
    report["summary"]={}
    for k,vals in methods.items():
        report["summary"][k]={
            "mean_abs_percent":float(np.mean([x[0] for x in vals])),
            "max_abs_percent":float(np.max([x[0] for x in vals])),
            "mean_octave_equiv_percent":float(np.mean([x[1] for x in vals])),
            "max_octave_equiv_percent":float(np.max([x[1] for x in vals])),
        }
    (EXP/"results-bpm-estimation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("SUMMARY",json.dumps(report["summary"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    main()
