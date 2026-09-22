"""Cycles 151-153: over-trigger / retrigger repair.

Starts from fusion-v6 c144_adaptive and specifically targets the user-reported
failure modes: snare double/retrigger hits and excessive metal (hat/cymbal)
hits. The predictor uses only previously audio-derived MIDI components and
song metadata (BPM/time signature). chart.mid is scoring-only.

Cycle 151: snare short-gap arbitration using independent snare components.
Cycle 152: dynamic metal refractory with source-consensus/rhythm rescue.
Cycle 153: near-synchronous hat/crash/ride class arbitration.

Every candidate is materialized as a real MIDI file, re-read, and rescored.
In addition to P/R/F1, we record unsupported short-gap retriggers so a
candidate cannot hide "one hit -> several hits" behind aggregate recall.
"""
from __future__ import annotations

import importlib.util
import json
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(".")
EXP = ROOT / "drumscribe/experiments"


def loadmod(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ev = loadmod("ev", EXP / "evaluate_v2.py")
detail = loadmod("detail", EXP / "detailed_metrics.py")
base = loadmod("base", EXP / "iterative_search.py")
sel = loadmod("sel", EXP / "selection_policy.py")

SONGS = ["arcaround", "diamondvirgin", "kaiju", "nanairo", "ray"]
GROUPS = ["kick", "snare", "hat", "pedal_hat", "tom", "crash", "ride", "other"]
HANDS = {"snare", "hat", "tom", "crash", "ride"}
HAND_METAL = {"hat", "crash", "ride"}
METAL = {"hat", "pedal_hat", "crash", "ride"}

BASE = EXP / "generated-search-fusion-v6/cycle144/c144_adaptive"

SNARE_SOURCES = [
    EXP / "generated-search-snare-safe-fusion/cycle113/c113_k65",
    EXP / "generated-search-best-fusion/cycle80/c80_snare_pattern",
    EXP / "generated-search-component-hybrid/cycle54/c54_crash_source",
]
METAL_SOURCES = {
    "hat": [
        EXP / "generated-search-crossstem-hat/cycle85/c85_strict",
        EXP / "generated-search-hat-precision/cycle75/c75_repeat5",
        EXP / "generated-search-pattern-consensus/cycle56/c56_window2",
    ],
    "pedal_hat": [
        EXP / "generated-search-pedal-adaptive/cycle135/c135_sparse060",
        EXP / "generated-search-pedal-repair/cycle77/c77_per75",
    ],
    "crash": [
        EXP / "generated-search-crash-context/cycle141/c141_support_only",
        EXP / "generated-search-crash-consensus/cycle72/c72_head18",
    ],
    "ride": [
        EXP / "generated-search-ride-segment/cycle138/c138_seed3",
        EXP / "generated-search-ride-song-gate/cycle108/c108_per50",
    ],
}


@lru_cache(maxsize=None)
def rows(path, song):
    return [(t, g) for t, g, *_ in ev.midi_events(path / f"{song}.mid")]


@lru_cache(maxsize=None)
def meta(song):
    return json.loads((ROOT / "DruMaster/songs" / song / "song.json").read_text())


def near(xs, t, w):
    return any(abs(x - t) <= w for x in xs)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def timing(song, events):
    m = meta(song)
    bpm = float(m["bpm"])
    ts = m.get("timeSignature") or {"numerator": 4, "denominator": 4}
    num = int(ts.get("numerator", 4))
    den = int(ts.get("denominator", 4))
    beat = 60.0 / bpm * 4.0 / den
    bar = beat * num
    best = (-1.0, 0.0)
    for q in range(96):
        ph = bar * q / 96.0
        score = 0.0
        for t, g in events:
            if g not in ("kick", "snare"):
                continue
            w = 1.7 if g == "kick" else 0.8
            x = (t - ph) % bar
            d = min(x, bar - x)
            score += w * math.exp(-0.5 * (d / max(0.025, 0.10 * beat)) ** 2)
        if score > best[0]:
            best = (score, ph)
    return m, best[1], beat, bar


def slot(t, ph, bar, n=16):
    return int(round((((t - ph) % bar) / bar) * n)) % n


def barno(t, ph, bar):
    return math.floor((t - ph) / bar)


def rep_support(times, t, ph, bar, window=6, n=16):
    s = slot(t, ph, bar, n)
    b = barno(t, ph, bar)
    bars = set()
    for x in times:
        bx = barno(x, ph, bar)
        if abs(bx - b) <= window and slot(x, ph, bar, n) == s:
            bars.add(bx)
    return len(bars)


def downbeat_strength(t, ph, beat, bar):
    x = (t - ph) % bar
    d = min(x, bar - x)
    sigma = max(0.04, beat * 0.13)
    return math.exp(-0.5 * (d / sigma) ** 2)


def source_times(paths, song, group):
    return [[t for t, g in rows(path, song) if g == group] for path in paths]


def source_votes(source_lists, t, w=0.045):
    return sum(1 for xs in source_lists if near(xs, t, w))


def enforce(events):
    mins = {
        "kick": 0.045, "snare": 0.038, "hat": 0.035, "pedal_hat": 0.045,
        "tom": 0.050, "crash": 0.090, "ride": 0.045, "other": 0.040,
    }
    ded = []
    for g in GROUPS:
        arr = sorted(t for t, gg in events if gg == g)
        last = -999.0
        for t in arr:
            if t - last >= mins.get(g, 0.04):
                ded.append((t, g))
                last = t
    ded.sort()
    out = []
    i = 0
    pri = {"snare": 0.93, "tom": 0.88, "crash": 0.86, "ride": 0.84, "hat": 0.60}
    while i < len(ded):
        t = ded[i][0]
        j = i
        while j < len(ded) and ded[j][0] - t <= 0.033:
            j += 1
        c = ded[i:j]
        ex = [e for e in c if e[1] not in HANDS]
        h = [e for e in c if e[1] in HANDS]
        h = sorted(h, key=lambda e: pri.get(e[1], 0.5), reverse=True)[:2]
        out.extend(ex + h)
        i = j
    return sorted(out)


def snare_repair(song, events, policy):
    if policy == "base":
        return events
    _, ph, beat, bar = timing(song, events)
    snares = sorted(t for t, g in events if g == "snare")
    src = source_times(SNARE_SOURCES, song, "snare")
    gap = clamp(0.12 * beat, 0.040, 0.080)

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

    keep = []
    for c in clusters:
        if len(c) == 1:
            keep.extend(c)
            continue
        info = []
        for t in c:
            votes = source_votes(src, t)
            rep = rep_support(snares, t, ph, bar)
            score = 2.0 * votes + min(rep, 4) * 0.35
            info.append((score, votes, rep, t))
        info.sort(reverse=True)
        chosen = {info[0][3]}
        for score, votes, rep, t in info[1:]:
            if policy == "loose":
                ok = votes >= 1 or rep >= 3
            elif policy == "balanced":
                ok = votes >= 2 or (votes >= 1 and rep >= 4)
            else:
                ok = votes >= 3 or (votes >= 2 and rep >= 4)
            if ok:
                chosen.add(t)
        keep.extend(sorted(chosen))

    others = [e for e in events if e[1] != "snare"]
    return sorted(others + [(t, "snare") for t in keep])


def metal_gap(group, beat):
    factor = {"hat": 0.14, "pedal_hat": 0.18, "crash": 0.28, "ride": 0.16}[group]
    lo = {"hat": 0.040, "pedal_hat": 0.050, "crash": 0.095, "ride": 0.045}[group]
    hi = {"hat": 0.095, "pedal_hat": 0.125, "crash": 0.180, "ride": 0.110}[group]
    return clamp(factor * beat, lo, hi)


def metal_repair(song, events, policy):
    if policy == "base":
        return events
    _, ph, beat, bar = timing(song, events)
    out = [e for e in events if e[1] not in METAL]
    for g in ("hat", "pedal_hat", "crash", "ride"):
        arr = sorted(t for t, gg in events if gg == g)
        if not arr:
            continue
        src = source_times(METAL_SOURCES[g], song, g)
        gap = metal_gap(g, beat)
        kept = []
        for t in arr:
            if not kept or t - kept[-1] >= gap:
                kept.append(t)
                continue
            votes = source_votes(src, t)
            rep = rep_support(arr, t, ph, bar)
            down = downbeat_strength(t, ph, beat, bar)
            if policy == "refractory":
                rescue = False
            elif policy == "consensus":
                rescue = votes >= 2
            else:
                rescue = votes >= 2 or rep >= 4
                if g == "crash":
                    rescue = rescue or (votes >= 1 and down >= 0.72)
                elif g == "ride":
                    rescue = rescue or (votes >= 1 and rep >= 3)
            if rescue:
                kept.append(t)
        out.extend((t, g) for t in kept)
    return sorted(out)


def metal_priority(song, events, t, g, ph, beat, bar):
    src = source_times(METAL_SOURCES[g], song, g)
    votes = source_votes(src, t)
    arr = [x for x, gg in events if gg == g]
    rep = rep_support(arr, t, ph, bar)
    down = downbeat_strength(t, ph, beat, bar)
    if g == "crash":
        prior = 1.20 * down
    elif g == "ride":
        prior = 0.28 * min(rep, 4)
    else:
        prior = 0.18 * min(rep, 4)
    return 2.0 * votes + prior


def metal_arbitrate(song, events, policy, window=0.035):
    if policy == "base":
        return events
    _, ph, beat, bar = timing(song, events)
    other = [e for e in events if e[1] not in HAND_METAL]
    hm = sorted(e for e in events if e[1] in HAND_METAL)
    out = []
    i = 0
    while i < len(hm):
        t0 = hm[i][0]
        j = i + 1
        while j < len(hm) and hm[j][0] - t0 <= window:
            j += 1
        c = hm[i:j]
        classes = {g for _, g in c}
        if len(classes) <= 1:
            out.extend(c)
        else:
            ranked = sorted(
                [(metal_priority(song, events, t, g, ph, beat, bar), t, g) for t, g in c],
                reverse=True,
            )
            out.append((ranked[0][1], ranked[0][2]))
            if policy == "consensus" and len(ranked) > 1:
                score2, t2, g2 = ranked[1]
                src2 = source_times(METAL_SOURCES[g2], song, g2)
                if source_votes(src2, t2) >= 2 and score2 >= 0.72 * ranked[0][0]:
                    out.append((t2, g2))
        i = j
    return sorted(other + out)


def build(song, snare_policy, metal_policy, arb_policy, arb_window=0.035):
    e = rows(BASE, song)
    e = snare_repair(song, e, snare_policy)
    e = metal_repair(song, e, metal_policy)
    e = metal_arbitrate(song, e, arb_policy, arb_window)
    return enforce(e)


def write(path, events, bpm):
    base.write_midi(
        path,
        [{"time": t, "group": g, "score": 1.0, "confidence": 1.0} for t, g in events],
        bpm,
    )


def matched_flags(pred_times, truth_times, tol=0.08):
    used = set()
    flags = []
    for x in pred_times:
        opts = [i for i, y in enumerate(truth_times) if i not in used and abs(x - y) <= tol]
        if opts:
            k = min(opts, key=lambda i: abs(x - truth_times[i]))
            used.add(k)
            flags.append(True)
        else:
            flags.append(False)
    return flags


def retrigger_stat(pred, truth, shift, group, gap):
    p = sorted(t for t, g, *_ in pred if g == group)
    q = sorted(t + shift for t, g, *_ in truth if g == group)
    flags = matched_flags(p, q)
    pairs = 0
    unsupported = 0
    for i in range(1, len(p)):
        if p[i] - p[i - 1] <= gap:
            pairs += 1
            if not flags[i]:
                unsupported += 1
    return {"pairs": pairs, "unsupported": unsupported, "predicted": len(p)}


def overlap_clusters(pred, window=0.035):
    xs = sorted((t, g) for t, g, *_ in pred if g in HAND_METAL)
    count = 0
    i = 0
    while i < len(xs):
        t0 = xs[i][0]
        j = i + 1
        while j < len(xs) and xs[j][0] - t0 <= window:
            j += 1
        if len({g for _, g in xs[i:j]}) > 1:
            count += 1
        i = j
    return count


def evaluate(name, snare_policy, metal_policy, arb_policy, arb_window, outdir):
    result = {
        "snare_policy": snare_policy,
        "metal_policy": metal_policy,
        "arb_policy": arb_policy,
        "arb_window": arb_window,
        "songs": {},
    }
    tot = Counter()
    for song in SONGS:
        m = meta(song)
        events = build(song, snare_policy, metal_policy, arb_policy, arb_window)
        p = outdir / name / f"{song}.mid"
        write(p, events, float(m["bpm"]))
        pred = ev.midi_events(p)
        truth = ev.midi_events(ROOT / "DruMaster/songs" / song / "chart.mid")
        shift = m["playback"]["stemOffsetSec"] + m["playback"].get("midiOffsetSec", 0)
        sc = ev.score(pred, truth, shift)
        cf = ev.confusion(pred, truth, shift)
        sc["confusion"] = cf
        sc["count_ratio"] = ev.count_ratios(sc)

        _, _, beat, _ = timing(song, events)
        sret = retrigger_stat(pred, truth, shift, "snare", clamp(0.12 * beat, 0.040, 0.080))
        metal = {g: retrigger_stat(pred, truth, shift, g, metal_gap(g, beat)) for g in METAL}
        rr = {
            "snare": sret,
            "metal": metal,
            "metal_overlap_clusters": overlap_clusters(pred, arb_window),
        }
        sc["retrigger"] = rr
        result["songs"][song] = sc

        tot.update(
            tp=sc["tp"], predicted=sc["predicted"], reference=sc["reference"],
            kick_to_snare=cf["kick_to_snare"], snare_to_kick=cf["snare_to_kick"],
            snare_short_pairs=sret["pairs"], snare_retrigger_fp=sret["unsupported"],
            metal_overlap=rr["metal_overlap_clusters"],
        )
        for g, x in sc["by_group"].items():
            tot[f"{g}_tp"] += x["tp"]
            tot[f"{g}_pred"] += x["predicted"]
            tot[f"{g}_ref"] += x["reference"]
        for g, x in metal.items():
            tot["metal_short_pairs"] += x["pairs"]
            tot["metal_retrigger_fp"] += x["unsupported"]
            tot["metal_pred"] += x["predicted"]

    tp, n, mr = tot["tp"], tot["predicted"], tot["reference"]
    s = {
        "tp": tp, "predicted": n, "reference": mr,
        "precision": tp / n if n else 0,
        "recall": tp / mr if mr else 0,
        "f1": 2 * tp / (n + mr) if n + mr else 0,
        "kick_to_snare": tot["kick_to_snare"],
        "snare_to_kick": tot["snare_to_kick"],
        "two_limb_violations": 0,
        "by_group": {},
    }
    for g in GROUPS:
        a, b, c = tot[f"{g}_tp"], tot[f"{g}_pred"], tot[f"{g}_ref"]
        sf = []
        for song in SONGS:
            x = result["songs"][song]["by_group"].get(g, {})
            ref = x.get("reference", 0)
            if ref:
                sf.append(2 * x.get("tp", 0) / (x.get("predicted", 0) + ref) if x.get("predicted", 0) + ref else 0)
        s["by_group"][g] = {
            "tp": a, "predicted": b, "reference": c,
            "precision": a / b if b else 0,
            "recall": a / c if c else 0,
            "f1": 2 * a / (b + c) if b + c else 0,
            "false_discovery_rate": (b - a) / b if b else 0,
            "miss_rate": (c - a) / c if c else 0,
            "count_ratio": b / c if c else None,
            "mean_song_f1": sum(sf) / len(sf) if sf else None,
            "worst_song_f1": min(sf) if sf else None,
        }

    sn_pred = max(1, s["by_group"]["snare"]["predicted"])
    metal_pred = max(1, sum(s["by_group"][g]["predicted"] for g in METAL))
    s["retrigger"] = {
        "snare_short_gap_pairs": tot["snare_short_pairs"],
        "snare_retrigger_fp": tot["snare_retrigger_fp"],
        "snare_retrigger_fp_rate": tot["snare_retrigger_fp"] / sn_pred,
        "metal_short_gap_pairs": tot["metal_short_pairs"],
        "metal_retrigger_fp": tot["metal_retrigger_fp"],
        "metal_retrigger_fp_rate": tot["metal_retrigger_fp"] / metal_pred,
        "metal_overlap_clusters": tot["metal_overlap"],
        "metal_overlap_rate": tot["metal_overlap"] / metal_pred,
    }
    canonical = sel.score(s)
    rt = s["retrigger"]
    repair_score = (
        canonical["score"]
        - 0.08 * rt["snare_retrigger_fp_rate"]
        - 0.10 * rt["metal_retrigger_fp_rate"]
        - 0.03 * rt["metal_overlap_rate"]
    )
    result["summary"] = s
    result["canonical_score"] = canonical
    result["repair_score"] = round(repair_score, 6)
    result["detailed"] = detail.compare_dir(outdir / name, name)["aggregate"]
    return result


def choose(candidates, baseline, targets, max_drop=0.035, target_tolerance=0.012):
    ranking = []
    guards = {}
    for name, obj in candidates.items():
        guard = sel.eligibility(
            obj["summary"], baseline["summary"], target_parts=targets,
            max_part_drop=max_drop, target_tolerance=target_tolerance,
        )
        obj["guard"] = guard
        guards[name] = guard
        ranking.append((guard["eligible"], obj["repair_score"], obj["summary"]["f1"], name))
    ranking.sort(reverse=True)
    winner = next((name for ok, _, _, name in ranking if ok), None)
    return {"winner": winner, "ranking": [x[3] for x in ranking], "guards": guards}


def main():
    root = EXP / "generated-search-overtrigger-repair"
    report = {
        "schema": 1,
        "description": "Cycles 151-153: direct repair of snare/cymbal over-trigger and retrigger errors.",
        "selection": "canonical score plus explicit unsupported-retrigger penalties",
        "cycles": [],
    }

    baseline = evaluate("baseline", "base", "base", "base", 0.035, root / "baseline")
    print("BASELINE", json.dumps({"summary": baseline["summary"], "repair_score": baseline["repair_score"]}, ensure_ascii=False), flush=True)

    res = {}
    for name, policy in [
        ("c151_base", "base"),
        ("c151_loose", "loose"),
        ("c151_balanced", "balanced"),
        ("c151_strict", "strict"),
    ]:
        res[name] = evaluate(name, policy, "base", "base", 0.035, root / "cycle151")
        print("SUMMARY", name, json.dumps({"f1": res[name]["summary"]["f1"], "snare": res[name]["summary"]["by_group"]["snare"], "retrigger": res[name]["summary"]["retrigger"], "repair_score": res[name]["repair_score"]}, ensure_ascii=False), flush=True)
    d = choose(res, baseline, ("snare",), 0.030, 0.015)
    win = d["winner"] or "c151_base"
    best = res[win]
    report["cycles"].append({"cycle": 151, "candidates": res, "winner": win, "ranking": d["ranking"], "guards": d["guards"]})
    print("DECISION151", json.dumps(d, ensure_ascii=False), flush=True)

    res = {}
    for name, policy in [
        ("c152_base", "base"),
        ("c152_refractory", "refractory"),
        ("c152_consensus", "consensus"),
        ("c152_rhythm", "rhythm"),
    ]:
        res[name] = evaluate(name, best["snare_policy"], policy, "base", 0.035, root / "cycle152")
        print("SUMMARY", name, json.dumps({"f1": res[name]["summary"]["f1"], "metal": {g: res[name]["summary"]["by_group"][g] for g in METAL}, "retrigger": res[name]["summary"]["retrigger"], "repair_score": res[name]["repair_score"]}, ensure_ascii=False), flush=True)
    d = choose(res, best, ("hat", "pedal_hat", "crash", "ride"), 0.040, 0.020)
    win = d["winner"] or "c152_base"
    best = res[win]
    report["cycles"].append({"cycle": 152, "candidates": res, "winner": win, "ranking": d["ranking"], "guards": d["guards"]})
    print("DECISION152", json.dumps(d, ensure_ascii=False), flush=True)

    res = {}
    for name, policy, window in [
        ("c153_base", "base", 0.035),
        ("c153_single30", "single", 0.030),
        ("c153_consensus35", "consensus", 0.035),
        ("c153_consensus45", "consensus", 0.045),
    ]:
        res[name] = evaluate(name, best["snare_policy"], best["metal_policy"], policy, window, root / "cycle153")
        print("SUMMARY", name, json.dumps({"f1": res[name]["summary"]["f1"], "metal": {g: res[name]["summary"]["by_group"][g] for g in METAL}, "retrigger": res[name]["summary"]["retrigger"], "repair_score": res[name]["repair_score"]}, ensure_ascii=False), flush=True)
    d = choose(res, best, ("hat", "crash", "ride"), 0.040, 0.020)
    win = d["winner"] or "c153_base"
    best = res[win]
    report["cycles"].append({"cycle": 153, "candidates": res, "winner": win, "ranking": d["ranking"], "guards": d["guards"]})
    print("DECISION153", json.dumps(d, ensure_ascii=False), flush=True)

    report["final"] = {
        "winner": win,
        "summary": best["summary"],
        "canonical_score": best["canonical_score"],
        "repair_score": best["repair_score"],
        "guard": best["guard"],
        "snare_policy": best["snare_policy"],
        "metal_policy": best["metal_policy"],
        "arb_policy": best["arb_policy"],
        "arb_window": best["arb_window"],
        "detailed": best["detailed"],
    }
    (EXP / "results-iterative-overtrigger-repair.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\\n")
    print("FINAL", json.dumps(report["final"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
