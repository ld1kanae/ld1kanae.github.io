"""Cycles 43-45: true five-WAV drum sub-stem separation benchmark.

Uses the MIT-licensed 'drumsep' package to separate each isolated drums.mp3 into
kick/snare/toms/hihat/cymbals WAV stems before onset detection.

This is an offline benchmark to answer whether explicit source separation fixes
the reviewed failure modes. It is not shipped to the browser unchanged.
"""
from __future__ import annotations
import json, math, shutil, tempfile
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks

from drumsep import separate

import importlib.util
ROOT=Path(".")
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
ev=loadmod("ev","drumscribe/experiments/evaluate_v2.py")
base=loadmod("base","drumscribe/experiments/iterative_search.py")
ps=loadmod("ps","drumscribe/experiments/iterative_search_phase.py")
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

def stem_path(result, outdir, key):
    stems=getattr(result,"stems",{}) or {}
    for k,v in stems.items():
        if key in str(k).lower():
            return Path(v)
    aliases={
      "kick":["kick"],"snare":["snare"],"tom":["tom"],"hat":["hihat","hi_hat","hat"],"cymbal":["cymbal"]
    }[key]
    for p in Path(outdir).rglob("*"):
        if p.suffix.lower() not in (".wav",".flac",".mp3"):continue
        n=p.stem.lower()
        if any(a in n for a in aliases):return p
    raise FileNotFoundError((key,outdir,stems))

def flux(path,lo,hi):
    x=ev.audio(path);S=ev.spectrum(x)
    R=np.maximum(S-np.pad(S[:,:-2],((0,0),(2,0))),0)
    freqs=np.arange(S.shape[0])*ev.SR/ev.FFT
    y=R[(freqs>=lo)&(freqs<hi)].sum(axis=0)
    y=np.maximum(y-.55*median_filter(y,size=101),0)
    y/=np.percentile(y,98)+1e-7
    return y.astype("f4")

def peaks(signal,thr,distance,prom=.05):
    floor=np.maximum(thr,median_filter(signal,size=201)*2.0)
    pp,_=find_peaks(signal,distance=max(1,int(distance*ev.SR/ev.HOP)),prominence=prom)
    return [int(x) for x in pp if signal[x]>=floor[x]]

def periodic(times,i,bpm):
    if len(times)<3:return 0.
    t=times[i];best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=0
        for k in (-2,-1,1,2):
            if any(abs(x-(t+k*step))<=.07 for x in times):n+=1
        best=max(best,n/4)
    return best

def phase_from(events,bpm,num,den):
    tuples=[(e["time"],e["group"],e["confidence"]) for e in events if e["group"] in ("kick","snare")]
    return ev.estimate_downbeat_phase(tuples,bpm,num,den)

def head_dist(t,phase,bpm,num,den):
    beat=60/bpm*4/den;bar=beat*num
    x=(t-phase)%bar
    return min(x,bar-x)/beat

def detect(stems,meta,p):
    sig={
      "kick":flux(stems["kick"],25,700),
      "snare":flux(stems["snare"],80,5000),
      "tom":flux(stems["tom"],50,2200),
      "hat":flux(stems["hat"],1800,5500),
      "cymbal":flux(stems["cymbal"],900,5500),
    }
    evs=[]
    spec={
      "kick":(p["kick_thr"],.060),
      "snare":(p["snare_thr"],.050),
      "tom":(p["tom_thr"],.070),
      "hat":(p["hat_thr"],.040),
    }
    for g,(thr,dist) in spec.items():
        for fr in peaks(sig[g],thr,dist):
            score=float(sig[g][fr])
            evs.append({"time":fr*ev.HOP/ev.SR,"frame":fr,"group":g,"score":score,"confidence":score/max(thr,1e-5)})

    bpm=float(meta["bpm"]);ts=meta.get("timeSignature") or {"numerator":4,"denominator":4}
    num=int(ts.get("numerator",4));den=int(ts.get("denominator",4))
    phase=phase_from(evs,bpm,num,den)
    cps=peaks(sig["cymbal"],p["cym_thr"],.075)
    ctimes=[fr*ev.HOP/ev.SR for fr in cps]
    for i,fr in enumerate(cps):
        t=ctimes[i];s=float(sig["cymbal"][fr]);hd=head_dist(t,phase,bpm,num,den);per=periodic(ctimes,i,bpm)
        # User's hard rule: crash only at measure head.
        if hd<=p["crash_head_beats"]:
            evs.append({"time":t,"frame":fr,"group":"crash","score":s,"confidence":s/max(p["cym_thr"],1e-5)})
        elif p["ride_mode"]!="off" and per>=p["ride_periodic"]:
            evs.append({"time":t,"frame":fr,"group":"ride","score":s,"confidence":s/max(p["cym_thr"],1e-5)+per})

    return base.enforce_two_limb(evs,{"poly_window":.033})

