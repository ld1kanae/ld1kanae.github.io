"""Materialize canonical full-detail metrics for current DrumScribe leaders."""
from __future__ import annotations
import importlib.util,json
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
spec=importlib.util.spec_from_file_location("detail",EXP/"detailed_metrics.py")
detail=importlib.util.module_from_spec(spec);spec.loader.exec_module(detail)

TARGETS={
  "fusion-v2-c84-pedal75":EXP/"generated-search-fusion-v2/cycle84/c84_pedal75",
  "hat-c75-repeat5":EXP/"generated-search-hat-precision/cycle75/c75_repeat5",
  "crash-c72-head18":EXP/"generated-search-crash-consensus/cycle72/c72_head18",
  "snare-c66-repeat1":EXP/"generated-search-snare-veto/cycle66/c66_repeat1",
  "pedal-c77-per75":EXP/"generated-search-pedal-repair/cycle77/c77_per75",
}
def main():
    outdir=EXP/"detailed-current";outdir.mkdir(parents=True,exist_ok=True)
    idx={"schema":1,"canonical_evaluator":"drumscribe/experiments/detailed_metrics.py","targets":[]}
    for name,p in TARGETS.items():
        obj=detail.compare_dir(p,name)
        dst=outdir/f"{name}.json";dst.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
        idx["targets"].append({"name":name,"pred_dir":str(p),"detail_file":str(dst),"aggregate":obj["aggregate"]})
        print(name,json.dumps(obj["aggregate"]["overall"],ensure_ascii=False),flush=True)
    (outdir/"index.json").write_text(json.dumps(idx,ensure_ascii=False,indent=2)+"\n")
if __name__=="__main__":main()
