"""Cycles 178-180: ADTOF-onset-anchored MDX crash/ride classification.

Unlike the earlier separated-stem transcription experiment, source separation
does NOT generate note candidates directly. Candidate cymbal onsets come from
ADTOF and/or the current integrated MIDI. MDX 6-stem is used only to decide
crash vs ride and to validate supplemental ADTOF cymbal onsets.

This prevents separator leakage/sustain from creating repeated notes.
chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util, json, math, subprocess, tempfile
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from mdxnet_infer import separate as mdx_separate

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

repair=loadmod("repair",EXP/"iterative_search_overtrigger_repair.py")
ev=repair.ev;sel=repair.sel;detail=repair.detail;base=repair.base
SONGS=repair.SONGS;GROUPS=repair.GROUPS

BASE=EXP/"generated-search-song-adaptive-v2/cycle174/c174_recall90"
AD=EXP/"generated-search-adtof/cycle163/c163_precision"
SR=22050;NFFT=1024;HOP=220

def rows(path,song):return repair.rows(path,song)
def meta(song):return repair.meta(song)

def ffmpeg_mono(path):
    cmd=["ffmpeg","-v","error","-i",str(path),"-ac","1","-ar",str(SR),"-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

def onset_env(path):
    x=ffmpeg_mono(path)
    x=np.pad(x,(NFFT//2,NFFT//2))
    frames=np.lib.stride_tricks.sliding_window_view(x,NFFT)[::HOP]
    S=np.abs(np.fft.rfft(frames*np.hanning(NFFT),axis=1)).astype("f4")
    rise=np.maximum(S[1:]-S[:-1],0).sum(axis=1)
    floor=median_filter(rise,size=101)
    env=np.maximum(rise-.55*floor,0)
    scale=np.percentile(env,98)+1e-8
    return (env/scale).astype("f4")

def value(env,t,rad=.035):
    f=int(round(t*SR/HOP));r=max(1,int(rad*SR/HOP))
    lo=max(0,f-r);hi=min(len(env),f+r+1)
    return float(np.max(env[lo:hi])) if hi>lo else 0.0

def prepare(tmp):
    cache=tmp/"mdx-cache";cache.mkdir(parents=True,exist_ok=True)
    feats={}
    for song in SONGS:
        out=tmp/song;out.mkdir(parents=True,exist_ok=True)
        print("MDX",song,flush=True)
        mr=mdx_separate(str(ROOT/"DruMaster/songs"/song/"drums.mp3"),
                        output_dir=str(out),model_name="drumsep-6stem",
                        device="cpu",cache_dir=cache,progress=True)
        crash=Path(mr["crash"]);ride=Path(mr["ride"])
        feats[song]={"crash":onset_env(crash),"ride":onset_env(ride)}
    return feats

def cluster_candidates(song):
    cur=rows(BASE,song)
    ad=[t for t,g in rows(AD,song) if g=="crash"]
    raw=[]
    for t,g in cur:
        if g in ("crash","ride"):raw.append((t,g,False))
    for t in ad:raw.append((t,None,True))
    raw.sort()
    clusters=[];c=[]
    for x in raw:
        if not c or x[0]-c[-1][0]<=.060:c.append(x)
        else:clusters.append(c);c=[x]
    if c:clusters.append(c)
    out=[]
    for c in clusters:
        curr=[x for x in c if x[1] in ("crash","ride")]
        ads=[x for x in c if x[2]]
        if curr:
            rep=min(curr,key=lambda x:abs(x[0]-np.mean([y[0] for y in c])))[0]
            old=min(curr,key=lambda x:abs(x[0]-rep))[1]
        else:
            rep=np.median([x[0] for x in c]);old=None
        out.append({"t":float(rep),"old":old,"ad":bool(ads)})
    return out

def periodic(times,t,bpm):
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.065 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def classify(song,cands,envs,method,margin,strength):
    m=meta(song);bpm=float(m["bpm"])
    _,ph,beat,bar=repair.timing(song,rows(BASE,song))
    times=[c["t"] for c in cands]
    chosen=[]
    for c in cands:
        t=c["t"];cv=value(envs["crash"],t);rv=value(envs["ride"],t)
        mx=max(cv,rv);ratio=(cv+1e-4)/(rv+1e-4)
        down=repair.downbeat_strength(t,ph,beat,bar)
        rep=periodic(times,t,bpm)
        if method=="base":
            if c["old"]:chosen.append((t,c["old"]))
            continue
        # Strong stem ratio chooses class; context helps only in ambiguous band.
        if ratio>=margin:
            g="crash";conf=ratio/margin
        elif ratio<=1.0/margin:
            g="ride";conf=(1.0/ratio)/margin
        else:
            if method=="ratio":
                g=c["old"]
            else:
                cscore=cv+0.55*down
                rscore=rv+0.30*rep
                g="crash" if cscore>=rscore else "ride"
            conf=1.0
        if c["old"] is not None:
            # Reclass current events only when stem evidence is strong enough.
            if mx>=strength and g is not None:chosen.append((t,g))
            else:chosen.append((t,c["old"]))
        elif c["ad"]:
            # Supplemental ADTOF cymbal needs stronger stem support.
            add_thr=strength*(1.30 if method=="ratio" else 1.15)
            if mx>=add_thr and g is not None:
                chosen.append((t,g))
    return chosen

def build(song,feats,method,margin,strength):
    e=rows(BASE,song);c=cluster_candidates(song)
    metal=classify(song,c,feats[song],method,margin,strength)
    return repair.enforce([x for x in e if x[1] not in ("crash","ride")]+metal)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,feats,method,margin,strength,outdir):
    result={"method":method,"margin":margin,"strength":strength,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);events=build(song,feats,method,margin,strength)
        p=outdir/name/f"{song}.mid";write(p,events,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,ref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":ref,"precision":tp/n if n else 0,"recall":tp/ref if ref else 0,
       "f1":2*tp/(n+ref) if n+ref else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,"false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s);return result

def choose(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("crash","ride"),max_part_drop=.04,target_tolerance=.018)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-adtof-mdx-cymbal";report={"schema":1,"cycles":[]}
    with tempfile.TemporaryDirectory(prefix="adtof-mdx-") as td:
        feats=prepare(Path(td))
        baseline=evaluate("baseline",feats,"base",1.5,.30,root/"baseline")

        res={}
        for name,method in [("c178_base","base"),("c178_ratio","ratio"),("c178_context","context")]:
            res[name]=evaluate(name,feats,method,1.5,.30,root/"cycle178")
            print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"crash":res[name]["summary"]["by_group"]["crash"],
              "ride":res[name]["summary"]["by_group"]["ride"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
        d=choose(res,baseline);win=d["winner"] or "c178_base";best=res[win]
        report["cycles"].append({"cycle":178,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

        res={}
        for name,margin in [("c179_m120",1.20),("c179_m150",1.50),("c179_m180",1.80),("c179_m220",2.20)]:
            res[name]=evaluate(name,feats,best["method"],margin,best["strength"],root/"cycle179")
            print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"crash":res[name]["summary"]["by_group"]["crash"],
              "ride":res[name]["summary"]["by_group"]["ride"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
        d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
        report["cycles"].append({"cycle":179,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

        res={}
        for name,strength in [("c180_s15",.15),("c180_s25",.25),("c180_s35",.35),("c180_s50",.50)]:
            res[name]=evaluate(name,feats,best["method"],best["margin"],strength,root/"cycle180")
            print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"crash":res[name]["summary"]["by_group"]["crash"],
              "ride":res[name]["summary"]["by_group"]["ride"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
        d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
        report["cycles"].append({"cycle":180,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
        report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
          "method":best["method"],"margin":best["margin"],"strength":best["strength"],
          "detailed":detail.compare_dir(root/"cycle180"/win,win)["aggregate"]}
        (EXP/"results-iterative-adtof-mdx-cymbal.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
