"""BPM estimator v2: resolve half/double tempo with snare periodicity.

The first benchmark showed that global onset autocorrelation consistently found
an octave-equivalent tempo (mostly exactly half of the reference). This version
keeps that strong periodic estimate, then resolves the metrical level using
audio-only mid-band/snare recurrence and alternating-beat structure.

song.json is read only after prediction for scoring.
"""
from __future__ import annotations
import importlib.util,json,math
from pathlib import Path
import numpy as np
from scipy.signal import find_peaks

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
v1=loadmod("bpm1",EXP/"estimate_bpm.py")
FPS=v1.FPS

def smooth_peak(x,center,r=2):
    i=int(round(center))
    a=max(0,i-r);b=min(len(x),i+r+1)
    return float(np.max(x[a:b])) if b>a else 0.

def snare_peaks(band):
    s=np.asarray(band[1],float)
    floor=np.percentile(s,72)
    p,_=find_peaks(s,height=floor,distance=max(1,int(.11*FPS)),prominence=.06)
    if len(p)>1800:
        idx=np.argsort(s[p])[-1800:];p=np.sort(p[idx])
    return p/FPS,s[p]

def snare_interval_hist(band,lo=50,hi=220):
    times,strength=snare_peaks(band)
    grid=np.arange(lo,hi+.25,.25);hist=np.zeros(len(grid))
    for i,t in enumerate(times):
        for j in range(i+1,min(len(times),i+12)):
            dt=times[j]-t
            if dt>3.0:break
            if dt<.28:continue
            w=math.sqrt(max(1e-9,strength[i]*strength[j]))/(j-i)**.55
            # Backbeat recurrence is nominally 2 beats. Missing a backbeat
            # creates 4/6-beat gaps, hence integer multiples.
            for mult in (1,2,3):
                bpm=120*mult/dt
                if lo<=bpm<=hi:
                    k=int(round((bpm-lo)/.25))
                    if 0<=k<len(hist):hist[k]+=w/(mult**.45)
    if hist.max()>0:hist/=hist.max()
    pk,_=find_peaks(hist,distance=6)
    if not len(pk):pk=np.arange(len(hist))
    order=pk[np.argsort(hist[pk])[::-1][:12]]
    return [(float(grid[i]),float(hist[i])) for i in order],grid,hist

def interp_hist(grid,hist,bpm):
    if bpm<grid[0] or bpm>grid[-1]:return 0.
    return float(np.interp(bpm,grid,hist))

def grid_features(env,band,bpm):
    period=FPS*60/bpm
    if period<2:return {"score":-1e9}
    phases=np.linspace(0,period,72,endpoint=False)
    best=None
    body=1.45*band[0]+1.15*band[1]+.25*band[2]+.2*band[3]
    mid=band[1]
    strong_thr=np.percentile(env,72)
    for ph in phases:
        pos=np.arange(ph,len(env),period)
        if len(pos)<8:continue
        vals=np.array([smooth_peak(env,x,2) for x in pos])
        mvals=np.array([smooth_peak(mid,x,2) for x in pos])
        bvals=np.array([smooth_peak(body,x,2) for x in pos])
        even=mvals[0::2];odd=mvals[1::2]
        parity=abs(float(np.mean(even))-float(np.mean(odd)))/(float(np.mean(mvals))+.08)
        # Correct quarter-note level in rock/pop often exposes alternating
        # snare backbeats. At half-tempo all sampled beats tend to have similar
        # snare strength and parity falls.
        parity=min(parity,2.0)
        coverage=float(np.mean(vals>strong_thr))
        pulse=float(np.mean(np.minimum(vals,2.5)))
        bodymean=float(np.mean(np.minimum(bvals,2.5)))
        # Midpoint support is useful as positive evidence for doubling a
        # candidate, but is not by itself decisive because 8th-note hats can
        # also be strong in genuinely slow music.
        mids=pos[:-1]+period/2
        midpoint=float(np.mean([smooth_peak(env,x,2) for x in mids])) if len(mids) else 0.
        score=.48*pulse+.22*bodymean+.42*parity+.10*coverage
        row={"score":score,"phase_sec":ph/FPS,"pulse":pulse,"body":bodymean,
             "snare_parity":parity,"coverage":coverage,"midpoint":midpoint}
        if best is None or row["score"]>best["score"]:best=row
    return best or {"score":-1e9}

def octave_candidates(seed):
    vals=[]
    for mult in (.5,1,2,4):
        b=seed*mult
        if 50<=b<=220 and not any(abs(b-x)<.5 for x in vals):vals.append(b)
    return vals

def estimate(env,band):
    ac_candidates,ac=v1.candidate_periods_from_ac(env,50,220,top=12)
    seed=ac_candidates[0][0]
    sh,grid,hist=snare_interval_hist(band)
    rows=[]
    for bpm in octave_candidates(seed):
        gf=grid_features(env,band,bpm)
        se=interp_hist(grid,hist,bpm)
        # Autocorrelation support at the exact lag.
        lag=FPS*60/bpm
        i=int(round(lag))
        acv=float(ac[i]) if 0<=i<len(ac) else 0.
        # Normalize AC against nearby candidate-family values.
        rows.append({"bpm":bpm,"snare_evidence":se,"ac":acv,**gf})
    if rows:
        amin=min(r["ac"] for r in rows);amax=max(r["ac"] for r in rows)
        for r in rows:r["ac_norm"]=(r["ac"]-amin)/(amax-amin+1e-9)
        # Snare periodicity and alternating beat pattern deliberately carry
        # more weight than raw pulse salience to resolve the half-tempo bias.
        for r in rows:
            r["selection_score"]=(
                .34*r["ac_norm"]+
                .38*r["snare_evidence"]+
                .55*min(1.5,r["snare_parity"])/1.5+
                .18*r["coverage"]+
                .10*min(1.0,r["pulse"])
            )
        rows.sort(key=lambda r:r["selection_score"],reverse=True)
    return {"bpm":rows[0]["bpm"],"phase":rows[0]["phase_sec"],"seed":seed,
            "snare_candidates":sh,"candidates":rows}

def err(est,truth):
    return {"abs_percent":abs(est-truth)/truth*100,
            "octave_equiv_percent":min(abs(est-truth),abs(est*2-truth),abs(est/2-truth))/truth*100,
            "ratio":est/truth}

def main():
    report={"schema":2,"description":"Audio-only BPM v2 with snare-based metrical-level resolution.","songs":{}}
    errors=[]
    for song in SONGS:
        env,band=v1.onset_envelope(ROOT/"DruMaster/songs"/song/"drums.mp3")
        pred=estimate(env,band)
        # scoring only from this point onward
        truth=float(json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())["bpm"])
        e=err(pred["bpm"],truth);errors.append(e["abs_percent"])
        report["songs"][song]={"prediction":pred,"truth_bpm":truth,"error":e}
        print("BPM2",song,json.dumps(report["songs"][song],ensure_ascii=False),flush=True)
    report["summary"]={"mean_abs_percent":float(np.mean(errors)),"max_abs_percent":float(np.max(errors))}
    (EXP/"results-bpm-estimation-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("SUMMARY",json.dumps(report["summary"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
