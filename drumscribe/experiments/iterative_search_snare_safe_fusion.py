"""Cycles 112-114: safe high-recall snare fusion.

Start from the current balanced base and add only selected snare hits from a
high-recall snare component. Prediction-time filtering uses only audio-derived
MIDI streams and musical structure. chart.mid is consulted only after writing
each candidate MIDI.

Cycle 112: three kick-conflict rescue policies.
Cycle 113: kick-veto window 25 / 45 / 65 ms.
Cycle 114: independent snare-consensus window 30 / 60 / 90 ms.
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

BASE=EXP/"generated-search-tom-consensus/cycle105/c105_density7"
HI=EXP/"generated-search-best-fusion/cycle80/c80_snare_pattern"
DSP=EXP/"generated-search-drumsep-rate/cycle47/c47_precision"

def erows(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]

def meta(song):
    return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)

def phase(events,m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;sc=0.
        for t,g in events:
            if g not in ("kick","snare"):continue
            w=1.8 if g=="kick" else .8
            x=(t-ph)%bar;d=min(x,bar-x)
            sc+=w*math.exp(-.5*(d/max(.025,.1*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def slot(t,ph,bar):
    return int(round((((t-ph)%bar)/bar)*16))%16

def repeated(times,t,ph,bar):
    target=slot(t,ph,bar);b=math.floor((t-ph)/bar);bars=set()
    for x in times:
        bx=math.floor((x-ph)/bar)
        if abs(bx-b)<=6 and slot(x,ph,bar)==target:bars.add(bx)
    return len(bars)

def enforce(events):
    ded=[]
    mind={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.05,"tom":.05,"crash":.10,"ride":.045,"other":.04}
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mind.get(g,.04):ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0
    pri={"snare":.92,"tom":.86,"crash":.84,"ride":.82,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[x for x in c if x[1] not in HANDS];h=[x for x in c if x[1] in HANDS]
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def fuse(song,policy,kick_window,dsp_window):
    b=erows(BASE,song); hi=erows(HI,song); dsp=erows(DSP,song)
    base_sn=[t for t,g in b if g=="snare"];hi_sn=[t for t,g in hi if g=="snare"]
    dsp_sn=[t for t,g in dsp if g=="snare"];kicks=[t for t,g in b if g=="kick"]
    m=meta(song);ph,beat,bar=phase(b,m);pool=sorted(base_sn+hi_sn)
    add=[]
    for t in hi_sn:
        if near(base_sn,t,.040):continue
        collides=near(kicks,t,kick_window)
        dsp_ok=near(dsp_sn,t,dsp_window)
        s=slot(t,ph,bar);backbeat=s in (4,12)
        rep=repeated(pool,t,ph,bar)
        if policy=="hard_veto":
            keep=not collides
        elif policy=="dsp_rescue":
            keep=(not collides) or dsp_ok
        else:
            keep=(not collides) or dsp_ok or (backbeat and rep>=2)
        if keep:add.append((t,"snare"))
    return enforce(b+add)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,policy,kick_window,dsp_window,outdir):
    result={"policy":policy,"kick_window":kick_window,"dsp_window":dsp_window,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=fuse(song,policy,kick_window,dsp_window)
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mref,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mref,4) if mref else 0,
       "f1":round(2*tp/(n+mref),4) if n+mref else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    parts=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];gf=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});r=x.get("reference",0)
            if r:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+r) if x.get("predicted",0)+r else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,
          "f1":round(gf,4),"count_ratio":round(b/c,4) if c else None,
          "mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):parts.append(gf)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"]
    s["selection_score"]=round(s["f1"]+.18*sum(parts)/len(parts)+.07*s["by_group"]["snare"]["f1"]+.05*ped-.34*ks,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-snare-safe-fusion";report={"schema":1,"cycles":[]}
    res={}
    for name,pol in [("c112_hard_veto","hard_veto"),("c112_dsp_rescue","dsp_rescue"),("c112_backbeat_rescue","backbeat_rescue")]:
        res[name]=evaluate(name,pol,.045,.060,root/"cycle112");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":112,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,w in [("c113_k25",.025),("c113_k45",.045),("c113_k65",.065)]:
        res[name]=evaluate(name,best["policy"],w,best["dsp_window"],root/"cycle113");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":113,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,w in [("c114_d30",.030),("c114_d60",.060),("c114_d90",.090)]:
        res[name]=evaluate(name,best["policy"],best["kick_window"],w,root/"cycle114");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":114,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"policy":res[win]["policy"],"kick_window":res[win]["kick_window"],"dsp_window":res[win]["dsp_window"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-snare-safe-fusion.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
