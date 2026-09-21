"""Cycles 85-87: cross-stem hi-hat bleed suppression.

True WAV separation is rerun for all five songs. Hi-hat onsets are detected on
the separated hihat stem, then compared against simultaneous kick/snare stem
onset strength. This directly tests whether cross-stem bleed explains excess
hat notes (notably arcaround).

The recent all-part fusion is used for non-hat parts. chart.mid is evaluation
only after each output MIDI is written.
"""
from __future__ import annotations
import importlib.util,json,tempfile
from collections import Counter
from pathlib import Path
from drumsep import separate

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")
rate=loadmod("rate",EXP/"iterative_search_drumsep_rate.py")

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}
BASE=EXP/"generated-search-fusion-v2/cycle84/c84_pedal75"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def stem_path(result,key):
    aliases={"kick":["kick"],"snare":["snare"],"tom":["tom"],"hat":["hihat","hat"],"cymbal":["cymbal"]}[key]
    for k,v in (getattr(result,"stems",{}) or {}).items():
        if any(a in str(k).lower() for a in aliases):return Path(v)
    raise KeyError((key,getattr(result,"stems",{})))

def prepare(tmp):
    out={}
    for song in SONGS:
        od=tmp/song;od.mkdir(parents=True)
        print("SEPARATE",song,flush=True)
        r=separate(str(ROOT/"DruMaster/songs"/song/"drums.mp3"),output_dir=str(od),enhanced=True)
        out[song]={k:stem_path(r,k) for k in ("kick","snare","tom","hat","cymbal")}
    return out

def periodic(times,t,bpm):
    if len(times)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(any(abs(x-(t+k*step))<=.06 for x in times) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def hat_candidates(stems,m,gate_k,gate_s,rescue,hat_thr):
    sig,hops=rate.signals(stems,44100)
    pp=rate.peaks(sig["hat"],hat_thr,.040,44100,hops["hat"])
    times=[fr*hops["hat"]/44100 for fr in pp]
    bpm=float(m["bpm"]);chosen=[]
    for fr,t in zip(pp,times):
        # Signals are song-normalized onset strengths per separated stem.
        h=float(sig["hat"][fr])
        k=float(sig["kick"][min(fr,len(sig["kick"])-1)])
        s=float(sig["snare"][min(fr,len(sig["snare"])-1)])
        ok=h>=gate_k*k and h>=gate_s*s
        if not ok and rescue>0 and periodic(times,t,bpm)>=rescue:ok=True
        if ok:chosen.append(t)
    return chosen

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

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,allstems,gate_k,gate_s,rescue,hat_thr,outdir):
    result={"gate_k":gate_k,"gate_s":gate_s,"rescue":rescue,"hat_thr":hat_thr,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);b=rows(BASE,song)
        hs=hat_candidates(allstems[song],m,gate_k,gate_s,rescue,hat_thr)
        rr=enforce([e for e in b if e[1]!="hat"]+[(t,"hat") for t in hs])
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
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
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"];hat_fdr=s["by_group"]["hat"]["false_discovery_rate"];crash_fdr=s["by_group"]["crash"]["false_discovery_rate"]
    s["selection_score"]=round(s["f1"]+.18*sum(core)/len(core)+.08*ped-.30*ks-.09*hat_fdr-.04*crash_fdr,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-crossstem-hat";report={"schema":1,"cycles":[]}
    with tempfile.TemporaryDirectory(prefix="crossstem-") as td:
        allstems=prepare(Path(td))
        res={}
        for name,gk,gs in [("c85_loose",.70,.60),("c85_balanced",1.00,.80),("c85_strict",1.25,1.00)]:
            res[name]=evaluate(name,allstems,gk,gs,0,.30,root/"cycle85");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
        rr=rank(res);win=rr[0][0];best=res[win]
        report["cycles"].append({"cycle":85,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

        res={}
        for name,q in [("c86_no_rescue",0),("c86_rescue50",.50),("c86_rescue75",.75)]:
            res[name]=evaluate(name,allstems,best["gate_k"],best["gate_s"],q,best["hat_thr"],root/"cycle86");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
        rr=rank(res);win=rr[0][0];best=res[win]
        report["cycles"].append({"cycle":86,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

        res={}
        for name,t in [("c87_thr24",.24),("c87_thr30",.30),("c87_thr36",.36)]:
            res[name]=evaluate(name,allstems,best["gate_k"],best["gate_s"],best["rescue"],t,root/"cycle87");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
        rr=rank(res);win=rr[0][0]
        report["cycles"].append({"cycle":87,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
        report["final"]={"winner":win,"summary":res[win]["summary"],"gate_k":res[win]["gate_k"],"gate_s":res[win]["gate_s"],"rescue":res[win]["rescue"],"hat_thr":res[win]["hat_thr"],"detailed":res[win]["detailed"]}
        (EXP/"results-iterative-crossstem-hat.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
