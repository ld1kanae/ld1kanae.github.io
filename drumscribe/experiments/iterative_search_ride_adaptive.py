"""Cycles 115-117: adaptive ride mode selection per song.

Prediction uses only candidate MIDI derived from drums.mp3:
- tight ride seed stream (song-gate)
- expanded ride streams (radius4 / radius8 / older recall)
- balanced all-part base

If ride seed density is high, use the tight stream. If it is low but non-zero,
use an expanded stream. If zero, emit no ride. chart.mid is used only after the
candidate MIDI is written.

Cycle 115: seed-density switch threshold 0.015 / 0.030 / 0.060.
Cycle 116: low-confidence expansion source radius4 / radius8 / old recall.
Cycle 117: hat replacement window 30 / 50 / 80 ms.
"""
from __future__ import annotations
import importlib.util,json
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

BASE=EXP/"generated-search-tom-consensus/cycle105/c105_density7"
TIGHT=EXP/"generated-search-ride-song-gate/cycle108/c108_per50"
EXPANSIONS={
  "r4":EXP/"generated-search-ride-seed-expand/cycle109/c109_radius4",
  "r8":EXP/"generated-search-ride-seed-expand/cycle109/c109_radius8",
  "old":EXP/"generated-search-composite/cycle28/c28_ride_recall",
}

def rows(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]

def meta(song):
    return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def enforce(events):
    ded=[]
    mind={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.05,"tom":.05,"crash":.10,"ride":.045,"other":.04}
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mind.get(g,.04):ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0
    pri={"snare":.92,"tom":.86,"crash":.84,"ride":.82,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[x for x in c if x[1] not in HANDS];h=[x for x in c if x[1] in HANDS]
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def predict(song,ratio_thr,expansion,hat_window):
    b=rows(BASE,song)
    tight=[t for t,g in rows(TIGHT,song) if g=="ride"]
    exp=[t for t,g in rows(EXPANSIONS[expansion],song) if g=="ride"]
    hats=sum(1 for _,g in b if g=="hat")
    ratio=len(tight)/max(1,hats)

    if not tight:
        chosen=[]
        mode="off"
    elif ratio>=ratio_thr:
        chosen=tight
        mode="tight"
    else:
        chosen=exp
        mode="expand"

    events=[e for e in b if e[1]!="ride"]
    for t in chosen:
        events=[e for e in events if not(e[1]=="hat" and abs(e[0]-t)<=hat_window)]
        events.append((t,"ride"))
    return enforce(events),{"seed_count":len(tight),"hat_count":hats,"seed_ratio":ratio,"mode":mode,"ride_count":len(chosen)}

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,ratio_thr,expansion,hat_window,outdir):
    result={"ratio_threshold":ratio_thr,"expansion":expansion,"hat_window":hat_window,"song_decisions":{},"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr,decision=predict(song,ratio_thr,expansion,hat_window)
        result["song_decisions"][song]=decision
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]

    tp,n,mref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mref,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mref,4) if mref else 0,
       "f1":round(2*tp/(n+mref),4) if n+mref else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    parts=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];gf=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});r=x.get("reference",0)
            if r:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+r) if x.get("predicted",0)+r else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,
          "f1":round(gf,4),"count_ratio":round(b/c,4) if c else None,
          "mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):parts.append(gf)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"]
    s["selection_score"]=round(s["f1"]+.18*sum(parts)/len(parts)+.12*s["by_group"]["ride"]["f1"]+.05*ped-.25*ks,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-ride-adaptive";report={"schema":1,"cycles":[]}

    res={}
    for name,t in [("c115_ratio015",.015),("c115_ratio030",.030),("c115_ratio060",.060)]:
        res[name]=evaluate(name,t,"r8",.050,root/"cycle115");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":115,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,e in [("c116_radius4","r4"),("c116_radius8","r8"),("c116_oldrecall","old")]:
        res[name]=evaluate(name,best["ratio_threshold"],e,best["hat_window"],root/"cycle116");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":116,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,w in [("c117_hat30",.030),("c117_hat50",.050),("c117_hat80",.080)]:
        res[name]=evaluate(name,best["ratio_threshold"],best["expansion"],w,root/"cycle117");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":117,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"ratio_threshold":res[win]["ratio_threshold"],"expansion":res[win]["expansion"],"hat_window":res[win]["hat_window"],"song_decisions":res[win]["song_decisions"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-ride-adaptive.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
