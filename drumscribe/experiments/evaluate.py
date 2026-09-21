"""Reproducible, dependency-light drum transcription experiments.

Run: python drumscribe/experiments/evaluate.py --data ../data --seconds 90
Input is the unmodified DruMaster song data; no reference MIDI is used by the
transcriber. Labels are consulted only after predictions have been generated.
"""
import argparse
import json
import subprocess
import wave
from pathlib import Path
from collections import Counter

import numpy as np
from scipy.ndimage import maximum_filter1d, median_filter
from scipy.signal import find_peaks, resample_poly

SR, FFT, HOP = 11025, 1024, 110
GROUPS = {
    "kick": (35, 36), "snare": (37, 38, 39, 40),
    "hat": (42, 44, 46), "tom": (41, 43, 45, 47, 48, 50),
    "cymbal": (49, 51, 52, 53, 55, 57, 58, 59),
}
ORDER = list(GROUPS)
MIDI_PITCH = dict(zip(ORDER, [36, 38, 42, 45, 49]))


def variable(data, i):
    result = 0
    while True:
        b = data[i]; i += 1
        result = (result << 7) | (b & 127)
        if not b & 128: return result, i


def midi_events(path):
    data = Path(path).read_bytes()
    assert data[:4] == b"MThd"
    division = int.from_bytes(data[12:14], "big")
    tracks, pos = [], 8 + int.from_bytes(data[4:8], "big")
    while pos < len(data) and data[pos:pos + 4] == b"MTrk":
        size = int.from_bytes(data[pos + 4:pos + 8], "big")
        end = pos + 8 + size; i = pos + 8; tick = 0; running = 0; notes = []; tempos = []
        while i < end:
            delta, i = variable(data, i); tick += delta
            status = data[i]
            if status & 128: i += 1; running = status
            else: status = running
            if status == 255:
                typ = data[i]; i += 1; n, i = variable(data, i)
                if typ == 81 and n == 3: tempos.append((tick, int.from_bytes(data[i:i + 3], "big")))
                i += n
            elif status in (240, 247):
                n, i = variable(data, i); i += n
            else:
                op = status & 240; channel = status & 15
                n = 1 if op in (192, 208) else 2
                pitch = data[i]; velocity = data[i + 1] if n == 2 else 0; i += n
                if op == 144 and velocity > 0: notes.append((tick, pitch, channel))
        tracks.append((notes, tempos)); pos = end
    tempos = sorted([t for _, tt in tracks for t in tt] or [(0, 500000)])
    if tempos[0][0] != 0: tempos.insert(0, (0, 500000))
    starts = [0.0]
    for (t, us), (t2, _) in zip(tempos, tempos[1:]):
        starts.append(starts[-1] + (t2 - t) * us / 1e6 / division)
    allnotes = [n for ns, _ in tracks for n in ns]
    channels = Counter(c for _, p, c in allnotes if 35 <= p <= 59)
    use_channel = 9 if channels[9] else (channels.most_common(1)[0][0] if channels else 9)
    out = []
    for tick, pitch, channel in allnotes:
        if channel != use_channel: continue
        group = next((g for g, pitches in GROUPS.items() if pitch in pitches), None)
        if group is None: continue
        j = np.searchsorted([t for t, _ in tempos], tick, side="right") - 1
        sec = starts[j] + (tick - tempos[j][0]) * tempos[j][1] / 1e6 / division
        out.append((sec, group, pitch))
    return sorted(out)


def audio(path, seconds=None):
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR)]
    if seconds: cmd += ["-t", str(seconds)]
    cmd += ["-f", "f32le", "-acodec", "pcm_f32le", "-"]
    return np.frombuffer(subprocess.check_output(cmd), dtype="<f4").copy()


