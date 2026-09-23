import json
from pathlib import Path

SONGS = ["arcaround", "diamondvirgin", "kaiju", "nanairo", "ray"]
OUT_DIR = Path("drumscribe/experiments/generated-v2-browser")
RESULT_PATH = Path("drumscribe/experiments/results-grid-browser-ci.json")


def varlen(data, i):
    value = 0
    while True:
        b = data[i]
        i += 1
        value = (value << 7) | (b & 0x7F)
        if not b & 0x80:
            return value, i


def midi_stats(path):
    data = Path(path).read_bytes()
    if data[:4] != b"MThd":
        raise ValueError(f"{path}: not an SMF")
    division = int.from_bytes(data[12:14], "big")
    pos = 8 + int.from_bytes(data[4:8], "big")
    tempo_ticks = []
    note_ticks = []
    signatures = []

    while pos + 8 <= len(data) and data[pos:pos + 4] == b"MTrk":
        size = int.from_bytes(data[pos + 4:pos + 8], "big")
        i = pos + 8
        end = i + size
        tick = 0
        running = 0
        while i < end:
            delta, i = varlen(data, i)
            tick += delta
            status = data[i]
            if status & 0x80:
                i += 1
                running = status
            else:
                status = running

            if status == 0xFF:
                typ = data[i]
                i += 1
                n, i = varlen(data, i)
                payload = data[i:i + n]
                i += n
                if typ == 0x51 and n == 3:
                    tempo_ticks.append(tick)
                elif typ == 0x58 and n >= 2:
                    signatures.append((tick, payload[0], 2 ** payload[1]))
            elif status in (0xF0, 0xF7):
                n, i = varlen(data, i)
                i += n
            else:
                op = status & 0xF0
                if op in (0x80, 0x90):
                    note = data[i]
                    velocity = data[i + 1]
                    i += 2
                    if op == 0x90 and velocity > 0:
                        note_ticks.append((tick, note))
                else:
                    i += 1 if op in (0xC0, 0xD0) else 2
        pos = end

    return {
        "division": division,
        "tempo_ticks": tempo_ticks,
        "note_ticks": note_ticks,
        "time_signatures": signatures,
    }


def quantum_ticks(label, ppq):
    if label == "1/16":
        return ppq // 4
    if label in ("1/16+1/32", "1/32"):
        return ppq // 8
    if label == "1/8T":
        return ppq // 3
    if label == "1/16T":
        return ppq // 6
    raise ValueError(f"unknown subdivision: {label}")


def tick_residual(tick, quantum):
    r = tick % quantum
    return min(r, quantum - r)


results = {"schema": 1, "songs": {}, "failures": []}

for song in SONGS:
    side_path = OUT_DIR / f"{song}.json"
    midi_path = OUT_DIR / f"{song}.mid"
    side = json.loads(side_path.read_text())
    info = side.get("rhythmGridInfo") or {}
    stats = midi_stats(midi_path)

    label = info.get("subdivision")
    quantum = quantum_ticks(label, stats["division"])
    residuals = [tick_residual(t, quantum) for t, _ in stats["note_ticks"]]
    max_residual = max(residuals, default=0)

    tempo_meta_events = len(stats["tempo_ticks"])
    expected_tempo_events = int(info.get("tempoEvents") or 0)
    median_ms = float(info.get("previewMedianDifferenceMs") or 0)
    p95_ms = float(info.get("previewP95DifferenceMs") or 0)

    tempo_min_gap_ticks = None
    tempo_gap_violations = 0
    if info.get("tempoResolution") == "bar" and len(stats["tempo_ticks"]) > 1:
        signatures = sorted(stats["time_signatures"]) or [(0, 4, 4)]
        def signature_at(tick):
            current = signatures[0]
            for row in signatures:
                if row[0] > tick:
                    break
                current = row
            return current[1], current[2]
        gaps = []
        for a, b in zip(stats["tempo_ticks"], stats["tempo_ticks"][1:]):
            n, d = signature_at(a)
            min_gap = round(stats["division"] * 4 * n / d)
            gap = b - a
            gaps.append(gap)
            if gap < min_gap:
                tempo_gap_violations += 1
        tempo_min_gap_ticks = min(gaps) if gaps else None

    song_result = {
        "family": info.get("family"),
        "subdivision": label,
        "notes": len(stats["note_ticks"]),
        "grid_quantum_ticks": quantum,
        "max_grid_residual_ticks": max_residual,
        "tempo_meta_events": tempo_meta_events,
        "reported_tempo_events": expected_tempo_events,
        "tempo_resolution": info.get("tempoResolution"),
        "tempo_beats_per_measure": info.get("tempoBeatsPerMeasure"),
        "tempo_min_gap_ticks": tempo_min_gap_ticks,
        "tempo_gap_violations": tempo_gap_violations,
        "tempo_min": info.get("tempoMin"),
        "tempo_max": info.get("tempoMax"),
        "tempo_mean": info.get("tempoMean"),
        "straight16_share": info.get("straight16Share"),
        "straight32_only_share": info.get("straight32OnlyShare"),
        "preview_median_difference_ms": median_ms,
        "preview_p95_difference_ms": p95_ms,
    }
    results["songs"][song] = song_result

    if max_residual != 0:
        results["failures"].append(f"{song}: max grid residual {max_residual} ticks")
    if tempo_meta_events != expected_tempo_events:
        results["failures"].append(
            f"{song}: tempo event mismatch MIDI={tempo_meta_events} runtime={expected_tempo_events}"
        )
    if tempo_gap_violations:
        results["failures"].append(
            f"{song}: {tempo_gap_violations} tempo changes occur less than one measure apart"
        )
    if median_ms > 10:
        results["failures"].append(f"{song}: preview median timing delta {median_ms:.2f} ms > 10 ms")
    if p95_ms > 25:
        results["failures"].append(f"{song}: preview p95 timing delta {p95_ms:.2f} ms > 25 ms")

results["summary"] = {
    "songs": len(SONGS),
    "failures": len(results["failures"]),
    "max_grid_residual_ticks": max(
        x["max_grid_residual_ticks"] for x in results["songs"].values()
    ),
    "max_preview_median_difference_ms": max(
        x["preview_median_difference_ms"] for x in results["songs"].values()
    ),
    "max_preview_p95_difference_ms": max(
        x["preview_p95_difference_ms"] for x in results["songs"].values()
    ),
}

RESULT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(results, ensure_ascii=False, indent=2))

if results["failures"]:
    raise SystemExit("grid/tempo browser validation failed")
