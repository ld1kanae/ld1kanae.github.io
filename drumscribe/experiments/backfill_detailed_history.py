"""Backfill canonical detailed metrics for every generated DrumScribe candidate.

Discovers every directory under drumscribe/experiments/generated* that contains
all five candidate MIDI files, re-parses those real MIDI files, and scores them
against chart.mid with the current canonical evaluator.

Writes one small JSON per candidate plus a compact index. This keeps the history
Git-friendly while preserving full song x part metrics for every reproducible
candidate.
"""
from __future__ import annotations
import importlib.util, json, re, shutil
from pathlib import Path

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"
OUT=EXP/"detailed-history"

spec=importlib.util.spec_from_file_location("detail",EXP/"detailed_metrics.py")
detail=importlib.util.module_from_spec(spec);spec.loader.exec_module(detail)

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

def candidate_dirs():
    seen=set()
    for top in sorted(EXP.glob("generated*")):
        if not top.is_dir():continue
        for p in [top,*[x for x in top.rglob("*") if x.is_dir()]]:
            if p in seen:continue
            seen.add(p)
            if all((p/f"{s}.mid").exists() for s in SONGS):
                yield p

def safe_rel(p):
    rel=p.relative_to(EXP)
    return Path(*[re.sub(r"[^A-Za-z0-9._-]+","_",x) for x in rel.parts])

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    index={"schema":1,"canonical_evaluator":"drumscribe/experiments/detailed_metrics.py","candidates":[]}
    count=0
    for p in candidate_dirs():
        name=str(p.relative_to(EXP))
        print("DETAIL",name,flush=True)
        obj=detail.compare_dir(p,name)
        target=OUT/safe_rel(p)
        target=target.parent/(target.name+".json")
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
        agg=obj["aggregate"]
        index["candidates"].append({
          "name":name,
          "pred_dir":str(p),
          "detail_file":str(target),
          "overall":agg["overall"],
          "by_group":agg["by_group"],
          "families":agg["families"],
        })
        count+=1
    index["candidate_count"]=count
    (OUT/"index.json").write_text(json.dumps(index,ensure_ascii=False,indent=2)+"\n")
    print("CANDIDATES",count,flush=True)

if __name__=="__main__":main()
