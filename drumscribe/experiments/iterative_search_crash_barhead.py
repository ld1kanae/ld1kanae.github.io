"""Cycles 145-147: raw-audio bar-head crash reconstruction.

Unlike previous crash searches that only filtered an existing crash pool, this
re-opens drums.mp3 at 44.1 kHz and explicitly searches around every inferred
measure head. At most one crash is emitted per bar.

Reference MIDI is used only after generated MIDI is written.

Cycle 145: high-frequency flux / cymbal-band ratio / hybrid score
Cycle 146: global score percentile 55 / 70 / 82
Cycle 147: measure-head search radius .10 / .18 / .28 beat
"""
from __future__ import annotations
import importlib.util,json,math,subprocess
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.ndimage import median_filter

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
BASE=EXP/"generated-search-fusion-v5/cycle129/c129_balanced"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def audio(song,sr=44100):
    p=ROOT/"DruMaster/songs"/song/"drums.mp3"
    cmd=["ffmpeg","-v","error","-i",str(p),"-ac","1","-ar",str(sr),"-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

def crash_features(song):
    sr=44100;nfft=2048;hop=220
    x=audio(song,sr);x=np.pad(x,(nfft//2,nfft//2))
    frames=np.lib.stride_tricks.sliding_window_view(x,nfft)[::hop]
    S=np.abs(np.fft.rfft(frames*np.hanning(nfft),axis=1)).astype("f4").T
    R=np.maximum(S-np.pad(S[:,:-1],((0,0),(1,0))),0)
    f=np.arange(S.shape[0])*sr/nfft
    def band(lo,hi):
        m=(f>=lo)&(f<hi)
        return R[m].sum(axis=0) if np.any(m) else np.zeros(S.shape[1])
    low=band(40,1000);mid=band(1000,4000);high=band(4000,16000);air=band(10000,21000)
    # remove slow floor then robust-normalize each descriptor
    def norm(v):
        v=np.maximum(v-.55*median_filter(v,size=201),0)
        q=np.percentile(v,98)+1e-8
        return np.clip(v/q,0,5)
    low,mid,high,air=map(norm,(low,mid,high,air))
    flux=high+.45*air
    ratio=(high+.35*air)/(mid+.35*low+.08)
    ratio=np.clip(ratio/np.percentile(ratio,95),0,5)
    hybrid=.58*flux+.42*ratio
    return {"flux":flux,"ratio":ratio,"hybrid":hybrid,"hop":hop,"sr":sr}

def phase(events,m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    den=int(ts.get("denominator",4));num=int(ts.get("numerator",4))
    beat=60/bpm*4/den;bar=beat*num
    best=(-1,0.)
    # Score phase with kick on beat 1/3 and snare on 2/4, with stronger bar-1 kick.
    for q in range(192):
        ph=bar*q/192;sc=0.
        for t,g in events:
            if g not in ("kick","snare"):continue
            pos=((t-ph)%bar)/beat
            targets=(0,2) if g=="kick" else (1,3)
            d=min(abs(pos-k) for k in targets)
            d=min(d,4-d)
            w=1.5 if g=="kick" else 1.0
            if g=="kick":
                head=min(pos,4-pos)
                sc+=.55*math.exp(-.5*(head/.12)**2)
            sc+=w*math.exp(-.5*(d/.12)**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def reconstruct(song,kind,percentile,radius):
    b=rows(BASE,song);m=meta(song);feat=crash_features(song);score=feat[kind]
    ph,beat,bar=phase(b,m)
    duration=float(m.get("duration") or (len(score)*feat["hop"]/feat["sr"]))
    starts=[]
    k=math.floor((0-ph)/bar)-1
    while ph+k*bar<duration+bar:
        t=ph+k*bar
        if 0<=t<=duration:starts.append(t)
        k+=1

    global_thr=float(np.percentile(score,percentile))
    chosen=[]
    for head in starts:
        lo=max(0,int((head-radius*beat)*feat["sr"]/feat["hop"]))
        hi=min(len(score),int((head+radius*beat)*feat["sr"]/feat["hop"])+1)
        if hi<=lo:continue
        local=score[lo:hi];j=int(np.argmax(local))+lo;v=float(score[j])
        # Relative/local gate suppresses quiet bars even when the global score
        # distribution is compressed.
        context_lo=max(0,j-int(2*beat*feat["sr"]/feat["hop"]))
        context_hi=min(len(score),j+int(2*beat*feat["sr"]/feat["hop"])+1)
        local_floor=float(np.median(score[context_lo:context_hi]))+.08
        if v>=global_thr and v>=1.35*local_floor:
            chosen.append(j*feat["hop"]/feat["sr"])
    # One per bar by construction.
    return chosen,{"phase":ph,"beat":beat,"bars":len(starts),"chosen":len(chosen),"threshold":global_thr}

def enforce(events):
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.050,"tom":.050,"crash":.090,"ride":.045,"other":.040}
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):ded.append((t,g));last=t
    ded.sort();out=[];i=0;pri={"snare":.93,"tom":.88,"crash":.86,"ride":.83,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def fuse(song,kind,percentile,radius):
    e=[x for x in rows(BASE,song) if x[1]!="crash"]
    crashes,diag=reconstruct(song,kind,percentile,radius)
    return enforce(e+[(t,"crash") for t in crashes]),diag

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,kind,percentile,radius,outdir):
    result={"kind":kind,"percentile":percentile,"radius":radius,"song_decisions":{},"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr,diag=fuse(song,kind,percentile,radius);result["song_decisions"][song]=diag
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
    d=sel.select(res,baseline["summary"],target_parts=("crash",),max_part_drop=.02,target_tolerance=.01)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-crash-barhead";report={"schema":1,"cycles":[]}
    # baseline reconstruction intentionally uses high percentile; actual
    # comparison guard is still all-part and target-part aware.
    baseline=evaluate("baseline","hybrid",99,.10,root/"baseline")

    res={}
    for name,k in [("c145_flux","flux"),("c145_ratio","ratio"),("c145_hybrid","hybrid")]:
        res[name]=evaluate(name,k,70,.18,root/"cycle145");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    # For first cycle select by canonical score without requiring improvement
    # over an artificially sparse baseline, then subsequent cycles use guards.
    ranking=sorted(res,key=lambda n:(res[n]["canonical_score"]["score"],res[n]["summary"]["by_group"]["crash"]["f1"]),reverse=True)
    win=ranking[0];best=res[win]
    report["cycles"].append({"cycle":145,"candidates":res,"ranking":ranking,"winner":win})

    res={}
    for name,p in [("c146_p55",55),("c146_p70",70),("c146_p82",82)]:
        res[name]=evaluate(name,best["kind"],p,best["radius"],root/"cycle146");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":146,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})

    res={}
    for name,r in [("c147_r10",.10),("c147_r18",.18),("c147_r28",.28)]:
        res[name]=evaluate(name,best["kind"],best["percentile"],r,root/"cycle147");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":147,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best.get("guard"),
      "kind":best["kind"],"percentile":best["percentile"],"radius":best["radius"],"song_decisions":best["song_decisions"],"detailed":best["detailed"]}
    (EXP/"results-iterative-crash-barhead.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
