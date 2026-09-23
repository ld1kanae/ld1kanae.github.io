# Triplet / Shuffle Held-out Browser Validation v32

Date: 2026-09-23

## Purpose

Validate the current `rhythm-grid.js` straight/triplet branch on real drum audio that was not part of the five-song development set.

The Groove MIDI Dataset v1.0.0 predefined `validation` and `test` splits were used. Browser prediction never received the reference MIDI.

## Protocol

1. Inspect all 116 held-out rows with `beat_type=beat`.
2. Select 12 positive cases and 12 strict straight controls before browser transcription.
3. One positive is explicitly labeled `funk/purdieshuffle` in metadata.
4. Eleven positives satisfy a predeclared reference-MIDI timing-position rule:
   - triplet-only weighted share >= 0.10;
   - at least 0.04 above straight-only share;
   - triplet residual <= 0.80 × straight residual.
5. The 11 timing-evidence positives are not all explicitly named shuffle/swing/triplet. They are therefore a diagnostic timing label, not unquestionable musical-style ground truth.
6. Transcribe every WAV in real Playwright Chromium under two modes:
   - `auto`: WAV only;
   - `oracle_bpm`: WAV plus metadata BPM.
7. Read reference MIDI only after prediction for scoring and diagnostic evidence.

Workflow:
- run `35834772664`
- head `eff23fb1e087eac4f8f2afbb0c7e736f6d8376fe`
- result: success
- artifact `10739205616`

## Production-rule result

Current rule:

```text
bestTriplet >= 0.72
and bestTriplet > bestStraight + 0.10
```

| Mode | Triplet evidence | Triplet detected | Straight controls | Straight correct | Overall |
|---|---:|---:|---:|---:|---:|
| audio-only auto BPM | 12 | 2 | 12 | 12 | 14/24 = 58.3% |
| metadata BPM | 12 | 2 | 12 | 12 | 14/24 = 58.3% |

All 48 generated MIDI files had a maximum selected-grid residual of **0 ticks**. The problem is grid-family selection, not failure to snap after a family is selected.

Detected positives in both modes:
- `test-drummer1-session1-239` — `funk/purdieshuffle`, explicit metadata label, `1/16T`.
- `validation-drummer5-session2-15` — `latin/venezuelan-joropo`, reference-MIDI timing evidence, `1/16T`.

## Interpretation

The branch is conservative:
- no false triplet among the 12 strict straight controls;
- low sensitivity under the timing-evidence labeling rule: 2/12.

Supplying the correct BPM did not improve the aggregate result. Therefore BPM octave errors are not the only cause.

For three missed cases in the oracle-BPM condition, triplet fit exceeded straight fit but failed the absolute/margin gate. A post-hoc replay of `floor=0.45, margin=0.08` would detect 5/12 positives while retaining 12/12 straight controls on this same set. This is not an independent estimate and is not adopted.

For the other seven misses, the detected-event fit itself favored straight. Threshold relaxation alone cannot recover those cases. The next investigation should compare reference-MIDI timing evidence with:
- raw acoustic onset candidates before class filtering;
- final detected drum events;
- part-specific periodicity, especially hats/ride;
- bar- or phrase-level sequence/ranking evidence.

## Decision

Do not change production thresholds from v32 alone.

Reasons:
- only one positive has an explicit shuffle/swing/triplet metadata label;
- eleven positives use a timing-evidence diagnostic label;
- post-hoc threshold replay used the same evaluation set;
- most misses require better event evidence, not only a lower threshold.

Persisted summary:
- `results-gmd-triplet-heldout-v32-summary.json`

Reproducible files:
- `prepare_gmd_triplet_heldout.py`
- `browser_validate_gmd_triplet.mjs`
- `score_gmd_triplet_heldout.py`
- `.github/workflows/drumscribe-gmd-triplet-heldout.yml`
