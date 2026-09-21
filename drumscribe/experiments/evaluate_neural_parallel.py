"""Cycles 130-132: cached/parallel replica of neural separation search.

Consumes normalized per-song stems created in parallel by
prepare_neural_stem_song.py. The transcription/classification logic is imported
from iterative_search_neural_separation.py so this validates the same algorithm
without serially separating all five songs in one runner.

Cycle 130: DSP / MDX neural / ensemble separator front-end
Cycle 131: logistic / random forest / extra trees classifier
Cycle 132: precision / balanced / recall operating point
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

ns=loadmod("ns",EXP/"iterative_search_neural_separation.py")
sel=loadmod("sel",EXP/"selection_policy.py")
SONGS=ns.SONGS

def allsep(cache):
    cache=Path(cache);out={}
    for song in SONGS:
        b=cache/song
        dsp={k:b/"dsp"/f"{k}.flac" for k in ("kick","snare","tom","hat","cymbal")}
        mdx={k:b/"mdx"/f"{k}.flac" for k in ("kick","snare","tom","hat","ride","crash")}
        missing=[str(p) for p in [*dsp.values(),*mdx.values()] if not p.exists()]
        if missing:raise FileNotFoundError(missing)
        out[song]={"dsp":dsp,"mdx":mdx}
    return out

def choose(res):
    rows=[]
    for name,v in res.items():
        s=v["summary"];missing=[]
        for g,x in (s.get("by_group") or {}).items():
            if int(x.get("reference") or 0)>0 and int(x.get("predicted") or 0)==0:missing.append(g)
        v["canonical_score"]=sel.score(s);v["missing_parts"]=missing
        rows.append((not missing,v["canonical_score"]["score"],float(s.get("f1") or 0),name))
    rows.sort(reverse=True)
    win=next((name for ok,_,_,name in rows if ok),rows[0][3] if rows else None)
    return win,[x[3] for x in rows]

def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument("--cache",required=True);a=ap.parse_args()
    sep=allsep(a.cache)
    root=EXP/"generated-search-neural-parallel"
    report={"schema":1,"method":"parallel cached replica of neural source-separation search","cycles":[]}

    datasets={m:ns.build_method_dataset(sep,m) for m in ("dsp","mdx","ensemble")}
    thresholds=dict(ns.BASE_THR)
    baseprof={"rhythm":"moderate","crash_head_beats":.15,"ride_periodic":.55,"hat_strong":.82}

    res={}
    for method in ("dsp","mdx","ensemble"):
        name="c130_"+method
        res[name]=ns.evaluate_candidate(name,datasets[method],"extra",thresholds,baseprof,root/"cycle130")
        res[name]["separation_method"]=method
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    win,ranking=choose(res);best_method=res[win]["separation_method"]
    report["cycles"].append({"cycle":130,"candidates":res,"ranking":ranking,"winner":win})

    data=datasets[best_method];res={}
    for fam in ("logistic","rf","extra"):
        name="c131_"+fam
        res[name]=ns.evaluate_candidate(name,data,fam,thresholds,baseprof,root/"cycle131")
        res[name]["separation_method"]=best_method
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    win,ranking=choose(res);best_family=res[win]["family"]
    report["cycles"].append({"cycle":131,"candidates":res,"ranking":ranking,"winner":win})

    res={}
    configs=[
      ("c132_precision",1.10,{"rhythm":"strict","crash_head_beats":.12,"ride_periodic":.75,"hat_strong":.86}),
      ("c132_balanced",1.00,{"rhythm":"moderate","crash_head_beats":.15,"ride_periodic":.55,"hat_strong":.82}),
      ("c132_recall",.90,{"rhythm":"none","crash_head_beats":.18,"ride_periodic":.40,"hat_strong":.78}),
    ]
    for name,mult,prof in configs:
        th={g:min(.95,max(.25,v*mult)) for g,v in thresholds.items()}
        res[name]=ns.evaluate_candidate(name,data,best_family,th,prof,root/"cycle132")
        res[name]["separation_method"]=best_method
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    win,ranking=choose(res)
    report["cycles"].append({"cycle":132,"candidates":res,"ranking":ranking,"winner":win})
    w=res[win]
    report["final"]={"winner":win,"separation_method":best_method,"classifier":best_family,
      "summary":w["summary"],"canonical_score":w["canonical_score"],"missing_parts":w["missing_parts"],
      "thresholds":w["thresholds"],"profile":w["profile"],"detailed":w["detailed"]}
    (EXP/"results-iterative-neural-parallel.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
