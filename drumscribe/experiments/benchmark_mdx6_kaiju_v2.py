"""Corrected one-song DrumSep/MDX23C + ADTOF benchmark on kaiju.

Implements the Riley & Dixon method more faithfully:
1. Run ADTOF on the full drum mix to obtain onset locations.
2. Run DrumSep once to obtain hh/ride/crash stems.
3. At generic cymbal onsets, compare crash vs ride stem loudness.
4. Apply a crash-refractory rule based on significant crash-stem peaks.

Extension for this project's main error mode:
5. At current browser hand-hat onsets, evaluate ride-vs-hh stem dominance.
   Reclass only inside bars with sustained ride-stem support.

DruMaster chart.mid is scoring-only. Separation audio is temporary and never
committed. This is a diagnostic search on kaiju, not a generalization claim.
"""
from __future__ import annotations
import importlib.util,json,math,tempfile,time
from collections import Counter,defaultdict
from pathlib import Path

import librosa
import numpy as np
from scipy.signal import find_peaks
import pretty_midi

from mdxnet_infer import separate
from adtof_pytorch import transcribe_to_midi

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SONG="kaiju";BASE=EXP/"generated-v2-browser"

def load_ev():
    spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=load_ev()

def browser_rows():
    side=json.loads((BASE/f"{SONG}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{SONG}.mid")],side

def loudness(path):
    y,_=librosa.load(path,sr=44100,mono=True)
    rms=librosa.feature.rms(y=y,frame_length=1024,hop_length=441,center=True)[0]
    return 20*np.log10(np.maximum(rms,1e-7))

def at(curve,t,half=.025):
    fps=100;i=int(round(t*fps));w=max(1,int(round(half*fps)))
    a=max(0,i-w);b=min(len(curve),i+w+1)
    return float(np.max(curve[a:b])) if b>a else -140.

def significant_crash_peaks(curve,pct,prom):
    floor=float(np.percentile(curve,pct))
    pk,_=find_peaks(curve,distance=25,prominence=prom,height=floor)
    return np.asarray(pk,dtype=float)/100

def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)

def classify_cymbals(times,curves,peak_pct,prom,peak_window=.10):
    peaks=significant_crash_peaks(curves["crash"],peak_pct,prom)
    out=[];diag=Counter()
    for t in sorted(times):
        c=at(curves["crash"],t);r=at(curves["ride"],t)
        # Significant crash peak alignment gets first claim.
        if near(peaks,t,peak_window) and c>=r-1.5:
            out.append((t,"crash"));diag["peak_crash"]+=1;continue
        # Riley/Dixon refractory interpretation: after a crash peak, until
        # one second before the next significant peak, assign cymbal hits ride.
        prev=[p for p in peaks if p<t]
        nxt=[p for p in peaks if p>t]
        in_refr=False
        if prev:
            p=prev[-1];q=nxt[0] if nxt else float("inf")
            in_refr=(t>p+peak_window and t<q-1.0)
        if in_refr:
            out.append((t,"ride"));diag["refractory_ride"]+=1
        else:
            g="ride" if r>c else "crash"
            out.append((t,g));diag["max_"+g]+=1
    return out,dict(diag),peaks

def hat_to_ride(rows,side,curves,seed_margin,bar_frac,event_margin,min_hits=3):
    bpm=float(side["bpm"]);phase=float(side["barPhaseSec"]);bar=4*60/bpm
    hats=[t for t,g in rows if g=="hat"]
    bybar=defaultdict(list)
    score={}
    for t in hats:
        d=at(curves["ride"],t)-at(curves["hh"],t);score[t]=d
        b=int(math.floor((t-phase)/bar));bybar[b].append(t)
    ride_bars=set()
    for b,xs in bybar.items():
        if len(xs)<min_hits:continue
        frac=sum(score[t]>=seed_margin for t in xs)/len(xs)
        if frac>=bar_frac:ride_bars.add(b)
    out=[];n=0
    for t,g in rows:
        if g=="hat":
            b=int(math.floor((t-phase)/bar))
            if b in ride_bars and score[t]>=event_margin:
                out.append((t,"ride"));n+=1;continue
        out.append((t,g))
    return out,{"rideBars":len(ride_bars),"converted":n,
                "scoreQuantiles":[float(np.quantile(list(score.values()),q)) for q in (.1,.25,.5,.75,.9)] if score else []}

