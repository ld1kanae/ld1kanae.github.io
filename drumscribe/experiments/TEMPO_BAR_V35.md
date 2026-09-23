# Tempo-map validation v35 — one BPM change per measure

Date: 2026-09-23

## Request

Keep the current quantization, BPM detection, downbeat detection, and note ticks unchanged, but stop emitting MIDI tempo changes at one-beat resolution. Tempo changes should occur no more often than once per measure.

## Implementation

`rhythm-grid.js` still estimates slow timing drift at beat resolution internally.

For each measure, the beat-level BPM sequence is converted to one **duration-equivalent bar BPM**:

- sum the playback duration implied by the beat-level tempos inside the bar
- compute the single BPM that gives the same total score duration for that bar
- emit that BPM only at the bar start
- use the same bar-level BPM sequence for preview `timeForScore()` and exported MIDI

Therefore:
- note score ticks are unchanged
- grid family/subdivision decisions are unchanged
- transcription classes are unchanged
- bar-boundary timing is preserved
- intra-bar micro-tempo variation is intentionally flattened

The runtime reports:
- `tempoResolution: "bar"`
- `tempoBeatsPerMeasure`

## Proof v34 MIDI tempo-only rewrite

Existing Proof v34 MIDI was rewritten by changing tempo metadata only.

- meter: 4/4
- tempo events: **426 -> 110**
- note ticks changed: **no**
- note-time delta vs old beat-level tempo map:
  - median **0.054 ms**
  - p95 **0.521 ms**
  - max **1.166 ms**
- bar-boundary cumulative timing delta:
  - median **0.005 ms**
  - max **0.010 ms**
- bar BPM range: **98.735–100.369**

This shows that bar aggregation removes most tempo events while preserving the existing v34 musical timeline to well below audible timing thresholds.

## Five-song fresh Chromium regression

Workflow run: `35849376347` — success.

| Song | Old tempo events | Bar-level events | Minimum event gap | Violations |
|---|---:|---:|---:|---:|
| arcaround | 549 | 139 | 1920 ticks | 0 |
| diamondvirgin | 589 | 149 | 1920 ticks | 0 |
| kaiju | 594 | 153 | 1920 ticks | 0 |
| nanairo | 491 | 127 | 1920 ticks | 0 |
| ray | 557 | 142 | 1920 ticks | 0 |

At PPQ 480 in 4/4, 1920 ticks is exactly one measure.

Aggregate transcription:
- Precision **0.911**
- Recall **0.743**
- F1 **0.818**
- grid failures **0**
- max exported grid residual **0.0 beat**

Preview raw-to-grid p95 timing deltas:
- arcaround 13.57 ms
- diamondvirgin 17.82 ms
- kaiju 13.10 ms
- nanairo 8.66 ms
- ray 6.56 ms

These remain within the existing CI limits and are effectively unchanged from the beat-resolution implementation.

## CI guard

`experiments/validate_grid_browser.py` now fails if `tempoResolution == "bar"` and any two exported tempo meta events occur less than one current measure apart.

This directly protects the requested invariant in future changes.

## Files

Changed:
- `rhythm-grid.js`
- `app.js`
- `midi.js`
- `index.html`
- `experiments/validate_grid_browser.py`

Results:
- `experiments/results-tempo-bar-v35.json`

