"""Cycles 106-108: song-gated ride recovery.

The 44.1kHz logistic detector has useful ride recall on diamondvirgin/kaiju but
large false positives on ray/arcaround. Independent-detector agreement is used
as an audio-prediction-only song confidence gate.

Definitions:
  highres = c86_logistic ride predictions
  consensus = c102_per25 intersection predictions
  confidence = consensus_count / max(1, highres_count)

No chart information is used by the gate or fusion.

Cycle 106: song confidence thresholds
Cycle 107: locality around consensus-supported ride hits
Cycle 108: periodic support thresholds
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

BASE=EXP/"generated-search-fusion-v2/cycle84/c84_pedal75"
HI=EXP/"generated-search-ride-hires/cycle86/c86_logistic"
CONS=EXP/"generated-search-ride-consensus/cycle102/c102_per25"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def periodic(times,t,bpm):
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.065 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def confidence(song):
    hi=[t for t,g in rows(HI,song) if g=="ride"]
    co=[t for t,g in rows(CONS,song) if g=="ride"]
    return len(co)/max(1,len(hi)),hi,co

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

def build(song,ratio_thr,local_beats,per_thr):
    b=rows(BASE,song);ratio,hi,co=confidence(song)
    if ratio<ratio_thr:
        return b
    bpm=float(meta(song)["bpm"]);beat=60/bpm
    selected=[]
    for t in hi:
        if local_beats is not None and not any(abs(t-x)<=local_beats*beat for x in co):
            continue
        if per_thr>0 and periodic(hi,t,bpm)<per_thr:
            continue
        selected.append(t)
    # Convert nearest base hat into ride. Do not invent a new metal hit unless
    # the highres source already had a corresponding base hat conversion.
    out=[e for e in b if e[1]!="ride"];hats=[t for t,g in out if g=="hat"]
    for t in selected:
        hs=[x for x in hats if abs(x-t)<=.060]
        if not hs:continue
        h=min(hs,key=lambda x:abs(x-t))
        out=[e for e in out if not(e[1]=="hat" and abs(e[0]-h)<=1e-6)]
        hats=[x for x in hats if abs(x-h)>1e-6]
        out.append((h,"ride"))
    return enforce(out)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,ratio_thr,local_beats,per_thr,outdir):
    result={"ratio_threshold":ratio_thr,"local_beats":local_beats,"periodic_threshold":per_thr,"song_confidence":{},"songs":{}};tot=Counter()
    for song in SONGS:
        ratio,_,_=confidence(song);result["song_confidence"][song]=round(ratio,6)
        m=meta(song);rr=build(song,ratio_thr,local_beats,per_thr);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
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
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"];ride=s["by_group"]["ride"]["f1"]
    s["selection_score"]=round(s["f1"]+.18*sum(core)/len(core)+.16*ride+.05*ped-.30*ks,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-ride-song-gate";report={"schema":1,"cycles":[]}
    res={}
    for name,q in [("c106_ratio015",.015),("c106_ratio025",.025),("c106_ratio040",.040)]:
        res[name]=evaluate(name,q,None,0,root/"cycle106");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":106,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,b in [("c107_local1",1),("c107_local2",2),("c107_local4",4)]:
        res[name]=evaluate(name,best["ratio_threshold"],b,best["periodic_threshold"],root/"cycle107");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":107,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,p in [("c108_per25",.25),("c108_per50",.50),("c108_per75",.75)]:
        res[name]=evaluate(name,best["ratio_threshold"],best["local_beats"],p,root/"cycle108");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":108,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"ratio_threshold":res[win]["ratio_threshold"],"local_beats":res[win]["local_beats"],"periodic_threshold":res[win]["periodic_threshold"],"song_confidence":res[win]["song_confidence"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-ride-song-gate.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