def params():
    return {
      "kick_thr":.34,"snare_thr":.30,"tom_thr":.30,"hat_thr":.24,"cym_thr":.30,
      "crash_head_beats":.15,"ride_mode":"off","ride_periodic":.75,"poly_window":.033
    }

def prepare_stems():
    cache=ROOT/"drumscribe/experiments/drumsep-stems";cache.mkdir(parents=True,exist_ok=True)
    out={}
    for song in SONGS:
        folder=ROOT/"DruMaster/songs"/song;od=cache/song
        need=not od.exists() or not any(od.rglob("*.wav"))
        if need:
            if od.exists():shutil.rmtree(od)
            od.mkdir(parents=True)
            print("SEPARATE",song,flush=True)
            result=separate(str(folder/"drums.mp3"),output_dir=str(od),enhanced=True)
        else:
            result=type("R",(),{"stems":{}})()
        paths={k:stem_path(result,od,k) for k in ("kick","snare","tom","hat","cymbal")}
        out[song]=paths
        print("STEMS",song,{k:str(v) for k,v in paths.items()},flush=True)
    return out

def evaluate(name,p,stems,outdir):
    result={"params":p,"songs":{}};tot=Counter()
    for song in SONGS:
        folder=ROOT/"DruMaster/songs"/song;meta=json.loads((folder/"song.json").read_text())
        pred=detect(stems[song],meta,p)
        mid=outdir/name/f"{song}.mid";base.write_midi(mid,pred,float(meta["bpm"]))
        parsed=ev.midi_events(mid);truth=ev.midi_events(folder/"chart.mid")
        shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
        sc=ev.score(parsed,truth,shift);cf=ev.confusion(parsed,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);sc["two_limb_violations"]=ps.poly_violations(parsed,.033)
        result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],poly=sc["two_limb_violations"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,m=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":m,
       "precision":round(tp/n,4) if n else 0,"recall":round(tp/m,4) if m else 0,
       "f1":round(2*tp/(n+m),4) if n+m else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":tot["poly"],"by_group":{}}
    macro=[]
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,
          "f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/len(macro),4)
    kr=s["by_group"]["kick"]["count_ratio"] or 1;hr=s["by_group"]["hat"]["count_ratio"] or 1
    excess=max(0,kr-1.1)+max(0,hr-1.15)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(s["f1"]+.14*s["macro_f1"]+.12*s["by_group"]["tom"]["f1"]+.10*s["by_group"]["crash"]["f1"]+.10*s["by_group"]["snare"]["recall"]-.30*ks-.08*excess,6)
    result["summary"]=s;return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    stems=prepare_stems();root=ROOT/"drumscribe/experiments/generated-search-drumsep";report={"schema":1,"method":"true 5-WAV drumsep separation","cycles":[]}

    # Cycle 43: onset detector operating points.
    res={}
    for name,scale in [("c43_precision",1.20),("c43_balanced",1.0),("c43_recall",.82)]:
        p=params()
        for k in ("kick_thr","snare_thr","tom_thr","hat_thr","cym_thr"):p[k]*=scale
        res[name]=evaluate(name,p,stems,root/"cycle43")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);winner=rr[0][0];best=dict(res[winner]["params"])
    report["cycles"].append({"cycle":43,"candidates":res,"ranking":[n for n,_ in rr],"winner":winner,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    # Cycle 44: crash head width / optional conservative ride.
    res={}
    for name,w,ride,per in [
      ("c44_crash_tight",.08,"off",.8),
      ("c44_crash_balanced",.15,"off",.8),
      ("c44_ride_conservative",.12,"on",.90)
    ]:
        p=dict(best);p["crash_head_beats"]=w;p["ride_mode"]=ride;p["ride_periodic"]=per
        res[name]=evaluate(name,p,stems,root/"cycle44")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);winner=rr[0][0];best=dict(res[winner]["params"])
    report["cycles"].append({"cycle":44,"candidates":res,"ranking":[n for n,_ in rr],"winner":winner,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    # Cycle 45: review-targeted kick/hat conservatism.
    res={}
    for name,ks,hs in [("c45_base",1.,1.),("c45_hat_guard",1.,1.20),("c45_kick_hat_guard",1.15,1.20)]:
        p=dict(best);p["kick_thr"]*=ks;p["hat_thr"]*=hs
        res[name]=evaluate(name,p,stems,root/"cycle45")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);winner=rr[0][0];best=dict(res[winner]["params"])
    report["cycles"].append({"cycle":45,"candidates":res,"ranking":[n for n,_ in rr],"winner":winner,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    report["final"]={"winner":winner,"summary":res[winner]["summary"],"params":best}
    (ROOT/"drumscribe/experiments/results-iterative-drumsep.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
