"""Cycles 154-156: second-pass refinement after c152_refractory.

This is a true follow-up iteration: the winner from the first overtrigger
experiment becomes the fixed base, and new hypotheses target only the
remaining errors.

Cycle 154: collapse very-close snare clusters with three dynamic gap sizes.
Cycle 155: filter ride candidates by independent-source / repetition support.
Cycle 156: suppress likely hi-hat bleed near kick/snare/tom only when hat
           source consensus and repetition evidence are both weak.

chart.mid is never used to generate predictions; it is scoring-only.
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
BASE = EXP / "generated-search-overtrigger-repair/cycle152/c152_refractory"


def rows(path, song):
    return repair.rows(path, song)


def meta(song):
    return repair.meta(song)


def replace_group(events, group, times):
    return sorted([e for e in events if e[1] != group] + [(t, group) for t in times])


def choose_cluster_rep(song, group, cluster, all_times, ph, bar):
    if group == "snare":
        src = repair.source_times(repair.SNARE_SOURCES, song, "snare")
    else:
        src = repair.source_times(repair.METAL_SOURCES[group], song, group)
    scored = []
    for t in cluster:
        votes = repair.source_votes(src, t)
        rep = repair.rep_support(all_times, t, ph, bar)
        scored.append((2.0 * votes + 0.30 * min(rep, 4), votes, rep, -t, t))
    return max(scored)[-1]


def snare_collapse(song, events, mode):
    if mode == "base":
        return events
    _, ph, beat, bar = repair.timing(song, events)
    snares = sorted(t for t, g in events if g == "snare")
    if mode == "gap08":
        gap = repair.clamp(0.08 * beat, 0.035, 0.060)
    elif mode == "gap12":
        gap = repair.clamp(0.12 * beat, 0.040, 0.080)
    else:
        gap = repair.clamp(0.16 * beat, 0.050, 0.100)

    clusters = []
    cur = []
    for t in snares:
        if not cur or t - cur[-1] <= gap:
            cur.append(t)
        else:
            clusters.append(cur)
            cur = [t]
    if cur:
        clusters.append(cur)

    kept = []
    for c in clusters:
        if len(c) == 1:
            kept.extend(c)
        else:
            kept.append(choose_cluster_rep(song, "snare", c, snares, ph, bar))
    return repair.enforce(replace_group(events, "snare", kept))


def ride_filter(song, events, mode):
    if mode == "base":
        return events
    _, ph, _, bar = repair.timing(song, events)
    rides = sorted(t for t, g in events if g == "ride")
    src = repair.source_times(repair.METAL_SOURCES["ride"], song, "ride")
    kept = []
    for t in rides:
        votes = repair.source_votes(src, t)
        rep = repair.rep_support(rides, t, ph, bar)
        if mode == "source2":
            ok = votes >= 2
        elif mode == "source1_repeat":
            ok = votes >= 2 or (votes >= 1 and rep >= 3)
        else:
            ok = votes >= 1 or rep >= 4
        if ok:
            kept.append(t)
    return repair.enforce(replace_group(events, "ride", kept))


def hat_guard(song, events, mode):
    if mode == "base":
        return events
    _, ph, _, bar = repair.timing(song, events)
    hats = sorted(t for t, g in events if g == "hat")
    src = repair.source_times(repair.METAL_SOURCES["hat"], song, "hat")
    kick = [t for t, g in events if g == "kick"]
    snare = [t for t, g in events if g == "snare"]
    tom = [t for t, g in events if g == "tom"]
    kept = []
    for t in hats:
        if mode == "kick":
            conflict = repair.near(kick, t, 0.030)
        elif mode == "kick_snare":
            conflict = repair.near(kick, t, 0.030) or repair.near(snare, t, 0.030)
        else:
            conflict = (
                repair.near(kick, t, 0.030)
                or repair.near(snare, t, 0.030)
                or repair.near(tom, t, 0.035)
            )
        if not conflict:
            kept.append(t)
            continue
        votes = repair.source_votes(src, t)
        rep = repair.rep_support(hats, t, ph, bar)
        # True simultaneous hat+drum hits are common. Therefore conflict alone
        # is never enough to remove a hat; both independent hat support and
        # rhythmic repetition must be weak.
        if votes >= 2 or rep >= 3:
            kept.append(t)
    return repair.enforce(replace_group(events, "hat", kept))


def build(song, snare_mode, ride_mode, hat_mode):
    e = rows(BASE, song)
    e = snare_collapse(song, e, snare_mode)
    e = ride_filter(song, e, ride_mode)
    e = hat_guard(song, e, hat_mode)
    return repair.enforce(e)


def write(path, events, bpm):
    base.write_midi(
        path,
        [{"time": t, "group": g, "score": 1.0, "confidence": 1.0} for t, g in events],
        bpm,
    )


def evaluate(name, snare_mode, ride_mode, hat_mode, outdir):
    result = {
        "snare_mode": snare_mode,
        "ride_mode": ride_mode,
        "hat_mode": hat_mode,
        "songs": {},
    }
    tot = Counter()

    for song in SONGS:
        m = meta(song)
        events = build(song, snare_mode, ride_mode, hat_mode)
        p = outdir / name / f"{song}.mid"
        write(p, events, float(m["bpm"]))
        pred = ev.midi_events(p)
        truth = ev.midi_events(ROOT / "DruMaster/songs" / song / "chart.mid")
        shift = m["playback"]["stemOffsetSec"] + m["playback"].get("midiOffsetSec", 0)
        sc = ev.score(pred, truth, shift)
        cf = ev.confusion(pred, truth, shift)
        sc["confusion"] = cf
        sc["count_ratio"] = ev.count_ratios(sc)

        _, _, beat, _ = repair.timing(song, events)
        sret = repair.retrigger_stat(
            pred, truth, shift, "snare", repair.clamp(0.12 * beat, 0.040, 0.080)
        )
        metal = {
            g: repair.retrigger_stat(pred, truth, shift, g, repair.metal_gap(g, beat))
            for g in METAL
        }
        sc["retrigger"] = {
            "snare": sret,
            "metal": metal,
            "metal_overlap_clusters": repair.overlap_clusters(pred, 0.035),
        }
        result["songs"][song] = sc

        tot.update(
            tp=sc["tp"], predicted=sc["predicted"], reference=sc["reference"],
            kick_to_snare=cf["kick_to_snare"], snare_to_kick=cf["snare_to_kick"],
            snare_short_pairs=sret["pairs"], snare_retrigger_fp=sret["unsupported"],
            metal_overlap=sc["retrigger"]["metal_overlap_clusters"],
        )
        for g, x in sc["by_group"].items():
            tot[f"{g}_tp"] += x["tp"]
            tot[f"{g}_pred"] += x["predicted"]
            tot[f"{g}_ref"] += x["reference"]
        for x in metal.values():
            tot["metal_short_pairs"] += x["pairs"]
            tot["metal_retrigger_fp"] += x["unsupported"]
            tot["metal_pred"] += x["predicted"]

    tp, n, ref = tot["tp"], tot["predicted"], tot["reference"]
    summary = {
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
        summary["by_group"][g] = {
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

    sn_pred = max(1, summary["by_group"]["snare"]["predicted"])
    metal_pred = max(1, sum(summary["by_group"][g]["predicted"] for g in METAL))
    summary["retrigger"] = {
        "snare_short_gap_pairs": tot["snare_short_pairs"],
        "snare_retrigger_fp": tot["snare_retrigger_fp"],
        "snare_retrigger_fp_rate": tot["snare_retrigger_fp"] / sn_pred,
        "metal_short_gap_pairs": tot["metal_short_pairs"],
        "metal_retrigger_fp": tot["metal_retrigger_fp"],
        "metal_retrigger_fp_rate": tot["metal_retrigger_fp"] / metal_pred,
        "metal_overlap_clusters": tot["metal_overlap"],
        "metal_overlap_rate": tot["metal_overlap"] / metal_pred,
    }

    canonical = sel.score(summary)
    rt = summary["retrigger"]
    repair_score = (
        canonical["score"]
        - 0.08 * rt["snare_retrigger_fp_rate"]
        - 0.10 * rt["metal_retrigger_fp_rate"]
        - 0.03 * rt["metal_overlap_rate"]
    )
    result["summary"] = summary
    result["canonical_score"] = canonical
    result["repair_score"] = round(repair_score, 6)
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
    root = EXP / "generated-search-overtrigger-refine"
    report = {
        "schema": 1,
        "description": "Cycles 154-156: second-pass refinement from c152_refractory.",
        "selection": "canonical score + retrigger penalties + all-part non-regression",
        "cycles": [],
    }

    baseline = evaluate("baseline", "base", "base", "base", root / "baseline")

    # 154: nearly every remaining sub-gap snare pair from Cycle 152 was
    # unsupported by chart.mid during scoring. Test complete cluster collapse
    # at three musically scaled windows.
    res = {}
    for name, mode in [
        ("c154_base", "base"),
        ("c154_gap08", "gap08"),
        ("c154_gap12", "gap12"),
        ("c154_gap16", "gap16"),
    ]:
        res[name] = evaluate(name, mode, "base", "base", root / "cycle154")
        print("SUMMARY", name, json.dumps({
            "f1": res[name]["summary"]["f1"],
            "snare": res[name]["summary"]["by_group"]["snare"],
            "retrigger": res[name]["summary"]["retrigger"],
            "repair_score": res[name]["repair_score"],
        }, ensure_ascii=False), flush=True)
    d = choose(res, baseline, ("snare",), 0.025, 0.015)
    win = d["winner"] or "c154_base"
    best = res[win]
    report["cycles"].append({"cycle": 154, "candidates": res, "winner": win, "ranking": d["ranking"], "guards": d["guards"]})

    # 155: do not change crash/hat. Filter only ride, whose FDR is still high.
    res = {}
    for name, mode in [
        ("c155_base", "base"),
        ("c155_source2", "source2"),
        ("c155_source1_repeat", "source1_repeat"),
        ("c155_periodic", "periodic"),
    ]:
        res[name] = evaluate(name, best["snare_mode"], mode, "base", root / "cycle155")
        print("SUMMARY", name, json.dumps({
            "f1": res[name]["summary"]["f1"],
            "ride": res[name]["summary"]["by_group"]["ride"],
            "repair_score": res[name]["repair_score"],
        }, ensure_ascii=False), flush=True)
    d = choose(res, best, ("ride",), 0.030, 0.015)
    win = d["winner"] or "c155_base"
    best = res[win]
    report["cycles"].append({"cycle": 155, "candidates": res, "winner": win, "ranking": d["ranking"], "guards": d["guards"]})

    # 156: only conditionally suppress hats likely to be bleed from another
    # drum onset. Simultaneous true hats survive on source/repetition evidence.
    res = {}
    for name, mode in [
        ("c156_base", "base"),
        ("c156_kick", "kick"),
        ("c156_kick_snare", "kick_snare"),
        ("c156_all_drum", "all_drum"),
    ]:
        res[name] = evaluate(name, best["snare_mode"], best["ride_mode"], mode, root / "cycle156")
        print("SUMMARY", name, json.dumps({
            "f1": res[name]["summary"]["f1"],
            "hat": res[name]["summary"]["by_group"]["hat"],
            "repair_score": res[name]["repair_score"],
        }, ensure_ascii=False), flush=True)
    d = choose(res, best, ("hat",), 0.030, 0.015)
    win = d["winner"] or "c156_base"
    best = res[win]
    report["cycles"].append({"cycle": 156, "candidates": res, "winner": win, "ranking": d["ranking"], "guards": d["guards"]})

    final_dir = root / "cycle156" / win
    report["final"] = {
        "winner": win,
        "summary": best["summary"],
        "canonical_score": best["canonical_score"],
        "repair_score": best["repair_score"],
        "guard": best["guard"],
        "snare_mode": best["snare_mode"],
        "ride_mode": best["ride_mode"],
        "hat_mode": best["hat_mode"],
        "detailed": detail.compare_dir(final_dir, win)["aggregate"],
    }
    (EXP / "results-iterative-overtrigger-refine.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print("FINAL", json.dumps(report["final"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
