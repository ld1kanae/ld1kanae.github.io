#!/usr/bin/env python3
"""Train a conservative GMD bar-phase rotation model.

Training:
- Google Magenta Groove MIDI Dataset v1.0.0
- official TRAIN split only
- model-family selection on a deterministic internal TRAIN holdout
- official validation/test are report-only

The model scores K/S/T occupancy under candidate 4/4 bar phases. It never
creates or moves notes; the browser runtime may only use it to choose among
metrical phase hypotheses already supported by acoustic events.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

import mido
import numpy as np
from sklearn.linear_model import LogisticRegression

GMD_URL = "https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0-midionly.zip"
GMD_SHA256 = "651cbc524ffb891be1a3e46d89dc82a1cecb09a57c748c7b45b844c4841dcc1e"
VERSION = "gmd-kst-bar-phase-discriminative-v1"
GROUP_INDEX = {
    36: 0,
    37: 1, 38: 1, 40: 1,
    43: 2, 45: 2, 47: 2, 48: 2, 50: 2, 58: 2,
}
GROUPS = ["kick", "snare", "tom"]
SLOTS = 16
DIM = 48


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and sha256(out) == GMD_SHA256:
        return
    urllib.request.urlretrieve(url, out)
    actual = sha256(out)
    if actual != GMD_SHA256:
        raise RuntimeError(f"GMD SHA256 mismatch: {actual}")


def extract(archive: Path, out_dir: Path) -> Path:
    infos = list(out_dir.rglob("info.csv")) if out_dir.exists() else []
    if infos:
        return infos[0].parent
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(out_dir)
    infos = list(out_dir.rglob("info.csv"))
    if not infos:
        raise RuntimeError("GMD info.csv not found")
    return infos[0].parent


def parse_sig(raw: str) -> tuple[int, int]:
    try:
        n, d = raw.replace("/", "-").split("-", 1)
        return int(n), int(d)
    except Exception:
        return 4, 4


def bar_features(path: Path, numerator: int, denominator: int) -> list[np.ndarray]:
    if (numerator, denominator) != (4, 4):
        return []
    midi = mido.MidiFile(path)
    tpq = midi.ticks_per_beat
    if not tpq:
        return []
    bars: dict[int, np.ndarray] = defaultdict(lambda: np.zeros(DIM, dtype=np.float64))
    hit_count = defaultdict(int)
    abs_tick = 0
    for msg in mido.merge_tracks(midi.tracks):
        abs_tick += msg.time
        if msg.type != "note_on" or getattr(msg, "velocity", 0) <= 0:
            continue
        gi = GROUP_INDEX.get(int(msg.note))
        if gi is None:
            continue
        q = abs_tick / tpq
        bar = int(math.floor((q + 1e-9) / 4.0))
        pos = q - 4.0 * bar
        slot = int(round(pos * 4.0)) % SLOTS
        bars[bar][gi * SLOTS + slot] = 1.0
        hit_count[bar] += 1
    out = []
    for b in sorted(bars):
        x = bars[b]
        if hit_count[b] < 2 or np.count_nonzero(x) < 2:
            continue
        out.append(x)
    return out


def rotate(x: np.ndarray, slot_shift: int) -> np.ndarray:
    y = np.zeros_like(x)
    for g in range(3):
        row = x[g*SLOTS:(g+1)*SLOTS]
        y[g*SLOTS:(g+1)*SLOTS] = np.roll(row, -slot_shift)
    return y


def read_rows(root: Path) -> list[dict]:
    with (root / "info.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def internal_dev(name: str) -> bool:
    h = hashlib.sha1(name.encode("utf-8")).digest()
    return h[0] % 5 == 0


def load_performances(root: Path, rows: list[dict]):
    data = {"train_fit": [], "train_dev": [], "validation": [], "test": []}
    skipped = defaultdict(int)
    for row in rows:
        split = (row.get("split") or "").strip()
        if split not in ("train", "validation", "test"):
            continue
        n, d = parse_sig(row.get("time_signature") or "4-4")
        if (n, d) != (4, 4):
            skipped[f"{split}_meter"] += 1
            continue
        path = root / row["midi_filename"]
        bars = bar_features(path, n, d)
        if len(bars) < 2:
            skipped[f"{split}_sparse"] += 1
            continue
        item = {
            "name": row["midi_filename"],
            "style": (row.get("style") or "").strip().lower(),
            "bpm": float(row.get("bpm") or 0),
            "bars": bars,
        }
        key = ("train_dev" if internal_dev(item["name"]) else "train_fit") if split == "train" else split
        data[key].append(item)
    return data, dict(skipped)


def fit_phase_logp(perfs: list[dict]):
    counts = np.ones(DIM, dtype=np.float64) * 0.5
    group_total = np.ones(3, dtype=np.float64) * (0.5 * SLOTS)
    for p in perfs:
        for x in p["bars"]:
            counts += x
            for g in range(3):
                group_total[g] += x[g*SLOTS:(g+1)*SLOTS].sum()
    weights = np.zeros(DIM)
    for g in range(3):
        probs = counts[g*SLOTS:(g+1)*SLOTS] / max(group_total[g], 1e-9)
        probs = np.maximum(probs, 1e-8)
        weights[g*SLOTS:(g+1)*SLOTS] = np.log(probs)
    return weights, 0.0


def fit_bernoulli(perfs: list[dict]):
    xs = [x for p in perfs for x in p["bars"]]
    X = np.stack(xs) if xs else np.zeros((0, DIM))
    n = len(X)
    present = X.sum(axis=0) if n else np.zeros(DIM)
    p = (present + 2.0) / (n + 4.0)
    p = np.clip(p, 1e-5, 1 - 1e-5)
    weights = np.log(p / (1 - p))
    intercept = float(np.log(1 - p).sum())
    return weights, intercept


def fit_logistic(perfs: list[dict]):
    X, y = [], []
    for p in perfs:
        for x in p["bars"]:
            X.append(x); y.append(1)
            for shift in (4, 8, 12):
                X.append(rotate(x, shift)); y.append(0)
    X = np.stack(X)
    y = np.asarray(y)
    clf = LogisticRegression(
        C=0.35,
        solver="liblinear",
        class_weight="balanced",
        max_iter=1000,
        random_state=23,
    )
    clf.fit(X, y)
    return clf.coef_[0].astype(np.float64), float(clf.intercept_[0])


def score_x(x: np.ndarray, weights: np.ndarray, intercept: float) -> float:
    return float(intercept + np.dot(x, weights))


def eval_model(perfs: list[dict], weights: np.ndarray, intercept: float):
    bar_ok = 0
    bar_total = 0
    perf_ok = 0
    margins = []
    details = []
    for p in perfs:
        sums = np.zeros(4, dtype=np.float64)
        used = 0
        for x in p["bars"]:
            scores = [score_x(rotate(x, shift), weights, intercept) for shift in (0, 4, 8, 12)]
            pred = int(np.argmax(scores))
            bar_ok += int(pred == 0)
            bar_total += 1
            sums += scores
            used += 1
        if not used:
            continue
        means = sums / used
        order = np.argsort(means)[::-1]
        pred = int(order[0])
        margin = float(means[order[0]] - means[order[1]])
        perf_ok += int(pred == 0)
        margins.append((margin, pred == 0))
        details.append({
            "name": p["name"],
            "style": p["style"],
            "bpm": p["bpm"],
            "bars": used,
            "prediction_rotation_beats": pred,
            "margin": margin,
            "scores": [float(v) for v in means],
        })
    return {
        "bars": bar_total,
        "bar_accuracy": bar_ok / bar_total if bar_total else 0.0,
        "performances": len(details),
        "performance_accuracy": perf_ok / len(details) if details else 0.0,
        "margins": margins,
        "details": details,
    }


def margin_gate(rows):
    if not rows:
        return 0.25
    vals = sorted({float(m) for m, _ in rows})
    best = None
    for t in vals:
        acc = [ok for m, ok in rows if m >= t]
        if len(acc) < max(5, int(len(rows) * 0.20)):
            continue
        precision = sum(acc) / len(acc)
        if precision >= 0.98:
            cand = (len(acc), -t, t, precision)
            if best is None or cand > best:
                best = cand
    if best:
        return float(best[2])
    correct = sorted(m for m, ok in rows if ok)
    return float(correct[len(correct)//2]) if correct else 0.25


def compact_eval(ev: dict):
    return {
        "bars": ev["bars"],
        "bar_accuracy": ev["bar_accuracy"],
        "performances": ev["performances"],
        "performance_accuracy": ev["performance_accuracy"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default=".cache/gmd-bar-phase")
    ap.add_argument("--output-model", default="drumscribe/models/gmd-kst/bar-phase-discriminative-v1.json")
    ap.add_argument("--output-results", default="drumscribe/experiments/gmd-kst/results-gmd-bar-phase-heldout-v1.json")
    args = ap.parse_args()

    cache = Path(args.cache_dir)
    archive = cache / "groove-v1.0.0-midionly.zip"
    download(GMD_URL, archive)
    root = extract(archive, cache / "groove-v1.0.0-midionly")
    perfs, skipped = load_performances(root, read_rows(root))

    fit = perfs["train_fit"]
    dev = perfs["train_dev"]
    hypotheses = {}
    fitters = {
        "phase_log_probability": fit_phase_logp,
        "bernoulli_presence": fit_bernoulli,
        "logistic_rotation": fit_logistic,
    }
    fitted = {}
    for name, fn in fitters.items():
        w, b = fn(fit)
        ev = eval_model(dev, w, b)
        hypotheses[name] = compact_eval(ev)
        fitted[name] = (w, b, ev)
        print(name, json.dumps(hypotheses[name], sort_keys=True), flush=True)

    selected = max(
        hypotheses,
        key=lambda name: (
            hypotheses[name]["performance_accuracy"],
            hypotheses[name]["bar_accuracy"],
            1 if name == "logistic_rotation" else 0,
        ),
    )
    min_margin = margin_gate(fitted[selected][2]["margins"])

    all_train = fit + dev
    final_w, final_b = fitters[selected](all_train)
    official = {
        split: eval_model(perfs[split], final_w, final_b)
        for split in ("validation", "test")
    }

    model = {
        "version": VERSION,
        "source": {
            "dataset": "Google Magenta Groove MIDI Dataset",
            "dataset_version": "1.0.0",
            "archive": "groove-v1.0.0-midionly.zip",
            "url": GMD_URL,
            "sha256": GMD_SHA256,
            "license": "CC BY 4.0",
            "training_split": "train",
            "selection_split": "deterministic internal 20% of train",
            "official_validation_test_usage": "report-only",
        },
        "scope": {
            "meter": "4/4",
            "groups": GROUPS,
            "slots_per_bar": SLOTS,
            "feature": "binary K/S/T occupancy on 16th-note positions",
            "candidate_search": "bar-phase hypotheses; model only ranks phase and never creates/moves notes",
        },
        "selected_hypothesis": selected,
        "weights": [float(v) for v in final_w],
        "intercept": float(final_b),
        "recommended_min_margin": float(min_margin),
        "internal_train_holdout": hypotheses,
        "official_heldout": {k: compact_eval(v) for k, v in official.items()},
        "counts": {
            "train_fit_performances": len(fit),
            "train_dev_performances": len(dev),
            "validation_performances": len(perfs["validation"]),
            "test_performances": len(perfs["test"]),
            "train_bars": sum(len(p["bars"]) for p in all_train),
        },
    }

    out_model = Path(args.output_model)
    out_model.parent.mkdir(parents=True, exist_ok=True)
    out_model.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    results = {
        "version": VERSION,
        "selected_hypothesis": selected,
        "recommended_min_margin": min_margin,
        "internal_train_holdout": hypotheses,
        "official_heldout": {
            k: {
                **compact_eval(v),
                "details": v["details"],
            }
            for k, v in official.items()
        },
        "skipped": skipped,
    }
    out_results = Path(args.output_results)
    out_results.parent.mkdir(parents=True, exist_ok=True)
    out_results.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "selected": selected,
        "min_margin": min_margin,
        "internal": hypotheses[selected],
        "validation": compact_eval(official["validation"]),
        "test": compact_eval(official["test"]),
    }, indent=2))


if __name__ == "__main__":
    main()
