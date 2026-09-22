"""BPM estimator v3: snare recurrence + full-song phase refinement.

Coarse metrical tempo is taken from the strongest snare recurrence peak,
validated against the onset autocorrelation octave family. A fine BPM is then
estimated from phase coherence of strong low/mid drum onsets across the entire
song, followed by a robust grid regression. No song metadata is used before
prediction.
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
v2=loadmod("bpm2",EXP/"estimate_bpm_v2.py")
FPS=v1.FPS

def peak_set(signal,percentile=78,distance=.10,prom=.06,maxn=1400):
    x=np.asarray(signal,float)
    h=np.percentile(x,percentile)
    p,_=find_peaks(x,height=h,distance=max(1,int(distance*FPS)),prominence=prom)
    if len(p)>maxn:
        keep=np.argsort(x[p])[-maxn:];p=np.sort(p[keep])
    return p/FPS,x[p]

def ac_octave_support(env,bpm):
    cand,ac=v1.candidate_periods_from_ac(env,50,220,top=16)
    fam=[]
    for b,s,_ in cand:
        ratio=b/bpm
        octave_dist=min(abs(math.log2(max(1e-9,ratio)/k)) for k in (.5,1,2))
        fam.append((octave_dist,b,s))
    fam.sort()
    return fam[0] if fam else (99,0,0)

def select_coarse(env,band):
    sn,grid,hist=v2.snare_interval_hist(band,50,220)
    # Start from strong snare recurrence candidates. Require approximate
    # compatibility with an onset-autocorrelation tempo family.
    rows=[]
    for bpm,se in sn[:10]:
        od,ab,acs=ac_octave_support(env,bpm)
        compat=math.exp(-.5*(od/.035)**2)
        # Practical confidence is evidence-based, not a fixed high-tempo bias.
        score=.78*se+.22*compat
        rows.append({"bpm":bpm,"snare":se,"ac_match_bpm":ab,"ac_compat":compat,"score":score})
    rows.sort(key=lambda r:r["score"],reverse=True)
    return rows[0],rows

def phase_coherence(times,weights,bpms):
    if not len(times):
        return np.zeros(len(bpms))
    times=np.asarray(times,float);weights=np.asarray(weights,float)
    weights=np.maximum(weights,1e-9);weights=weights/weights.sum()
    out=np.empty(len(bpms),float)
    chunk=256
    for a in range(0,len(bpms),chunk):
        bs=np.asarray(bpms[a:a+chunk])
        ang=2j*np.pi*(bs[:,None]/60.0)*times[None,:]
        z=np.exp(ang)@weights
        out[a:a+chunk]=np.abs(z)
    return out

def fine_spectral(band,coarse):
    kt,kw=peak_set(band[0],75,.10,.05,1200)
    st,sw=peak_set(band[1],80,.12,.07,1200)
    span=max(1.2,coarse*.012)
    grid=np.linspace(coarse-span,coarse+span,3201)
    kc=phase_coherence(kt,kw,grid)
    sc=phase_coherence(st,sw,grid)
    # Snare recurrence is especially stable; kick gives independent support.
    score=.68*sc+.32*kc
    i=int(np.argmax(score))
    return float(grid[i]),{
      "grid_lo":float(grid[0]),"grid_hi":float(grid[-1]),
      "score":float(score[i]),"snare_coherence":float(sc[i]),"kick_coherence":float(kc[i]),
      "kick_peaks":len(kt),"snare_peaks":len(st)
    }

def circular_phase(times,weights,period):
    if not len(times):return 0.
    ang=2*np.pi*np.asarray(times)/period
    z=np.sum(np.asarray(weights)*np.exp(1j*ang))
    ph=(np.angle(z)%(2*np.pi))/(2*np.pi)*period
    return float(ph)

def robust_grid_fit(times,weights,bpm,iterations=4):
    times=np.asarray(times,float);weights=np.asarray(weights,float)
    if len(times)<8:return bpm,{"used":0}
    p=60/bpm
    ph=circular_phase(times,weights,p)
    used=np.ones(len(times),bool)
    for _ in range(iterations):
        n=np.rint((times-ph)/p)
        resid=times-(ph+n*p)
        limit=min(.095,.18*p)
        # Prefer the dominant grid-phase cluster.
        used=np.abs(resid)<=limit
        if used.sum()<8:break
        nn=n[used];tt=times[used];ww=np.maximum(weights[used],1e-6)
        # weighted least squares: t = intercept + n * period
        X=np.column_stack([np.ones(len(nn)),nn])
        WX=X*np.sqrt(ww)[:,None];Wy=tt*np.sqrt(ww)
        coef=np.linalg.lstsq(WX,Wy,rcond=None)[0]
        ph=float(coef[0]);p=float(coef[1])
        if p<=0:break
    fitted=60/p if p>0 else bpm
    residuals=times[used]-(ph+np.rint((times[used]-ph)/p)*p) if used.sum() else np.array([])
    return float(fitted),{
      "used":int(used.sum()),"total":len(times),"phase_sec":float(ph%p if p>0 else ph),
      "median_abs_residual_sec":float(np.median(np.abs(residuals))) if len(residuals) else None
    }

def estimate(env,band):
    coarse,coarse_rows=select_coarse(env,band)
    b1,sp=fine_spectral(band,coarse["bpm"])
    # Refine on strong snare peaks first; fit a beat-period grid even though
    # snare events can skip beats because integer grid indices may have gaps.
    st,sw=peak_set(band[1],82,.12,.08,1000)
    b2,fit=robust_grid_fit(st,sw,b1)
    # Reject a regression jump inconsistent with the spectral fine search.
    if abs(b2-b1)/b1>.004:
        final=b1;fit["rejected"]=True
    else:
        final=b2;fit["rejected"]=False
    return {"bpm":final,"coarse":coarse,"coarse_candidates":coarse_rows,
            "spectral_bpm":b1,"spectral":sp,"grid_fit_bpm":b2,"grid_fit":fit}

def main():
    report={"schema":3,"description":"Audio-only BPM v3: snare recurrence with full-song fine phase fit.","songs":{}}
    errs=[]
    for song in SONGS:
        env,band=v1.onset_envelope(ROOT/"DruMaster/songs"/song/"drums.mp3")
        pred=estimate(env,band)
        truth=float(json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())["bpm"])
        ep=abs(pred["bpm"]-truth)/truth*100;errs.append(ep)
        report["songs"][song]={"prediction":pred,"truth_bpm":truth,"abs_percent":ep,
            "drift_sec_per_3min":abs(180*(pred["bpm"]-truth)/truth)}
        print("BPM3",song,json.dumps(report["songs"][song],ensure_ascii=False),flush=True)
    report["summary"]={"mean_abs_percent":float(np.mean(errs)),"max_abs_percent":float(np.max(errs)),
                       "mean_drift_sec_per_3min":float(np.mean(errs))*1.8,
                       "max_drift_sec_per_3min":float(np.max(errs))*1.8}
    (EXP/"results-bpm-estimation-v3.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("SUMMARY",json.dumps(report["summary"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
