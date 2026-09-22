"""Cycles 181-183: refine the song-level activation threshold for hat bleed suppression.

Base behavior is c177_periodic. The key diagnostic is the predicted conflict
fraction (hat events near kick/snare), not chart.mid. We search the threshold
that decides which songs receive the aggressive hat filter.
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

a=loadmod("adaptive",EXP/"iterative_search_adaptive_refine.py")
detail=a.detail

def choose(res,baseline):
    return a.choose(res,baseline,("hat",),.025,.015)

def main():
    root=EXP/"generated-search-hat-gate-refine";report={"schema":1,"cycles":[]}
    baseline=a.evaluate("baseline","strict","very_strict",.20,"vote3_periodic",root/"baseline")

    res={}
    for gate in (.30,.33,.34,.35,.38,.40,.45,.50,.60):
        name="c181_g"+str(int(round(gate*100)))
        res[name]=a.evaluate(name,"strict","very_strict",gate,"vote3_periodic",root/"cycle181")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],
          "k2h":res[name]["summary"]["kick_to_hat"],"s2h":res[name]["summary"]["snare_to_hat"],
          "diag":res[name]["diagnostics"],"score":res[name]["selection_score"]},ensure_ascii=False),flush=True)
    d=choose(res,baseline);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":181,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    res={}
    for mode in ("loose","balanced","strict","very_strict"):
        name="c182_"+mode
        res[name]=a.evaluate(name,"strict",mode,best["hat_gate"],"vote3_periodic",root/"cycle182")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],
          "k2h":res[name]["summary"]["kick_to_hat"],"s2h":res[name]["summary"]["snare_to_hat"],
          "score":res[name]["selection_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":182,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})

    center=float(best["hat_gate"])
    gates=sorted(set(max(.20,min(.75,round(center+x,3))) for x in (-.04,-.02,-.01,0,.01,.02,.04)))
    res={}
    for gate in gates:
        name="c183_g"+str(int(round(gate*1000)))
        res[name]=a.evaluate(name,best["metal_mode"],best["hat_mode"],gate,best["pedal_mode"],root/"cycle183")
        print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],
          "k2h":res[name]["summary"]["kick_to_hat"],"s2h":res[name]["summary"]["snare_to_hat"],
          "score":res[name]["selection_score"]},ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":183,"candidates":res,"winner":win,"ranking":d["ranking"],"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"selection_score":best["selection_score"],
      "guard":best["guard"],"metal_mode":best["metal_mode"],"hat_mode":best["hat_mode"],"hat_gate":best["hat_gate"],"pedal_mode":best["pedal_mode"],
      "diagnostics":best["diagnostics"],"detailed":detail.compare_dir(root/"cycle183"/win,win)["aggregate"]}
    (EXP/"results-iterative-hat-gate-refine.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
