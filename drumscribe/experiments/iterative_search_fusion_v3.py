"""Cycles 118-120: fuse current strongest non-regressing components.

Cycle 118: base / +tom / +snare / +tom+snare
Cycle 119: no ride / song-gated ride / conservative consensus ride
Cycle 120: crash precision / recall / zero-fallback

Hard non-regression selection policy is mandatory.
"""
from __future__ import annotations
import importlib.util,json
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
TOM=EXP/"generated-search-tom-consensus/cycle105/c105_density7"
SNARE=EXP/"generated-search-snare-additive/cycle114/c114_repeat3"
RIDE_GATE=EXP/"generated-search-ride-song-gate/cycle108/c108_per50"
RIDE_CONS=EXP/"generated-search-ride-consensus/cycle102/c102_per25"
CRASH_PREC=EXP/"generated-search-best-fusion/cycle79/c79_crash_precision"
CRASH_REC=EXP/"generated-search-best-fusion/cycle79/c79_crash_recall"
CRASH_ZERO=EXP/"generated-search-crash-fallback/cycle88/c88_zero_base"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def replace(events,g,path,song):
    src=[e for e in rows(path,song) if e[1]==g]
    return [e for e in events if e[1]!=g]+src

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

def build(song,tom=False,snare=False,ride="off",crash="precision"):
    e=rows(BASE,song)
    if tom:e=replace(e,"tom",TOM,song)
    if snare:e=replace(e,"snare",SNARE,song)
    if ride=="gate":
        e=replace(e,"ride",RIDE_GATE,song);e=replace(e,"hat",RIDE_GATE,song)
    elif ride=="consensus":
        e=replace(e,"ride",RIDE_CONS,song);e=replace(e,"hat",RIDE_CONS,song)
    cp={"precision":CRASH_PREC,"recall":CRASH_REC,"zero":CRASH_ZERO}[crash]
    e=replace(e,"crash",cp,song)
    return enforce(e)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,tom,snare,ride,crash,outdir):
    result={"tom":tom,"snare":snare,"ride":ride,"crash":crash,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=build(song,tom,snare,ride,crash);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
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

def decision(res,baseline,targets):
    d=sel.select(res,baseline["summary"],target_parts=targets,max_part_drop=.05)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-fusion-v3";report={"schema":1,"selection_policy":"hard non-regression + canonical FDR score","cycles":[]}
    basec=evaluate("base",False,False,"off","precision",root/"base")

    res={
      "c118_base":evaluate("c118_base",False,False,"off","precision",root/"cycle118"),
      "c118_tom":evaluate("c118_tom",True,False,"off","precision",root/"cycle118"),
      "c118_snare":evaluate("c118_snare",False,True,"off","precision",root/"cycle118"),
      "c118_tom_snare":evaluate("c118_tom_snare",True,True,"off","precision",root/"cycle118"),
    }
    d=decision(res,basec,("tom","snare"));win=d["winner"] or "c118_base";best=res[win]
    report["cycles"].append({"cycle":118,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    print("DECISION118",json.dumps(d,ensure_ascii=False),flush=True)
    for n,v in res.items():print("SUMMARY",n,json.dumps(v["summary"],ensure_ascii=False),flush=True)

    res={}
    for ride in ("off","gate","consensus"):
        n=f"c119_ride_{ride}";res[n]=evaluate(n,best["tom"],best["snare"],ride,best["crash"],root/"cycle119")
    d=decision(res,best,("ride",));win=d["winner"] or "c119_ride_off";best=res[win]
    report["cycles"].append({"cycle":119,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    print("DECISION119",json.dumps(d,ensure_ascii=False),flush=True)
    for n,v in res.items():print("SUMMARY",n,json.dumps(v["summary"],ensure_ascii=False),flush=True)

    res={}
    for crash in ("precision","recall","zero"):
        n=f"c120_crash_{crash}";res[n]=evaluate(n,best["tom"],best["snare"],best["ride"],crash,root/"cycle120")
    d=decision(res,best,("crash",));win=d["winner"] or "c120_crash_precision";best=res[win]
    report["cycles"].append({"cycle":120,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    print("DECISION120",json.dumps(d,ensure_ascii=False),flush=True)
    for n,v in res.items():print("SUMMARY",n,json.dumps(v["summary"],ensure_ascii=False),flush=True)

    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],"tom":best["tom"],"snare":best["snare"],"ride":best["ride"],"crash":best["crash"],"detailed":best["detailed"]}
    (EXP/"results-iterative-fusion-v3.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
