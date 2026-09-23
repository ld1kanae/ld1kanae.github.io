from __future__ import annotations
import importlib.util,json
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
OUT=EXP/"results-arrangement-egmd-portable-v46.json"
MD=EXP/"ARRANGEMENT_EGMD_PORTABLE_V46.md"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("v44",EXP/"evaluate_arrangement_egmd_fusion_v44.py")
v44=importlib.util.module_from_spec(spec);spec.loader.exec_module(v44)

RULES={
  "R1_p93_conf55_lift165":{"p":.93,"c":.55,"l":1.65},
  "R2_p95_conf55_lift165":{"p":.95,"c":.55,"l":1.65},
  "R3_p93_conf70_lift165":{"p":.93,"c":.70,"l":1.65},
}

def k(r):return (r["song"],r["group"],round(float(r["time"]),3))
def select_rule(rows,song,rule,fixed_keys):
    out=[]
    for r in rows:
        if r["song"]!=song or r["group"]!="snare" or k(r) in fixed_keys:continue
        if r["egmd_probability"]<rule["p"] or r["confidence"]<rule["c"] or r["gmd_lift"]<rule["l"]:continue
        out.append((r,r["egmd_probability"]+.1*r["gmd_lift"]))
    return v44.dedupe(out)

def main():
    data=json.loads((EXP/"results-arrangement-kst-candidates-v44.json").read_text())
    prior=json.loads((ROOT/"drumscribe/models/gmd-kst/slot-prior-v1.json").read_text())
    truth={}
    for s in SONGS:
        meta=json.loads((ROOT/"DruMaster"/"songs"/s/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        truth[s]=v44.parse_midi(ROOT/"DruMaster"/"songs"/s/"chart.mid",shift)
    rows,base=v44.build_rows(data,prior,truth)
    baseline=v44.merge_scores([v44.score(base[s],truth[s]) for s in SONGS])
    fixed={s:v44.fixed_v39(rows,s) for s in SONGS}
    fixed_keys={k(r) for s in SONGS for r,_ in fixed[s]}
    fixed_agg,_,_=v44.evaluate(fixed,base,truth)

    variants={}
    for name,rule in RULES.items():
        adds={}
        for s in SONGS:
            extra=select_rule(rows,s,rule,fixed_keys)
            adds[s]=v44.dedupe([*fixed[s],*extra])
        agg,scores,detail=v44.evaluate(adds,base,truth)
        agg["delta_vs_baseline"]=agg["f1"]-baseline["f1"]
        agg["delta_vs_fixed"]=agg["f1"]-fixed_agg["f1"]
        for g in v44.GROUPS:
            agg["by_group"][g]["delta_vs_fixed"]=agg["by_group"][g]["f1"]-fixed_agg["by_group"][g]["f1"]
        variants[name]={"rule":rule,"aggregate":agg,"songs":scores,"detail":detail}

    result={"schema":1,"date":"2026-09-23","experiment":"arrangement-egmd-portable-v46",
      "warning":"These portable rules were hypothesized after inspecting v45 on the same five-song development set; this is not an independent unknown-song generalization test.",
      "baseline":baseline,"fixed_v39d":fixed_agg,"variants":variants}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")

    def f(x):return f"{x:.6f}"
    lines=["# Arrangement + E-GMD portable residual gate v46","",
      "Goal: reproduce the v45 held-out Extra Trees residual gain with a small JS-portable rule.","",
      "**Caveat:** the rule family was proposed after v45 inspection on the same five-song development set. Treat this as internal development validation, not independent generalization.","",
      "| rule | KST F1 | vs fixed | snare vs fixed | total TP/FP additions |",
      "|---|---:|---:|---:|---:|"]
    for name in RULES:
        v=variants[name];a=v["aggregate"];d=v["detail"]
        tp=sum(x["tp"] for x in d.values());fp=sum(x["fp"] for x in d.values())
        lines.append(f"| {name} | {f(a['f1'])} | {f(a['delta_vs_fixed'])} | {f(a['by_group']['snare']['delta_vs_fixed'])} | {tp}/{fp} |")
    lines += ["","All variants are additive on top of fixed v39D; Kick/Tom decisions are unchanged.",""]
    MD.write_text("\n".join(lines));print("\n".join(lines))

if __name__=="__main__":main()
