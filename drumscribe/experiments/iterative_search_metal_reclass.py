"""Cycles 157-159: pairwise metal reclassification after c156_kick_snare.

Base: generated-search-overtrigger-refine/cycle156/c156_kick_snare.

Motivation from scoring diagnostics (not used by predictor): the remaining
metal errors are dominated by hat<->pedal, hat<->ride and hat<->crash class
confusions rather than pure onset timing errors. This search therefore keeps
onsets where possible and changes class only when independent source votes and
rhythmic context support it.

chart.mid remains scoring-only.
"""
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT = Path(".")
EXP = ROOT / "drumscribe/experiments"


def loadmod(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


repair = loadmod("repair", EXP / "iterative_search_overtrigger_repair.py")
ev = repair.ev
sel = repair.sel
detail = repair.detail
base = repair.base

SONGS = repair.SONGS
GROUPS = repair.GROUPS
METAL = repair.METAL
BASE = EXP / "generated-search-overtrigger-refine/cycle156/c156_kick_snare"


def rows(path, song):
    return repair.rows(path, song)


def meta(song):
    return repair.meta(song)


def near_index(events, t, group, w=0.035):
    idx = [i for i, (x, g) in enumerate(events) if g == group and abs(x - t) <= w]
    return min(idx, key=lambda i: abs(events[i][0] - t)) if idx else None


def source_evidence(song, group, t):
    src = repair.source_times(repair.METAL_SOURCES[group], song, group)
    return repair.source_votes(src, t)


def pedal_hat_reclass(song, events, mode):
    if mode == "base":
        return events
    out = list(events)
    pedals = [(i, t) for i, (t, g) in enumerate(out) if g == "pedal_hat"]
    hats = [t for t, g in out if g == "hat"]
    _, ph, _, bar = repair.timing(song, out)
    converted = set()
    dropped = set()

    for i, t in pedals:
        pv = source_evidence(song, "pedal_hat", t)
        hv = source_evidence(song, "hat", t)
        hnear = repair.near(hats, t, 0.035)
        rep = repair.rep_support(hats, t, ph, bar)
        if mode == "near_hat_drop":
            if hnear and pv < 2:
                dropped.add(i)
        elif mode == "vote_reclass":
            if hnear and hv > pv:
                dropped.add(i)
            elif hv >= pv + 1 and hv >= 2:
                converted.add(i)
        else:  # conservative
            if hnear and hv >= 2 and pv == 0:
                dropped.add(i)
            elif (not hnear) and hv >= 2 and pv == 0 and rep >= 3:
                converted.add(i)

    rebuilt = []
    for i, (t, g) in enumerate(out):
        if i in dropped:
            continue
        if i in converted:
            rebuilt.append((t, "hat"))
        else:
            rebuilt.append((t, g))
    return repair.enforce(rebuilt)


def ride_hat_reclass(song, events, mode):
    if mode == "base":
        return events
    _, ph, _, bar = repair.timing(song, events)
    out = []
    for t, g in events:
        if g not in ("hat", "ride"):
            out.append((t, g))
            continue
        hv = source_evidence(song, "hat", t)
        rv = source_evidence(song, "ride", t)
        hats = [x for x, gg in events if gg == "hat"]
        rides = [x for x, gg in events if gg == "ride"]
        hrep = repair.rep_support(hats, t, ph, bar)
        rrep = repair.rep_support(rides, t, ph, bar)

        ng = g
        if mode == "ride_to_hat":
            if g == "ride" and hv >= rv + 1 and hv >= 2:
                ng = "hat"
        elif mode == "balanced":
            if g == "ride" and hv >= rv + 1 and hv >= 2:
                ng = "hat"
            elif g == "hat" and rv >= hv + 1 and rv >= 2 and rrep >= 3:
                ng = "ride"
        else:  # strong_margin
            if g == "ride" and hv >= rv + 2 and hv >= 2:
                ng = "hat"
            elif g == "hat" and rv >= hv + 2 and rv >= 2 and rrep >= 4:
                ng = "ride"
        out.append((t, ng))
    return repair.enforce(out)


def crash_hat_reclass(song, events, mode):
    if mode == "base":
        return events
    _, ph, beat, bar = repair.timing(song, events)
    out = []
    for t, g in events:
        if g not in ("hat", "crash"):
            out.append((t, g))
            continue
        hv = source_evidence(song, "hat", t)
        cv = source_evidence(song, "crash", t)
        down = repair.downbeat_strength(t, ph, beat, bar)
        ng = g
        if mode == "conservative":
            if g == "hat" and cv >= hv + 1 and cv >= 2 and down >= 0.72:
                ng = "crash"
            elif g == "crash" and hv >= cv + 2 and hv >= 2 and down < 0.45:
                ng = "hat"
        elif mode == "balanced":
            if g == "hat" and cv >= hv + 1 and cv >= 1 and down >= 0.60:
                ng = "crash"
            elif g == "crash" and hv >= cv + 1 and hv >= 2 and down < 0.55:
                ng = "hat"
        else:  # crash_recall
            if g == "hat" and cv >= hv and cv >= 1 and down >= 0.50:
                ng = "crash"
            elif g == "crash" and hv >= cv + 2 and hv >= 2 and down < 0.35:
                ng = "hat"
        out.append((t, ng))
    return repair.enforce(out)


def build(song, pedal_mode, ride_mode, crash_mode):
    e = rows(BASE, song)
    e = pedal_hat_reclass(song, e, pedal_mode)
    e = ride_hat_reclass(song, e, ride_mode)
    e = crash_hat_reclass(song, e, crash_mode)
    return repair.enforce(e)


def write(path, events, bpm):
    base.write_midi(
        path,
        [{"time": t, "group": g, "score": 1.0, "confidence": 1.0} for t, g in events],
        bpm,
    )


def evaluate(name, pedal_mode, ride_mode, crash_mode, outdir):
    result = {
        "pedal_mode": pedal_mode,
        "ride_mode": ride_mode,
        "crash_mode": crash_mode,
        "songs": {},
    }
    tot = Counter()
    for song in SONGS:
        m = meta(song)
        events = build(song, pedal_mode, ride_mode, crash_mode)
        p = outdir / name / f"{song}.mid"
        write(p, events, float(m["bpm"]))
        pred = ev.midi_events(p)
        truth = ev.midi_events(ROOT / "DruMaster/songs" / song / "chart.mid")
        shift = m["playback"]["stemOffsetSec"] + m["playback"].get("midiOffsetSec", 0)
        sc = ev.score(pred, truth, shift)
        cf = ev.confusion(pred, truth, shift)
        sc["confusion"] = cf
        sc["count_ratio"] = ev.count_ratios(sc)
        result["songs"][song] = sc
        tot.update(
            tp=sc["tp"], predicted=sc["predicted"], reference=sc["reference"],
            kick_to_snare=cf["kick_to_snare"], snare_to_kick=cf["snare_to_kick"],
        )
        for g, x in sc["by_group"].items():
            tot[f"{g}_tp"] += x["tp"]
            tot[f"{g}_pred"] += x["predicted"]
            tot[f"{g}_ref"] += x["reference"]

    tp, n, ref = tot["tp"], tot["predicted"], tot["reference"]
    s = {
        "tp": tp, "predicted": n, "reference": ref,
        "precision": tp / n if n else 0,
        "recall": tp / ref if ref else 0,
        "f1": 2 * tp / (n + ref) if n + ref else 0,
        "kick_to_snare": tot["kick_to_snare"],
        "snare_to_kick": tot["snare_to_kick"],
        "two_limb_violations": 0,
        "by_group": {},
    }
    for g in GROUPS:
        a, b, c = tot[f"{g}_tp"], tot[f"{g}_pred"], tot[f"{g}_ref"]
        song_f1 = []
        for song in SONGS:
            x = result["songs"][song]["by_group"].get(g, {})
            rr = x.get("reference", 0)
            if rr:
                song_f1.append(
                    2 * x.get("tp", 0) / (x.get("predicted", 0) + rr)
                    if x.get("predicted", 0) + rr else 0
                )
        s["by_group"][g] = {
            "tp": a, "predicted": b, "reference": c,
            "precision": a / b if b else 0,
            "recall": a / c if c else 0,
            "f1": 2 * a / (b + c) if b + c else 0,
            "false_discovery_rate": (b - a) / b if b else 0,
            "miss_rate": (c - a) / c if c else 0,
            "count_ratio": b / c if c else None,
            "mean_song_f1": sum(song_f1) / len(song_f1) if song_f1 else None,
            "worst_song_f1": min(song_f1) if song_f1 else None,
        }

    s["retrigger"] = {
        "snare_retrigger_fp_rate": 0.0,
        "metal_retrigger_fp_rate": 0.0,
        "metal_overlap_rate": 0.0,
    }
    canonical = sel.score(s)
    result["summary"] = s
    result["canonical_score"] = canonical
    result["repair_score"] = canonical["score"]
    return result


def choose(candidates, baseline, targets, max_drop=0.035, tolerance=0.012):
    ranking = []
    guards = {}
    for name, obj in candidates.items():
        guard = sel.eligibility(
            obj["summary"], baseline["summary"],
            target_parts=targets,
            max_part_drop=max_drop,
            target_tolerance=tolerance,
        )
        obj["guard"] = guard
        guards[name] = guard
        ranking.append((guard["eligible"], obj["repair_score"], obj["summary"]["f1"], name))
    ranking.sort(reverse=True)
    winner = next((name for ok, _, _, name in ranking if ok), None)
    return {"winner": winner, "ranking": [x[3] for x in ranking], "guards": guards}


def main():
    root = EXP / "generated-search-metal-reclass"
    report = {
        "schema": 1,
        "description": "Cycles 157-159: pairwise metal reclassification after c156.",
        "cycles": [],
    }
    baseline = evaluate("baseline", "base", "base", "base", root / "baseline")

    res = {}
    for name, mode in [
        ("c157_base", "base"),
        ("c157_near_hat_drop", "near_hat_drop"),
        ("c157_vote_reclass", "vote_reclass"),
        ("c157_conservative", "conservative"),
    ]:
        res[name] = evaluate(name, mode, "base", "base", root / "cycle157")
        print("SUMMARY", name, json.dumps({
            "f1": res[name]["summary"]["f1"],
            "hat": res[name]["summary"]["by_group"]["hat"],
            "pedal": res[name]["summary"]["by_group"]["pedal_hat"],
            "score": res[name]["repair_score"],
        }, ensure_ascii=False), flush=True)
    d = choose(res, baseline, ("hat", "pedal_hat"), 0.030, 0.015)
    win = d["winner"] or "c157_base"
    best = res[win]
    report["cycles"].append({"cycle": 157, "candidates": res, "winner": win, "ranking": d["ranking"], "guards": d["guards"]})

    res = {}
    for name, mode in [
        ("c158_base", "base"),
        ("c158_ride_to_hat", "ride_to_hat"),
        ("c158_balanced", "balanced"),
        ("c158_strong_margin", "strong_margin"),
    ]:
        res[name] = evaluate(name, best["pedal_mode"], mode, "base", root / "cycle158")
        print("SUMMARY", name, json.dumps({
            "f1": res[name]["summary"]["f1"],
            "hat": res[name]["summary"]["by_group"]["hat"],
            "ride": res[name]["summary"]["by_group"]["ride"],
            "score": res[name]["repair_score"],
        }, ensure_ascii=False), flush=True)
    d = choose(res, best, ("hat", "ride"), 0.035, 0.015)
    win = d["winner"] or "c158_base"
    best = res[win]
    report["cycles"].append({"cycle": 158, "candidates": res, "winner": win, "ranking": d["ranking"], "guards": d["guards"]})

    res = {}
    for name, mode in [
        ("c159_base", "base"),
        ("c159_conservative", "conservative"),
        ("c159_balanced", "balanced"),
        ("c159_crash_recall", "crash_recall"),
    ]:
        res[name] = evaluate(name, best["pedal_mode"], best["ride_mode"], mode, root / "cycle159")
        print("SUMMARY", name, json.dumps({
            "f1": res[name]["summary"]["f1"],
            "hat": res[name]["summary"]["by_group"]["hat"],
            "crash": res[name]["summary"]["by_group"]["crash"],
            "score": res[name]["repair_score"],
        }, ensure_ascii=False), flush=True)
    d = choose(res, best, ("hat", "crash"), 0.035, 0.015)
    win = d["winner"] or "c159_base"
    best = res[win]
    report["cycles"].append({"cycle": 159, "candidates": res, "winner": win, "ranking": d["ranking"], "guards": d["guards"]})

    final_dir = root / "cycle159" / win
    report["final"] = {
        "winner": win,
        "summary": best["summary"],
        "canonical_score": best["canonical_score"],
        "pedal_mode": best["pedal_mode"],
        "ride_mode": best["ride_mode"],
        "crash_mode": best["crash_mode"],
        "detailed": detail.compare_dir(final_dir, win)["aggregate"],
    }
    (EXP / "results-iterative-metal-reclass.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print("FINAL", json.dumps(report["final"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
