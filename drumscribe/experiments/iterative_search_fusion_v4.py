"""Cycles 121-123: fourth-generation all-part fusion.

Uses the latest validated component candidates. Prediction-time fusion only reads
MIDI previously generated from drums.mp3. chart.mid is evaluation-only after
each fused candidate MIDI has been written.

Cycle 121: ride = off / adaptive / zero-seed-fallback
Cycle 122: crash = balanced / zero-fallback / precision
Cycle 123: snare = balanced / safe / high-recall

Selection uses selection_policy.py hard non-regression guards plus the canonical
multi-part score. No part may silently collapse to improve overall F1.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")
sel=loadmod("sel",EXP/"selection_policy.py")

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

STABLE=EXP/"generated-search-tom-consensus/cycle105/c105_density7"
RIDE={
    "off":None,
    "adaptive":EXP/"generated-search-ride-adaptive/cycle117/c117_hat30",
    "fallback":EXP/"generated-search-ride-fallback/cycle120/c120_density7",
}
CRASH={
    "balanced":STABLE,
    "fallback":EXP/"generated-search-crash-fallback/cycle88/c88_zero_base",
    "precision":EXP/"generated-search-crash-fallback/cycle88/c88_precision",
}
SNARE={
    "balanced":STABLE,
    "safe":EXP/"generated-search-snare-safe-fusion/cycle113/c113_k65",
    "highrecall":EXP/"generated-search-best-fusion/cycle80/c80_snare_pattern",
}

def rows(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]

def meta(song):
    return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def replace_group(events,group,path,song):
    return [e for e in events if e[1]!=group]+[e for e in rows(path,song) if e[1]==group]

def enforce(events):
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.050,"tom":.050,"crash":.090,"ride":.045,"other":.040}
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):
                ded.append((t,g));last=t
    ded.sort()
    out=[];i=0
    pri={"snare":.93,"tom":.88,"crash":.85,"ride":.83,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j]
        exempt=[e for e in c if e[1] not in HANDS]
        hand=[e for e in c if e[1] in HANDS]
        hand=sorted(hand,key=lambda e:pri.get(e[1],.5),reverse=True)[:2]
        out.extend(exempt+hand);i=j
    return sorted(out)

def fuse(song,ride_src,crash_src,snare_src):
    e=rows(STABLE,song)

    # Snare and crash are full component replacement.
    e=replace_group(e,"snare",SNARE[snare_src],song)
    e=replace_group(e,"crash",CRASH[crash_src],song)

    # Ride is optional. The adaptive/fallback streams were already generated
    # with song-level audio-derived gating. Only near-synchronous hat is removed.
    e=[x for x in e if x[1]!="ride"]
    if RIDE[ride_src] is not None:
        rides=[x for x in rows(RIDE[ride_src],song) if x[1]=="ride"]
        rt=[t for t,_ in rides]
        e=[x for x in e if not(x[1]=="hat" and any(abs(x[0]-t)<=.030 for t in rt))]
        e+=rides

    return enforce(e)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,ride_src,crash_src,snare_src,outdir):
    result={"ride_src":ride_src,"crash_src":crash_src,"snare_src":snare_src,"songs":{}}
    tot=Counter()
    for song in SONGS:
        m=meta(song);pred_rows=fuse(song,ride_src,crash_src,snare_src)
        path=outdir/name/f"{song}.mid";write(path,pred_rows,float(m["bpm"]))
        pred=ev.midi_events(path);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]

    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,
       "precision":tp/n if n else 0,"recall":tp/mr if mr else 0,
       "f1":2*tp/(n+mr) if n+mr else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        gf=2*a/(b+c) if b+c else 0
        songf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{})
            ref=x.get("reference",0)
            if ref:
                songf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={
          "tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,"f1":gf,
          "false_discovery_rate":(b-a)/b if b else 0,
          "miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,
          "mean_song_f1":sum(songf)/len(songf) if songf else None,
          "worst_song_f1":min(songf) if songf else None,
        }
    result["summary"]=s
    result["canonical_score"]=sel.score(s)
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"]
    return result

def select_cycle(res,baseline,target_parts,max_drop=.05):
    d=sel.select(res,baseline["summary"],target_parts=target_parts,max_part_drop=max_drop)
    for n in res:
        res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-fusion-v4"
    report={"schema":1,"selection_policy":"hard non-regression + canonical multi-part score","cycles":[]}

    baseline=evaluate("baseline","off","balanced","balanced",root/"baseline")

    # 121 — ride
    res={}
    for name,ride in [("c121_off","off"),("c121_adaptive","adaptive"),("c121_fallback","fallback")]:
        res[name]=evaluate(name,ride,"balanced","balanced",root/"cycle121")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=select_cycle(res,baseline,("ride",),max_drop=.035)
    win=d["winner"] or "c121_off";best=res[win]
    report["cycles"].append({"cycle":121,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    print("DECISION121",json.dumps(d,ensure_ascii=False),flush=True)

    # 122 — crash
    res={}
    for name,crash in [("c122_balanced","balanced"),("c122_fallback","fallback"),("c122_precision","precision")]:
        res[name]=evaluate(name,best["ride_src"],crash,best["snare_src"],root/"cycle122")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=select_cycle(res,best,("crash",),max_drop=.035)
    win=d["winner"] or "c122_balanced";best=res[win]
    report["cycles"].append({"cycle":122,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    print("DECISION122",json.dumps(d,ensure_ascii=False),flush=True)

    # 123 — snare
    res={}
    for name,sn in [("c123_balanced","balanced"),("c123_safe","safe"),("c123_highrecall","highrecall")]:
        res[name]=evaluate(name,best["ride_src"],best["crash_src"],sn,root/"cycle123")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=select_cycle(res,best,("snare",),max_drop=.035)
    win=d["winner"] or "c123_balanced";best=res[win]
    report["cycles"].append({"cycle":123,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    print("DECISION123",json.dumps(d,ensure_ascii=False),flush=True)

    report["final"]={
      "winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],
      "guard":best["guard"],"ride_src":best["ride_src"],"crash_src":best["crash_src"],
      "snare_src":best["snare_src"],"detailed":best["detailed"]
    }
    (EXP/"results-iterative-fusion-v4.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
