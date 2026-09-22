"""Cycles 151-153: raw-audio tom rescue inside fill contexts.

Base: fusion-v6 c144_adaptive.
Re-opens drums.mp3 at 44.1 kHz and searches low-mid transients only inside
musically plausible fill contexts. Current kick/snare hits veto nearby peaks.

Cycle 151: current-tom neighborhood / final beat of bar / union context
Cycle 152: score percentile 65 / 75 / 85
Cycle 153: minimum inter-tom distance 55 / 85 / 120 ms
"""
from __future__ import annotations
import importlib.util,json,math,subprocess
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")
sel=loadmod("sel",EXP/"selection_policy.py")
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}
BASE=EXP/"generated-search-fusion-v6/cycle144/c144_adaptive"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def audio_score(song):
    sr=44100;nfft=2048;hop=220
    p=ROOT/"DruMaster/songs"/song/"drums.mp3"
    cmd=["ffmpeg","-v","error","-i",str(p),"-ac","1","-ar",str(sr),"-f","f32le","-acodec","pcm_f32le","-"]
    x=np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()
    x=np.pad(x,(nfft//2,nfft//2))
    F=np.lib.stride_tricks.sliding_window_view(x,nfft)[::hop]
    S=np.abs(np.fft.rfft(F*np.hanning(nfft),axis=1)).astype("f4").T
    R=np.maximum(S-np.pad(S[:,:-1],((0,0),(1,0))),0)
    freq=np.arange(S.shape[0])*sr/nfft
    def band(lo,hi):
        m=(freq>=lo)&(freq<hi);return R[m].sum(axis=0)
    sub=band(35,120);body=band(120,900);attack=band(900,2200);snarehi=band(2200,9000)
    def norm(v):
        v=np.maximum(v-.55*median_filter(v,size=201),0);return v/(np.percentile(v,98)+1e-8)
    sub,body,attack,snarehi=map(norm,(sub,body,attack,snarehi))
    score=np.maximum(.95*body+.35*attack-.38*sub-.28*snarehi,0)
    return score,hop,sr

def phase(events,m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(128):
        ph=bar*q/128;sc=0.
        for t,g in events:
            if g not in ("kick","snare"):continue
            pos=((t-ph)%bar)/beat
            targets=(0,2) if g=="kick" else (1,3)
            d=min(abs(pos-k) for k in targets);d=min(d,4-d)
            sc+=(1.6 if g=="kick" else .9)*math.exp(-.5*(d/.12)**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def allowed(t,mode,current_toms,ph,beat,bar):
    seed=any(abs(t-x)<=1.0 for x in current_toms)
    pos=((t-ph)%bar)/beat
    # final beat plus the immediately preceding eighth-note is a common fill zone
    barend=pos>=2.45
    if mode=="seed":return seed
    if mode=="barend":return barend
    return seed or barend

def rescue(song,mode,percentile,min_dist):
    b=rows(BASE,song);m=meta(song);score,hop,sr=audio_score(song)
    kicks=[t for t,g in b if g=="kick"];snares=[t for t,g in b if g=="snare"];current=[t for t,g in b if g=="tom"]
    ph,beat,bar=phase(b,m)
    peaks,_=find_peaks(score,distance=max(1,int(min_dist*sr/hop)),prominence=.06)
    thr=float(np.percentile(score,percentile));add=[]
    for fr in peaks:
        v=float(score[fr])
        if v<thr:continue
        t=fr*hop/sr
        if not allowed(t,mode,current,ph,beat,bar):continue
        if near(current,t,.055) or near(kicks,t,.050) or near(snares,t,.045):continue
        # demand stronger evidence for bar-end-only candidates
        if not near(current,t,1.0) and v<1.15*thr:continue
        add.append(t)
    return add,{"current":len(current),"raw_peaks":len(peaks),"added":len(add),"threshold":thr,"phase":ph}

def enforce(events):
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.045,"tom":.050,"crash":.090,"ride":.045,"other":.040}
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):ded.append((t,g));last=t
    ded.sort();out=[];i=0;pri={"snare":.93,"tom":.89,"crash":.86,"ride":.84,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def fuse(song,mode,percentile,min_dist):
    b=rows(BASE,song);add,diag=rescue(song,mode,percentile,min_dist)
    return enforce(b+[(t,"tom") for t in add]),diag

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,percentile,min_dist,outdir):
    result={"mode":mode,"percentile":percentile,"min_dist":min_dist,"song_decisions":{},"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr,diag=fuse(song,mode,percentile,min_dist);result["song_decisions"][song]=diag
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,"precision":tp/n if n else 0,"recall":tp/mr if mr else 0,"f1":2*tp/(n+mr) if n+mr else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];gf=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":gf,
          "false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,"count_ratio":b/c if c else None,
          "mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s);result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def choose(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("tom",),max_part_drop=.02,target_tolerance=.006)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-tom-raw-fill";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","seed",99,.120,root/"baseline")

    res={}
    for name,mode in [("c151_seed","seed"),("c151_barend","barend"),("c151_union","union")]:
        res[name]=evaluate(name,mode,75,.085,root/"cycle151");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,baseline);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":151,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})

    res={}
    for name,p in [("c152_p65",65),("c152_p75",75),("c152_p85",85)]:
        res[name]=evaluate(name,best["mode"],p,best["min_dist"],root/"cycle152");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":152,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})

    res={}
    for name,dst in [("c153_d55",.055),("c153_d85",.085),("c153_d120",.120)]:
        res[name]=evaluate(name,best["mode"],best["percentile"],dst,root/"cycle153");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":153,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "mode":best["mode"],"percentile":best["percentile"],"min_dist":best["min_dist"],
      "song_decisions":best["song_decisions"],"detailed":best["detailed"]}
    (EXP/"results-iterative-tom-raw-fill.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