def score(pred):
    meta=json.loads((ROOT/"DruMaster/songs"/SONG/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth=ev.midi_events(ROOT/"DruMaster/songs"/SONG/"chart.mid")
    return ev.score([(t,g,0,0) for t,g in pred],truth,shift)

def run_adtof(src,tmp,scale):
    out=tmp/f"adtof-{scale:.2f}.mid"
    th=[.22*scale,.24*scale,.32*scale,.22*scale,.30*scale]
    transcribe_to_midi(src,out,thresholds=th,device="cpu")
    return [(t,g) for t,g,*_ in ev.midi_events(out)]

def replace_cymbal(base,cy,keep_current):
    fixed=[(t,g) for t,g in base if g not in ("crash","ride")]
    if keep_current:
        chosen=list(cy)
        for t,g in base:
            if g not in ("crash","ride"):continue
            if not any(abs(t-x)<=.06 for x,_ in chosen):chosen.append((t,g))
        cy=chosen
    return sorted(fixed+cy)

def main():
    src=ROOT/"DruMaster/songs"/SONG/"drums.mp3";base,side=browser_rows()
    baseline=score(base);t0=time.time()
    with tempfile.TemporaryDirectory() as td0:
        td=Path(td0)
        stems=separate(str(src),output_dir=str(td/"stems"),model_name="drumsep-6stem",device="cpu")
        sep_sec=time.time()-t0
        curves={g:loudness(Path(stems[g])) for g in ("hh","ride","crash")}
        # same global dB reference shift for all stems; comparisons unchanged
        global_peak=max(float(np.max(x)) for x in curves.values())
        curves={g:x-global_peak for g,x in curves.items()}

        adtof={}
        for scale in (.72,.85,1.00,1.15):
            a=time.time();adtof[scale]=run_adtof(src,td,scale)
            print("ADTOF",scale,time.time()-a,Counter(g for _,g in adtof[scale]),flush=True)

        results=[]
        for scale,arows in adtof.items():
            cy_times=sorted(t for t,g in arows if g=="crash")
            for pct in (70,80,88,93):
              for prom in (2.5,4.5,6.5):
                cy,cy_diag,peaks=classify_cymbals(cy_times,curves,pct,prom)
                for keep in (False,True):
                    merged=replace_cymbal(base,cy,keep)
                    # No hat->ride extension baseline for this separation config.
                    sc=score(merged)
                    results.append({"config":{"scale":scale,"peakPct":pct,"prom":prom,"keepCurrent":keep,
                                               "seedMargin":None,"barFrac":None,"eventMargin":None},
                                    "summary":sc,"cymbalDiag":cy_diag,"crashPeaks":len(peaks)})
                    # Extended state search.
                    for seed in (0,3,6,9):
                      for frac in (.25,.40,.55,.70):
                       for em in (-3,0,3,6):
                        hr,hdiag=hat_to_ride(merged,side,curves,seed,frac,em)
                        sc2=score(hr)
                        results.append({"config":{"scale":scale,"peakPct":pct,"prom":prom,"keepCurrent":keep,
                                                   "seedMargin":seed,"barFrac":frac,"eventMargin":em},
                                        "summary":sc2,"cymbalDiag":cy_diag,"hatRideDiag":hdiag,"crashPeaks":len(peaks)})
        def gf(x):
            return 2*x["tp"]/(x["predicted"]+x["reference"]) if x["predicted"]+x["reference"] else 0.
        def obj(z):
            s=z["summary"];r=s["by_group"]["ride"];cc=s["by_group"]["crash"];h=s["by_group"]["hat"]
            return s["f1"]+.09*gf(r)+.06*gf(cc)+.02*gf(h)
        for z in results:z["objective"]=obj(z)
        results.sort(key=lambda z:(z["objective"],z["summary"]["f1"]),reverse=True)

    report={"schema":2,"song":SONG,"method":"Riley-Dixon-style DrumSep loudness classification + hat-to-ride state extension",
            "separationSec":sep_sec,"elapsedSec":time.time()-t0,"baseline":baseline,"top":results[:80]}
    (EXP/"results-mdx6-kaiju-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps({"f1":baseline["f1"],"groups":baseline["by_group"]},ensure_ascii=False),flush=True)
    for z in report["top"][:12]:
        s=z["summary"]
        print("TOP",json.dumps({"cfg":z["config"],"f1":s["f1"],"ride":s["by_group"]["ride"],"crash":s["by_group"]["crash"],"hat":s["by_group"]["hat"],"hdiag":z.get("hatRideDiag")},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
