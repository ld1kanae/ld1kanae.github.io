#!/usr/bin/env python3
"""Build a reproducible genre-aware GMD K/S/T knowledge base.

Production knowledge is derived from the official GMD TRAIN split only.
Validation/test are summarized separately and never used to tune the knowledge
asset. DruMaster data is not read by this script.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import mido

GMD_URL = "https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0-midionly.zip"
GMD_SHA256 = "651cbc524ffb891be1a3e46d89dc82a1cecb09a57c748c7b45b844c4841dcc1e"
VERSION = "gmd-kst-knowledge-v1"

PITCH_GROUP = {
    36: "kick",
    37: "snare",
    38: "snare",
    40: "snare",
    43: "tom",
    45: "tom",
    47: "tom",
    48: "tom",
    50: "tom",
    58: "tom",
}
GROUP_ORDER = ("kick", "snare", "tom")
MASK_NAME = {
    1: "K",
    2: "S",
    3: "K+S",
    4: "T",
    5: "K+T",
    6: "S+T",
    7: "K+S+T",
}
VELOCITY_BINS = ((1, 31), (32, 63), (64, 95), (96, 127))


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


def extract_if_needed(archive: Path, out_dir: Path) -> Path:
    marker = out_dir / ".gmd-extracted"
    if marker.exists():
        roots = list(out_dir.rglob("info.csv"))
        if roots:
            return roots[0].parent
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(out_dir)
    infos = list(out_dir.rglob("info.csv"))
    if not infos:
        raise RuntimeError("info.csv not found after extracting GMD")
    marker.write_text("ok\n", encoding="utf-8")
    return infos[0].parent


def parse_signature(raw: str) -> tuple[int, int]:
    try:
        n, d = raw.strip().replace("/", "-").split("-", 1)
        n, d = int(n), int(d)
        if n > 0 and d > 0:
            return n, d
    except Exception:
        pass
    return 4, 4


def tempo_band(bpm: float) -> str:
    if bpm < 90:
        return "lt90"
    if bpm < 120:
        return "90-119"
    if bpm < 150:
        return "120-149"
    if bpm < 180:
        return "150-179"
    return "ge180"


def velocity_bin(v: int) -> str:
    for lo, hi in VELOCITY_BINS:
        if lo <= v <= hi:
            return f"{lo:03d}-{hi:03d}"
    return "unknown"


class Aggregate:
    def __init__(self) -> None:
        self.rows = 0
        self.duration_sec = 0.0
        self.bpms: list[float] = []
        self.hits = Counter()
        self.phase = {g: Counter() for g in GROUP_ORDER}
        self.phase_denominator = Counter()
        self.cooccurrence = Counter()
        self.transitions = Counter()
        self.velocity_hist = {g: Counter() for g in GROUP_ORDER}
        self.velocity_sum = Counter()
        self.velocity_count = Counter()

    def add_row(self, *, bpm: float, duration: float) -> None:
        self.rows += 1
        self.duration_sec += max(0.0, duration)
        if math.isfinite(bpm) and bpm > 0:
            self.bpms.append(bpm)

    def add_hit(self, group: str, slot: int, slots_per_bar: int, velocity: int) -> None:
        self.hits[group] += 1
        self.phase[group][str(slot)] += 1
        self.phase_denominator[str(slots_per_bar)] += 1
        self.velocity_hist[group][velocity_bin(velocity)] += 1
        self.velocity_sum[group] += velocity
        self.velocity_count[group] += 1

    def add_slot_sequence(self, masks: list[int]) -> None:
        for mask in masks:
            if mask:
                self.cooccurrence[MASK_NAME[mask]] += 1
        occupied = [m for m in masks if m]
        for a, b in zip(occupied, occupied[1:]):
            self.transitions[f"{MASK_NAME[a]}>{MASK_NAME[b]}"] += 1

    def as_dict(self) -> dict:
        total_hits = sum(self.hits.values())
        return {
            "rows": self.rows,
            "duration_sec": round(self.duration_sec, 6),
            "bpm": {
                "mean": round(statistics.fmean(self.bpms), 6) if self.bpms else None,
                "median": round(statistics.median(self.bpms), 6) if self.bpms else None,
                "min": min(self.bpms) if self.bpms else None,
                "max": max(self.bpms) if self.bpms else None,
            },
            "hits": {g: int(self.hits[g]) for g in GROUP_ORDER},
            "hit_rate": {
                g: (self.hits[g] / total_hits if total_hits else 0.0) for g in GROUP_ORDER
            },
            "phase_16th_counts": {g: dict(sorted(self.phase[g].items(), key=lambda kv: int(kv[0]))) for g in GROUP_ORDER},
            "slots_per_bar_observations": dict(sorted(self.phase_denominator.items(), key=lambda kv: int(kv[0]))),
            "cooccurrence_counts": dict(self.cooccurrence.most_common()),
            "transition_counts": dict(self.transitions.most_common()),
            "velocity": {
                g: {
                    "mean": (
                        self.velocity_sum[g] / self.velocity_count[g]
                        if self.velocity_count[g]
                        else None
                    ),
                    "count": self.velocity_count[g],
                    "histogram": dict(self.velocity_hist[g]),
                }
                for g in GROUP_ORDER
            },
        }


def midi_kst_slots(path: Path, numerator: int, denominator: int):
    midi = mido.MidiFile(path)
    tpq = midi.ticks_per_beat
    if not tpq:
        return [], 16

    bar_quarters = numerator * 4.0 / denominator
    slots_per_bar = max(1, int(round(numerator * 16.0 / denominator)))

    abs_tick = 0
    raw = []
    for msg in mido.merge_tracks(midi.tracks):
        abs_tick += msg.time
        if msg.type != "note_on" or getattr(msg, "velocity", 0) <= 0:
            continue
        group = PITCH_GROUP.get(int(msg.note))
        if not group:
            continue
        q = abs_tick / tpq
        bar_index = int(math.floor((q + 1e-9) / bar_quarters))
        pos_q = q - bar_index * bar_quarters
        slot = int(round(pos_q * 4.0)) % slots_per_bar
        raw.append((bar_index, slot, group, int(msg.velocity)))

    return raw, slots_per_bar


def add_performance(agg: Aggregate, root: Path, row: dict) -> dict:
    bpm = float(row.get("bpm") or 0)
    duration = float(row.get("duration") or 0)
    numerator, denominator = parse_signature(row.get("time_signature") or "4-4")
    midi_path = root / row["midi_filename"]
    if not midi_path.exists():
        raise FileNotFoundError(midi_path)

    hits, slots_per_bar = midi_kst_slots(midi_path, numerator, denominator)
    agg.add_row(bpm=bpm, duration=duration)

    slots_by_bar: dict[int, list[int]] = defaultdict(lambda: [0] * slots_per_bar)
    for bar, slot, group, velocity in hits:
        agg.add_hit(group, slot, slots_per_bar, velocity)
        bit = 1 << GROUP_ORDER.index(group)
        slots_by_bar[bar][slot] |= bit

    for _, masks in sorted(slots_by_bar.items()):
        agg.add_slot_sequence(masks)

    return {
        "kst_hits": len(hits),
        "slots_per_bar": slots_per_bar,
        "time_signature": f"{numerator}/{denominator}",
    }


def nested_aggregates() -> dict:
    return {
        "global": defaultdict(Aggregate),
        "genre": defaultdict(Aggregate),
        "style": defaultdict(Aggregate),
        "genre_beat_type": defaultdict(Aggregate),
        "genre_tempo_band": defaultdict(Aggregate),
    }


def build(root: Path) -> tuple[dict, dict]:
    info = root / "info.csv"
    if not info.exists():
        candidates = list(root.rglob("info.csv"))
        if not candidates:
            raise FileNotFoundError("GMD info.csv not found")
        info = candidates[0]
        root = info.parent

    aggregates = nested_aggregates()
    split_summary = {
        split: {
            "rows": 0,
            "duration_sec": 0.0,
            "styles": Counter(),
            "genres": Counter(),
            "beat_types": Counter(),
            "kst_hits": 0,
        }
        for split in ("train", "validation", "test")
    }

    with info.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    for i, row in enumerate(rows, start=1):
        split = (row.get("split") or "").strip()
        if split not in split_summary:
            continue
        style = (row.get("style") or "unknown/unknown").strip().lower()
        primary, _, secondary = style.partition("/")
        primary = primary or "unknown"
        secondary = secondary or "unknown"
        beat_type = (row.get("beat_type") or "unknown").strip().lower()
        bpm = float(row.get("bpm") or 0)
        duration = float(row.get("duration") or 0)

        summary = split_summary[split]
        summary["rows"] += 1
        summary["duration_sec"] += duration
        summary["styles"][style] += 1
        summary["genres"][primary] += 1
        summary["beat_types"][beat_type] += 1

        # Validation/test are evaluated only enough to count K/S/T references.
        if split != "train":
            temp = Aggregate()
            result = add_performance(temp, root, row)
            summary["kst_hits"] += result["kst_hits"]
            continue

        keys = [
            ("global", "all"),
            ("genre", primary),
            ("style", f"{primary}/{secondary}"),
            ("genre_beat_type", f"{primary}|{beat_type}"),
            ("genre_tempo_band", f"{primary}|{tempo_band(bpm)}"),
        ]
        row_aggs = [aggregates[family][key] for family, key in keys]

        # Parse once, then feed all aggregates.
        numerator, denominator = parse_signature(row.get("time_signature") or "4-4")
        midi_path = root / row["midi_filename"]
        hits, slots_per_bar = midi_kst_slots(midi_path, numerator, denominator)
        summary["kst_hits"] += len(hits)

        slots_by_bar: dict[int, list[int]] = defaultdict(lambda: [0] * slots_per_bar)
        for agg in row_aggs:
            agg.add_row(bpm=bpm, duration=duration)

        for bar, slot, group, velocity in hits:
            bit = 1 << GROUP_ORDER.index(group)
            slots_by_bar[bar][slot] |= bit
            for agg in row_aggs:
                agg.add_hit(group, slot, slots_per_bar, velocity)

        for _, masks in sorted(slots_by_bar.items()):
            for agg in row_aggs:
                agg.add_slot_sequence(masks)

        if i % 100 == 0:
            print(f"processed {i}/{len(rows)} rows", flush=True)

    knowledge = {
        "version": VERSION,
        "source": {
            "dataset": "Google Magenta Groove MIDI Dataset",
            "dataset_version": "1.0.0",
            "archive": "groove-v1.0.0-midionly.zip",
            "url": GMD_URL,
            "sha256": GMD_SHA256,
            "license": "CC BY 4.0",
            "training_split": "train",
        },
        "pitch_groups": {
            "kick": [36],
            "snare": [37, 38, 40],
            "tom": [43, 45, 47, 48, 50, 58],
        },
        "tempo_bands_bpm": ["<90", "90-119", "120-149", "150-179", ">=180"],
        "aggregates": {
            family: {key: agg.as_dict() for key, agg in sorted(groups.items())}
            for family, groups in aggregates.items()
        },
    }

    summary_json = {}
    for split, data in split_summary.items():
        summary_json[split] = {
            "rows": data["rows"],
            "duration_sec": round(data["duration_sec"], 6),
            "kst_hits": data["kst_hits"],
            "genres": dict(data["genres"].most_common()),
            "styles": dict(data["styles"].most_common()),
            "beat_types": dict(data["beat_types"].most_common()),
        }

    evaluation_manifest = {
        "version": VERSION,
        "rule": "knowledge-v1.json uses train only; validation/test remain held out",
        "splits": summary_json,
    }
    return knowledge, evaluation_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", default=".cache/gmd-kst")
    parser.add_argument("--dataset-root", default=None)
    parser.add_argument("--output-dir", default="drumscribe/models/gmd-kst")
    args = parser.parse_args()

    cache = Path(args.cache_dir)
    if args.dataset_root:
        root = Path(args.dataset_root)
    else:
        archive = cache / "groove-v1.0.0-midionly.zip"
        download(GMD_URL, archive)
        root = extract_if_needed(archive, cache / "groove-v1.0.0-midionly")

    knowledge, evaluation = build(root)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    knowledge_path = out / "knowledge-v1.json"
    eval_path = out / "heldout-manifest-v1.json"
    knowledge_path.write_text(json.dumps(knowledge, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    eval_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "version": VERSION,
        "source_sha256": GMD_SHA256,
        "knowledge_sha256": sha256(knowledge_path),
        "heldout_manifest_sha256": sha256(eval_path),
        "notes": [
            "GMD train split only is used for runtime knowledge",
            "validation/test are reserved for external evaluation",
            "DruMaster chart.mid is not read by this build",
        ],
    }
    (out / "manifest-v1.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
