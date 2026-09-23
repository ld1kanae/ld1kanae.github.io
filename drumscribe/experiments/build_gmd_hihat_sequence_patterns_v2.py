"""Build GMD-only hi-hat sequence/context statistics for DrumScribe.

This is intentionally source-separated. It reads only the official Magenta
Groove MIDI Dataset MIDI-only archive. It never reads DruMaster songs or the
synchronized Nanairo acoustic teacher.

Articulation policy for this task:
  Open   = MIDI 26, 46
  Closed = MIDI 22, 42, 44   (pedal folded into Closed)

The v2 asset keeps more sequential information than hihat-style-patterns-v1:
- 16-slot bar and 32-slot two-bar symbolic patterns
- local 9-slot hi-hat occupancy context -> Open/Closed counts
- local kick/snare context -> Open/Closed counts
- 2/3/4-event Open/Closed n-grams
- state transition counts stratified by sixteenth-note gap
- consecutive Open-run length histograms
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import mido
import requests

ROOT = Path(".")
OUT = ROOT / "drumscribe/models/gmd-kst/hihat-sequence-patterns-v2.json"
ZIP_URL = "https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0-midionly.zip"
ZIP_SHA256 = "651cbc524ffb891be1a3e46d89dc82a1cecb09a57c748c7b45b844c4841dcc1e"
OPEN = {26, 46}
CLOSED = {22, 42, 44}
KICK = {35, 36}
SNARE = {37, 38, 40}
TOP_BAR = 256
TOP_2BAR = 192


def resolve_name(names, rel):
    rel = str(rel).replace("\\", "/").lstrip("./")
    if rel in names:
        return rel
    suffix = "/" + rel
    cands = [n for n in names if n.endswith(suffix) or n.endswith(rel)]
    if not cands:
        raise KeyError(rel)
    return min(cands, key=len)


def parse_midi(data: bytes):
    mf = mido.MidiFile(file=io.BytesIO(data))
    tick = 0
    hats = defaultdict(set)
    kick_ticks = []
    snare_ticks = []
    for msg in mido.merge_tracks(mf.tracks):
        tick += msg.time
        if msg.type != "note_on" or msg.velocity <= 0:
            continue
        n = int(msg.note)
        if n in OPEN:
            hats[int(tick)].add("O")
        elif n in CLOSED:
            hats[int(tick)].add("C")
        if n in KICK:
            kick_ticks.append(int(tick))
        if n in SNARE:
            snare_ticks.append(int(tick))
    hh = [(t, "O" if "O" in states else "C") for t, states in sorted(hats.items())]
    return int(mf.ticks_per_beat), hh, kick_ticks, snare_ticks


def init_stat():
    return {
        "sequences": 0,
        "openHits": 0,
        "closedHits": 0,
        "slotOpen": [0] * 16,
        "slotClosed": [0] * 16,
        "transitions": Counter(),
        "transitionGap16": defaultdict(Counter),
        "ngrams2": Counter(),
        "ngrams3": Counter(),
        "ngrams4": Counter(),
        "openRunLength": Counter(),
        "hatContext9": defaultdict(lambda: [0, 0]),
        "ksContext6": defaultdict(lambda: [0, 0]),
        "barPatterns": Counter(),
        "twoBarPatterns": Counter(),
    }


def qslot(tick, tpb):
    return int(round(float(tick) / (float(tpb) / 4.0)))


def add_sequence(stat, tpb, hats, kicks, snares):
    stat["sequences"] += 1
    hq = []
    by_slot = defaultdict(set)
    for tick, state in hats:
        s = qslot(tick, tpb)
        by_slot[s].add(state)
    for s, states in sorted(by_slot.items()):
        hq.append((s, "O" if "O" in states else "C"))

    kset = {qslot(t, tpb) for t in kicks}
    sset = {qslot(t, tpb) for t in snares}
    hset = {s for s, _ in hq}

    for s, state in hq:
        idx = 0 if state == "C" else 1
        sl = s % 16
        stat["slotOpen" if state == "O" else "slotClosed"][sl] += 1
        stat["openHits" if state == "O" else "closedHits"] += 1

        mask = 0
        for bit, off in enumerate(range(-4, 5)):
            if s + off in hset:
                mask |= 1 << bit
        stat["hatContext9"][str(mask)][idx] += 1

        # kick[-1,0,+1], snare[-1,0,+1] around the candidate sixteenth.
        kmask = 0
        for bit, off in enumerate((-1, 0, 1)):
            if s + off in kset:
                kmask |= 1 << bit
            if s + off in sset:
                kmask |= 1 << (bit + 3)
        stat["ksContext6"][str(kmask)][idx] += 1

    states = [x[1] for x in hq]
    for n in (2, 3, 4):
        c = stat[f"ngrams{n}"]
        for i in range(len(states) - n + 1):
            c["".join(states[i:i+n])] += 1

    run = 0
    for st in states + ["C"]:
        if st == "O":
            run += 1
        elif run:
            stat["openRunLength"][str(min(run, 16))] += 1
            run = 0

    for (a, sa), (b, sb) in zip(hq, hq[1:]):
        key = sa + ">" + sb
        stat["transitions"][key] += 1
        gap = max(0, min(16, b - a))
        stat["transitionGap16"][key][str(gap)] += 1

    bars = defaultdict(dict)
    for s, st in hq:
        b = s // 16
        p = s % 16
        old = bars[b].get(p)
        bars[b][p] = "O" if old == "O" or st == "O" else "C"
    if bars:
        lo, hi = min(bars), max(bars)
        strings = {}
        for b in range(lo, hi + 1):
            chars = ["-"] * 16
            for p, st in bars.get(b, {}).items():
                chars[p] = st
            strings[b] = "".join(chars)
            stat["barPatterns"][strings[b]] += 1
        for b in range(lo, hi):
            stat["twoBarPatterns"][strings[b] + strings[b + 1]] += 1


def sparse_counts(d, min_count=1):
    out = {}
    for k, v in d.items():
        c, o = int(v[0]), int(v[1])
        if c + o >= min_count:
            out[str(k)] = {"closed": c, "open": o, "count": c + o, "pOpen": o / (c + o)}
    return out


def finalize(stat):
    o = int(stat["openHits"])
    c = int(stat["closedHits"])
    pslot = []
    for a, b in zip(stat["slotOpen"], stat["slotClosed"]):
        pslot.append(a / (a + b) if a + b else None)
    return {
        "sequences": int(stat["sequences"]),
        "openHits": o,
        "closedHits": c,
        "openRate": o / (o + c) if o + c else 0.0,
        "slotOpen": list(map(int, stat["slotOpen"])),
        "slotClosed": list(map(int, stat["slotClosed"])),
        "pOpenGivenHatSlot": pslot,
        "transitions": {k: int(v) for k, v in stat["transitions"].items()},
        "transitionGap16": {
            k: {str(g): int(n) for g, n in sorted(v.items(), key=lambda q: int(q[0]))}
            for k, v in stat["transitionGap16"].items()
        },
        "stateNgrams": {
            "2": {k: int(v) for k, v in stat["ngrams2"].most_common()},
            "3": {k: int(v) for k, v in stat["ngrams3"].most_common()},
            "4": {k: int(v) for k, v in stat["ngrams4"].most_common()},
        },
        "openRunLength": {k: int(v) for k, v in sorted(stat["openRunLength"].items(), key=lambda q: int(q[0]))},
        "hatContext9": sparse_counts(stat["hatContext9"]),
        "ksContext6": sparse_counts(stat["ksContext6"]),
        "topBarPatterns": [{"pattern": p, "count": int(n)} for p, n in stat["barPatterns"].most_common(TOP_BAR)],
        "topTwoBarPatterns": [{"pattern": p, "count": int(n)} for p, n in stat["twoBarPatterns"].most_common(TOP_2BAR)],
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

    global_stat = init_stat()
    genres = defaultdict(init_stat)
    split_counts = Counter()
    skipped = Counter()
    used = 0

    for row in rows:
        ts = str(row.get("time_signature", "")).replace("-", "/")
        if ts != "4/4":
            skipped[ts or "unknown"] += 1
            continue
        rel = row.get("midi_filename")
        if not rel:
            continue
        style = (row.get("style") or "unknown").split("/")[0].strip().lower() or "unknown"
        split_counts[(row.get("split") or "unknown").strip().lower()] += 1
        name = resolve_name(names, rel)
        tpb, hats, kicks, snares = parse_midi(z.read(name))
        if not hats:
            continue
        add_sequence(global_stat, tpb, hats, kicks, snares)
        add_sequence(genres[style], tpb, hats, kicks, snares)
        used += 1

    out = {
        "schema": 2,
        "kind": "gmd-hihat-sequence-patterns",
        "source": {
            "dataset": "Google Magenta Groove MIDI Dataset v1.0.0",
            "url": ZIP_URL,
            "archiveSha256": ZIP_SHA256,
            "license": "CC BY 4.0",
            "sourceMode": "MIDI-only; direct original GMD MIDI parse",
        },
        "sourceSeparation": {
            "gmdOnly": True,
            "readsDruMasterSongs": False,
            "readsSynchronizedNanairoTeacher": False,
            "trainingRowsPooledWithOtherSources": False,
        },
        "labelMapping": {"open": [26, 46], "closed": [22, 42, 44]},
        "grid": {
            "timeSignature": "4/4",
            "slotsPerBar": 16,
            "quantization": "nearest sixteenth",
            "hatContext9Offsets16": [-4,-3,-2,-1,0,1,2,3,4],
            "ksContext6": "kick[-1,0,+1] bits0..2; snare[-1,0,+1] bits3..5",
        },
        "global": finalize(global_stat),
        "genres": {k: finalize(v) for k, v in sorted(genres.items())},
        "metadata": {
            "usableSequences4_4": used,
            "primaryGenres": len(genres),
            "splitCounts": dict(split_counts),
            "skippedNon4_4": dict(skipped),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print("GMD_HIHAT_V2", json.dumps({
        "usable": used,
        "genres": len(genres),
        "open": out["global"]["openHits"],
        "closed": out["global"]["closedHits"],
        "openRate": out["global"]["openRate"],
        "hatContext9": len(out["global"]["hatContext9"]),
        "ksContext6": len(out["global"]["ksContext6"]),
    }), flush=True)


if __name__ == "__main__":
    main()
