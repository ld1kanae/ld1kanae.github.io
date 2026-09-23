import json
from collections import Counter
from pathlib import Path

import mido

DATA = Path("drumscribe/experiments/gmd-triplet-heldout-v32")
MANIFEST = json.loads((DATA / "manifest.json").read_text())
GENERATED = DATA / "generated"
RESULT = Path("drumscribe/experiments/results-gmd-triplet-heldout-v32.json")


def weight(note):
    if note in {35, 36, 37, 38, 39, 40}:
        return 3.0
    if note in {41, 43, 45, 47, 48, 50}:
        return 1.7
    if note in {49, 51, 52, 53, 55, 57, 58, 59}:
        return 1.25
    return 0.75


def distance_to_grid(q, step):
    r = q % step
    return min(r, step - r)


def reference_evidence(path):
    mid = mido.MidiFile(path)
    tick = 0
    notes = []
    for msg in mido.merge_tracks(mid.tracks):
        tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            notes.append((tick / mid.ticks_per_beat, msg.note, weight(msg.note)))
    total = sum(w for _, _, w in notes) or 1.0
    residuals = {}
    for name, step in (("straight16", 0.25), ("straight32", 0.125), ("triplet8", 1 / 3), ("triplet16", 1 / 6)):
        vals = sorted((distance_to_grid(q, step), w) for q, _, w in notes)
        weighted_mean = sum(d * w for d, w in vals) / total
        acc = 0.0
        median = None
        p95 = None
        for d, w in vals:
            acc += w
            if median is None and acc >= total * 0.5:
                median = d
            if p95 is None and acc >= total * 0.95:
                p95 = d
                break
        residuals[name] = {"weighted_mean_beats": weighted_mean, "median_beats": median or 0.0, "p95_beats": p95 or 0.0}
    triplet_only = sum(w for q, _, w in notes if min(distance_to_grid(q, 1/3), distance_to_grid(q, 1/6)) <= 0.035 and distance_to_grid(q, 0.25) >= 0.055) / total
    straight_only = sum(w for q, _, w in notes if distance_to_grid(q, 0.25) <= 0.035 and min(distance_to_grid(q, 1/3), distance_to_grid(q, 1/6)) >= 0.055) / total
    return {"notes": len(notes), "weighted_notes": total, "residuals": residuals, "triplet_only_share": triplet_only, "straight_only_share": straight_only}


def generated_midi_stats(path, subdivision):
    mid = mido.MidiFile(path)
    tick = 0
    note_ticks = []
    tempo_events = 0
    for msg in mido.merge_tracks(mid.tracks):
        tick += msg.time
        if msg.type == "set_tempo":
            tempo_events += 1
        elif msg.type == "note_on" and msg.velocity > 0:
            note_ticks.append(tick)
    quantum = {"1/16": mid.ticks_per_beat // 4, "1/16+1/32": mid.ticks_per_beat // 8, "1/32": mid.ticks_per_beat // 8, "1/8T": mid.ticks_per_beat // 3, "1/16T": mid.ticks_per_beat // 6}.get(subdivision)
    if not quantum:
        return {"notes": len(note_ticks), "tempo_events": tempo_events, "grid_quantum_ticks": None, "max_grid_residual_ticks": None}
    residuals = []
    for t in note_ticks:
        r = t % quantum
        residuals.append(min(r, quantum - r))
    return {"notes": len(note_ticks), "tempo_events": tempo_events, "grid_quantum_ticks": quantum, "max_grid_residual_ticks": max(residuals, default=0)}


out = {
    "schema": 2,
    "experiment": "gmd-triplet-heldout-v32",
    "prediction_rule": "Reference MIDI is used to select and label held-out cases, but is read by the scorer only after browser transcription. auto uses audio only; oracle_bpm supplies metadata BPM only.",
    "cases": [],
}

for item in MANIFEST["cases"]:
    evidence = reference_evidence(item["local_midi"])
    case = {"item": item, "reference_evidence": evidence, "modes": {}}
    expected = item["expected_family_from_reference"]
    for mode in ("auto", "oracle_bpm"):
        stem = f"{item['case_id']}-{mode}"
        payload = json.loads((GENERATED / f"{stem}.json").read_text())
        timing = payload.get("timing") or {}
        info = timing.get("rhythmGridInfo") or {}
        family = info.get("family")
        subdivision = info.get("subdivision")
        midi_stats = generated_midi_stats(GENERATED / f"{stem}.mid", subdivision)
        case["modes"][mode] = {
            "family": family,
            "subdivision": subdivision,
            "correct_vs_reference": family == expected,
            "bpm": timing.get("bpm"),
            "bpm_ratio_to_metadata": (timing.get("bpm") / item["bpm"]) if timing.get("bpm") and item.get("bpm") else None,
            "fit": info.get("fit"),
            "tempo_events_reported": info.get("tempoEvents"),
            "tempo_min": info.get("tempoMin"),
            "tempo_max": info.get("tempoMax"),
            "straight16_share": info.get("straight16Share"),
            "straight32_only_share": info.get("straight32OnlyShare"),
            "preview_median_difference_ms": info.get("previewMedianDifferenceMs"),
            "preview_p95_difference_ms": info.get("previewP95DifferenceMs"),
            "midi": midi_stats,
        }
    out["cases"].append(case)

summary = {}
for mode in ("auto", "oracle_bpm"):
    counts = Counter()
    errors = []
    for case in out["cases"]:
        expected = case["item"]["expected_family_from_reference"]
        result = case["modes"][mode]
        predicted = result["family"]
        counts["total"] += 1
        counts["correct"] += predicted == expected
        counts[f"expected_{expected}"] += 1
        counts[f"expected_{expected}_correct"] += predicted == expected
        if predicted != expected:
            errors.append({"case_id": case["item"]["case_id"], "style": case["item"]["style"], "expected": expected, "predicted": predicted, "bpm": result["bpm"], "reference_bpm": case["item"]["bpm"], "fit": result["fit"]})
    summary[mode] = {
        "total": counts["total"],
        "accuracy_vs_reference": counts["correct"] / max(1, counts["total"]),
        "triplet_cases": counts["expected_triplet"],
        "triplet_recall": counts["expected_triplet_correct"] / max(1, counts["expected_triplet"]),
        "straight_controls": counts["expected_straight"],
        "straight_control_accuracy": counts["expected_straight_correct"] / max(1, counts["expected_straight"]),
        "max_generated_grid_residual_ticks": max((c["modes"][mode]["midi"]["max_grid_residual_ticks"] or 0) for c in out["cases"]),
        "errors": errors,
    }
out["summary"] = summary
RESULT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(summary, ensure_ascii=False, indent=2))
