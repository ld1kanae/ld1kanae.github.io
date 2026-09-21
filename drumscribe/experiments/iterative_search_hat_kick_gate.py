"""Cycles 115-117: kick-overlap-only hi-hat cross-stem gate.

Whole-song cross-stem hat replacement hurt recall. Here cross-stem evidence is
used only where the current hat coincides with a predicted kick, the dominant
false-hat mode in arcaround.

Base: fusion-v2 c84.
Cross-stem support: old completed c87_thr24 output.

Cycle 115: cross-stem support matching windows 25/45/70 ms
Cycle 116: define kick-overlap at 20/35/55 ms
Cycle 117: rescue removed hits when repeated in 2/3/4 bars

No chart information is used before writing candidate MIDI.
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

BASE=EXP/"generated-search-fusion-v2/cycle84/c84_pedal75"
CROSS=EXP/"generated-search-crossstem-hat/cycle87/c87_thr24"

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
            sc+=w*math.exp(-.5*(d/max(.025,.1*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],bar

def slot(t,ph,bar):return int(round((((t-ph)%bar)/bar)*16))%16
def repeat_support(times,t,ph,bar):
    target=slot(t,ph,bar);b=math.floor((t-ph)/bar);bars=set()
    for x in times:
        bx=math.floor((x-ph)/bar)
        if abs(bx-b)<=6 and slot(x,ph,bar)==target:bars.add(bx)
    return len(bars)

def enforce(events):
    ded=[];mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.05,"tom":.05,"crash":.09,"ride":.04}
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

def build(song,support_window,kick_window,rescue_need):
    b=rows(BASE,song);cross=[t for t,g in rows(CROSS,song) if g=="hat"]
    hats=[t for t,g in b if g=="hat"];kicks=[t for t,g in b if g=="kick"]
    ph,bar=phase(b,meta(song));kept=[];removed=[]
    for t in hats:
        if not near(kicks,t,kick_window):
            kept.append(t);continue
        if near(cross,t,support_window):
            kept.append(t)
        else:
            removed.append(t)
    if rescue_need>0:
        for t in removed:
            if repeat_support(hats,t,ph,bar)>=rescue_need:
                kept.append(t)
    other=[e for e in b if e[1]!="hat"]
    return enforce(other+[(t,"hat") for t in kept])

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,support_window,kick_window,rescue_need,outdir):
    result={"support_window":support_window,"kick_window":kick_window,"rescue_need":rescue_need,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=build(song,support_window,kick_window,rescue_need);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid");shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,"precision":tp/n if n else 0,"recall":tp/mr if mr else 0,"f1":2*tp/(n+mr) if n+mr else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});r=x.get("reference",0)
            if r:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+r) if x.get("predicted",0)+r else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":f,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];result["canonical_score"]=sel.score(s)
    return result

def exact_base(outdir):
    # Near-zero kick window means effectively no overlap gate.
    return evaluate("base",.045,0.0,0,outdir/"base")

def choose(res,basec):
    d=sel.select(res,basec["summary"],target_parts=("hat",),max_part_drop=.05)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-hat-kick-gate";report={"schema":1,"cycles":[]}
    b=exact_base(root)
    res={}
    for n,w in [("c115_support25",.025),("c115_support45",.045),("c115_support70",.070)]:
        res[n]=evaluate(n,w,.035,0,root/"cycle115")
    d=choose(res,b);win=d["winner"] or "c115_support45";best=res[win]
    report["cycles"].append({"cycle":115,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    print("DECISION115",json.dumps(d,ensure_ascii=False),flush=True)
    for n,v in res.items():print("SUMMARY",n,json.dumps(v["summary"],ensure_ascii=False),flush=True)

    res={}
    for n,w in [("c116_kick20",.020),("c116_kick35",.035),("c116_kick55",.055)]:
        res[n]=evaluate(n,best["support_window"],w,0,root/"cycle116")
    d=choose(res,b);win=d["winner"] or next(iter(res));best=res[win]
    report["cycles"].append({"cycle":116,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    print("DECISION116",json.dumps(d,ensure_ascii=False),flush=True)
    for n,v in res.items():print("SUMMARY",n,json.dumps(v["summary"],ensure_ascii=False),flush=True)

    res={}
    for k in (2,3,4):
        n=f"c117_rescue{k}";res[n]=evaluate(n,best["support_window"],best["kick_window"],k,root/"cycle117")
    d=choose(res,b);win=d["winner"] or next(iter(res));best=res[win]
    report["cycles"].append({"cycle":117,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    print("DECISION117",json.dumps(d,ensure_ascii=False),flush=True)
    for n,v in res.items():print("SUMMARY",n,json.dumps(v["summary"],ensure_ascii=False),flush=True)

    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],"support_window":best["support_window"],"kick_window":best["kick_window"],"rescue_need":best["rescue_need"],"detailed":best["detailed"]}
    (EXP/"results-iterative-hat-kick-gate.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
