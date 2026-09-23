import csv
import io
import json
import re
from pathlib import Path

import mido
from remotezip import RemoteZip

URL = "https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0.zip"
OUT = Path("drumscribe/experiments/gmd-triplet-heldout-v32")
KEYWORDS = ("shuffle", "swing", "triplet")
MAX_POSITIVES = 12
MAX_CONTROLS = 12


def safe_id(value):
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-")
    return value or "case"


def is_triplet_label(row):
    text = " ".join(str(row.get(k, "")) for k in ("style", "beat_type", "id", "midi_filename", "audio_filename")).lower()
    return any(k in text for k in KEYWORDS)


def note_weight(note):
    if note in {35, 36, 37, 38, 39, 40}:
        return 3.0
    if note in {41, 43, 45, 47, 48, 50}:
        return 1.7
    if note in {49, 51, 52, 53, 55, 57, 58, 59}:
        return 1.25
    return 0.75


def grid_distance(q, step):
    r = q % step
    return min(r, step - r)


def midi_evidence(data):
    mid = mido.MidiFile(file=io.BytesIO(data))
    tick = 0
    notes = []
    for msg in mido.merge_tracks(mid.tracks):
        tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            notes.append((tick / mid.ticks_per_beat, note_weight(msg.note)))
    total = sum(w for _, w in notes) or 1.0
    straight_mean = sum(grid_distance(q, 0.25) * w for q, w in notes) / total
    triplet_mean = sum(min(grid_distance(q, 1 / 3), grid_distance(q, 1 / 6)) * w for q, w in notes) / total
    triplet_only = sum(w for q, w in notes if min(grid_distance(q, 1 / 3), grid_distance(q, 1 / 6)) <= 0.035 and grid_distance(q, 0.25) >= 0.055) / total
    straight_only = sum(w for q, w in notes if grid_distance(q, 0.25) <= 0.035 and min(grid_distance(q, 1 / 3), grid_distance(q, 1 / 6)) >= 0.055) / total
    return {
        "notes": len(notes),
        "straight16_weighted_mean_residual_beats": straight_mean,
        "triplet_weighted_mean_residual_beats": triplet_mean,
        "triplet_only_share": triplet_only,
        "straight_only_share": straight_only,
    }


def base_rank(row):
    return (0 if row.get("split") == "test" else 1, row.get("style", ""), row.get("id", ""))


OUT.mkdir(parents=True, exist_ok=True)
with RemoteZip(URL) as rz:
    names = set(rz.namelist())
    info_name = next((n for n in names if n.endswith("/info.csv") or n == "info.csv"), None)
    if info_name is None:
        raise RuntimeError("info.csv not found in GMD archive")
    prefix = info_name.rsplit("/", 1)[0] + "/" if "/" in info_name else ""
    rows = list(csv.DictReader(io.TextIOWrapper(rz.open(info_name), encoding="utf-8")))
    heldout = [r for r in rows if r.get("split") in {"validation", "test"} and r.get("beat_type") == "beat" and r.get("audio_filename") and r.get("midi_filename")]

    analyzed = []
    for row in heldout:
        midi_member = row["midi_filename"] if row["midi_filename"] in names else prefix + row["midi_filename"]
        audio_member = row["audio_filename"] if row["audio_filename"] in names else prefix + row["audio_filename"]
        if midi_member not in names or audio_member not in names:
            continue
        evidence = midi_evidence(rz.read(midi_member))
        analyzed.append({"row": row, "midi_member": midi_member, "audio_member": audio_member, "evidence": evidence, "explicit": is_triplet_label(row)})

    positives = [x for x in analyzed if x["explicit"] or (
        x["evidence"]["triplet_only_share"] >= 0.10
        and x["evidence"]["triplet_only_share"] >= x["evidence"]["straight_only_share"] + 0.04
        and x["evidence"]["triplet_weighted_mean_residual_beats"] <= x["evidence"]["straight16_weighted_mean_residual_beats"] * 0.80
    )]
    positives.sort(key=lambda x: (
        0 if x["explicit"] else 1,
        -x["evidence"]["triplet_only_share"],
        x["evidence"]["triplet_weighted_mean_residual_beats"],
        *base_rank(x["row"]),
    ))
    positives = positives[:MAX_POSITIVES]

    positive_genres = {x["row"].get("style", "").split("/", 1)[0] for x in positives}
    controls = [x for x in analyzed if not x["explicit"] and (
        x["evidence"]["straight_only_share"] >= 0.08
        and x["evidence"]["straight_only_share"] >= x["evidence"]["triplet_only_share"] + 0.04
        and x["evidence"]["straight16_weighted_mean_residual_beats"] <= x["evidence"]["triplet_weighted_mean_residual_beats"] * 0.85
    )]
    controls.sort(key=lambda x: (
        0 if x["row"].get("style", "").split("/", 1)[0] in positive_genres else 1,
        -x["evidence"]["straight_only_share"],
        x["evidence"]["straight16_weighted_mean_residual_beats"],
        *base_rank(x["row"]),
    ))
    controls = controls[:MAX_CONTROLS]

    if not positives:
        raise RuntimeError("No held-out triplet cases found from metadata or reference MIDI evidence")

    manifest = {
        "schema": 2,
        "dataset": "Groove MIDI Dataset v1.0.0",
        "archive_url": URL,
        "selection": {
            "splits": ["validation", "test"],
            "beat_type": "beat",
            "positive_keywords": list(KEYWORDS),
            "reference_midi_selection_only": True,
            "prediction_does_not_read_reference_midi": True,
            "positive_rule": "explicit metadata keyword OR triplet_only>=0.10, margin>=0.04, triplet residual <= 0.80*straight residual",
            "control_rule": "straight_only>=0.08, margin>=0.04, straight residual <= 0.85*triplet residual",
        },
        "cases": [],
    }

    selected = [(x, "triplet") for x in positives] + [(x, "straight") for x in controls]
    for index, (x, expected) in enumerate(selected):
        row = x["row"]
        base = safe_id(f"{row.get('split')}-{row.get('id') or index}")
        audio_path = OUT / f"{base}.wav"
        midi_path = OUT / f"{base}.mid"
        audio_path.write_bytes(rz.read(x["audio_member"]))
        midi_path.write_bytes(rz.read(x["midi_member"]))
        manifest["cases"].append({
            "case_id": base,
            "expected_family_from_reference": expected,
            "expected_family_from_metadata": "triplet" if x["explicit"] else None,
            "selection_reason": "metadata_keyword" if x["explicit"] else "reference_midi_triplet_evidence" if expected == "triplet" else "reference_midi_straight_control",
            "reference_selection_evidence": x["evidence"],
            "split": row.get("split"),
            "style": row.get("style"),
            "beat_type": row.get("beat_type"),
            "bpm": float(row.get("bpm") or 0),
            "time_signature": row.get("time_signature"),
            "duration": float(row.get("duration") or 0),
            "source_audio_filename": row.get("audio_filename"),
            "source_midi_filename": row.get("midi_filename"),
            "local_audio": str(audio_path),
            "local_midi": str(midi_path),
        })

manifest_path = OUT / "manifest.json"
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({
    "manifest": str(manifest_path),
    "analyzed_heldout": len(analyzed),
    "positives": len(positives),
    "controls": len(controls),
    "cases": len(manifest["cases"]),
    "positive_styles": sorted({x["row"].get("style", "") for x in positives}),
    "positive_reasons": {"metadata": sum(x["explicit"] for x in positives), "midi_evidence": sum(not x["explicit"] for x in positives)},
}, ensure_ascii=False, indent=2))
