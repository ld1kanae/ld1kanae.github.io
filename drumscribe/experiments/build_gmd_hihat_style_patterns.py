"""Build genre-specific Open/Closed hi-hat pattern data from GMD MIDI.

IMPORTANT: this file builds a GMD-only symbolic dataset.  It never reads
DruMaster songs or the synchronized Nanairo teacher, so those learning sources
remain strictly separated.

GMD label mapping follows the official paper mapping:
  open   = {26, 46}
  closed = {22, 42, 44}  # pedal is intentionally folded into closed

For 4/4 performances, each bar is reduced to 16 sixteenth-note slots.  We
collect per-primary-genre:
- open/closed hit counts
- P(open | hat hit, sixteenth slot)
- Open/Closed transition counts stratified by sixteenth-slot gap
- representative 16-slot symbolic patterns

The output is compact derived learning data, not a redistribution of GMD MIDI.
"""
from __future__ import annotations

import csv, hashlib, io, json, zipfile
from collections import Counter, defaultdict
from pathlib import Path

import mido
import requests

ROOT = Path(".")
OUT = ROOT / "drumscribe/models/gmd-kst/hihat-style-patterns-v1.json"
ZIP_URL = "https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0-midionly.zip"
ZIP_SHA256 = "651cbc524ffb891be1a3e46d89dc82a1cecb09a57c748c7b45b844c4841dcc1e"
OPEN = {26, 46}
CLOSED = {22, 42, 44}
TOP_PATTERNS = 96


def resolve_name(names, rel):
    rel = str(rel).replace("\\", "/").lstrip("./")
    if rel in names:
        return rel
    suffix = "/" + rel
    candidates = [n for n in names if n.endswith(suffix) or n.endswith(rel)]
    if not candidates:
        raise KeyError(rel)
    return min(candidates, key=len)


def hat_notes(data: bytes):
    mf = mido.MidiFile(file=io.BytesIO(data))
    tpb = mf.ticks_per_beat
    tick = 0
    out = []
    for msg in mido.merge_tracks(mf.tracks):
        tick += msg.time
        if msg.type != "note_on" or msg.velocity <= 0:
            continue
        if msg.note in OPEN:
            out.append((tick, "O"))
        elif msg.note in CLOSED:
            out.append((tick, "C"))
    # Collapse simultaneous HH messages to one articulation. Open wins only if
    # an actual open note exists at the same tick.
    by_tick = defaultdict(set)
    for t, s in out:
        by_tick[int(t)].add(s)
    collapsed = [(t, "O" if "O" in ss else "C") for t, ss in sorted(by_tick.items())]
    return tpb, collapsed


def init_stat():
    return {
        "sequences": 0,
        "openHits": 0,
        "closedHits": 0,
        "slotOpen": [0] * 16,
        "slotClosed": [0] * 16,
        "transitions": {k: 0 for k in ("C>C", "C>O", "O>C", "O>O")},
        "transitionGap16": {k: [0] * 17 for k in ("C>C", "C>O", "O>C", "O>O")},
        "patterns": Counter(),
    }


def add_sequence(stat, tpb, notes):
    stat["sequences"] += 1
    by_bar = defaultdict(dict)
    prev = None
    prev_tick = None
    for tick, state in notes:
        # Sixteenth grid. Human microtiming is intentionally quantized only for
        # symbolic pattern aggregation.
        abs_slot = int(round(tick / (tpb / 4.0)))
        bar = abs_slot // 16
        slot = abs_slot % 16
        old = by_bar[bar].get(slot)
        by_bar[bar][slot] = "O" if old == "O" or state == "O" else "C"
        if state == "O":
            stat["openHits"] += 1
            stat["slotOpen"][slot] += 1
        else:
            stat["closedHits"] += 1
            stat["slotClosed"][slot] += 1
        if prev is not None:
            key = prev + ">" + state
            stat["transitions"][key] += 1
            gap = int(round((tick - prev_tick) / (tpb / 4.0)))
            gap = max(0, min(16, gap))
            stat["transitionGap16"][key][gap] += 1
        prev, prev_tick = state, tick
    for _, slots in by_bar.items():
        chars = ["-"] * 16
        for i, s in slots.items():
            chars[i] = s
        stat["patterns"]["".join(chars)] += 1


