"""Cycles 67-69: hi-hat false-positive/recall tradeoff.

Uses audio-derived MIDI outputs only during filtering. Ground truth is consulted
only after writing each candidate MIDI.

Cycle 67: current guarded hat vs 44.1kHz hat vs consensus.
Cycle 68: consensus matching windows 25/45/70 ms.
Cycle 69: rescue policy for unmatched high-res hits.
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

BASE=EXP/"generated-search-recall-repair/cycle63/c63_pedal_keep"
GUARD=EXP/"generated-search-drumsep-rate/cycle48/c48_hat_guard"
HI=EXP/"generated-search-drumsep-rate/cycle46/c46_sr44100"

def erows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def phase(events,m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;sc=0.
        for t,g in events:
            if g not in ("kick","snare"):continue
            w=1.7 if g=="kick" else .8;x=(t-ph)%bar;d=min(x,bar-x)
            sc+=w*math.exp(-.5*(d/max(.025,.1*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def slot(t,ph,bar):return int(round((((t-ph)%bar)/bar)*16))%16

def repeat_support(xs,t,ph,bar):
    s=slot(t,ph,bar);b=math.floor((t-ph)/bar);bars=set()
    for x in xs:
        bx=math.floor((x-ph)/bar)
        if abs(bx-b)<=6 and slot(x,ph,bar)==s:bars.add(bx)
    return len(bars)

def enforce(events):
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.;mind=.033 if g=="hat" else .04
        for t in arr:
            if t-last>=mind:ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0;pri={"snare":.9,"tom":.86,"crash":.82,"ride":.78,"hat":.6}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def hats(song,mode,w,rescue):
    b=erows(BASE,song);g=[t for t,gg in erows(GUARD,song) if gg=="hat"];h=[t for t,gg in erows(HI,song) if gg=="hat"]
    if mode=="guard":chosen=g
    elif mode=="hi":chosen=h
    else:
        chosen=[t for t in g if near(h,t,w)]
        if rescue!="none":
            m=meta(song);ph,beat,bar=phase(b,m);pool=sorted(g+h)
            for t in h:
                if near(chosen,t,w):continue
                rep=repeat_support(pool,t,ph,bar)
                # Avoid rescuing hats colliding with predicted kick/snare unless
                # they have stronger repetition support.
                ks=[x for x,gg in b if gg in ("kick","snare")]
                collision=near(ks,t,.035)
                if rescue=="repeat2" and rep>=2 and (not collision or rep>=3):chosen.append(t)
                elif rescue=="repeat3" and rep>=3 and (not collision or rep>=4):chosen.append(t)
        chosen=sorted(chosen)
    others=[e for e in b if e[1]!="hat"]
    return enforce(others+[(t,"hat") for t in chosen])

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,w,rescue,outdir):
    result={"mode":mode,"window":w,"rescue":rescue,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=hats(song,mode,w,rescue);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid");shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mr,4) if mr else 0,"f1":round(2*tp/(n+mr),4) if n+mr else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    parts=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),
          "count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):parts.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"]
    s["selection_score"]=round(s["f1"]+.20*sum(parts)/len(parts)+.06*ped-.32*ks,6);result["summary"]=s
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-hat-fusion";report={"schema":1,"cycles":[]}
    res={}
    for name,mode in [("c67_guard","guard"),("c67_hi441","hi"),("c67_consensus","consensus")]:
        res[name]=evaluate(name,mode,.045,"none",root/"cycle67");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":67,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    # Only consensus has a meaningful matching window; if a direct source wins,
    # compare it to consensus windows anyway so the cycle still has 3 hypotheses.
    res={}
    for name,w in [("c68_w25",.025),("c68_w45",.045),("c68_w70",.070)]:
        res[name]=evaluate(name,"consensus",w,"none",root/"cycle68");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win2=rr[0][0];b2=res[win2]
    # Keep cycle67 winner if it is better.
    if best["summary"]["selection_score"]>b2["summary"]["selection_score"]:chosen=best
    else:chosen=b2
    report["cycles"].append({"cycle":68,"candidates":res,"ranking":[n for n,_ in rr],"winner":win2,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    basew=chosen.get("window",.045) if chosen.get("mode")=="consensus" else .045
    for name,rescue in [("c69_none","none"),("c69_repeat2","repeat2"),("c69_repeat3","repeat3")]:
        res[name]=evaluate(name,"consensus",basew,rescue,root/"cycle69");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":69,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    candidates=[best,b2,res[win]];final=max(candidates,key=lambda x:x["summary"]["selection_score"])
    report["final"]={"winner":"cross-cycle-best","summary":final["summary"],"mode":final["mode"],"window":final["window"],"rescue":final["rescue"],"detailed":final["detailed"]}
    (EXP/"results-iterative-hat-fusion.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
