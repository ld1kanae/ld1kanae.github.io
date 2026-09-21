"""Cycles 112-114: additive snare repair with strict kick veto.

Base = current all-part best fusion-v2.
High-recall snare source = c80_snare_pattern.
Only *new* snare hits absent from base are considered. Base snares are untouched.

Cycle 112: kick-veto windows 35 / 50 / 70 ms.
Cycle 113: require no extra support / DSP support / repeated-slot support.
Cycle 114: repeated-slot thresholds 1 / 2 / 3 bars.

Reference MIDI is used only after writing candidate MIDI.
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
PAT=EXP/"generated-search-best-fusion/cycle80/c80_snare_pattern"
DSP=EXP/"generated-search-drumsep-rate/cycle47/c47_precision"

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

def build(song,kick_window,support_mode,repeat_need):
    b=rows(BASE,song);base_sn=[t for t,g in b if g=="snare"];kicks=[t for t,g in b if g=="kick"]
    pat=[t for t,g in rows(PAT,song) if g=="snare"];dsp=[t for t,g in rows(DSP,song) if g=="snare"]
    ph,bar=phase(b,meta(song));pool=sorted(base_sn+pat)
    add=[]
    for t in pat:
        if near(base_sn,t,.040):continue
        # Strict rule: supplements never create a snare on a base kick.
        if near(kicks,t,kick_window):continue
        if support_mode=="none":keep=True
        elif support_mode=="dsp":keep=near(dsp,t,.060)
        else:keep=repeat_support(pool,t,ph,bar)>=repeat_need
        if keep:add.append((t,"snare"))
    return enforce(b+add)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,kick_window,support_mode,repeat_need,outdir):
    result={"kick_window":kick_window,"support_mode":support_mode,"repeat_need":repeat_need,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=build(song,kick_window,support_mode,repeat_need);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
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
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":f,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];result["canonical_score"]=sel.score(s)
    return result

def select(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("snare",),max_part_drop=.05)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-snare-additive";report={"schema":1,"cycles":[]}
    base_eval=evaluate("baseline",.050,"dsp",2,root/"baseline")
    # overwrite baseline with exact base MIDI evaluation by using a huge veto so no supplements
    # then explicitly use fusion-v2 metrics through this path with support impossible.
    base_eval=evaluate("baseline",10.0,"none",99,root/"baseline")

    res={}
    for n,w in [("c112_veto35",.035),("c112_veto50",.050),("c112_veto70",.070)]:
        res[n]=evaluate(n,w,"none",1,root/"cycle112")
    dec=select(res,base_eval);win=dec["winner"] or "c112_veto50";best=res[win]
    report["cycles"].append({"cycle":112,"candidates":res,"ranking":dec["ranking"],"winner":win,"guards":dec["guards"]})
    print("DECISION112",json.dumps(dec,ensure_ascii=False),flush=True)
    for n,v in res.items():print("SUMMARY",n,json.dumps(v["summary"],ensure_ascii=False),flush=True)

    res={}
    for mode in ("none","dsp","repeat"):
        n=f"c113_{mode}";res[n]=evaluate(n,best["kick_window"],mode,2,root/"cycle113")
    dec=select(res,base_eval);win=dec["winner"] or next(iter(res));best=res[win]
    report["cycles"].append({"cycle":113,"candidates":res,"ranking":dec["ranking"],"winner":win,"guards":dec["guards"]})
    print("DECISION113",json.dumps(dec,ensure_ascii=False),flush=True)
    for n,v in res.items():print("SUMMARY",n,json.dumps(v["summary"],ensure_ascii=False),flush=True)

    res={}
    for k in (1,2,3):
        n=f"c114_repeat{k}";res[n]=evaluate(n,best["kick_window"],"repeat",k,root/"cycle114")
    dec=select(res,base_eval);win=dec["winner"] or next(iter(res));best=res[win]
    report["cycles"].append({"cycle":114,"candidates":res,"ranking":dec["ranking"],"winner":win,"guards":dec["guards"]})
    print("DECISION114",json.dumps(dec,ensure_ascii=False),flush=True)
    for n,v in res.items():print("SUMMARY",n,json.dumps(v["summary"],ensure_ascii=False),flush=True)

    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],"kick_window":best["kick_window"],"support_mode":best["support_mode"],"repeat_need":best["repeat_need"],"detailed":best["detailed"]}
    (EXP/"results-iterative-snare-additive.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
