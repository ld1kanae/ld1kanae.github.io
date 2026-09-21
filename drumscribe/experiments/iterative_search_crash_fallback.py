"""Cycles 88-90: adaptive crash fallback.

Fixes the failure mode where the precision/downbeat crash component predicts
zero or nearly zero crashes for an entire song. Fallback decisions use only
prediction density, never chart.mid.

Cycle 94: precision only / zero fallback to base / sparse fallback to recall.
Cycle 95: sparse-ratio thresholds.
Cycle 96: recall rescue spacing.
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

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

BASE=EXP/"generated-search-fusion-v2/cycle84/c84_pedal75"
PREC=EXP/"generated-search-crash-consensus/cycle72/c72_head18"
RECALL=EXP/"generated-search-crash-consensus/cycle71/c71_crash"
OLD=EXP/"generated-search-recall-repair/cycle63/c63_pedal_keep"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def enforce(events):
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        mind=.09 if g=="crash" else .045 if g=="pedal_hat" else .035 if g in ("snare","hat","ride") else .045
        for t in arr:
            if t-last>=mind:ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0;pri={"snare":.93,"tom":.88,"crash":.84,"ride":.80,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def phase(events,m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;sc=0.
        for t,g in events:
            if g!="kick":continue
            x=(t-ph)%bar;d=min(x,bar-x);sc+=math.exp(-.5*(d/max(.025,.10*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def source_crashes(path,song):return [t for t,g in rows(path,song) if g=="crash"]

def choose(song,mode,ratio,spacing_bars):
    b=rows(BASE,song);p=source_crashes(PREC,song);r=source_crashes(RECALL,song);o=source_crashes(OLD,song)
    chosen=list(p)
    if mode=="zero_base":
        if len(p)==0:chosen=o
    elif mode=="sparse_recall":
        # fallback if precision component is suspiciously sparse relative to the
        # recall source, but only when recall source itself has enough evidence.
        if len(r)>=4 and len(p)<max(1,ratio*len(r)):
            chosen=r
    elif mode=="section_rescue":
        m=meta(song);ph,beat,bar=phase(b,m);gap=spacing_bars*bar
        for t in r:
            if near(chosen,t,.08):continue
            if chosen and min(abs(t-x) for x in chosen)<gap:continue
            x=(t-ph)%bar;db=min(x,bar-x)/beat
            if db<=.20:chosen.append(t)
    others=[e for e in b if e[1]!="crash"]
    return enforce(others+[(t,"crash") for t in sorted(chosen)])

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,ratio,spacing_bars,outdir):
    result={"mode":mode,"ratio":ratio,"spacing_bars":spacing_bars,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=choose(song,mode,ratio,spacing_bars);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid");shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
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
          "false_discovery_rate":round((b-a)/b,4) if b else 0,"miss_rate":round((c-a)/c,4) if c else 0,
          "count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):core.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"];hf=s["by_group"]["hat"]["false_discovery_rate"];cfdr=s["by_group"]["crash"]["false_discovery_rate"]
    worst_crash=s["by_group"]["crash"]["worst_song_f1"] or 0
    s["selection_score"]=round(s["f1"]+.18*sum(core)/len(core)+.08*ped+.05*worst_crash-.30*ks-.06*hf-.04*cfdr,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-crash-fallback";report={"schema":1,"cycles":[]}
    res={}
    for name,mode in [("c94_precision","precision"),("c94_zero_base","zero_base"),("c94_sparse_recall","sparse_recall")]:
        res[name]=evaluate(name,mode,.25,8,root/"cycle94");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":94,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,q in [("c95_ratio10",.10),("c95_ratio25",.25),("c95_ratio50",.50)]:
        res[name]=evaluate(name,"sparse_recall",q,best["spacing_bars"],root/"cycle95");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win2=rr[0][0];b2=res[win2]
    report["cycles"].append({"cycle":95,"candidates":res,"ranking":[n for n,_ in rr],"winner":win2,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    cur=max([best,b2],key=lambda x:x["summary"]["selection_score"])

    res={}
    for name,gap in [("c96_gap4",4),("c96_gap8",8),("c96_gap12",12)]:
        res[name]=evaluate(name,"section_rescue",cur.get("ratio",.25),gap,root/"cycle96");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":96,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    final=max([best,b2,res[win]],key=lambda x:x["summary"]["selection_score"])
    report["final"]={"winner":"cross-cycle-best","summary":final["summary"],"mode":final["mode"],"ratio":final["ratio"],"spacing_bars":final["spacing_bars"],"detailed":final["detailed"]}
    (EXP/"results-iterative-crash-fallback.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
