"""Cycles 103-105: tom recall fusion without sacrificing current precision.

Base is current all-part best (fusion-v2 cycle84). Supplement sources are
independent audio-derived tom predictors:
- dedicated tom ML
- separated-feature tom predictor

chart.mid is evaluation only after writing candidate MIDI.

Cycle 103: three supplementation strategies
Cycle 104: match/fill windows
Cycle 105: cluster support thresholds
"""
from __future__ import annotations
import importlib.util,json,math,statistics
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

BASE=EXP/"generated-search-fusion-v2/cycle84/c84_pedal75"
TOMML=EXP/"generated-search-tom/cycle27/c27_no_context"
SEP=EXP/"generated-search-separation/cycle42/c42_snare_roll_recall"

def rows(path,song): return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song): return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w): return any(abs(x-t)<=w for x in xs)

def phase(events,m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;sc=0.
        for t,g in events:
            if g not in ("kick","snare"):continue
            wt=1.7 if g=="kick" else .8
            x=(t-ph)%bar;d=min(x,bar-x)
            sc+=wt*math.exp(-.5*(d/max(.025,.10*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def bar_index(t,ph,bar): return math.floor((t-ph)/bar)

def fill_bars(events,ph,bar,extra=4):
    hand=Counter(bar_index(t,ph,bar) for t,g in events if g in HANDS)
    sn=Counter(bar_index(t,ph,bar) for t,g in events if g=="snare")
    vals=list(hand.values()) or [0];med=statistics.median(vals)
    return {b for b,n in hand.items() if n>=med+extra or sn[b]>=4}

def cluster_support(times,t,w):
    return sum(abs(x-t)<=w for x in times)

def enforce(events):
    ded=[]
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.05,"tom":.05,"crash":.09,"ride":.04}
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0;pri={"snare":.93,"tom":.89,"crash":.84,"ride":.82,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def build(song,mode,match_w,cluster_w,cluster_need,fill_extra):
    b=rows(BASE,song);current=[t for t,g in b if g=="tom"]
    ml=[t for t,g in rows(TOMML,song) if g=="tom"]
    sp=[t for t,g in rows(SEP,song) if g=="tom"]
    m=meta(song);ph,beat,bar=phase(b,m);fills=fill_bars(b,ph,bar,fill_extra)
    pool=sorted(set(ml+sp));add=[]
    for t in pool:
        if near(current,t,.05):continue
        agree=near(ml,t,match_w) and near(sp,t,match_w)
        in_fill=bar_index(t,ph,bar) in fills
        dense=cluster_support(pool,t,cluster_w)>=cluster_need
        if mode=="agree":
            keep=agree
        elif mode=="fill":
            keep=in_fill and (agree or dense)
        else:
            keep=agree or (in_fill and dense)
        if keep:add.append((t,"tom"))
    return enforce(b+add)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,match_w,cluster_w,cluster_need,fill_extra,outdir):
    result={"mode":mode,"match_window":match_w,"cluster_window":cluster_w,"cluster_need":cluster_need,"fill_extra":fill_extra,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=build(song,mode,match_w,cluster_w,cluster_need,fill_extra)
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mr,4) if mr else 0,"f1":round(2*tp/(n+mr),4) if n+mr else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    core=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),
          "count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):core.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"]
    s["selection_score"]=round(s["f1"]+.18*sum(core)/len(core)+.08*ped+.10*s["by_group"]["tom"]["f1"]-.30*ks,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x): return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-tom-fusion";report={"schema":1,"cycles":[]}
    res={}
    for name,mode in [("c103_agree","agree"),("c103_fill","fill"),("c103_hybrid","hybrid")]:
        res[name]=evaluate(name,mode,.060,.70,2,4,root/"cycle103");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":103,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,w in [("c104_match35",.035),("c104_match60",.060),("c104_match90",.090)]:
        res[name]=evaluate(name,best["mode"],w,best["cluster_window"],best["cluster_need"],best["fill_extra"],root/"cycle104");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":104,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,n in [("c105_cluster2",2),("c105_cluster3",3),("c105_cluster4",4)]:
        res[name]=evaluate(name,best["mode"],best["match_window"],best["cluster_window"],n,best["fill_extra"],root/"cycle105");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":105,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"mode":res[win]["mode"],"match_window":res[win]["match_window"],"cluster_window":res[win]["cluster_window"],"cluster_need":res[win]["cluster_need"],"fill_extra":res[win]["fill_extra"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-tom-fusion.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
