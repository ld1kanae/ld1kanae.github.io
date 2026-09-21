"""Cycles 82-84: second-generation all-part fusion.

Combines the strongest recent independently validated components:
- hat: c75_repeat5 (or c69/c67 alternatives)
- snare: c66 veto (or c61 high-recall)
- crash: c72 precision/downbeat (or c71 recall)
- pedal hat: c77 periodic-75 (or alternatives)
Other parts are retained from the stable recent base.

Prediction fusion uses only previously generated audio-derived MIDI. chart.mid
is evaluation-only after writing each candidate.
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

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

STABLE=EXP/"generated-search-recall-repair/cycle63/c63_pedal_keep"
HAT={
 "precision":EXP/"generated-search-hat-precision/cycle75/c75_repeat5",
 "recall":EXP/"generated-search-hat-fusion/cycle69/c69_repeat3",
 "hi441":EXP/"generated-search-hat-fusion/cycle67/c67_hi441",
}
SNARE={
 "veto":EXP/"generated-search-snare-veto/cycle66/c66_repeat1",
 "consensus":EXP/"generated-search-recall-repair/cycle61/c61_snare_consensus",
 "pattern":EXP/"generated-search-recall-repair/cycle61/c61_snare_pattern",
}
CRASH={
 "precision":EXP/"generated-search-crash-consensus/cycle72/c72_head18",
 "recall":EXP/"generated-search-crash-consensus/cycle71/c71_crash",
 "base":STABLE,
}
PEDAL={
 "per75":EXP/"generated-search-pedal-repair/cycle77/c77_per75",
 "per50":EXP/"generated-search-pedal-repair/cycle77/c77_per50",
 "base":STABLE,
}

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

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
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def fuse(song,hat_src,snare_src,crash_src,pedal_src):
    b=rows(STABLE,song)
    out=[e for e in b if e[1] not in ("hat","snare","crash","pedal_hat")]
    out += [e for e in rows(HAT[hat_src],song) if e[1]=="hat"]
    out += [e for e in rows(SNARE[snare_src],song) if e[1]=="snare"]
    out += [e for e in rows(CRASH[crash_src],song) if e[1]=="crash"]
    out += [e for e in rows(PEDAL[pedal_src],song) if e[1]=="pedal_hat"]
    return enforce(out)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,hat_src,snare_src,crash_src,pedal_src,outdir):
    result={"hat_src":hat_src,"snare_src":snare_src,"crash_src":crash_src,"pedal_src":pedal_src,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=fuse(song,hat_src,snare_src,crash_src,pedal_src);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
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
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    ped=s["by_group"]["pedal_hat"]["f1"];hat_fdr=s["by_group"]["hat"]["false_discovery_rate"];crash_fdr=s["by_group"]["crash"]["false_discovery_rate"]
    # All-part selection: reward pedal/ride/crash quality explicitly; penalize
    # audible false hats/cymbals and kick->snare confusion.
    s["selection_score"]=round(
      s["f1"]+.18*sum(core)/len(core)+.08*ped+.06*s["by_group"]["crash"]["f1"]+.08*s["by_group"]["ride"]["f1"]
      -.30*ks-.06*hat_fdr-.04*crash_fdr,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-fusion-v2";report={"schema":1,"cycles":[]}
    res={}
    configs=[
      ("c82_robust","precision","veto","precision","per75"),
      ("c82_balanced","precision","consensus","recall","per75"),
      ("c82_recall","recall","pattern","recall","per50"),
    ]
    for name,h,s,c,p in configs:
        res[name]=evaluate(name,h,s,c,p,root/"cycle82");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":82,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,h in [("c83_hat_precision","precision"),("c83_hat_recall","recall"),("c83_hat_hi441","hi441")]:
        res[name]=evaluate(name,h,best["snare_src"],best["crash_src"],best["pedal_src"],root/"cycle83");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":83,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,p in [("c84_pedal_base","base"),("c84_pedal50","per50"),("c84_pedal75","per75")]:
        res[name]=evaluate(name,best["hat_src"],best["snare_src"],best["crash_src"],p,root/"cycle84");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":84,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"hat_src":res[win]["hat_src"],"snare_src":res[win]["snare_src"],"crash_src":res[win]["crash_src"],"pedal_src":res[win]["pedal_src"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-fusion-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
