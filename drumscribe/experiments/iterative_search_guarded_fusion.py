"""Cycles 109-111: guarded all-part fusion after tom and ride repairs.

Uses the canonical non-regression policy. A candidate cannot become the new
all-part base by deleting or substantially degrading a previously working part.

Cycle 109:
  A current fusion-v2 base
  B + improved tom
  C + song-gated ride
  D + improved tom + song-gated ride
Cycle 110:
  safe snare / high-recall snare / veto snare on the Cycle109 winner
Cycle 111:
  crash precision / recall / zero-fallback on the winner

All components are prior drums.mp3-derived MIDI predictions. chart.mid is used
only after each fused MIDI is written.
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
RIDE=EXP/"generated-search-ride-song-gate/cycle108/c108_per50"
SNARE_PATTERN=EXP/"generated-search-best-fusion/cycle80/c80_snare_pattern"
SNARE_VETO=EXP/"generated-search-snare-veto/cycle66/c66_repeat1"
CRASH_PREC=EXP/"generated-search-best-fusion/cycle79/c79_crash_precision"
CRASH_RECALL=EXP/"generated-search-best-fusion/cycle79/c79_crash_recall"
CRASH_ZERO=EXP/"generated-search-crash-fallback/cycle88/c88_zero_base"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def replace_group(events,g,src,song):
    if src is None:return events
    repl=[e for e in rows(src,song) if e[1]==g]
    return [e for e in events if e[1]!=g]+repl

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

def build(song,tom=False,ride=False,snare="base",crash="base"):
    e=rows(BASE,song)
    if tom:e=replace_group(e,"tom",TOM,song)
    if ride:e=replace_group(e,"ride",RIDE,song);e=replace_group(e,"hat",RIDE,song)
    if snare=="pattern":e=replace_group(e,"snare",SNARE_PATTERN,song)
    elif snare=="veto":e=replace_group(e,"snare",SNARE_VETO,song)
    if crash=="precision":e=replace_group(e,"crash",CRASH_PREC,song)
    elif crash=="recall":e=replace_group(e,"crash",CRASH_RECALL,song)
    elif crash=="zero":e=replace_group(e,"crash",CRASH_ZERO,song)
    return enforce(e)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,tom,ride,snare,crash,outdir):
    result={"tom":tom,"ride":ride,"snare":snare,"crash":crash,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=build(song,tom,ride,snare,crash);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
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
    result["summary"]=s
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"]
    result["canonical_score"]=sel.score(s)
    return result

def baseline_summary():
    # Evaluate the base in exactly the same fusion/evaluator path.
    return None

def choose(candidates,baseline,target_parts):
    decision=sel.select(candidates,baseline["summary"],target_parts=target_parts,max_part_drop=.05)
    for name,c in candidates.items():c["guard"]=decision["guards"][name]
    return decision

def main():
    root=EXP/"generated-search-guarded-fusion";report={"schema":1,"selection_policy":"selection_policy.py hard non-regression","cycles":[]}

    res={
      "c109_base":evaluate("c109_base",False,False,"base","base",root/"cycle109"),
      "c109_tom":evaluate("c109_tom",True,False,"base","base",root/"cycle109"),
      "c109_ride":evaluate("c109_ride",False,True,"base","base",root/"cycle109"),
      "c109_tom_ride":evaluate("c109_tom_ride",True,True,"base","base",root/"cycle109"),
    }
    basec=res["c109_base"];dec=choose(res,basec,("tom","ride"));win=dec["winner"] or "c109_base"
    print("DECISION109",json.dumps(dec,ensure_ascii=False),flush=True)
    for n,v in res.items():print("SUMMARY",n,json.dumps(v["summary"],ensure_ascii=False),flush=True)
    report["cycles"].append({"cycle":109,"candidates":res,"ranking":dec["ranking"],"winner":win,"guards":dec["guards"]});best=res[win]

    res={}
    for src in ("base","pattern","veto"):
        n=f"c110_snare_{src}";res[n]=evaluate(n,best["tom"],best["ride"],src,best["crash"],root/"cycle110")
    dec=choose(res,best,("snare",));win=dec["winner"] or next(iter(res))
    print("DECISION110",json.dumps(dec,ensure_ascii=False),flush=True)
    for n,v in res.items():print("SUMMARY",n,json.dumps(v["summary"],ensure_ascii=False),flush=True)
    report["cycles"].append({"cycle":110,"candidates":res,"ranking":dec["ranking"],"winner":win,"guards":dec["guards"]});best=res[win]

    res={}
    for src in ("precision","recall","zero"):
        n=f"c111_crash_{src}";res[n]=evaluate(n,best["tom"],best["ride"],best["snare"],src,root/"cycle111")
    dec=choose(res,best,("crash",));win=dec["winner"] or next(iter(res))
    print("DECISION111",json.dumps(dec,ensure_ascii=False),flush=True)
    for n,v in res.items():print("SUMMARY",n,json.dumps(v["summary"],ensure_ascii=False),flush=True)
    report["cycles"].append({"cycle":111,"candidates":res,"ranking":dec["ranking"],"winner":win,"guards":dec["guards"]});best=res[win]

    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],"tom":best["tom"],"ride":best["ride"],"snare":best["snare"],"crash":best["crash"],"detailed":best["detailed"]}
    (EXP/"results-iterative-guarded-fusion.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()

# trigger-after-tom-save-1

# rerun-selection-policy-fdr-1
