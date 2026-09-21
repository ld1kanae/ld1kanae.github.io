"""Cycles 73-75: hi-hat precision repair after high-recall fusion.

Filters the c69 high-recall hat candidate using only audio-derived source
agreement and predicted rhythmic structure. chart.mid is evaluation only.

Cycle 73: three precision rules.
Cycle 74: three density thresholds.
Cycle 75: three repetition thresholds.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter,defaultdict
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

BASE=EXP/"generated-search-hat-fusion/cycle69/c69_repeat3"
GUARD=EXP/"generated-search-drumsep-rate/cycle48/c48_hat_guard"
HI=EXP/"generated-search-drumsep-rate/cycle46/c46_sr44100"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def phase(events,m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    den=int(ts.get("denominator",4));num=int(ts.get("numerator",4))
    beat=60/bpm*4/den;bar=beat*num
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;sc=0.
        for t,g in events:
            if g not in ("kick","snare"):continue
            w=1.6 if g=="kick" else .75;x=(t-ph)%bar;d=min(x,bar-x)
            sc+=w*math.exp(-.5*(d/max(.025,.10*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar,num

def slot(t,ph,bar):return int(round((((t-ph)%bar)/bar)*16))%16
def barno(t,ph,bar):return math.floor((t-ph)/bar)

def rep_support(xs,t,ph,bar,window=6):
    s=slot(t,ph,bar);b=barno(t,ph,bar);bars=set()
    for x in xs:
        bx=barno(x,ph,bar)
        if abs(bx-b)<=window and slot(x,ph,bar)==s:bars.add(bx)
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

def filter_hat(song,rule,density_thr,rep_thr):
    b=rows(BASE,song); hats=[t for t,g in b if g=="hat"]
    gd=[t for t,g in rows(GUARD,song) if g=="hat"];hi=[t for t,g in rows(HI,song) if g=="hat"]
    m=meta(song);ph,beat,bar,num=phase(b,m)
    perbar=Counter(barno(t,ph,bar) for t in hats)
    chosen=[]
    for t in hats:
        agree=near(gd,t,.045) and near(hi,t,.045)
        rep=rep_support(hats,t,ph,bar)
        density=perbar[barno(t,ph,bar)]/max(1,num)
        if rule=="consensus_or_repeat":
            keep=agree or rep>=rep_thr
        elif rule=="adaptive_density":
            need=rep_thr+1 if density>density_thr else rep_thr
            keep=agree or rep>=need
        else: # strict adaptive; dense bars need both stronger repetition and source support
            if density>density_thr:
                keep=agree and rep>=max(2,rep_thr-1)
            else:
                keep=agree or rep>=rep_thr
        if keep:chosen.append(t)
    others=[e for e in b if e[1]!="hat"]
    return enforce(others+[(t,"hat") for t in chosen])

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,rule,density_thr,rep_thr,outdir):
    result={"rule":rule,"density_thr":density_thr,"rep_thr":rep_thr,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=filter_hat(song,rule,density_thr,rep_thr);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
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
          "false_discovery_rate":round((b-a)/b,4) if b else 0,"miss_rate":round((c-a)/c,4) if c else 0,
          "count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):parts.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"];hat_fdr=s["by_group"]["hat"]["false_discovery_rate"]
    # Explicitly penalize excess hat hits in addition to F1.
    s["selection_score"]=round(s["f1"]+.20*sum(parts)/len(parts)+.06*ped-.32*ks-.08*hat_fdr,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-hat-precision";report={"schema":1,"cycles":[]}
    res={}
    for name,rule in [("c73_consensus_repeat","consensus_or_repeat"),("c73_adaptive","adaptive_density"),("c73_strict","strict_adaptive")]:
        res[name]=evaluate(name,rule,2.25,4,root/"cycle73");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":73,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,d in [("c74_density175",1.75),("c74_density225",2.25),("c74_density275",2.75)]:
        res[name]=evaluate(name,best["rule"],d,best["rep_thr"],root/"cycle74");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":74,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,k in [("c75_repeat3",3),("c75_repeat4",4),("c75_repeat5",5)]:
        res[name]=evaluate(name,best["rule"],best["density_thr"],k,root/"cycle75");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":75,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"rule":res[win]["rule"],"density_thr":res[win]["density_thr"],"rep_thr":res[win]["rep_thr"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-hat-precision.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
