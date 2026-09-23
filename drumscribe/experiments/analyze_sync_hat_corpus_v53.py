#!/usr/bin/env python3
"""Analyze synchronized drum WAV/MIDI pairs for hi-hat articulation.

This is an offline teacher/validation tool. It never participates in prediction
runtime and must not read reference MIDI during normal transcription.

Example:
  python analyze_sync_hat_corpus_v53.py \
    --pair kaiju path/to/kaiju.wav path/to/kaiju.mid \
    --pair arcaround path/to/arcaround.wav path/to/arcaround.mid \
    --pair ray path/to/ray.wav path/to/ray.mid \
    --out results-sync-hat-corpus-v53.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import mido
import numpy as np
import pandas as pd
import soundfile as sf
from numpy.fft import rfft, rfftfreq
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

WINDOWS = {
    "pre": (-0.040, 0.000),
    "attack": (0.000, 0.035),
    "early": (0.040, 0.090),
    "mid": (0.090, 0.160),
    "late": (0.160, 0.250),
    "tail1": (0.250, 0.400),
    "tail2": (0.400, 0.600),
}
BANDS = {
    "low": (100, 1200),
    "midband": (1200, 5000),
    "high": (5000, 18000),
    "air": (10000, 20000),
}
NOTE_NAME = {42: "closed", 44: "pedal", 46: "open", 51: "ride", 53: "ride", 59: "ride"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def midi_note_events(path: Path):
    mid = mido.MidiFile(path)
    tempo = 500000
    sec = 0.0
    out = []
    for msg in mido.merge_tracks(mid.tracks):
        sec += mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
        if msg.type == "set_tempo":
            tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0:
            out.append({"time": sec, "note": msg.note, "velocity": msg.velocity})
    return mid.ticks_per_beat, out


def segment_features(x: np.ndarray, sr: int, start: float, end: float):
    i0 = max(0, int(round(start * sr)))
    i1 = min(len(x), int(round(end * sr)))
    seg = x[i0:i1].astype(np.float64, copy=False)
    if len(seg) < 16:
        return {**{f"{k}_e": 0.0 for k in BANDS}, "rms": 0.0, "peak": 0.0, "zcr": 0.0, "centroid": 0.0}
    seg = seg - np.mean(seg)
    rms = float(np.sqrt(np.mean(seg * seg) + 1e-15))
    peak = float(np.max(np.abs(seg)) + 1e-12)
    zcr = float(np.mean(seg[1:] * seg[:-1] < 0)) if len(seg) > 1 else 0.0
    n = 1 << (len(seg) - 1).bit_length()
    spec = np.abs(rfft(seg * np.hanning(len(seg)), n=n)) ** 2
    freqs = rfftfreq(n, 1 / sr)
    total = float(spec.sum() + 1e-18)
    out = {}
    for key, (lo, hi) in BANDS.items():
        out[f"{key}_e"] = float(spec[(freqs >= lo) & (freqs < hi)].sum() / total)
    out.update(rms=rms, peak=peak, zcr=zcr, centroid=float((freqs * spec).sum() / total))
    return out


def extract_pair(name: str, wav_path: Path, midi_path: Path):
    audio, sr = sf.read(wav_path, dtype="float32", always_2d=True)
    x = audio.mean(axis=1)
    info = sf.info(wav_path)
    tpq, events = midi_note_events(midi_path)
    hats = sorted([e for e in events if e["note"] in NOTE_NAME], key=lambda e: e["time"])
    rows = []
    for i, e in enumerate(hats):
        t = e["time"]
        row = {"song": name, "index": i, "time": t, "note": e["note"], "label": NOTE_NAME[e["note"]], "velocity": e["velocity"]}
        for window, (a, b) in WINDOWS.items():
            for key, value in segment_features(x, sr, t + a, t + b).items():
                row[f"{window}_{key}"] = value
        nxt = hats[i + 1] if i + 1 < len(hats) else None
        if nxt:
            row["next_gap"] = nxt["time"] - t
            row["next_label"] = NOTE_NAME[nxt["note"]]
            for window, a, b in (("pre_next", -0.060, -0.015), ("post_next", 0.060, 0.180)):
                for key, value in segment_features(x, sr, nxt["time"] + a, nxt["time"] + b).items():
                    row[f"{window}_{key}"] = value
        else:
            row["next_gap"] = np.nan
            row["next_label"] = "end"
        rows.append(row)
    df = pd.DataFrame(rows)
    eps = 1e-9
    for band in ("rms", "high_e", "air_e", "centroid"):
        attack = df[f"attack_{band}"].to_numpy()
        for window in ("early", "mid", "late", "tail1", "tail2", "pre_next", "post_next"):
            col = f"{window}_{band}"
            if col in df:
                df[f"{window}_to_attack_{band}"] = np.log1p(np.maximum(df[col].to_numpy(), 0) / (np.maximum(attack, 0) + eps))
    df["choke_high_logratio"] = np.log((df["post_next_high_e"] + eps) / (df["pre_next_high_e"] + eps))
    df["persistence_high"] = np.log1p((df["pre_next_high_e"] + eps) / (df["attack_high_e"] + eps))

    counts = Counter(row["label"] for row in rows)
    transitions = Counter()
    for a, b in zip(rows, rows[1:]):
        transitions[(a["label"], b["label"])] += 1
    meta = {
        "wav_bytes": wav_path.stat().st_size,
        "mid_bytes": midi_path.stat().st_size,
        "wav_sha256": sha256_file(wav_path),
        "mid_sha256": sha256_file(midi_path),
        "samplerate": info.samplerate,
        "channels": info.channels,
        "frames": info.frames,
        "duration": info.duration,
        "tpq": tpq,
        "hat_counts": dict(counts),
        "open_next": {k: transitions[("open", k)] for k in ("open", "closed", "pedal", "ride")},
    }
    return df, meta


def metric(y, pred, prob):
    precision, recall, f1, _ = precision_recall_fscore_support(y, pred, average="binary", zero_division=0)
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "accuracy": float(np.mean(np.asarray(y) == np.asarray(pred))),
        "auc": float(roc_auc_score(y, prob)) if len(set(y)) > 1 else None,
        "cm": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
        "n": int(len(y)),
        "open_ref": int(np.sum(y)),
        "open_pred": int(np.sum(pred)),
    }


def high_gap_threshold(prob, floor=0.35, ceiling=0.98):
    values = np.sort(prob[(prob >= floor) & (prob <= ceiling)])
    if len(values) < 4:
        return 0.60
    gaps = np.diff(values)
    i = int(np.argmax(gaps))
    return float((values[i] + values[i + 1]) / 2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", nargs=3, action="append", metavar=("NAME", "WAV", "MIDI"), required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    frames = []
    pairs = {}
    for name, wav, midi in args.pair:
        df, meta = extract_pair(name, Path(wav), Path(midi))
        frames.append(df)
        pairs[name] = meta
    all_df = pd.concat(frames, ignore_index=True)
    binary = all_df[all_df["label"].isin(["closed", "open"])].copy()
    binary["y"] = (binary["label"] == "open").astype(int)

    exclude = {"song", "index", "time", "note", "label", "next_label", "y"}
    context_cols = [c for c in binary.columns if c not in exclude and pd.api.types.is_numeric_dtype(binary[c])]
    local_cols = [c for c in context_cols if not c.startswith(("pre_next_", "post_next_")) and c not in {"next_gap", "choke_high_logratio", "persistence_high"}]

    hypotheses = {
        "H1_local_logistic": (
            local_cols,
            Pipeline([("imp", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                      ("model", LogisticRegression(max_iter=2000, class_weight="balanced"))]),
            "fixed",
        ),
        "H2_context_extratrees_fixed_050": (
            context_cols,
            Pipeline([("imp", SimpleImputer(strategy="median")),
                      ("model", ExtraTreesClassifier(n_estimators=240, max_depth=12, min_samples_leaf=4,
                                                     class_weight="balanced", max_features="sqrt",
                                                     random_state=42, n_jobs=-1))]),
            "fixed",
        ),
        "H4_context_extratrees_high_gap": (
            context_cols,
            Pipeline([("imp", SimpleImputer(strategy="median")),
                      ("model", ExtraTreesClassifier(n_estimators=240, max_depth=12, min_samples_leaf=4,
                                                     class_weight="balanced", max_features="sqrt",
                                                     random_state=42, n_jobs=-1))]),
            "high_gap",
        ),
    }

    results = {}
    for hname, (cols, model, threshold_mode) in hypotheses.items():
        rows = {}
        all_y, all_pred, all_prob = [], [], []
        for held in sorted(binary["song"].unique()):
            train = binary[binary["song"] != held]
            test = binary[binary["song"] == held].sort_values("time")
            model.fit(train[cols], train["y"])
            prob = model.predict_proba(test[cols])[:, 1]
            threshold = high_gap_threshold(prob) if threshold_mode == "high_gap" else 0.50
            pred = (prob >= threshold).astype(int)
            rows[held] = {"threshold": threshold, **metric(test["y"].to_numpy(), pred, prob)}
            all_y.extend(test["y"].tolist())
            all_pred.extend(pred.tolist())
            all_prob.extend(prob.tolist())
        results[hname] = {"per_song": rows, "aggregate": metric(np.array(all_y), np.array(all_pred), np.array(all_prob))}

    output = {
        "schema": 1,
        "experiment": "sync-hat-corpus-v53",
        "scope": "oracle synchronized hat-event articulation study; not full production onset transcription",
        "pairs": pairs,
        "hypotheses": results,
        "conclusion": {
            "reference_midi_policy": "used only for offline teacher extraction and scoring",
            "production_status": "research only until applied to actual browser-detected candidates",
        },
    }
    Path(args.out).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
