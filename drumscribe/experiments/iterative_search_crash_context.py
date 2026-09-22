"""Cycles 139-141: crash zero-source fallback with musical context.

Base: fusion-v5 c129_balanced (precision crash).
Fallback: crash-fallback c88_zero_base.

Only when the precision crash stream is empty for a song do we consider fallback
crashes. Prediction-time filters use only the predicted kick/snare grid and BPM.
chart.mid is used only after each candidate MIDI is written.

Cycle 139: all fallback / kick-supported / kick-or-snare-supported
Cycle 140: support window 60 / 100 / 140 ms
Cycle 141: support only / support+bar-head 0.15 / support+bar-head 0.25 beat
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
PREC=EXP/"generated-search-crash-fallback/cycle88/c88_precision"
FALL=EXP/"generated-search-crash-fallback/cycle88/c88_zero_base"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def phase(events,m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(128):
        ph=bar*q/128;sc=0.
        for t,g in events:
            if g not in ("kick","snare"):continue
            w=1.8 if g=="kick" else .75
            x=(t-ph)%bar;d=min(x,bar-x)
            sc+=w*math.exp(-.5*(d/max(.025,.10*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def head_distance(t,ph,beat,bar):
    x=(t-ph)%bar
    return min(x,bar-x)/beat

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
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def fallback_crashes(song,mode,window,bar_gate):
    b=rows(BASE,song);m=meta(song)
    p=[t for t,g in rows(PREC,song) if g=="crash"]
    f=[t for t,g in rows(FALL,song) if g=="crash"]
    if p:
        return p,{"precision":len(p),"fallback":len(f),"used":"precision","chosen":len(p)}
    kicks=[t for t,g in b if g=="kick"];snares=[t for t,g in b if g=="snare"]
    ph,beat,bar=phase(b,m)
    chosen=[]
    for t in f:
        if mode=="all":support=True
        elif mode=="kick":support=near(kicks,t,window)
        else:support=near(kicks,t,window) or near(snares,t,window)
        if not support:continue
        if bar_gate is not None and head_distance(t,ph,beat,bar)>bar_gate:continue
        chosen.append(t)
    return chosen,{"precision":len(p),"fallback":len(f),"used":mode,"chosen":len(chosen)}

def fuse(song,mode,window,bar_gate):
    e=[x for x in rows(BASE,song) if x[1]!="crash"]
    crashes,diag=fallback_crashes(song,mode,window,bar_gate)
    return enforce(e+[(t,"crash") for t in crashes]),diag

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,window,bar_gate,outdir):
    result={"mode":mode,"window":window,"bar_gate":bar_gate,"song_decisions":{},"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr,diag=fuse(song,mode,window,bar_gate);result["song_decisions"][song]=diag
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
    d=sel.select(res,baseline["summary"],target_parts=("crash",),max_part_drop=.02,target_tolerance=.005)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-crash-context";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","all",.10,None,root/"baseline")
    # The true baseline for the guard is fusion-v5 precision crash.
    base0=evaluate("baseline_precision","kick",0.0,None,root/"baseline_precision")
    # overwrite its crash with precision by using a no-fallback sentinel:
    base0=baseline if False else base0

    res={}
    for name,mode in [("c139_all","all"),("c139_kick","kick"),("c139_kick_snare","kick_snare")]:
        res[name]=evaluate(name,mode,.10,None,root/"cycle139");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    # Compare against fusion-v5 reconstructed through mode=kick with zero window:
    # on zero-source songs this adds nothing, matching precision behavior.
    precision_base=evaluate("precision_base","kick",0.0,None,root/"precision_base")
    d=choose(res,precision_base);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":139,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})

    res={}
    mode=best["mode"] if best["mode"]!="all" else "kick_snare"
    for name,w in [("c140_w060",.060),("c140_w100",.100),("c140_w140",.140)]:
        res[name]=evaluate(name,mode,w,None,root/"cycle140");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":140,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})

    res={}
    for name,bg in [("c141_support_only",None),("c141_head15",.15),("c141_head25",.25)]:
        res[name]=evaluate(name,best["mode"],best["window"],bg,root/"cycle141");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":141,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "mode":best["mode"],"window":best["window"],"bar_gate":best["bar_gate"],"song_decisions":best["song_decisions"],"detailed":best["detailed"]}
    (EXP/"results-iterative-crash-context.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
