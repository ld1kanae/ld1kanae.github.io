# Grid / Tempo Map Validation v28

Date: 2026-09-23

## Purpose

The user reported that the generated MIDI notes were slightly off the beat grid. This experiment treats that as an **export-timing problem**, not an instrument-classification problem.

- Kick/snare/tom/cymbal detection is not changed.
- Note starts are placed on a musical subdivision grid.
- Timing differences that would otherwise make the MIDI drift from the source are represented as MIDI tempo changes.
- Straight and triplet grids are evaluated separately.

## Reference-chart evidence

The existing gold charts already use this design.

| Song | Reference tempo events | BPM range | Notes exactly on 16th grid | Old generated MIDI exactly on 16th grid |
|---|---:|---:|---:|---:|
| diamondvirgin | 527 | 134.143–135.558 | 99.54% | 4.03% |
| nanairo | 419 | 125.010–125.059 | 100% | 0% |
| ray | 1 | 132.000 fixed | 100% | 0.50% |

`diamondvirgin` and `nanairo` keep notes on the score grid and express small performance drift through tempo events. `ray` is sufficiently stable to use one tempo event.

## Uploaded song

Inputs:

- `君は詩人になった [drums].wav`
- `君は詩人になった [drums]-drumscribe.mid`

The uploaded MIDI contained 1,211 notes at a fixed 134.00784 BPM. Only 3.80% of note starts were exactly on the straight 16th-note grid.

### Grid-family decision

| Candidate | Fit |
|---|---:|
| Straight 8th | 0.7259 |
| **Straight 16th** | **0.9673** |
| Straight 32nd | 0.8847 |
| Triplet 8th | 0.4855 |
| Triplet 16th | 0.6953 |

The song is therefore treated as straight 16th timing, not shuffle/triplet timing.

### Reconstructed confirmation MIDI

Output: `君は詩人になった [drums]-drumscribe-grid-v28.mid`

| Metric | Result |
|---|---:|
| Notes exactly on 16th grid | **100%** |
| Tempo events | 391 |
| Tempo range | 133.744–134.434 BPM |
| Mean tempo | 134.006 BPM |
| Median playback-time change from old MIDI | **2.81 ms** |
| 95th percentile playback-time change | **8.44 ms** |
| Maximum playback-time change | 50.00 ms |

This confirms that score ticks can be fully quantized while retaining almost all of the original audio-following timing.

## Audio-onset check

A spectral onset envelope was compared with the existing MIDI after optimizing one constant offset. The median absolute onset residual was approximately 7.1 ms, with a 95th percentile of 25.4 ms.

This is **not** a gold transcription score. It only indicates that the existing raw detected times already follow source transients reasonably well. The new export layer preserves those times through the tempo map instead of storing the deviations in note ticks.

## Straight / shuffle policy

GMD `beat` metadata contains 503 rows in the inspected split, of which 21 are explicitly labeled shuffle, swing, or triplet:

- jazz: 11
- rock: 4
- blues: 4
- funk: 1
- neworleans: 1

This supports using genre/pattern information as a prior, but not as a hard rule. The runtime policy is:

1. Compare straight 16th/32nd and triplet 8th/16th fits from actual detected event timing.
2. Select triplet timing only when it clearly exceeds the straight-grid fit.
3. Use GMD genre/pattern priors later only for borderline cases.

## Runtime changes

- `rhythm-grid.js`
  - chooses straight 16th/32nd or triplet subdivision;
  - estimates slow phase drift in overlapping windows;
  - snaps note starts to score ticks;
  - derives a quarter-note tempo map, clamped to ±3% around the base BPM.
- `midi.js`
  - writes the quantized ticks and tempo meta-events.
- `app.js`
  - previews the same tempo-mapped timing that is written to the MIDI file.
- `index.html`
  - loads the v28 export code with cache busting.

## Limitations

- The uploaded song has no corresponding gold `chart.mid`, so class-level precision/recall cannot be measured.
- The confirmation MIDI was reconstructed from the previously generated MIDI. A fresh browser transcription is still required to validate the complete WAV-to-MIDI path.
- Shuffle/triplet thresholds still require broader held-out calibration.

Raw metrics: [results-grid-tempo-v28.json](results-grid-tempo-v28.json)
