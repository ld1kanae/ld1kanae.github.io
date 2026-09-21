"""Cycles 67-69: snare recall repair with kick-conflict guard.

Base is the best all-part recall-repair candidate, but snare is rebuilt from the
high-precision hybrid core plus supplemental ML/DSP evidence.

Cycle 67: consensus vs pattern vs guarded-pattern
Cycle 68: 25/45/70ms kick conflict windows
Cycle 69: repetition support 2/3/4 bars

Reference MIDI is scoring-only.
"""
from __future__ import annotations
import importlib.util,json,math
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

CORE=EXP/"generated-search-component-hybrid/cycle54/c54_crash_source"
ML=EXP/"generated-round4-ml"
DSP=EXP/"generated-search-drumsep-rate/cycle47/c47_precision"
TOM_SRC=EXP/"generated-search-recall-repair/cycle62/c62_tom_consensus"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def phase(rs,m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;sc=0.
        for t,g in rs:
            if g not in ("kick","snare"):continue
            w=1.7 if g=="kick" else .8;x=(t-ph)%bar;d=min(x,bar-x)
            sc+=w*math.exp(-.5*(d/max(.025,.10*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],bar

def slot(t,ph,bar):return int(round((((t-ph)%bar)/bar)*16))%16

def repeated(times,t,ph,bar,min_bars):
    b=math.floor((t-ph)/bar);s=slot(t,ph,bar)
    bars={math.floor((x-ph)/bar) for x in times if abs(math.floor((x-ph)/bar)-b)<=6 and slot(x,ph,bar)==s}
    return len(bars)>=min_bars

def enforce(rs):
    rs=sorted(set((round(t,6),g) for t,g in rs));out=[];i=0
    while i<len(rs):
        t=rs[i][0];j=i
        while j<len(rs) and rs[j][0]-t<=.033:j+=1
        c=rs[i:j];ex=[x for x in c if x[1] not in HANDS];h=[x for x in c if x[1] in HANDS]
        pri={"snare":.90,"tom":.86,"crash":.82,"ride":.78,"hat":.60}
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def build(song,mode,kick_window,min_bars):
    core=rows(CORE,song)
    # Carry the improved tom from cycle 62 while rebuilding snare.
    tom=[x for x in rows(TOM_SRC,song) if x[1]=="tom"]
    rs=[x for x in core if x[1]!="tom"]+tom
    base_sn=[t for t,g in core if g=="snare"];kicks=[t for t,g in core if g=="kick"]
    ml=[t for t,g in rows(ML,song) if g=="snare"];dsp=[t for t,g in rows(DSP,song) if g=="snare"]
    m=meta(song);ph,bar=phase(core,m);pattern_times=sorted(base_sn+ml)
    add=[]
    for t in ml:
        if near(base_sn,t,.045):continue
        dsp_ok=near(dsp,t,.060)
        pat_ok=repeated(pattern_times,t,ph,bar,min_bars)
        kick_conflict=near(kicks,t,kick_window)
        if mode=="consensus":keep=dsp_ok
        elif mode=="pattern":keep=dsp_ok or pat_ok
        else:
            # A supplemental snare may coexist with a kick only when another
            # acoustic snare detector independently agrees. Pattern evidence
            # alone cannot override a nearby kick.
            keep=dsp_ok or (pat_ok and not kick_conflict)
        if keep:add.append((t,"snare"))
    return enforce(rs+add),m

def write(path,rs,bpm):base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in rs],bpm)

def evaluate(name,mode,kick_window,min_bars,outdir):
    result={"mode":mode,"kick_window":kick_window,"min_bars":min_bars,"songs":{}};tot=Counter()
    for song in SONGS:
        rs,m=build(song,mode,kick_window,min_bars);p=outdir/name/f"{song}.mid";write(p,rs,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mref,"precision":round(tp/n,4),"recall":round(tp/mref,4),"f1":round(2*tp/(n+mref),4),"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    part=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","pedal_hat","tom","crash","ride"):part.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(s["f1"]+.20*sum(part)/len(part)-.30*ks,6);result["summary"]=s
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-snare-guard";report={"schema":1,"cycles":[]}
    res={}
    for name,mode in [("c67_consensus","consensus"),("c67_pattern","pattern"),("c67_guarded","guarded")]:
        res[name]=evaluate(name,mode,.045,2,root/"cycle67");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":67,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    res={}
    for name,w in [("c68_kick25",.025),("c68_kick45",.045),("c68_kick70",.070)]:
        res[name]=evaluate(name,best["mode"],w,best["min_bars"],root/"cycle68");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":68,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    res={}
    for name,b in [("c69_repeat2",2),("c69_repeat3",3),("c69_repeat4",4)]:
        res[name]=evaluate(name,best["mode"],best["kick_window"],b,root/"cycle69");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":69,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"mode":res[win]["mode"],"kick_window":res[win]["kick_window"],"min_bars":res[win]["min_bars"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-snare-guard.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
