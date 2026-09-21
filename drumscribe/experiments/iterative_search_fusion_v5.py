"""Cycles 127-129: fifth-generation all-part fusion.

Base is the new adaptive-hi-hat candidate (c126_t20), which already contains
the current kick/snare/pedal/tom/crash parts. Every ride option is non-zero so
the all-part selection policy cannot win by omitting ride.

Cycle 127: ride = song-gate / adaptive / zero-seed-fallback
Cycle 128: crash = balanced / zero-fallback / precision
Cycle 129: snare = balanced / safe / high-recall

Prediction uses only previously generated audio-derived MIDI. chart.mid is used
only after each fused MIDI is written and re-read.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
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

BASE=EXP/"generated-search-hat-adaptive/cycle126/c126_t20"
RIDE={
 "tight":EXP/"generated-search-ride-song-gate/cycle108/c108_per50",
 "adaptive":EXP/"generated-search-ride-adaptive/cycle117/c117_hat30",
 "fallback":EXP/"generated-search-ride-fallback/cycle120/c120_density7",
}
CRASH={
 "balanced":BASE,
 "fallback":EXP/"generated-search-crash-fallback/cycle88/c88_zero_base",
 "precision":EXP/"generated-search-crash-fallback/cycle88/c88_precision",
}
SNARE={
 "balanced":BASE,
 "safe":EXP/"generated-search-snare-safe-fusion/cycle113/c113_k65",
 "highrecall":EXP/"generated-search-best-fusion/cycle80/c80_snare_pattern",
}

def rows(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]

def meta(song):
    return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def replace(events,g,path,song):
    return [e for e in events if e[1]!=g]+[e for e in rows(path,song) if e[1]==g]

def enforce(events):
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.050,"tom":.050,"crash":.090,"ride":.045,"other":.040}
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):ded.append((t,g));last=t
    ded.sort();out=[];i=0
    pri={"snare":.93,"tom":.88,"crash":.85,"ride":.83,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def fuse(song,ride_src,crash_src,snare_src):
    e=rows(BASE,song)
    e=replace(e,"crash",CRASH[crash_src],song)
    e=replace(e,"snare",SNARE[snare_src],song)
    e=[x for x in e if x[1]!="ride"]
    rides=[x for x in rows(RIDE[ride_src],song) if x[1]=="ride"]
    rt=[t for t,_ in rides]
    # ride replaces only a near-synchronous hand hi-hat, not surrounding hats.
    e=[x for x in e if not(x[1]=="hat" and any(abs(x[0]-t)<=.030 for t in rt))]
    e+=rides
    return enforce(e)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,ride_src,crash_src,snare_src,outdir):
    result={"ride_src":ride_src,"crash_src":crash_src,"snare_src":snare_src,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=fuse(song,ride_src,crash_src,snare_src)
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

def decide(res,baseline,target):
    d=sel.select(res,baseline["summary"],target_parts=(target,),max_part_drop=.035)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-fusion-v5";report={"schema":1,"selection_policy":"no missing parts + hard non-regression + canonical score","cycles":[]}
    # baseline is an all-part candidate using tight ride; no referenced part is absent.
    baseline=evaluate("baseline","tight","balanced","balanced",root/"baseline")

    res={}
    for name,r in [("c127_tight","tight"),("c127_adaptive","adaptive"),("c127_fallback","fallback")]:
        res[name]=evaluate(name,r,"balanced","balanced",root/"cycle127");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=decide(res,baseline,"ride");win=d["winner"] or "c127_tight";best=res[win]
    report["cycles"].append({"cycle":127,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]});print("DECISION127",json.dumps(d,ensure_ascii=False),flush=True)

    res={}
    for name,c in [("c128_balanced","balanced"),("c128_fallback","fallback"),("c128_precision","precision")]:
        res[name]=evaluate(name,best["ride_src"],c,best["snare_src"],root/"cycle128");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=decide(res,best,"crash");win=d["winner"] or "c128_balanced";best=res[win]
    report["cycles"].append({"cycle":128,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]});print("DECISION128",json.dumps(d,ensure_ascii=False),flush=True)

    res={}
    for name,sn in [("c129_balanced","balanced"),("c129_safe","safe"),("c129_highrecall","highrecall")]:
        res[name]=evaluate(name,best["ride_src"],best["crash_src"],sn,root/"cycle129");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=decide(res,best,"snare");win=d["winner"] or "c129_balanced";best=res[win]
    report["cycles"].append({"cycle":129,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]});print("DECISION129",json.dumps(d,ensure_ascii=False),flush=True)

    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "ride_src":best["ride_src"],"crash_src":best["crash_src"],"snare_src":best["snare_src"],"detailed":best["detailed"]}
    (EXP/"results-iterative-fusion-v5.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
