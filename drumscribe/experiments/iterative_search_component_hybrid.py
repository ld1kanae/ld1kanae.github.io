"""Cycles 52-54: component-bank hybrid search.

This combines only previously generated predictions that each originated from
drums.mp3; chart.mid is not consulted until after the new hybrid MIDI is
written. The goal is to preserve per-part standouts that lost on total F1.

Cycle 52: three cross-experiment part combinations.
Cycle 53: three conflict-resolution policies on the best combination.
Cycle 54: three cymbal policies on the best result.
"""
from __future__ import annotations
import importlib.util, json, math
from collections import Counter
from pathlib import Path

ROOT=Path(".")
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
ev=loadmod("ev","drumscribe/experiments/evaluate_v2.py")
detail=loadmod("detail","drumscribe/experiments/detailed_metrics.py")
base=loadmod("base","drumscribe/experiments/iterative_search.py")
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

SOURCES={
  # Stable / robust component sources with real generated MIDI directories.
  "kick_sharp": ROOT/"drumscribe/experiments/generated-search-separation/cycle40/c40_sharp",
  "kick_guard": ROOT/"drumscribe/experiments/generated-search-separation/cycle42/c42_snare_guard",
  "kick_soft": ROOT/"drumscribe/experiments/generated-search-separation/cycle40/c40_soft",

  "snare_anchor": ROOT/"drumscribe/experiments/generated-search-anchor/cycle7/c7_all",
  "snare_sep": ROOT/"drumscribe/experiments/generated-search-separation/cycle42/c42_snare_roll_recall",
  "snare_dsp": ROOT/"drumscribe/experiments/generated-search-drumsep-rate/cycle47/c47_precision",

  "hat_guard": ROOT/"drumscribe/experiments/generated-search-drumsep-rate/cycle48/c48_hat_guard",
  "hat_hi": ROOT/"drumscribe/experiments/generated-search-drumsep-rate/cycle46/c46_sr44100",
  "hat_sep": ROOT/"drumscribe/experiments/generated-search-separation/cycle42/c42_snare_roll_recall",

  "tom_best": ROOT/"drumscribe/experiments/generated-search-composite-v2/cycle38/c38_pedal_strict",
  "tom_sep": ROOT/"drumscribe/experiments/generated-search-separation/cycle42/c42_snare_roll_recall",

  "crash_soft": ROOT/"drumscribe/experiments/generated-search-separation/cycle40/c40_soft",
  "crash_strict": ROOT/"drumscribe/experiments/generated-search-composite-v2/cycle39/c39_crash_strict",
  "crash_bal": ROOT/"drumscribe/experiments/generated-search-composite-v2/cycle39/c39_crash_balanced",

  "ride_recall": ROOT/"drumscribe/experiments/generated-search-composite/cycle28/c28_ride_recall",
  "ride_off": None,

  "pedal_strict": ROOT/"drumscribe/experiments/generated-search-composite-v2/cycle38/c38_pedal_strict",
}

def load_group(src,song,group):
    if src is None:return []
    p=SOURCES[src]/f"{song}.mid"
    if not p.exists():raise FileNotFoundError(p)
    return [(t,g,v,n) for t,g,v,n in ev.midi_events(p) if g==group]

def write_events(path,events,bpm):
    # Reuse common MIDI writer via minimal event dicts.
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":conf} for t,g,conf in events],bpm)

def dedupe(events,mins):
    out=[]
    for g in GROUPS:
        arr=sorted([e for e in events if e[1]==g],key=lambda e:e[0]);last=-999.
        for e in arr:
            if e[0]-last<mins.get(g,.04):continue
            out.append(e);last=e[0]
    return sorted(out)

def enforce(events,policy):
    # Events are (time, group, confidence), source confidence is synthesized
    # from component ranking in the recipe.
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.05,"tom":.05,"crash":.10,"ride":.045}
    events=dedupe(events,mins)
    if policy=="none":return events
    out=[];i=0
    while i<len(events):
        t=events[i][0];j=i
        while j<len(events) and events[j][0]-t<=.033:j+=1
        cluster=events[i:j]
        exempt=[e for e in cluster if e[1] not in HANDS]
        hands=[e for e in cluster if e[1] in HANDS]
        if policy=="two_hands":
            hands=sorted(hands,key=lambda e:e[2],reverse=True)[:2]
        elif policy=="priority":
            pri={"snare":.25,"tom":.20,"crash":.18,"ride":.15,"hat":0}
            hands=sorted(hands,key=lambda e:e[2]+pri.get(e[1],0),reverse=True)[:2]
        out.extend(exempt+hands);i=j
    return sorted(out)

