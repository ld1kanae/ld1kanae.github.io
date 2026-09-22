"""Cycles 195-197: browser-core + retained ride/pedal component fusion.

Base is the current real-browser generated-v2-browser output, normalized back
to audio time using exportOffsetSec. Component source is component-merge-v7
c194_basecrash.

Cycle 195 compares base / ride-only / pedal-only / both.
Cycle 196 compares ride replacement policies on the winning component set.
Cycle 197 compares pedal replacement policies.

Every candidate is written as real MIDI, re-read, then scored against chart.mid.
chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
base=loadmod("base",EXP/"iterative_search.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
sel=loadmod("sel",EXP/"selection_policy.py")

BROWSER=EXP/"generated-v2-browser"
COMP=EXP/"generated-search-component-merge-v7/cycle194/c194_basecrash"

def meta(song):
    return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def browser_rows(song):
    side=json.loads((BROWSER/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BROWSER/f"{song}.mid")],side

def comp_rows(song):
    return [(t,g) for t,g,*_ in ev.midi_events(COMP/f"{song}.mid")]

def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)

def periodic(times,t,bpm):
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.065 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def enforce(rows):
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in rows if gg==g);last=-999.
        md=.035 if g in ("snare","hat","ride") else .05 if g in ("tom","pedal_hat") else .08 if g=="crash" else .04
        for t in arr:
            if t-last>=md:ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0
    pri={"snare":.95,"tom":.88,"crash":.84,"ride":.80,"hat":.62}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[x for x in c if x[1] not in HANDS];h=[x for x in c if x[1] in HANDS]
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def replace_ride(rows,comp,mode,bpm):
    base_hat=[t for t,g in rows if g=="hat"]
    cride=[t for t,g in comp if g=="ride"]
    chat=[t for t,g in comp if g=="hat"]
    if mode=="keep":return list(rows)
    if mode=="off":return [x for x in rows if x[1]!="ride"]
    if mode=="ride_only":
        out=[x for x in rows if x[1]!="ride"]+[(t,"ride") for t in cride]
        return enforce(out)
    if mode=="pair":
        out=[x for x in rows if x[1] not in ("hat","ride")]
        out += [(t,"hat") for t in chat]+[(t,"ride") for t in cride]
        return enforce(out)
    if mode=="periodic":
        keep=[t for t in cride if periodic(cride,t,bpm)>=.50]
        out=[x for x in rows if x[1]!="ride"]
        # Replace only a nearby base hat when ride has periodic support.
        for t in keep:
            out=[x for x in out if not(x[1]=="hat" and abs(x[0]-t)<=.06)]
            out.append((t,"ride"))
        return enforce(out)
    raise ValueError(mode)

def replace_pedal(rows,comp,mode,bpm):
    cped=[t for t,g in comp if g=="pedal_hat"]
    if mode=="keep":return list(rows)
    if mode=="off":return [x for x in rows if x[1]!="pedal_hat"]
    if mode=="all":
        return enforce([x for x in rows if x[1]!="pedal_hat"]+[(t,"pedal_hat") for t in cped])
    if mode=="periodic":
        keep=[t for t in cped if periodic(cped,t,bpm)>=.50]
        return enforce([x for x in rows if x[1]!="pedal_hat"]+[(t,"pedal_hat") for t in keep])
    if mode=="merge":
        bped=[t for t,g in rows if g=="pedal_hat"];allp=sorted(bped+cped);keep=[];last=-999.
        for t in allp:
            if t-last>=.05:keep.append(t);last=t
        return enforce([x for x in rows if x[1]!="pedal_hat"]+[(t,"pedal_hat") for t in keep])
    raise ValueError(mode)

def build(song,ride_mode,pedal_mode):
    b,side=browser_rows(song);c=comp_rows(song);bpm=float(side["bpm"])
    x=replace_ride(b,c,ride_mode,bpm)
    x=replace_pedal(x,c,pedal_mode,bpm)
    return enforce(x),side

def write(path,rows,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in rows],bpm)

def evaluate(name,ride_mode,pedal_mode,outdir):
    result={"ride_mode":ride_mode,"pedal_mode":pedal_mode,"songs":{}};tot=Counter()
    for song in SONGS:
        rows,side=build(song,ride_mode,pedal_mode)
        p=outdir/name/f"{song}.mid";write(p,rows,float(side["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        m=meta(song);shift=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,r=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":r,"precision":tp/n if n else 0,"recall":tp/r if r else 0,
       "f1":2*tp/(n+r) if n+r else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for song in SONGS:
            z=result["songs"][song]["by_group"].get(g,{});rr=z.get("reference",0)
            if rr:sf.append(2*z.get("tp",0)/(z.get("predicted",0)+rr) if z.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,
          "false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,
          "worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s)
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"]
    return result

def choose(res,baseline,targets):
    d=sel.select(res,baseline["summary"],target_parts=targets,max_part_drop=.020,target_tolerance=.010)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-browser-component-fusion";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","keep","keep",root/"baseline")

    res={}
    for name,rm,pm in [
      ("c195_browser_base","keep","keep"),
      ("c195_ride","pair","keep"),
      ("c195_pedal","keep","all"),
      ("c195_both","pair","all"),
    ]:
        res[name]=evaluate(name,rm,pm,root/"cycle195")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],
          "ride":res[name]["summary"]["by_group"]["ride"],"pedal":res[name]["summary"]["by_group"]["pedal_hat"],
          "hat":res[name]["summary"]["by_group"]["hat"],"crash":res[name]["summary"]["by_group"]["crash"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline,("ride","pedal_hat","hat","crash"));win=d["winner"] or "c195_both";best=res[win]
    report["cycles"].append({"cycle":195,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    # Cycle 196: ride policy while preserving chosen pedal policy.
    pm=best["pedal_mode"];res={}
    for name,rm in [("c196_ride_only","ride_only"),("c196_pair","pair"),("c196_periodic","periodic")]:
        res[name]=evaluate(name,rm,pm,root/"cycle196")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"ride":res[name]["summary"]["by_group"]["ride"],"hat":res[name]["summary"]["by_group"]["hat"]},ensure_ascii=False),flush=True)
    d=choose(res,best,("ride","hat"));win=d["winner"] or "c196_pair";best=res[win]
    report["cycles"].append({"cycle":196,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    # Cycle 197: pedal policy.
    rm=best["ride_mode"];res={}
    for name,pm in [("c197_all","all"),("c197_periodic","periodic"),("c197_merge","merge")]:
        res[name]=evaluate(name,rm,pm,root/"cycle197")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"pedal":res[name]["summary"]["by_group"]["pedal_hat"]},ensure_ascii=False),flush=True)
    d=choose(res,best,("pedal_hat",));win=d["winner"] or "c197_all";best=res[win]
    report["cycles"].append({"cycle":197,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    report["baseline"]=baseline
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],
                     "ride_mode":best["ride_mode"],"pedal_mode":best["pedal_mode"],
                     "detailed":best["detailed"]}
    (EXP/"results-iterative-browser-component-fusion.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
