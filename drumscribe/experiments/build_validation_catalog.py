"""Build a reproducible catalog of every DrumScribe validation result.

Scans all results*.json files, records source/result git commits, extracts every
candidate/cycle/summary/params, and builds a per-part component bank so a strong
snare/kick/hat/tom/crash/ride subsystem is never lost just because its total F1
was lower.
"""
from __future__ import annotations
import json, re, subprocess
from pathlib import Path
from statistics import mean

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"
OUT=EXP/"validation-history.json"
BANK=EXP/"component-bank.json"
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]

def git(*args):
    try:return subprocess.check_output(["git",*args],text=True).strip()
    except:return None

def commit_for(path):
    return git("log","-1","--format=%H","--",str(path))

def guess_script(result_path):
    n=result_path.name
    mapping=[
      ("results-iterative-snare-veto.json","iterative_search_snare_veto.py"),
      ("results-iterative-best-fusion.json","iterative_search_best_fusion.py"),
      ("results-iterative-crossstem-hat.json","iterative_search_crossstem_hat.py"),
      ("results-iterative-crash-fallback.json","iterative_search_crash_fallback.py"),
      ("results-iterative-pedal-structural.json","iterative_search_pedal_structural.py"),
      ("results-iterative-ride-consensus.json","iterative_search_ride_consensus.py"),
      ("results-iterative-tom-consensus.json","iterative_search_tom_consensus.py"),
      ("results-iterative-ride-song-gate.json","iterative_search_ride_song_gate.py"),


      ("results-iterative-fusion-v2.json","iterative_search_fusion_v2.py"),
      ("results-iterative-pedal-repair.json","iterative_search_pedal_repair.py"),
      ("results-iterative-hat-fusion.json","iterative_search_hat_fusion.py"),
      ("results-iterative-hat-precision.json","iterative_search_hat_precision.py"),
      ("results-iterative-crash-consensus.json","iterative_search_crash_consensus.py"),
      ("results-iterative-pedal-repair.json","iterative_search_pedal_repair.py"),
      ("results-iterative-recall-repair.json","iterative_search_recall_repair.py"),
      ("results-iterative-pattern-consensus.json","iterative_search_pattern_consensus.py"),
      ("results-iterative-component-hybrid.json","iterative_search_component_hybrid.py"),
      ("results-iterative-neural-separation.json","iterative_search_neural_separation.py"),
      ("results-iterative-cymbal-fusion.json","iterative_search_cymbal_fusion.py"),
      ("results-iterative-composite-v2.json","iterative_search_composite_v2.py"),
      ("results-iterative-composite.json","iterative_search_composite.py"),
      ("results-iterative-separation.json","iterative_search_separation.py"),
      ("results-iterative-drumsep-rate.json","iterative_search_drumsep_rate.py"),
      ("results-iterative-drumsep.json","iterative_search_drumsep.py"),
      ("results-iterative-pedal-grid.json","iterative_search_pedal_grid.py"),
      ("results-iterative-pedal-hat.json","iterative_search_pedal_hat.py"),
      ("results-iterative-ride-contiguous.json","iterative_search_ride_contiguous.py"),
      ("results-iterative-ride-section.json","iterative_search_ride_section.py"),
      ("results-iterative-ride-ml.json","iterative_search_ride_ml.py"),
      ("results-iterative-tom.json","iterative_search_tom.py"),
      ("results-iterative-ml.json","iterative_search_cymbal_ml.py"),
      ("results-iterative-loop.json","iterative_search_loop.py"),
      ("results-iterative-rotation.json","iterative_search_rotation.py"),
      ("results-iterative-anchor.json","iterative_search_anchor.py"),
      ("results-iterative-phase.json","iterative_search_phase.py"),
      ("results-iterative-search.json","iterative_search.py"),
      ("results-ml-loo.json","evaluate_ml_cv.py"),
      ("results-v2-round4-ml.json","evaluate_ml_cv.py"),
      ("results-v2","evaluate_v2.py"),
      ("results-full.json","evaluate.py"),
      ("results-targeted.json","evaluate.py"),
      ("results-80s.json","evaluate.py"),
    ]
    for key,script in mapping:
        if n==key or n.startswith(key):
            p=EXP/script
            return p if p.exists() else None
    if n.startswith("results-v2"):
        return EXP/"evaluate_v2.py"
    return None

def iter_candidates(obj):
    if isinstance(obj,dict) and isinstance(obj.get("cycles"),list):
        for cyc in obj["cycles"]:
            cycle=cyc.get("cycle")
            for name,c in (cyc.get("candidates") or {}).items():
                yield cycle,name,c,cyc.get("winner")==name, name in (cyc.get("carried_close") or [])
    elif isinstance(obj,dict) and isinstance(obj.get("songs"),dict) and isinstance(obj.get("summary"),dict):
        yield obj.get("formal_round") or obj.get("round"),obj.get("name","result"),obj,True,False
    elif isinstance(obj,dict):
        # Legacy evaluator shapes: top-level method keys each holding full result.
        for name,c in obj.items():
            if isinstance(c,dict) and ("summary" in c or "songs" in c):
                yield None,name,c,False,False