def finalize(stat):
    o, c = stat["openHits"], stat["closedHits"]
    den = o + c
    pslot = []
    for a, b in zip(stat["slotOpen"], stat["slotClosed"]):
        pslot.append(a / (a + b) if a + b else None)
    patterns = [{"pattern": p, "count": n} for p, n in stat["patterns"].most_common(TOP_PATTERNS)]
    return {
        "sequences": stat["sequences"],
        "openHits": o,
        "closedHits": c,
        "openRate": o / den if den else 0.0,
        "slotOpen": stat["slotOpen"],
        "slotClosed": stat["slotClosed"],
        "pOpenGivenHatSlot": pslot,
        "transitions": stat["transitions"],
        "transitionGap16": stat["transitionGap16"],
        "topPatterns": patterns,
    }


def main():
    raw = requests.get(ZIP_URL, timeout=120)
    raw.raise_for_status()
    sha = hashlib.sha256(raw.content).hexdigest()
    if sha != ZIP_SHA256:
        raise RuntimeError(f"GMD MIDI zip SHA256 mismatch: {sha}")
    z = zipfile.ZipFile(io.BytesIO(raw.content))
    names = set(z.namelist())
    info_name = min((n for n in names if n.endswith("info.csv")), key=len)
    rows = list(csv.DictReader(io.TextIOWrapper(z.open(info_name), encoding="utf-8-sig")))

    genres = defaultdict(init_stat)
    global_stat = init_stat()
    skipped_non44 = Counter()
    split_counts = Counter()
    style_counts = Counter()

    for row in rows:
        sig = (row.get("time_signature") or "").replace("/", "-")
        if sig != "4-4":
            skipped_non44[sig or "unknown"] += 1
            continue
        midi_name = resolve_name(names, row["midi_filename"])
        tpb, notes = hat_notes(z.read(midi_name))
        if not notes:
            continue
        style = row.get("style") or "unknown"
        primary = style.split("/", 1)[0].strip().lower() or "unknown"
        add_sequence(global_stat, tpb, notes)
        add_sequence(genres[primary], tpb, notes)
        split_counts[row.get("split") or "unknown"] += 1
        style_counts[style] += 1

    out = {
        "schema": 1,
        "kind": "drumscribe-gmd-hihat-style-patterns",
        "source": {
            "dataset": "Google Magenta Groove MIDI Dataset v1.0.0",
            "url": ZIP_URL,
            "archiveSha256": ZIP_SHA256,
            "license": "CC BY 4.0",
            "sourceMode": "MIDI-only; direct original GMD MIDI parse",
        },
        "sourceSeparation": {
            "gmdOnly": True,
            "pooledWithDruMasterSongs": False,
            "pooledWithNanairoSyncTeacher": False,
        },
        "labelMapping": {
            "open": [26, 46],
            "closed": [22, 42, 44],
            "pedal44Policy": "fold into closed",
        },
        "grid": {"timeSignature": "4/4", "slotsPerBar": 16},
        "global": finalize(global_stat),
        "genres": {g: finalize(s) for g, s in sorted(genres.items())},
        "metadata": {
            "splitSequenceCounts": dict(split_counts),
            "styleSequenceCounts": dict(style_counts),
            "skippedNon44": dict(skipped_non44),
            "genreCount": len(genres),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "path": str(OUT),
        "genres": len(genres),
        "sequences": out["global"]["sequences"],
        "openHits": out["global"]["openHits"],
        "closedHits": out["global"]["closedHits"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
