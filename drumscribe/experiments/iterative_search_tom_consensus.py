"""Cycles 103-105: tom recall repair by multi-model consensus.

Base: fusion-v2 cycle84 (current all-part best).
Supplement sources:
- tom RF / ExtraTrees / logistic historical predictions

Reference MIDI is never used during fusion. It is only used after candidate MIDI
files are written.

Cycle 103: extra-only / extra+logistic consensus / fill-context consensus
Cycle 104: consensus matching windows 40 / 60 / 80 ms
Cycle 105: fill density thresholds 3 / 5 / 7 extra hand hits above median
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
RF=EXP/"generated-search-tom/cycle25/c25_rf"
EXTRA=EXP/"generated-search-tom/cycle25/c25_extra"
LOG=EXP/"generated-search-tom/cycle25/c25_logistic"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
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
            sc+=w*math.exp(-.5*(d/max(.025,.10*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def fill_bars(events,m,density_extra):
    ph,beat,bar=phase(events,m)
    count=Counter(math.floor((t-ph)/bar) for t,g in events if g in HANDS)
    vals=list(count.values()) or [0];med=statistics.median(vals)
    fills={b for b,n in count.items() if n>=med+density_extra}
    # Also protect bars containing existing tom clusters.
    tom=Counter(math.floor((t-ph)/bar) for t,g in events if g=="tom")
    fills|={b for b,n in tom.items() if n>=2}
    return fills,ph,bar

def dedupe(xs,w=.045):
    out=[];last=-999.
    for t in sorted(xs):
        if t-last>=w:out.append(t);last=t
    return out

def enforce(events):
    ded=[]
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.05,"tom":.05,"crash":.09,"ride":.04}
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0;pri={"snare":.92,"tom":.88,"crash":.84,"ride":.82,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[x for x in c if x[1] not in HANDS];h=[x for x in c if x[1] in HANDS]
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def build(song,mode,window,density_extra):
    b=rows(BASE,song);current=[t for t,g in b if g=="tom"]
    rf=[t for t,g in rows(RF,song) if g=="tom"]
    ex=[t for t,g in rows(EXTRA,song) if g=="tom"]
    lg=[t for t,g in rows(LOG,song) if g=="tom"]
    fills,ph,bar=fill_bars(b,meta(song),density_extra)
    cand=[]
    if mode=="extra":
        cand=ex
    elif mode=="consensus":
        cand=[t for t in ex if near(lg,t,window)]
    else:
        pool=dedupe(ex+lg,.020)
        for t in pool:
            votes=sum([near(ex,t,window),near(lg,t,window),near(rf,t,window)])
            if votes<2:continue
            bb=math.floor((t-ph)/bar)
            if bb in fills:cand.append(t)
    add=[]
    for t in dedupe(cand,.050):
        if near(current,t,.050):continue
        # weak candidates colliding with kick/snare are excluded; true tom fills
        # are allowed only if multi-model consensus put them into cand.
        ks=[x for x,g in b if g in ("kick","snare")]
        if mode=="extra" and near(ks,t,.035):continue
        add.append((t,"tom"))
    return enforce(b+add)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,mode,window,density_extra,outdir):
    result={"mode":mode,"window":window,"density_extra":density_extra,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=build(song,mode,window,density_extra);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
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
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,
          "f1":round(f,4),"count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):core.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"];tom=s["by_group"]["tom"]["f1"]
    s["selection_score"]=round(s["f1"]+.18*sum(core)/len(core)+.10*tom+.05*ped-.30*ks,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-tom-consensus";report={"schema":1,"cycles":[]}
    res={}
    for name,mode in [("c103_extra","extra"),("c103_consensus","consensus"),("c103_fill","fill")]:
        res[name]=evaluate(name,mode,.060,5,root/"cycle103");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":103,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,w in [("c104_w40",.040),("c104_w60",.060),("c104_w80",.080)]:
        res[name]=evaluate(name,best["mode"],w,best["density_extra"],root/"cycle104");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":104,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,d in [("c105_density3",3),("c105_density5",5),("c105_density7",7)]:
        res[name]=evaluate(name,best["mode"],best["window"],d,root/"cycle105");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":105,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"mode":res[win]["mode"],"window":res[win]["window"],"density_extra":res[win]["density_extra"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-tom-consensus.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