def measure_head_filter(events,meta,width):
    bpm=float(meta["bpm"]);ts=meta.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    # Estimate phase using strongest kick/snare regularity from already selected parts.
    ks=[e for e in events if e[1] in ("kick","snare")]
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;sc=0.
        for t,g,c in ks:
            x=(t-ph)%bar;d=min(x,bar-x);w=1.7 if g=="kick" else .8
            sc+=w*c*math.exp(-.5*(d/max(.03,.1*beat))**2)
        if sc>best[0]:best=(sc,ph)
    ph=best[1];out=[]
    for e in events:
        if e[1]!="crash":out.append(e);continue
        x=(e[0]-ph)%bar;d=min(x,bar-x)/beat
        if d<=width:out.append(e)
    return out

def recipe_events(song,recipe,policy="two_hands",crash_policy="source"):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    events=[]
    for g in GROUPS:
        src=recipe.get(g)
        if not src:continue
        rank_conf=float(recipe.get("_confidence",{}).get(g,1.0))
        for t,gg,v,n in load_group(src,song,g):
            events.append((t,gg,rank_conf))
    if crash_policy.startswith("head"):
        width=float(crash_policy.split(":")[1])
        events=measure_head_filter(events,meta,width)
    elif crash_policy=="off":
        events=[e for e in events if e[1]!="crash"]
    events=enforce(events,policy)
    return events,meta

def evaluate(name,recipe,policy,crash_policy,outdir):
    result={"recipe":recipe,"policy":policy,"crash_policy":crash_policy,"songs":{}};tot=Counter()
    for song in SONGS:
        events,meta=recipe_events(song,recipe,policy,crash_policy)
        path=outdir/name/f"{song}.mid";write_events(path,events,float(meta["bpm"]))
        pred=ev.midi_events(path);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,m=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4) if n else 0,"recall":round(tp/m,4) if m else 0,"f1":round(2*tp/(n+m),4) if n+m else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    part=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{})
            rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None,
          "mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):part.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(s["f1"]+.20*sum(part)/len(part)-.25*ks,6);result["summary"]=s
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"]
    return result

def rank(res):return sorted(res.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=ROOT/"drumscribe/experiments/generated-search-component-hybrid";report={"schema":1,"cycles":[]}
    # Confidence reflects prior component strength, not chart of current song.
    recipes={
      "c52_robust":{
        "kick":"kick_sharp","snare":"snare_anchor","hat":"hat_guard","pedal_hat":"pedal_strict","tom":"tom_best","crash":"crash_soft",
        "_confidence":{"kick":1.00,"snare":.94,"hat":.86,"pedal_hat":.52,"tom":.88,"crash":.62}},
      "c52_precision":{
        "kick":"kick_guard","snare":"snare_anchor","hat":"hat_guard","pedal_hat":"pedal_strict","tom":"tom_best","crash":"crash_strict",
        "_confidence":{"kick":1.00,"snare":.96,"hat":.88,"pedal_hat":.48,"tom":.90,"crash":.82}},
      "c52_recall":{
        "kick":"kick_soft","snare":"snare_dsp","hat":"hat_hi","pedal_hat":"pedal_strict","tom":"tom_best","crash":"crash_soft","ride":"ride_recall",
        "_confidence":{"kick":.98,"snare":.82,"hat":.82,"pedal_hat":.48,"tom":.88,"crash":.62,"ride":.42}},
    }
    res={}
    for name,rec in recipes.items():
        res[name]=evaluate(name,rec,"two_hands","source",root/"cycle52")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=copy.deepcopy(recipes[win])
    report["cycles"].append({"cycle":52,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,policy in [("c53_two_hands","two_hands"),("c53_priority","priority"),("c53_none","none")]:
        res[name]=evaluate(name,best,policy,"source",root/"cycle53")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best_policy=res[win]["policy"]
    report["cycles"].append({"cycle":53,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,cp in [("c54_crash_source","source"),("c54_crash_head_tight","head:0.10"),("c54_crash_head_balanced","head:0.18")]:
        res[name]=evaluate(name,best,best_policy,cp,root/"cycle54")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":54,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"recipe":best,"policy":best_policy,"crash_policy":res[win]["crash_policy"],"detailed":res[win]["detailed"]}
    (ROOT/"drumscribe/experiments/results-iterative-component-hybrid.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
