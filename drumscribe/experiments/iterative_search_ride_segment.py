"""Cycles 136-138: seed-guided ride-segment expansion.

Base: fusion-v5 c129_balanced.
Seeds: adaptive ride c117_hat30.

Prediction uses only BPM + previously generated audio-derived MIDI. It detects
ride-active runs from high-confidence ride seeds and converts base hi-hat hits
onto a seed-anchored eighth-note grid inside those runs.

Cycle 136: segment extension 1 / 2 / 4 beats
Cycle 137: grid tolerance 0.10 / 0.18 / 0.26 of an eighth-note
Cycle 138: minimum seeds per run 2 / 3 / 4
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
SEED=EXP/"generated-search-ride-adaptive/cycle117/c117_hat30"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def grid_match(t,seeds,step,tol):
    if not seeds:return False
    lim=step*tol
    for s in seeds:
        d=t-s
        q=round(d/step)
        if abs(d-q*step)<=lim:return True
    return False

def seed_runs(seeds,beat,min_seeds,gap_beats=4):
    seeds=sorted(seeds)
    if not seeds:return []
    runs=[];cur=[seeds[0]]
    for t in seeds[1:]:
        if t-cur[-1] <= gap_beats*beat:cur.append(t)
        else:
            if len(cur)>=min_seeds:runs.append(cur)
            cur=[t]
    if len(cur)>=min_seeds:runs.append(cur)
    return runs

def enforce(events):
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.050,"tom":.050,"crash":.090,"ride":.045,"other":.040}
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):ded.append((t,g));last=t
    ded.sort();out=[];i=0;pri={"snare":.93,"tom":.88,"crash":.85,"ride":.84,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def fuse(song,extend_beats,grid_tol,min_seeds):
    b=rows(BASE,song);m=meta(song);bpm=float(m["bpm"])
    ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));step=beat/2
    seeds=[t for t,g in rows(SEED,song) if g=="ride"]
    runs=seed_runs(seeds,beat,min_seeds)
    hats=[t for t,g in b if g=="hat"]
    convert=set()
    diagnostics=[]
    for run in runs:
        lo=run[0]-extend_beats*beat;hi=run[-1]+extend_beats*beat
        local=[t for t in hats if lo<=t<=hi and grid_match(t,run,step,grid_tol)]
        convert.update(round(t,6) for t in local)
        diagnostics.append({"seed_count":len(run),"start":run[0],"end":run[-1],"converted":len(local)})
    e=[x for x in b if x[1] not in ("ride","hat")]
    e += [(t,"hat") for t in hats if round(t,6) not in convert]
    e += [(t,"ride") for t in sorted(set([round(x,6) for x in seeds])|convert)]
    return enforce(e),{"seed_count":len(seeds),"run_count":len(runs),"converted_hat":len(convert),"runs":diagnostics}

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,extend_beats,grid_tol,min_seeds,outdir):
    result={"extend_beats":extend_beats,"grid_tol":grid_tol,"min_seeds":min_seeds,"song_decisions":{},"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr,diag=fuse(song,extend_beats,grid_tol,min_seeds);result["song_decisions"][song]=diag
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
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
    d=sel.select(res,baseline["summary"],target_parts=("ride","hat"),max_part_drop=.03,target_tolerance=.01)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-ride-segment";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline",0,.10,99,root/"baseline")

    res={}
    for name,x in [("c136_extend1",1),("c136_extend2",2),("c136_extend4",4)]:
        res[name]=evaluate(name,x,.18,2,root/"cycle136");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,baseline);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":136,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})

    res={}
    for name,tol in [("c137_tol10",.10),("c137_tol18",.18),("c137_tol26",.26)]:
        res[name]=evaluate(name,best["extend_beats"],tol,best["min_seeds"],root/"cycle137");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":137,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})

    res={}
    for name,n in [("c138_seed2",2),("c138_seed3",3),("c138_seed4",4)]:
        res[name]=evaluate(name,best["extend_beats"],best["grid_tol"],n,root/"cycle138");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":138,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "extend_beats":best["extend_beats"],"grid_tol":best["grid_tol"],"min_seeds":best["min_seeds"],
      "song_decisions":best["song_decisions"],"detailed":best["detailed"]}
    (EXP/"results-iterative-ride-segment.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