def group_metric(candidate,g):
    s=candidate.get("summary") or {}
    by=s.get("by_group") or {}
    if g in by:
        x=by[g]
        pr=x.get("precision")
        rc=x.get("recall")
        f=x.get("f1")
        if f is None:
            tp=x.get("tp",0);pred=x.get("predicted",0);ref=x.get("reference",0)
            f=2*tp/(pred+ref) if pred+ref else 0
            pr=tp/pred if pred else 0;rc=tp/ref if ref else 0
        return {"f1":float(f or 0),"precision":float(pr or 0),"recall":float(rc or 0),
                "count_ratio":x.get("count_ratio")}
    return None

def song_group_f1(candidate,g):
    vals=[]
    for song,s in (candidate.get("songs") or {}).items():
        x=(s.get("by_group") or {}).get(g)
        if not x:continue
        ref=x.get("reference",0)
        if not ref:continue
        f=x.get("f1")
        if f is None:
            tp=x.get("tp",0);pred=x.get("predicted",0)
            f=2*tp/(pred+ref) if pred+ref else 0
        vals.append((song,float(f)))
    return vals

def main():
    history={"schema":1,"generated_from_head":git("rev-parse","HEAD"),"reference_dataset":{
      "songs":["arcaround","diamondvirgin","kaiju","nanairo","ray"],
      "audio":"DruMaster/songs/<song>/drums.mp3","truth":"DruMaster/songs/<song>/chart.mid",
      "alignment":"stemOffsetSec + midiOffsetSec from song.json",
      "canonical_evaluator":"drumscribe/experiments/detailed_metrics.py",
      "same_class_tolerance_sec":0.080
    },"result_files":[],"candidates":[]}
    bank_rows={g:[] for g in GROUPS}

    for p in sorted(EXP.glob("results*.json")):
        try:obj=json.loads(p.read_text())
        except Exception as e:
            history["result_files"].append({"path":str(p),"parse_error":str(e)});continue
        script=guess_script(p)
        rec={"path":str(p),"result_commit":commit_for(p),"script":str(script) if script else None,
             "script_commit":commit_for(script) if script else None}
        history["result_files"].append(rec)
        for cycle,name,c,winner,close in iter_candidates(obj):
            summary=c.get("summary") or {}
            cid=f"{p.name}:{cycle}:{name}"
            row={"id":cid,"result_file":str(p),"cycle":cycle,"name":name,
                 "winner":winner,"carried_close":close,"params":c.get("params"),
                 "summary":summary,
                 "song_metrics_ref":str(p),
                 "result_commit":rec["result_commit"],"script":rec["script"],"script_commit":rec["script_commit"]}
            history["candidates"].append(row)
            for g in GROUPS:
                gm=group_metric(c,g)
                if not gm:continue
                sf=song_group_f1(c,g)
                bank_rows[g].append({
                  "candidate_id":cid,"result_file":str(p),"cycle":cycle,"name":name,
                  **gm,
                  "mean_song_f1":round(mean(v for _,v in sf),6) if sf else None,
                  "worst_song_f1":round(min(v for _,v in sf),6) if sf else None,
                  "song_f1":dict(sf),"params":c.get("params"),"script":rec["script"],
                  "result_commit":rec["result_commit"],"script_commit":rec["script_commit"]
                })

    bank={"schema":1,"generated_from_head":history["generated_from_head"],"parts":{}}
    for g,rows in bank_rows.items():
        # Prefer robust all-song strength, then aggregate F1, then precision.
        ranked=sorted(rows,key=lambda x:(
          -1 if x["worst_song_f1"] is None else x["worst_song_f1"],
          -1 if x["mean_song_f1"] is None else x["mean_song_f1"],
          x["f1"],x["precision"]
        ),reverse=True)
        bank["parts"][g]={"top":ranked[:12],"best":ranked[0] if ranked else None}

    OUT.write_text(json.dumps(history,ensure_ascii=False,indent=2)+"\n")
    BANK.write_text(json.dumps(bank,ensure_ascii=False,indent=2)+"\n")
    print("result files",len(history["result_files"]),"candidates",len(history["candidates"]))
    for g in GROUPS:
        b=bank["parts"][g]["best"]
        print(g, None if not b else {k:b[k] for k in ("candidate_id","f1","mean_song_f1","worst_song_f1","precision","recall")})

if __name__=="__main__":main()