def spectrum(x):
    x = np.pad(x, (FFT // 2, FFT // 2))
    frames = np.lib.stride_tricks.sliding_window_view(x, FFT)[::HOP]
    return np.abs(np.fft.rfft(frames * np.hanning(FFT), axis=1)).astype("f4").T


def templates(folder):
    by_group = {g: [] for g in ORDER}
    for group, pitches in GROUPS.items():
        for pitch in pitches:
            p = folder / f"{pitch}.wav"
            if not p.exists(): continue
            with wave.open(str(p)) as w:
                raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("f4") / 32768
                raw = raw.reshape(-1, w.getnchannels()).mean(axis=1)
                x = resample_poly(raw, SR, w.getframerate())
            by_group[group].append(spectrum(x[:int(.15 * SR)])[:, 2:12].mean(axis=1))
    return np.stack([np.mean(by_group[g], axis=0) for g in ORDER], axis=1)


def features(spec, tmpl):
    # Local positive flux cancels sustained cymbals; retain instantaneous spectrum.
    rise = np.maximum(spec - np.pad(spec[:, :-2], ((0, 0), (2, 0))), 0)
    freqs = np.arange(spec.shape[0]) * SR / FFT
    bands = [(35, 140), (140, 900), (900, 3000), (3000, 5500)]
    flux = np.stack([rise[(freqs >= lo) & (freqs < hi)].sum(axis=0) for lo, hi in bands])
    baseline = median_filter(flux, size=(1, 101))
    flux = np.maximum(flux - baseline * .6, 0)
    bandnorm = np.percentile(flux, 98, axis=1)[:, None] + 1e-7
    bandscores = flux / bandnorm
    # Whiten spectral bins, then cosine similarity to source kit templates.
    whitening = np.maximum(np.mean(spec, axis=1), np.percentile(np.mean(spec, axis=1), 35))
    whitening = np.maximum(whitening, 1e-3) ** .6
    a = rise / whitening[:, None]
    b = tmpl / whitening[:, None]
    b /= np.linalg.norm(b, axis=0, keepdims=True) + 1e-8
    sims = b.T @ a
    sims /= np.linalg.norm(a, axis=0, keepdims=True) + 1e-8
    return bandscores, sims


def candidates(band, sim, pattern):
    # All thresholds use only observed audio statistics, never chart labels.
    if pattern == "bands":
        signals = np.stack([band[0], band[1], band[3], band[1], band[2]])
        thresholds = [.25, .3, .25, .28, .25]
    elif pattern == "templates":
        signals = sim
        thresholds = [.42, .45, .4, .4, .43]
    elif pattern == "fusion":
        signals = .55 * sim + .45 * np.stack([band[0], band[1], band[3], band[1], band[2]])
        thresholds = [.36, .38, .36, .38, .36]
    elif pattern == "adaptive":
        signals = .48 * sim + .52 * np.stack([band[0], band[1], band[3], band[1], band[2]])
        thresholds = [.31, .32, .38, .38, .39]
    elif pattern == "selective":
        signals = .55 * sim + .45 * np.stack([band[0], band[1], band[3], band[1], band[2]])
        thresholds = [.42, .42, .45, .44, .46]
    elif pattern in ("band-gated", "band-balanced", "band-rhythm", "band-hybrid", "band-precision", "band-conservative", "band-controlled"):
        signals = np.stack([band[0], band[1], band[3], band[1], band[2]])
        thresholds = {
            "band-gated": [.38, .47, .24, 1.0, .65],
            "band-balanced": [.53, .65, .20, 1.4, .82],
            "band-rhythm": [.48, .55, .13, 1.2, .85],
            "band-hybrid": [.51, .60, .16, 1.3, .83],
            "band-precision": [.58, .70, .19, 1.5, 1.0],
            "band-conservative": [.58, .70, .19, 2.3, 1.5],
            "band-controlled": [.58, .70, .19, 3.0, 2.0],
        }[pattern]
    events = []
    for idx, group in enumerate(ORDER):
        s = signals[idx]
        floor = np.maximum(thresholds[idx], median_filter(s, size=201) * 2.4)
        distance = int(([.075, .075, .055, .09, .12][idx]) * SR / HOP)
        peaks, _ = find_peaks(s, distance=distance, prominence=.07)
        for p in peaks:
            if pattern.startswith("band-"):
                if idx == 0 and band[0,p] < .48 * band[1,p]: continue
                if idx == 1 and band[1,p] < .62 * band[0,p]: continue
                strict = pattern in ("band-conservative", "band-controlled")
                if idx == 3 and (sim[3,p] < (.6 if strict else .44) or sim[3,p] < (1.05 if strict else .85) * max(sim[0,p],sim[1,p])): continue
                if idx == 4 and sim[4,p] < (.52 if strict else .39): continue
            if s[p] >= floor[p]: events.append((p * HOP / SR, group, float(s[p])))
    return sorted(events)


def score(pred, truth, shift=0, tol=.08):
    totals = Counter(); hits = Counter(); errors = []
    for group in ORDER:
        a = np.array([t for t, g, _ in pred if g == group]); b = np.array([t + shift for t, g, *_ in truth if g == group])
        totals[group] = (len(a), len(b))
        if not len(a) or not len(b): continue
        # Greedy ordered one-to-one match: timeline timestamps and small tolerance.
        used = set()
        for x in a:
            j = np.searchsorted(b, x)
            options = [k for k in (j-1, j, j+1) if 0 <= k < len(b) and k not in used]
            if options:
                k = min(options, key=lambda k: abs(x - b[k]))
                if abs(x - b[k]) <= tol: hits[group] += 1; used.add(k); errors.append(x-b[k])
    tp = sum(hits.values()); n = sum(v[0] for v in totals.values()); m = sum(v[1] for v in totals.values())
    return dict(tp=tp, predicted=n, reference=m, precision=round(tp / n, 3) if n else 0, recall=round(tp / m, 3) if m else 0, f1=round(2 * tp / (n + m), 3) if n+m else 0,
                by_group={g:dict(tp=hits[g], predicted=totals[g][0], reference=totals[g][1]) for g in ORDER}, median_error=round(float(np.median(errors)), 3) if errors else None)


def main():
    p = argparse.ArgumentParser(); p.add_argument("--data", type=Path, required=True); p.add_argument("--seconds", type=float, default=90); p.add_argument("--output", type=Path)
    p.add_argument("--patterns", nargs="+", default=["bands", "templates", "fusion", "adaptive", "selective", "band-gated", "band-balanced", "band-rhythm", "band-hybrid", "band-precision", "band-conservative", "band-controlled"])
    p.add_argument("--diagnostic", action="store_true", help="Sweep timing for inspection only; never use sweep for scored comparisons")
    args = p.parse_args(); tmpl = templates(args.data / "samples")
    results = {}
    for folder in sorted(args.data.iterdir()):
        if not (folder / "song.json").exists(): continue
        meta = json.loads((folder / "song.json").read_text())
        # Editor schedules audio at logical_time + stemOffsetSec and MIDI at
        # midi_time + midiOffsetSec, hence their local time difference is sum.
        shift = meta["playback"]["stemOffsetSec"] + meta["playback"].get("midiOffsetSec", 0)
        x = audio(folder / "drums.mp3", args.seconds); spec = spectrum(x)
        band, sim = features(spec, tmpl)
        truth = [(t,g,p) for t,g,p in midi_events(folder / "chart.mid") if 0 <= t+shift < len(x)/SR]
        # Report fixed metadata shift and a separate diagnostic ±5s alignment sweep.
        tests = {}
        for pattern in args.patterns:
            pred = candidates(band, sim, pattern)
            tests[pattern] = score(pred, truth, shift)
            if args.diagnostic and pattern == "fusion":
                sweep = [(s, score(pred, truth, s)["f1"]) for s in np.arange(shift-5, shift+5.01, .05)]
                best = max(sweep, key=lambda z:z[1]); tests["alignment_diagnostic"] = dict(shift=round(float(best[0]),3), f1=best[1], metadata_shift=shift)
        results[folder.name] = tests
        print(folder.name, "reference", len(truth), "metadata shift", shift, "f1", {k:v["f1"] for k,v in tests.items() if "f1" in v}, "diagnostic",tests.get("alignment_diagnostic"),flush=True)
    if args.output: args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False)+"\n")


if __name__ == "__main__": main()
