"""Post-process audio-derived MIDI with review-motivated rhythm guards.

Only candidate MIDI and song tempo are read to propose notes. Chart MIDI is
loaded strictly after the output MIDI is written, for evaluation.
"""
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "drumscribe" / "experiments"
DATA = ROOT / "DruMaster/songs" if (ROOT / "DruMaster/songs/arcaround/chart.mid").exists() else ROOT.parent / "data"
SONGS = ("arcaround", "diamondvirgin", "kaiju", "nanairo", "ray")
SOURCE = EXP / "generated-search-fusion-v6/cycle144/c144_adaptive"
OUTPUT = EXP / "generated-review-guards"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ev = module("evaluate_v2_review", EXP / "evaluate_v2.py")
writer = module("iterative_review", EXP / "iterative_search.py")


def supports(times, t, interval, radius=.065):
    return any(abs(other - t - step * interval) <= radius
               for other in times for step in (-1, 1))


def transform(rows, bpm, mode):
    beat = 60 / bpm
    kick = [t for t, g in rows if g == "kick"]
    snare = [t for t, g in rows if g == "snare"]
    hats = [t for t, g in rows if g == "hat"]
    rides = [t for t, g in rows if g == "ride"]
    crash = [t for t, g in rows if g == "crash"]
    simultaneous = [t for t in snare if any(abs(k-t) <= .045 for k in kick)]
    beat_pairs = sum(supports(snare, t, beat) for t in simultaneous)
    suspect_bleed = len(simultaneous) >= 30 and beat_pairs >= 20 and beat_pairs / len(simultaneous) >= .30
    output = []
    for t, group in rows:
        near_kick = any(abs(k - t) <= .045 for k in kick)
        if group == "snare" and mode in ("snare", "all", "density", "adaptive_snare", "review_strict", "kick_veto") and near_kick:
            # Kick bleed often creates a false snare on consecutive kick beats;
            # preserve a repeating backbeat and other synchronized strokes.
            on_beat_pair = supports(snare, t, beat)
            on_backbeat = supports(snare, t, 2 * beat) or supports(snare, t, 4 * beat)
            if suspect_bleed and mode == "kick_veto":
                continue
            if (on_beat_pair or suspect_bleed and mode in ("adaptive_snare", "review_strict")) and not on_backbeat:
                continue
        if group == "hat" and mode in ("hat", "all", "density", "review_strict") and near_kick:
            # An isolated kick-coincident high-frequency attack can be kick bleed.
            if not (supports(hats, t, beat / 2) or supports(hats, t, beat)):
                continue
        if group == "crash" and mode in ("metal", "all", "density", "review_strict"):
            if mode in ("density", "review_strict") and not near_kick and not any(abs(s-t) < .07 for s in snare):
                continue
            if sum(abs(c-t) <= 1.5 * beat for c in crash) >= 3 and not near_kick:
                continue
        if group == "ride" and mode in ("metal", "all", "density", "review_strict"):
            if not (supports(rides, t, beat / 2) or supports(rides, t, beat)):
                continue
        output.append((t, group))
    if mode in ("density", "review_strict"):
        # One loud cymbal attack per beat at most within dense ride passages.
        thinned = []
        last = -999.
        for t, group in output:
            if group == "ride" and t - last < .7 * beat:
                continue
            if group == "ride":
                last = t
            thinned.append((t, group))
        output = thinned
    return output


def main():
    results = {}
    for mode in ("baseline", "snare", "hat", "metal", "all", "density", "adaptive_snare", "review_strict", "kick_veto"):
        summary = Counter()
        songs = {}
        for song in SONGS:
            meta = json.loads((DATA / song / "song.json").read_text())
            rows = [(t, g) for t, g, *_ in ev.midi_events(SOURCE / f"{song}.mid")]
            pred = rows if mode == "baseline" else transform(rows, float(meta["bpm"]), mode)
            out = OUTPUT / mode / f"{song}.mid"
            writer.write_midi(out, [dict(time=t, group=g, score=1., confidence=1.) for t, g in pred], float(meta["bpm"]))
            predicted = ev.midi_events(out)
            truth = ev.midi_events(DATA / song / "chart.mid")
            shift = meta["playback"]["stemOffsetSec"] + meta["playback"].get("midiOffsetSec", 0)
            score = ev.score(predicted, truth, shift)
            confusion = ev.confusion(predicted, truth, shift)
            songs[song] = dict(score=score, confusion=confusion)
            summary.update(tp=score["tp"], predicted=score["predicted"], reference=score["reference"],
                           kick_to_snare=confusion["kick_to_snare"])
            for g, x in score["by_group"].items():
                summary.update({g+"_tp":x["tp"],g+"_pred":x["predicted"],g+"_ref":x["reference"]})
        tp, n, r = (summary[k] for k in ("tp", "predicted", "reference"))
        results[mode] = dict(summary=dict(summary, f1=round(2*tp/(n+r), 4)), songs=songs)
        print(mode, "F1", results[mode]["summary"]["f1"], "kick→snare", summary["kick_to_snare"],
              "arcaround snare", songs["arcaround"]["score"]["by_group"]["snare"], flush=True)
    (EXP / "results-human-review-guards.json").write_text(json.dumps(results, ensure_ascii=False, separators=(",", ":"))+"\n")
    modes = {"adaptive_snare":"c145_snare", "review_strict":"c145_rhythm", "kick_veto":"c145_kick_veto"}
    ui = {"schema":1,"cycles":[{"cycle":145,"candidates":{}}]}
    for mode, key in modes.items():
        source = results[mode]
        songs = {}
        for song, x in source["songs"].items():
            songs[song] = dict(x["score"], confusion=x["confusion"])
        ui["cycles"][0]["candidates"][key] = {"summary":source["summary"],"songs":songs}
    (EXP / "results-human-review-ui.json").write_text(json.dumps(ui, ensure_ascii=False, separators=(",", ":"))+"\n")


if __name__ == "__main__":
    main()
