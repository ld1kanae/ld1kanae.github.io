"""Cycles 133-135: adaptive pedal-hi-hat repair on fusion-v5.

Prediction-time inputs are only previously generated audio-derived MIDI:
- fusion-v5 current pedal/hat
- strict/balanced/recall pedal candidates
No chart.mid information is used until after each candidate MIDI is written.

Cycle 133: base / anti-hand-hat / multi-source consensus
Cycle 134: periodic support threshold 0.25 / 0.50 / 0.75
Cycle 135: sparse-song rescue threshold 0.015 / 0.03 / 0.06

The sparse-song rescue is designed for songs where the current pedal detector
nearly goes silent; it supplements only periodic, non-hand-hat recall events.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter
from pathlib import Path

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
STRICT=EXP/"generated-search-best-fusion/cycle81/c81_pedal_strict"
BAL=EXP/"generated-search-best-fusion/cycle81/c81_pedal_balanced"
RECALL=EXP/"generated-search-pedal-component/cycle64/c64_recall"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def periodic_support(times,t,bpm):
    if len(times)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.065 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def clusters(*sources,window=.035):
    pts=sorted(set(round(float(t),5) for src in sources for t in src))
    out=[]
    for t in pts:
        if out and t-out[-1][0]<=window:
            prev=out[-1]
            merged=(prev[0]+t)/2
            out[-1]=(merged,prev[1])
        else:out.append((t,1))
    return [x[0] for x in out]

def source_votes(t,sources,w=.035):
    return sum(1 for xs in sources if near(xs,t,w))

def make_pedals(song,mode,per_thr=.50,sparse_ratio=.03):
    b=rows(BASE,song)
    hats=[t for t,g in b if g=="hat"]
    cur=[t for t,g in b if g=="pedal_hat"]
    strict=[t for t,g in rows(STRICT,song) if g=="pedal_hat"]
    bal=[t for t,g in rows(BAL,song) if g=="pedal_hat"]
    rec=[t for t,g in rows(RECALL,song) if g=="pedal_hat"]
    m=meta(song);bpm=float(m["bpm"])
    union=clusters(cur,strict,bal,rec)
    sources=[cur,strict,bal,rec]

    if mode=="base":
        chosen=list(cur)
    elif mode=="anti_hat":
        chosen=[]
        for t in cur:
            votes=source_votes(t,sources)
            per=periodic_support(union,t,bpm)
            overlap=near(hats,t,.030)
            if (not overlap) or (votes>=2 and per>=per_thr):
                chosen.append(t)
    elif mode=="consensus":
        chosen=[]
        for t in union:
            votes=source_votes(t,sources)
            per=periodic_support(union,t,bpm)
            overlap=near(hats,t,.030)
            if votes>=2 and (not overlap or per>=per_thr):
                chosen.append(t)
    elif mode=="adaptive":
        # Start with the safer anti-hat current stream.
        chosen=[]
        for t in cur:
            votes=source_votes(t,sources);per=periodic_support(union,t,bpm)
            if (not near(hats,t,.030)) or (votes>=2 and per>=per_thr):
                chosen.append(t)

        ratio=len(cur)/max(1,len(hats))
        # Rescue only detector-sparse songs. Use the high-recall source, but
        # require periodicity and no hand-hat coincidence.
        if ratio < sparse_ratio:
            for t in rec:
                if near(chosen,t,.040):continue
                per=periodic_support(rec,t,bpm)
                votes=source_votes(t,[strict,bal,rec])
                if per>=per_thr and votes>=2 and not near(hats,t,.030):
                    chosen.append(t)
    else:raise ValueError(mode)

    # Dedupe pedal only. It remains exempt from the two-hand limit.
    out=[];last=-999.
    for t in sorted(chosen):
        if t-last>=.045:out.append(t);last=t
    return out,{
      "current":len(cur),"strict":len(strict),"balanced":len(bal),"recall":len(rec),
      "hat":len(hats),"current_hat_ratio":len(cur)/max(1,len(hats)),"chosen":len(out)
    }

def enforce(events):
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.045,"tom":.050,"crash":.090,"ride":.045,"other":.040}
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):ded.append((t,g));last=t
    ded.sort();out=[];i=0;pri={"snare":.93,"tom":.88,"crash":.85,"ride":.83,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def fuse(song,mode,per_thr,sparse_ratio):
    e=[x for x in rows(BASE,song) if x[1]!="pedal_hat"]
    ped,diag=make_pedals(song,mode,per_thr,sparse_ratio)
    return enforce(e+[(t,"pedal_hat") for t in ped]),diag

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,per_thr,sparse_ratio,outdir):
    result={"mode":mode,"periodic_threshold":per_thr,"sparse_ratio":sparse_ratio,"song_decisions":{},"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr,diag=fuse(song,mode,per_thr,sparse_ratio);result["song_decisions"][song]=diag
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,"precision":tp/n if n else 0,"recall":tp/mr if mr else 0,
       "f1":2*tp/(n+mr) if n+mr else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];gf=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":gf,
          "false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s);result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def choose(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("pedal_hat",),max_part_drop=.02,target_tolerance=.005)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-pedal-adaptive";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","base",.50,.03,root/"baseline")

    res={}
    for name,mode in [("c133_base","base"),("c133_anti_hat","anti_hat"),("c133_consensus","consensus")]:
        res[name]=evaluate(name,mode,.50,.03,root/"cycle133");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,baseline);win=d["winner"] or "c133_base";best=res[win]
    report["cycles"].append({"cycle":133,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})

    res={}
    mode=best["mode"] if best["mode"]!="base" else "anti_hat"
    for name,thr in [("c134_per25",.25),("c134_per50",.50),("c134_per75",.75)]:
        res[name]=evaluate(name,mode,thr,.03,root/"cycle134");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":134,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})

    res={}
    for name,ratio in [("c135_sparse015",.015),("c135_sparse030",.030),("c135_sparse060",.060)]:
        res[name]=evaluate(name,"adaptive",best["periodic_threshold"],ratio,root/"cycle135");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":135,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "mode":best["mode"],"periodic_threshold":best["periodic_threshold"],"sparse_ratio":best["sparse_ratio"],
      "song_decisions":best["song_decisions"],"detailed":best["detailed"]}
    (EXP/"results-iterative-pedal-adaptive.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
