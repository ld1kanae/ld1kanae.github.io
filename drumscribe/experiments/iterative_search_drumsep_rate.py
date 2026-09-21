"""Cycles 46-48: true drum separation + sample-rate search.

Separate isolated drums.mp3 into five real WAV stems, then compare 11.025,
22.05 and 44.1 kHz transcription front ends. This directly tests whether the
old 11.025 kHz front end is discarding critical hat/cymbal information.
"""
from __future__ import annotations
import json, math, subprocess, tempfile
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

def stem_path(result,key):
    aliases={"kick":["kick"],"snare":["snare"],"tom":["tom"],"hat":["hihat","hat"],"cymbal":["cymbal"]}[key]
    for k,v in (getattr(result,"stems",{}) or {}).items():
        if any(a in str(k).lower() for a in aliases):return Path(v)
    raise KeyError((key,getattr(result,"stems",{})))

def audio_at(path,sr):
    cmd=["ffmpeg","-v","error","-i",str(path),"-ac","1","-ar",str(sr),"-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

def spectrum_at(x,sr):
    # Keep ~46 ms FFT and ~10 ms hop at every sample rate.
    nfft=1024 if sr<=12000 else 2048 if sr<=24000 else 4096
    hop=max(1,round(sr*.010))
    x=np.pad(x,(nfft//2,nfft//2))
    frames=np.lib.stride_tricks.sliding_window_view(x,nfft)[::hop]
    S=np.abs(np.fft.rfft(frames*np.hanning(nfft),axis=1)).astype("f4").T
    return S,nfft,hop

def flux(path,sr,bands):
    x=audio_at(path,sr);S,nfft,hop=spectrum_at(x,sr)
    R=np.maximum(S-np.pad(S[:,:-2],((0,0),(2,0))),0)
    freqs=np.arange(S.shape[0])*sr/nfft
    parts=[]
    for lo,hi,w in bands:
        mask=(freqs>=lo)&(freqs<min(hi,sr/2))
        parts.append(w*R[mask].sum(axis=0) if np.any(mask) else np.zeros(S.shape[1]))
    y=np.sum(parts,axis=0)
    y=np.maximum(y-.55*median_filter(y,size=101),0)
    y/=np.percentile(y,98)+1e-7
    return y.astype("f4"),hop

def peaks(signal,thr,distance_s,sr,hop,prom=.05):
    floor=np.maximum(thr,median_filter(signal,size=201)*2.0)
    pp,_=find_peaks(signal,distance=max(1,int(distance_s*sr/hop)),prominence=prom)
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

def estimate_phase(events,bpm,num,den):
    beat=60/bpm*4/den;bar=beat*num;sigma=max(.035,beat*.11)
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;score=0.
        for e in events:
            if e["group"]=="kick":w=1.8
            elif e["group"]=="snare":w=.8
            else:continue
            x=(e["time"]-ph)%bar;d=min(x,bar-x)
            score+=w*e["confidence"]*math.exp(-.5*(d/sigma)**2)
        if score>best[0]:best=(score,ph)
    return best[1]

def head_dist(t,phase,bpm,num,den):
    beat=60/bpm*4/den;bar=beat*num;x=(t-phase)%bar
    return min(x,bar-x)/beat

def signals(stems,sr):
    ny=sr/2
    # Bands intentionally use information unavailable at 11.025 kHz.
    defs={
      "kick":[(20,180,1.0),(180,1200,.15)],
      "snare":[(120,450,.8),(1500,5000,1.0),(5000,9000,.25)],
      "tom":[(55,900,1.0),(900,2200,.20)],
      "hat":[(4000,12000,1.0),(2500,4000,.20)],
      "cymbal":[(2500,16000,1.0),(1000,2500,.20)],
    }
    out={};hops={}
    for k in defs:
        out[k],hops[k]=flux(stems[k],sr,defs[k])
    return out,hops

def params():
    return {"kick_thr":.34,"snare_thr":.30,"tom_thr":.30,"hat_thr":.25,"cym_thr":.30,
      "crash_head_beats":.15,"ride_mode":"off","ride_periodic":.85,"poly_window":.033,
      "hat_guard":1.0,"kick_guard":1.0}

def detect(stems,meta,p,sr):
    sig,hops=signals(stems,sr);events=[]
    dists={"kick":.060,"snare":.045,"tom":.065,"hat":.040}
    for g in ("kick","snare","tom","hat"):
        thr=p[g+"_thr"]*(p["kick_guard"] if g=="kick" else p["hat_guard"] if g=="hat" else 1)
        pp=peaks(sig[g],thr,dists[g],sr,hops[g])
        for fr in pp:
            sc=float(sig[g][fr])
            events.append({"time":fr*hops[g]/sr,"frame":fr,"group":g,"score":sc,"confidence":sc/max(thr,1e-6)})

    bpm=float(meta["bpm"]);ts=meta.get("timeSignature") or {"numerator":4,"denominator":4}
    num=int(ts.get("numerator",4));den=int(ts.get("denominator",4));phase=estimate_phase(events,bpm,num,den)
    cps=peaks(sig["cymbal"],p["cym_thr"],.075,sr,hops["cymbal"])
    times=[fr*hops["cymbal"]/sr for fr in cps]
    for i,fr in enumerate(cps):
        t=times[i];sc=float(sig["cymbal"][fr]);hd=head_dist(t,phase,bpm,num,den);per=periodic(times,i,bpm)
        if hd<=p["crash_head_beats"]:
            events.append({"time":t,"frame":fr,"group":"crash","score":sc,"confidence":sc/max(p["cym_thr"],1e-6)})
        elif p["ride_mode"]!="off" and per>=p["ride_periodic"]:
            events.append({"time":t,"frame":fr,"group":"ride","score":sc,"confidence":sc/max(p["cym_thr"],1e-6)+per})
    return base.enforce_two_limb(events,p)

def score_candidate(name,p,sr,allstems,outdir):
    result={"params":p,"sample_rate":sr,"songs":{}};tot=Counter()
    for song,stems in allstems.items():
        folder=ROOT/"DruMaster/songs"/song;meta=json.loads((folder/"song.json").read_text())
        pred=detect(stems,meta,p,sr)
        mid=outdir/name/f"{song}.mid";base.write_midi(mid,pred,float(meta["bpm"]))
        parsed=ev.midi_events(mid);truth=ev.midi_events(folder/"chart.mid")
        shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
        sc=ev.score(parsed,truth,shift);cf=ev.confusion(parsed,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);sc["two_limb_violations"]=ps.poly_violations(parsed,.033)
        result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],poly=sc["two_limb_violations"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,m=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4) if n else 0,"recall":round(tp/m,4) if m else 0,"f1":round(2*tp/(n+m),4) if n+m else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":tot["poly"],"by_group":{}}
    macro=[]
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0;macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/len(macro),4)
    kr=s["by_group"]["kick"]["count_ratio"] or 1;hr=s["by_group"]["hat"]["count_ratio"] or 1
    excess=max(0,kr-1.1)+max(0,hr-1.15);ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(s["f1"]+.14*s["macro_f1"]+.12*s["by_group"]["tom"]["f1"]+.10*s["by_group"]["crash"]["f1"]+.10*s["by_group"]["snare"]["recall"]-.30*ks-.08*excess,6)
    result["summary"]=s;return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    report={"schema":1,"method":"true five-WAV separation + sample-rate search","cycles":[]}
    root=ROOT/"drumscribe/experiments/generated-search-drumsep-rate"
    with tempfile.TemporaryDirectory(prefix="drumsep-") as td:
        td=Path(td);allstems={}
        for song in SONGS:
            folder=ROOT/"DruMaster/songs"/song;od=td/song;od.mkdir()
            print("SEPARATE",song,flush=True)
            result=separate(str(folder/"drums.mp3"),output_dir=str(od),enhanced=True)
            allstems[song]={k:stem_path(result,k) for k in ("kick","snare","tom","hat","cymbal")}

        # Cycle 46: sample rate.
        res={}
        for sr in (11025,22050,44100):
            name=f"c46_sr{sr}";p=params()
            res[name]=score_candidate(name,p,sr,allstems,root/"cycle46")
            print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
        rr=rank(res);winner=rr[0][0];best_sr=res[winner]["sample_rate"];best=dict(res[winner]["params"])
        report["cycles"].append({"cycle":46,"candidates":res,"ranking":[n for n,_ in rr],"winner":winner,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

        # Cycle 47: detector operating point at winning rate.
        res={}
        for name,scale in [("c47_precision",1.20),("c47_balanced",1.0),("c47_recall",.82)]:
            p=dict(best)
            for k in ("kick_thr","snare_thr","tom_thr","hat_thr","cym_thr"):p[k]*=scale
            res[name]=score_candidate(name,p,best_sr,allstems,root/"cycle47")
            print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
        rr=rank(res);winner=rr[0][0];best=dict(res[winner]["params"])
        report["cycles"].append({"cycle":47,"candidates":res,"ranking":[n for n,_ in rr],"winner":winner,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

        # Cycle 48: human-review anti-burst guards.
        res={}
        for name,kg,hg in [("c48_none",1.0,1.0),("c48_hat_guard",1.0,1.18),("c48_kick_hat_guard",1.12,1.18)]:
            p=dict(best);p["kick_guard"]=kg;p["hat_guard"]=hg
            res[name]=score_candidate(name,p,best_sr,allstems,root/"cycle48")
            print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
        rr=rank(res);winner=rr[0][0];best=dict(res[winner]["params"])
        report["cycles"].append({"cycle":48,"candidates":res,"ranking":[n for n,_ in rr],"winner":winner,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
        report["final"]={"winner":winner,"sample_rate":best_sr,"summary":res[winner]["summary"],"params":best}
        (ROOT/"drumscribe/experiments/results-iterative-drumsep-rate.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
