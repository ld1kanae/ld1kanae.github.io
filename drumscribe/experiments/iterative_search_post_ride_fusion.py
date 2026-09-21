"""Cycles 88-90: post-ride all-part fusion.

Prerequisite: results-iterative-ride-hires.json.
Uses the ride winner as the base, then re-optimizes crash, snare, pedal-hat
with previously validated component sources. No chart information is used
during fusion; chart.mid is only used after writing candidate MIDI.

Cycle 88: crash precision / recall / base
Cycle 89: snare base / high-recall / veto
Cycle 90: pedal per75 / per50 / base
"""
from __future__ import annotations
import importlib.util, json
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

CRASH={
 "base":None,
 "precision":EXP/"generated-search-best-fusion/cycle79/c79_crash_precision",
 "recall":EXP/"generated-search-best-fusion/cycle79/c79_crash_recall",
}
SNARE={
 "base":None,
 "pattern":EXP/"generated-search-best-fusion/cycle80/c80_snare_pattern",
 "veto":EXP/"generated-search-snare-veto/cycle66/c66_repeat1",
}
PEDAL={
 "base":None,
 "per75":EXP/"generated-search-pedal-repair/cycle77/c77_per75",
 "per50":EXP/"generated-search-pedal-repair/cycle77/c77_per50",
}

def winner_dir():
    o=json.loads((EXP/"results-iterative-ride-hires.json").read_text());w=o["final"]["winner"]
    return EXP/"generated-search-ride-hires"/"cycle87"/w,w

def rows(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]

def component(path,song,g):
    if path is None:return None
    return [(t,gg) for t,gg in rows(path,song) if gg==g]

def replace_group(events,g,source):
    if source is None:return events
    return [e for e in events if e[1]!=g]+source

def enforce(events):
    ded=[]
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.05,"tom":.05,"crash":.09,"ride":.04}
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0;pri={"snare":.92,"tom":.86,"crash":.84,"ride":.82,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[x for x in c if x[1] not in HANDS];h=[x for x in c if x[1] in HANDS]
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def build(song,basedir,crash_src,snare_src,pedal_src):
    e=rows(basedir,song)
    if crash_src!="base":e=replace_group(e,"crash",component(CRASH[crash_src],song,"crash"))
    if snare_src!="base":e=replace_group(e,"snare",component(SNARE[snare_src],song,"snare"))
    if pedal_src!="base":e=replace_group(e,"pedal_hat",component(PEDAL[pedal_src],song,"pedal_hat"))
    return enforce(e)

def evaluate(name,basedir,crash_src,snare_src,pedal_src,outdir):
    result={"base":str(basedir),"crash_src":crash_src,"snare_src":snare_src,"pedal_src":pedal_src,"songs":{}};tot=Counter()
    for song in SONGS:
        m=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        e=build(song,basedir,crash_src,snare_src,pedal_src)
        p=outdir/name/f"{song}.mid";write(p,e,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mr,4) if mr else 0,
       "f1":round(2*tp/(n+mr),4) if n+mr else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    core=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});r=x.get("reference",0)
            if r:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+r) if x.get("predicted",0)+r else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,
          "f1":round(f,4),"count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):core.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"]
    s["selection_score"]=round(s["f1"]+.18*sum(core)/len(core)+.08*s["by_group"]["ride"]["f1"]+.06*ped-.30*ks,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    bd,bn=winner_dir();root=EXP/"generated-search-post-ride-fusion";report={"schema":1,"ride_base":bn,"cycles":[]}
    res={}
    for src in ("base","precision","recall"):
        name=f"c88_crash_{src}";res[name]=evaluate(name,bd,src,"base","base",root/"cycle88");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":88,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for src in ("base","pattern","veto"):
        name=f"c89_snare_{src}";res[name]=evaluate(name,bd,best["crash_src"],src,"base",root/"cycle89");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":89,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for src in ("base","per75","per50"):
        name=f"c90_pedal_{src}";res[name]=evaluate(name,bd,best["crash_src"],best["snare_src"],src,root/"cycle90");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":90,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"crash_src":res[win]["crash_src"],"snare_src":res[win]["snare_src"],"pedal_src":res[win]["pedal_src"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-post-ride-fusion.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
