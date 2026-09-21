"""Cycles 58-60: neural cymbal fusion on top of the best hybrid/pattern base.

Prerequisites:
- results-iterative-neural-separation.json
- results-iterative-component-hybrid.json
Optionally uses the pattern-consensus winner if available.

Cycle 58: neural ride injection policy
Cycle 59: crash source policy
Cycle 60: hat<->ride replacement window
"""
from __future__ import annotations
import importlib.util, json, math
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

def winner_dir(result_file,root,cycle):
    obj=json.loads((EXP/result_file).read_text());winner=obj["final"]["winner"]
    return EXP/root/f"cycle{cycle}"/winner,winner

def base_dir():
    p=EXP/"results-iterative-pattern-consensus.json"
    if p.exists():
        return winner_dir("results-iterative-pattern-consensus.json","generated-search-pattern-consensus",57)
    return winner_dir("results-iterative-component-hybrid.json","generated-search-component-hybrid",54)

def neural_dir():
    return winner_dir("results-iterative-neural-separation.json","generated-search-neural-separation",51)

def periodic_support(times,t,bpm):
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.065 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def section_support(times,t,bpm):
    beat=60/bpm
    w=beat*8
    local=[x for x in times if abs(x-t)<=w/2]
    if len(local)<4:return 0.
    ps=[periodic_support(times,x,bpm) for x in local]
    return sum(p>=.5 for p in ps)/len(ps)

def remove_near(events,group,t,window):
    return [e for e in events if not(e[1]==group and abs(e[0]-t)<=window)]

def enforce_two_hands(events):
    events=sorted(events,key=lambda e:(e[0],e[1]));out=[];i=0
    while i<len(events):
        t=events[i][0];j=i
        while j<len(events) and events[j][0]-t<=.033:j+=1
        c=events[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        # Neural ride/crash and dedicated tom are weighted above hat at conflicts.
        pri={"crash":.9,"ride":.82,"tom":.8,"snare":.78,"hat":.58}
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out,key=lambda e:e[0])

def phase(events,meta):
    bpm=float(meta["bpm"]);ts=meta.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;sc=0.
        for t,g,*_ in events:
            if g not in ("kick","snare"):continue
            w=1.7 if g=="kick" else .8;x=(t-ph)%bar;d=min(x,bar-x)
            sc+=w*math.exp(-.5*(d/max(.025,beat*.10))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def crash_head(events,meta,width):
    ph,beat,bar=phase(events,meta);out=[]
    for e in events:
        if e[1]!="crash":out.append(e);continue
        x=(e[0]-ph)%bar;d=min(x,bar-x)/beat
        if d<=width:out.append(e)
    return out

def fuse(song,basepath,neuralpath,ride_mode,crash_mode,replace_window):
    folder=ROOT/"DruMaster/songs"/song;meta=json.loads((folder/"song.json").read_text());bpm=float(meta["bpm"])
    b=[(t,g) for t,g,*_ in ev.midi_events(basepath/f"{song}.mid")]
    n=[(t,g) for t,g,*_ in ev.midi_events(neuralpath/f"{song}.mid")]
    rides=[t for t,g in n if g=="ride"];crashes=[t for t,g in n if g=="crash"]

    events=[e for e in b if e[1]!="ride"]
    selected=[]
    for t in rides:
        per=periodic_support(rides,t,bpm);sec=section_support(rides,t,bpm)
        keep=(ride_mode=="raw") or (ride_mode=="periodic" and per>=.5) or (ride_mode=="section" and per>=.5 and sec>=.45)
        if keep:selected.append(t)
    for t in selected:
        events=remove_near(events,"hat",t,replace_window)
        events.append((t,"ride"))

    if crash_mode!="base":
        events=[e for e in events if e[1]!="crash"]
        if crash_mode=="neural":
            events.extend((t,"crash") for t in crashes)
        elif crash_mode=="union":
            bc=[t for t,g in b if g=="crash"]
            merged=sorted(bc+crashes);last=-999.
            for t in merged:
                if t-last>=.08:events.append((t,"crash"));last=t
        events=crash_head(events,meta,.16)
    return enforce_two_hands(events),meta

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,basedir,neuraldir,ride_mode,crash_mode,replace_window,outdir):
    result={"base":str(basedir),"neural":str(neuraldir),"ride_mode":ride_mode,"crash_mode":crash_mode,"replace_window":replace_window,"songs":{}};tot=Counter()
    for song in SONGS:
        events,meta=fuse(song,basedir,neuraldir,ride_mode,crash_mode,replace_window)
        path=outdir/name/f"{song}.mid";write(path,events,float(meta["bpm"]))
        pred=ev.midi_events(path);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,m=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,4) if n else 0,"recall":round(tp/m,4) if m else 0,"f1":round(2*tp/(n+m),4) if n+m else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    parts=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None,
          "mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):parts.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    # Give ride meaningful weight so "never predict ride" cannot win solely by
    # avoiding false positives.
    s["selection_score"]=round(s["f1"]+.18*sum(parts)/len(parts)+.08*s["by_group"]["ride"]["f1"]-.25*ks,6);result["summary"]=s
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    bd,bn=base_dir();nd,nn=neural_dir();root=EXP/"generated-search-cymbal-fusion";report={"schema":1,"base_winner":bn,"neural_winner":nn,"cycles":[]}
    res={}
    for name,mode in [("c58_raw","raw"),("c58_periodic","periodic"),("c58_section","section")]:
        res[name]=evaluate(name,bd,nd,mode,"base",.055,root/"cycle58");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":58,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,cm in [("c59_base_crash","base"),("c59_neural_crash","neural"),("c59_union_crash","union")]:
        res[name]=evaluate(name,bd,nd,best["ride_mode"],cm,best["replace_window"],root/"cycle59");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":59,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,w in [("c60_replace35",.035),("c60_replace55",.055),("c60_replace80",.080)]:
        res[name]=evaluate(name,bd,nd,best["ride_mode"],best["crash_mode"],w,root/"cycle60");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":60,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"ride_mode":res[win]["ride_mode"],"crash_mode":res[win]["crash_mode"],"replace_window":res[win]["replace_window"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-cymbal-fusion.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
