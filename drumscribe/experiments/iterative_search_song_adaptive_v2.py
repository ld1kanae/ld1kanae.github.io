"""Cycles 172-174: song-adaptive ADTOF/pedal routing.

Base: generated-search-adtof-components/cycle168/c168_kick_tom.

172: song-level pedal stream gate from detector agreement ratio.
173: switch hat operating point only when ADTOF precision is abnormally sparse
     relative to the legacy hat stream.
174: switch snare operating point only when ADTOF precision is abnormally sparse
     relative to the legacy snare stream.

chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util, json
from collections import Counter
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

repair=loadmod("repair",EXP/"iterative_search_overtrigger_repair.py")
ev=repair.ev; sel=repair.sel; detail=repair.detail; base=repair.base
SONGS=repair.SONGS; GROUPS=repair.GROUPS

BASE=EXP/"generated-search-adtof-components/cycle168/c168_kick_tom"
LEGACY=EXP/"generated-search-metal-reclass/cycle159/c159_crash_recall"
AD_RECALL=EXP/"generated-search-adtof/cycle163/c163_recall"
AD_DEFAULT=EXP/"generated-search-adtof/cycle163/c163_default"

PEDAL_RAW=EXP/"generated-search-fusion-v5/cycle129/c129_balanced"
PEDAL_RECALL=EXP/"generated-search-pedal-component/cycle64/c64_recall"

def rows(path,song):return repair.rows(path,song)
def meta(song):return repair.meta(song)

def replace_group(events,g,path,song):
    return [e for e in events if e[1]!=g]+[e for e in rows(path,song) if e[1]==g]

def pedal_gate(song,events,strong,sparse=.08):
    raw=[t for t,g in rows(PEDAL_RAW,song) if g=="pedal_hat"]
    rec=[t for t,g in rows(PEDAL_RECALL,song) if g=="pedal_hat"]
    ratio=len(raw)/max(1,len(rec))
    current=[t for t,g in events if g=="pedal_hat"]
    keep=(ratio>=strong or ratio<sparse)
    chosen=current if keep else []
    out=[e for e in events if e[1]!="pedal_hat"]+[(t,"pedal_hat") for t in chosen]
    return repair.enforce(out),{"raw":len(raw),"recall":len(rec),"ratio":ratio,"keep":keep,"chosen":len(chosen)}

def hat_adapt(song,events,mode,threshold):
    cur=[t for t,g in events if g=="hat"]
    old=[t for t,g in rows(LEGACY,song) if g=="hat"]
    ratio=len(cur)/max(1,len(old))
    chosen=list(cur);source="precision"
    if ratio<threshold:
        if mode=="recall":
            chosen=[t for t,g in rows(AD_RECALL,song) if g=="hat"];source="recall"
        elif mode=="default":
            chosen=[t for t,g in rows(AD_DEFAULT,song) if g=="hat"];source="default"
        elif mode=="legacy":
            chosen=old;source="legacy"
        elif mode=="union_recall":
            rr=[t for t,g in rows(AD_RECALL,song) if g=="hat"]
            chosen=sorted(set(round(x,5) for x in cur+rr));source="union_recall"
    out=[e for e in events if e[1]!="hat"]+[(t,"hat") for t in chosen]
    return repair.enforce(out),{"precision":len(cur),"legacy":len(old),"ratio":ratio,"source":source,"chosen":len(chosen)}

def snare_adapt(song,events,mode,threshold):
    cur=[t for t,g in events if g=="snare"]
    old=[t for t,g in rows(LEGACY,song) if g=="snare"]
    ratio=len(cur)/max(1,len(old))
    chosen=list(cur);source="precision"
    if ratio<threshold:
        if mode=="recall":
            chosen=[t for t,g in rows(AD_RECALL,song) if g=="snare"];source="recall"
        elif mode=="default":
            chosen=[t for t,g in rows(AD_DEFAULT,song) if g=="snare"];source="default"
    out=[e for e in events if e[1]!="snare"]+[(t,"snare") for t in chosen]
    return repair.enforce(out),{"precision":len(cur),"legacy":len(old),"ratio":ratio,"source":source,"chosen":len(chosen)}

def build(song,strong,hat_mode,hat_thr,snare_mode,snare_thr):
    e=rows(BASE,song)
    e,pdiag=pedal_gate(song,e,strong)
    e,hdiag=hat_adapt(song,e,hat_mode,hat_thr)
    e,sdiag=snare_adapt(song,e,snare_mode,snare_thr)
    return repair.enforce(e),{"pedal":pdiag,"hat":hdiag,"snare":sdiag}

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,strong,hat_mode,hat_thr,snare_mode,snare_thr,outdir):
    result={"strong":strong,"hat_mode":hat_mode,"hat_thr":hat_thr,"snare_mode":snare_mode,"snare_thr":snare_thr,"decisions":{},"songs":{}}
    tot=Counter()
    for song in SONGS:
        m=meta(song);events,diag=build(song,strong,hat_mode,hat_thr,snare_mode,snare_thr);result["decisions"][song]=diag
        p=outdir/name/f"{song}.mid";write(p,events,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,ref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":ref,"precision":tp/n if n else 0,"recall":tp/ref if ref else 0,
       "f1":2*tp/(n+ref) if n+ref else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,"false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s)
    return result

def choose(res,baseline,targets,maxdrop=.035,tol=.012):
    ranking=[];guards={}
    for n,o in res.items():
        gd=sel.eligibility(o["summary"],baseline["summary"],target_parts=targets,max_part_drop=maxdrop,target_tolerance=tol)
        o["guard"]=gd;guards[n]=gd;ranking.append((gd["eligible"],o["canonical_score"]["score"],o["summary"]["f1"],n))
    ranking.sort(reverse=True)
    return {"winner":next((n for ok,_,_,n in ranking if ok),None),"ranking":[x[3] for x in ranking],"guards":guards}

def main():
    root=EXP/"generated-search-song-adaptive-v2";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline",0.0,"precision",0.0,"precision",0.0,root/"baseline")

    res={}
    for name,strong in [("c172_base",0.0),("c172_gate43",.43),("c172_gate45",.45),("c172_gate55",.55),("c172_gate70",.70)]:
        res[name]=evaluate(name,strong,"precision",0.0,"precision",0.0,root/"cycle172")
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],"pedal":res[name]["summary"]["by_group"]["pedal_hat"],
          "decisions":{s:d["pedal"] for s,d in res[name]["decisions"].items()},"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline,("pedal_hat",),.04,.015);win=d["winner"] or "c172_base";best=res[win]
    report["cycles"].append({"cycle":172,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    cfg=[
      ("c173_base","precision",0.0),
      ("c173_recall45","recall",.45),
      ("c173_recall55","recall",.55),
      ("c173_default55","default",.55),
      ("c173_legacy55","legacy",.55),
    ]
    for name,mode,thr in cfg:
        res[name]=evaluate(name,best["strong"],mode,thr,"precision",0.0,root/"cycle173")
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],
          "decisions":{s:d["hat"] for s,d in res[name]["decisions"].items()},"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best,("hat",),.035,.015);win=d["winner"] or "c173_base";best=res[win]
    report["cycles"].append({"cycle":173,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    cfg=[
      ("c174_base","precision",0.0),
      ("c174_recall75","recall",.75),
      ("c174_recall80","recall",.80),
      ("c174_recall90","recall",.90),
      ("c174_default80","default",.80),
    ]
    for name,mode,thr in cfg:
        res[name]=evaluate(name,best["strong"],best["hat_mode"],best["hat_thr"],mode,thr,root/"cycle174")
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],"snare":res[name]["summary"]["by_group"]["snare"],
          "decisions":{s:d["snare"] for s,d in res[name]["decisions"].items()},"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best,("snare",),.03,.015);win=d["winner"] or "c174_base";best=res[win]
    report["cycles"].append({"cycle":174,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "strong":best["strong"],"hat_mode":best["hat_mode"],"hat_thr":best["hat_thr"],"snare_mode":best["snare_mode"],"snare_thr":best["snare_thr"],
      "decisions":best["decisions"],"detailed":detail.compare_dir(root/"cycle174"/win,win)["aggregate"]}
    (EXP/"results-iterative-song-adaptive-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
