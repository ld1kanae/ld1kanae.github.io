"""Build a human-readable current precision report from real generated MIDI."""
from __future__ import annotations
import importlib.util,json
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
spec=importlib.util.spec_from_file_location("detail",EXP/"detailed_metrics.py")
detail=importlib.util.module_from_spec(spec);spec.loader.exec_module(detail)

TARGETS=[
 ("balanced-tom-c105","generated-search-tom-consensus/cycle105/c105_density7"),
 ("fusion-v2-c84","generated-search-fusion-v2/cycle84/c84_pedal75"),
 ("ride-song-gate-c108","generated-search-ride-song-gate/cycle108/c108_per50"),
 ("ride-expand-c109","generated-search-ride-seed-expand/cycle109/c109_radius8"),
 ("snare-pattern-c80","generated-search-best-fusion/cycle80/c80_snare_pattern"),
]
PARTS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
OUT_JSON=EXP/"current-precision-report.json"
OUT_MD=EXP/"CURRENT_PRECISION_REPORT.md"

def f(x,d=4):
    if x is None:return "-"
    return f"{float(x):.{d}f}"

def main():
    reports=[]
    for name,rel in TARGETS:
        p=EXP/rel
        if not all((p/f"{s}.mid").exists() for s in detail.SONGS):
            continue
        obj=detail.compare_dir(p,name)
        reports.append(obj)

    OUT_JSON.write_text(json.dumps({"schema":1,"targets":reports},ensure_ascii=False,indent=2)+"\n")
    L=[
      "# DrumScribe 現在精密評価レポート","",
      "生成済みMIDIを再読み込みし、chart.midと標準80ms一対一マッチで照合した値。予測生成にはchart.midを使用しない。","",
    ]
    for r in reports:
        L += [f"## {r['name']}","",
          f"- prediction dir: {r['pred_dir']}",
          f"- overall F1: {f(r['aggregate']['overall']['f1'])}",
          f"- precision: {f(r['aggregate']['overall']['precision'])}",
          f"- recall: {f(r['aggregate']['overall']['recall'])}","",
          "### 全曲集計","",
          "|Part|Ref|Pred|TP|FP|FN|P|R|F1|False discovery|Miss|Count ratio|",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
        ]
        for g in PARTS:
            x=r["aggregate"]["by_group"].get(g)
            if not x:continue
            L.append("|"+"|".join([g,str(x["reference"]),str(x["predicted"]),str(x["tp"]),str(x["fp"]),str(x["fn"]),
              f(x["precision"]),f(x["recall"]),f(x["f1"]),f(x["false_discovery_rate"]),f(x["miss_rate"]),f(x["count_ratio"])])+"|")
        L += ["","### 曲別 × パート","",
          "|Song|Part|Ref|Pred|TP|FP|FN|P|R|F1|FDR|Miss|Timing median ms|Timing p90 ms|Unmatched-nearest median ms|Far >160ms|",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
        ]
        for song,s in r["songs"].items():
            for g in PARTS:
                x=s["by_group"].get(g)
                if not x:continue
                L.append("|"+"|".join([song,g,str(x["reference"]),str(x["predicted"]),str(x["tp"]),str(x["fp"]),str(x["fn"]),
                  f(x["precision"]),f(x["recall"]),f(x["f1"]),f(x["false_discovery_rate"]),f(x["miss_rate"]),
                  f(x["timing_abs_median_ms"],2),f(x["timing_abs_p90_ms"],2),f(x["unmatched_nearest_ref_median_ms"],2),
                  str(x["unmatched_farther_than_160ms"])])+"|")
        L += ["","### クラス間誤認",""]
        for song,s in r["songs"].items():
            L.append(f"- {song}: "+json.dumps(s["confusion_matrix"],ensure_ascii=False))
        L += [""]
    OUT_MD.write_text("\n".join(L)+"\n")
    print(json.dumps({"targets":[r["name"] for r in reports],"out":str(OUT_MD)},ensure_ascii=False))

if __name__=="__main__":main()
