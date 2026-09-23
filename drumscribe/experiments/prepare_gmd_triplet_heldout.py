import csv
import io
import json
import re
from pathlib import Path

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


def rank(row):
    return (0 if row.get("split") == "test" else 1, row.get("style", ""), row.get("id", ""))


OUT.mkdir(parents=True, exist_ok=True)
with RemoteZip(URL) as rz:
    names = rz.namelist()
    info_name = next((n for n in names if n.endswith("/info.csv") or n == "info.csv"), None)
    if info_name is None:
        raise RuntimeError("info.csv not found in GMD archive")
    rows = list(csv.DictReader(io.TextIOWrapper(rz.open(info_name), encoding="utf-8")))
    heldout = [r for r in rows if r.get("split") in {"validation", "test"} and r.get("beat_type") == "beat" and r.get("audio_filename") and r.get("midi_filename")]
    positives = sorted((r for r in heldout if is_triplet_label(r)), key=rank)[:MAX_POSITIVES]
    positive_genres = {r.get("style", "").split("/", 1)[0] for r in positives}
    controls = sorted((r for r in heldout if not is_triplet_label(r)), key=lambda r: (0 if r.get("style", "").split("/", 1)[0] in positive_genres else 1, *rank(r)))[:MAX_CONTROLS]
    if not positives:
        raise RuntimeError("No held-out shuffle/swing/triplet rows found")
    manifest = {"schema": 1, "dataset": "Groove MIDI Dataset v1.0.0", "archive_url": URL, "selection": {"splits": ["validation", "test"], "beat_type": "beat", "positive_keywords": list(KEYWORDS)}, "cases": []}
    prefix = info_name.rsplit("/", 1)[0] + "/" if "/" in info_name else ""
    for index, (row, expected_triplet) in enumerate([(r, True) for r in positives] + [(r, False) for r in controls]):
        base = safe_id(f"{row.get('split')}-{row.get('id') or index}")
        audio_member = row["audio_filename"] if row["audio_filename"] in names else prefix + row["audio_filename"]
        midi_member = row["midi_filename"] if row["midi_filename"] in names else prefix + row["midi_filename"]
        if audio_member not in names or midi_member not in names:
            raise FileNotFoundError(f"Archive members missing: {audio_member}, {midi_member}")
        audio_path = OUT / f"{base}.wav"
        midi_path = OUT / f"{base}.mid"
        audio_path.write_bytes(rz.read(audio_member))
        midi_path.write_bytes(rz.read(midi_member))
        manifest["cases"].append({"case_id": base, "expected_family_from_metadata": "triplet" if expected_triplet else "straight", "split": row.get("split"), "style": row.get("style"), "beat_type": row.get("beat_type"), "bpm": float(row.get("bpm") or 0), "time_signature": row.get("time_signature"), "duration": float(row.get("duration") or 0), "source_audio_filename": row.get("audio_filename"), "source_midi_filename": row.get("midi_filename"), "local_audio": str(audio_path), "local_midi": str(midi_path)})

manifest_path = OUT / "manifest.json"
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"manifest": str(manifest_path), "positives": len(positives), "controls": len(controls), "cases": len(manifest["cases"]), "positive_styles": sorted({r.get("style", "") for r in positives})}, ensure_ascii=False, indent=2))
