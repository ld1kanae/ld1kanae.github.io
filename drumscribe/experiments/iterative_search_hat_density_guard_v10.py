"""Cycles 222-224: density guard for the nested 44.1-kHz hat suppressor.

Cycle 221 reduces false hi-hats but hurts a low-density song. This experiment
uses only current prediction density (hat/kick ratio) to decide where the
held-out nested classifier is allowed to suppress hats.

Prediction inputs never use the target chart. chart.mid is scoring-only.
222: whole-song guard thresholds 0.45 / 0.55 / 0.65.
223: local 8-bar guard thresholds 0.45 / 0.55 / 0.65.
224: local block sizes 4 / 8 / 16 bars at the best local threshold.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
BASE=EXP/"generated-search-best-merge-v8/cycle216/c216_both"
FILTER=EXP/"generated-search-hat-nested-fusion-v9/cycle221/c221_rep100_w60"
BROWSER=EXP/"generated-v2-browser"

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
base=loadmod("base",EXP/"iterative_search.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
sel=loadmod("sel",EXP/"selection_policy.py")
cf=loadmod("cf",EXP/"iterative_search_browser_component_fusion.py")

def rows(path,s):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{s}.mid")]
def side(s):return json.loads((BROWSER/f"{s}.json").read_text())
def meta(s):return json.loads((ROOT/"DruMaster/songs"/s/"song.json").read_text())
def near(xs,t,w=.060):return any(abs(x-t)<=w for x in xs)

def whole(song,thr):
    b=rows(BASE,song);f=rows(FILTER,song)
    bh=sorted(t for t,g in b if g=="hat");bk=sorted(t for t,g in b if g=="kick")
    fh=sorted(t for t,g in f if g=="hat")
    ratio=len(bh)/max(1,len(bk));active=ratio>=thr
    hats=fh if active else bh
    out=cf.enforce([x for x in b if x[1]!="hat"]+[(t,"hat") for t in hats])
    return out,{"ratio":ratio,"filtered":active,"baseHat":len(bh),"filterHat":len(fh)}

def local(song,thr,bars_per):
    b=rows(BASE,song);f=rows(FILTER,song);sd=side(song)
    bpm=float(sd["bpm"]);phase=float(sd["barPhaseSec"]);bar=4*60/bpm
    bh=sorted(t for t,g in b if g=="hat");bk=sorted(t for t,g in b if g=="kick")
    fh=sorted(t for t,g in f if g=="hat")
    blocks=defaultdict(lambda:{"h":[],"k":[]})
    def block(t):return math.floor(((t-phase)/bar)/bars_per)
    for t in bh:blocks[block(t)]["h"].append(t)
    for t in bk:blocks[block(t)]["k"].append(t)
    active={q:len(z["h"])/max(1,len(z["k"]))>=thr for q,z in blocks.items()}
    keep=[]
    for t in bh:
        q=block(t)
        if not active.get(q,False) or near(fh,t,.060):keep.append(t)
    out=cf.enforce([x for x in b if x[1]!="hat"]+[(t,"hat") for t in keep])
    diag={str(q):{"ratio":len(z["h"])/max(1,len(z["k"])),"filtered":active[q],
                  "hat":len(z["h"]),"kick":len(z["k"])} for q,z in blocks.items()}
    return out,{"barsPer":bars_per,"blocks":diag}

def write(path,rr,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in rr],bpm)

def build(song,mode,thr,bars_per):
    if mode=="base":return rows(BASE,song),{"filtered":False}
    return whole(song,thr) if mode=="whole" else local(song,thr,bars_per)

def evaluate(name,mode,thr,bars_per,outdir):
    result={"mode":mode,"threshold":thr,"bars_per":bars_per,"songs":{},"diagnostic":{}}
    tot=Counter()
    for s in SONGS:
        rr,diag=build(s,mode,thr,bars_per);result["diagnostic"][s]=diag
        m=meta(s);p=outdir/name/f"{s}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/s/"chart.mid")
        sh=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
        sc=ev.score(pred,truth,sh);conf=ev.confusion(pred,truth,sh)
        sc["confusion"]=conf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][s]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=conf["kick_to_snare"],snare_to_kick=conf["snare_to_kick"])
        for g,z in sc["by_group"].items():
            tot[f"{g}_tp"]+=z["tp"];tot[f"{g}_pred"]+=z["predicted"];tot[f"{g}_ref"]+=z["reference"]
    tp,n,r=tot["tp"],tot["predicted"],tot["reference"]
    sm={"tp":tp,"predicted":n,"reference":r,"precision":tp/n if n else 0,
        "recall":tp/r if r else 0,"f1":2*tp/(n+r) if n+r else 0,
        "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
        "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for s in SONGS:
            z=result["songs"][s]["by_group"].get(g,{})
            if z.get("reference",0):
                sf.append(2*z.get("tp",0)/(z.get("predicted",0)+z["reference"])
                          if z.get("predicted",0)+z["reference"] else 0)
        sm["by_group"][g]={"tp":a,"predicted":b,"reference":c,
            "precision":a/b if b else 0,"recall":a/c if c else 0,
            "f1":2*a/(b+c) if b+c else 0,
            "false_discovery_rate":(b-a)/b if b else 0,
            "miss_rate":(c-a)/c if c else 0,
            "count_ratio":b/c if c else None,
            "mean_song_f1":sum(sf)/len(sf) if sf else None,
            "worst_song_f1":min(sf) if sf else None}
    result["summary"]=sm;result["canonical_score"]=sel.score(sm)
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"]
    return result

def choose(cands,baseline):
    d=sel.select(cands,baseline["summary"],target_parts=("hat",),
                 max_part_drop=.006,target_tolerance=.004)
    for n in cands:cands[n]["guard"]=d["guards"][n]
    return d

def brief(x):
    h=x["summary"]["by_group"]["hat"]
    return {"f1":x["summary"]["f1"],"hat_f1":h["f1"],"hat_p":h["precision"],
            "hat_r":h["recall"],"hat_fdr":h["false_discovery_rate"],
            "hat_worst":h["worst_song_f1"],"score":x["canonical_score"]["score"]}

def main():
    root=EXP/"generated-search-hat-density-guard-v10";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline","base",99,8,root/"baseline")
    print("BASE",json.dumps(brief(baseline),ensure_ascii=False),flush=True)

    c222={"c222_base":baseline}
    for n,t in [("c222_r045",.45),("c222_r055",.55),("c222_r065",.65)]:
        c222[n]=evaluate(n,"whole",t,8,root/"cycle222")
        print("SUMMARY",n,json.dumps({"metrics":brief(c222[n]),"diag":c222[n]["diagnostic"]},ensure_ascii=False),flush=True)
    d=choose(c222,baseline);w222=d["winner"] or "c222_base";b222=c222[w222]
    report["cycles"].append({"cycle":222,"candidates":c222,"winner":w222,
                             "ranking":d["ranking"],"guards":d["guards"]})

    c223={"c223_whole_best":b222}
    for n,t in [("c223_l045",.45),("c223_l055",.55),("c223_l065",.65)]:
        c223[n]=evaluate(n,"local",t,8,root/"cycle223")
        print("SUMMARY",n,json.dumps(brief(c223[n]),ensure_ascii=False),flush=True)
    d=choose(c223,b222);w223=d["winner"] or "c223_whole_best";b223=c223[w223]
    report["cycles"].append({"cycle":223,"candidates":c223,"winner":w223,
                             "ranking":d["ranking"],"guards":d["guards"]})

    # Search block size around the best local threshold. If whole-song remains
    # best, use 0.55 as the neutral low-density guard for this diagnostic cycle.
    thr=b223["threshold"] if b223["mode"]=="local" else .55
    c224={"c224_prev_best":b223}
    for n,bars in [("c224_b4",4),("c224_b8",8),("c224_b16",16)]:
        c224[n]=evaluate(n,"local",thr,bars,root/"cycle224")
        print("SUMMARY",n,json.dumps(brief(c224[n]),ensure_ascii=False),flush=True)
    d=choose(c224,b223);w224=d["winner"] or "c224_prev_best";b224=c224[w224]
    report["cycles"].append({"cycle":224,"candidates":c224,"winner":w224,
                             "ranking":d["ranking"],"guards":d["guards"]})

    best=max([baseline,b222,b223,b224],key=lambda x:x["canonical_score"]["score"])
    report["baseline"]=baseline
    report["final"]={"summary":best["summary"],"canonical_score":best["canonical_score"],
                     "mode":best["mode"],"threshold":best["threshold"],
                     "bars_per":best["bars_per"],"diagnostic":best["diagnostic"],
                     "detailed":best["detailed"]}
    (EXP/"results-iterative-hat-density-guard-v10.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps({"config":{"mode":best["mode"],"threshold":best["threshold"],
        "bars_per":best["bars_per"]},"metrics":brief(best)},ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
