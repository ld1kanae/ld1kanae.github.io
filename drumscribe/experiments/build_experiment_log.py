"""Generate exhaustive human-readable and machine-readable DrumScribe experiment logs."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"
HIST=EXP/"validation-history.json"
BANK=EXP/"component-bank.json"
MD=EXP/"EXPERIMENT_LOG.md"
OUT=EXP/"experiment-log.json"
PARTS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]

def fmt(v,d=4):
    if v is None:return "-"
    try:return f"{float(v):.{d}f}"
    except:return str(v)

def part_f1(summary,g):
    x=(summary.get("by_group") or {}).get(g) or {}
    if x.get("f1") is not None:return float(x["f1"])
    tp=x.get("tp");pred=x.get("predicted");ref=x.get("reference")
    if tp is None or pred is None or ref is None:return None
    return 2*tp/(pred+ref) if pred+ref else 0.0

def main():
    h=json.loads(HIST.read_text())
    bank=json.loads(BANK.read_text()) if BANK.exists() else {"parts":{}}
    leader_ids=set(); leader_by_part={}
    for g,v in bank.get("parts",{}).items():
        best=v.get("best")
        if best:
            leader_ids.add(best["candidate_id"]); leader_by_part[g]=best

    groups=defaultdict(lambda:defaultdict(list))
    files={x["path"]:x for x in h.get("result_files",[])}
    all_candidates=[]
    for c in h.get("candidates",[]):
        groups[c["result_file"]][str(c.get("cycle"))].append(c)
        s=c.get("summary") or {}
        all_candidates.append({
          "id":c["id"],"result_file":c["result_file"],"cycle":c.get("cycle"),"name":c["name"],
          "winner":bool(c.get("winner")),"carried_close":bool(c.get("carried_close")),
          "component_leader":c["id"] in leader_ids,"params":c.get("params"),"summary":s,
          "part_f1":{g:part_f1(s,g) for g in PARTS},
          "song_metrics_ref":c.get("song_metrics_ref"),"result_commit":c.get("result_commit"),
          "script":c.get("script"),"script_commit":c.get("script_commit")
        })

    sortable=[c for c in all_candidates if c["summary"].get("f1") is not None]
    overall=sorted(sortable,key=lambda c:float(c["summary"]["f1"]),reverse=True)[:20]
    OUT.write_text(json.dumps({
      "schema":1,"generated_from_head":h.get("generated_from_head"),
      "evaluation_reference":h.get("reference_dataset"),
      "candidate_count":len(all_candidates),"result_file_count":len(groups),
      "current_overall_top20":overall,"current_component_leaders":leader_by_part,
      "candidates":all_candidates
    },ensure_ascii=False,indent=2)+"\n")

    lines=[
      "# DrumScribe 全実験ログ","",
      "このファイルは build_experiment_log.py で自動生成する。候補を手作業で省略しない。","",
      f"- 集録 result files: {len(groups)}",f"- 集録 candidates: {len(all_candidates)}",
      "- 生の曲別データ: 各 results*.json",
      "- 標準詳細評価: detailed_metrics.py / detailed-history/",
      "- 再現用索引: validation-history.json",
      "- パート別保持候補: component-bank.json","",
      "## 評価規則","",
      "- 予測生成時に評価対象曲の chart.mid を参照しない。学習型はLOSOを基本とする。",
      "- drums.mp3 から実MIDIを生成し、そのMIDIを再読み込みして chart.mid と照合する。",
      "- 同一パート80 ms以内の1対1対応を基本TPとし、P/R/F1、FP/FN、ノート数比、時間誤差、クラス間誤認を保持する。",
      "- 総合勝者だけでなく、特定パートで突出した候補を component bank に残す。",
      "- pedal-hat / ride等をゼロにして総合F1だけ上げた候補は、それだけで本採用しない。","",
      "## 現在の総合上位候補","",
      "|候補|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|",
      "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    ]
    for c in overall[:12]:
        s=c["summary"];pf=c["part_f1"]
        lines.append("|"+"|".join([c["id"],fmt(s.get("f1")),fmt(s.get("precision")),fmt(s.get("recall")),
          fmt(pf["kick"]),fmt(pf["snare"]),fmt(pf["hat"]),fmt(pf["pedal_hat"]),
          fmt(pf["tom"]),fmt(pf["crash"]),fmt(pf["ride"])])+"|")

    lines += ["","## 現在のパート別保持候補","",
      "|Part|Candidate|F1|Precision|Recall|Mean-song F1|Worst-song F1|",
      "|---|---|---:|---:|---:|---:|---:|"]
    for g in PARTS:
        b=leader_by_part.get(g)
        if b:
            lines.append("|"+"|".join([g,b["candidate_id"],fmt(b.get("f1")),fmt(b.get("precision")),
              fmt(b.get("recall")),fmt(b.get("mean_song_f1")),fmt(b.get("worst_song_f1"))])+"|")

    lines += ["","## 全result / cycle / candidate",""]
    def ck(x):
        try:return (0,int(x))
        except:return (1,str(x))
    for rf in sorted(groups):
        meta=files.get(rf,{})
        lines += [f"### {rf}","",f"- implementation: {meta.get('script') or '-'}",
          f"- script commit: {meta.get('script_commit') or '-'}",
          f"- result commit: {meta.get('result_commit') or '-'}",""]
        for cyc in sorted(groups[rf],key=ck):
            cs=groups[rf][cyc]
            lines += [f"#### Cycle {cyc}","",
              "|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
            for c in sorted(cs,key=lambda x:float((x.get("summary") or {}).get("f1") or -1),reverse=True):
                s=c.get("summary") or {};state=[]
                if c.get("winner"):state.append("winner")
                if c.get("carried_close"):state.append("close")
                if c["id"] in leader_ids:state.append("part-leader")
                vals=[fmt(part_f1(s,g)) for g in ("kick","snare","hat","pedal_hat","tom","crash","ride")]
                lines.append("|"+"|".join([c["name"],", ".join(state) or "-",fmt(s.get("f1")),
                  fmt(s.get("precision")),fmt(s.get("recall")),*vals,
                  str(s.get("kick_to_snare","-")),str(s.get("snare_to_kick","-"))])+"|")
            lines += ["",f"詳細params・曲別データ参照: {rf} / experiment-log.json",""]
    MD.write_text("\n".join(lines)+"\n")
    print(json.dumps({"result_files":len(groups),"candidates":len(all_candidates)},ensure_ascii=False))

if __name__=="__main__":main()
