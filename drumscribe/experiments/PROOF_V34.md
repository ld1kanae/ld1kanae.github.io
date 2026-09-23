# Proof v34 — tempo octave / GMD bar-phase validation

Date: 2026-09-23

## Problem reproduced

User-supplied drums:
- `1_1_Proof v6 (Add Vocal)_(Instrumental)_(Drums).wav`

Companion instrumental:
- `1_Proof v6 (Add Vocal)_(Instrumental).wav`

The user reports the real tempo is around 99 BPM and changes slightly.

Current main fresh auto analysis selected:
- BPM **198.163893889**
- beat phase **0.193377 s**
- bar phase **1.092027 s**

The same transcription's event-family estimator independently ranked:
- **99.125 BPM** score **0.66037**
- 198.25 BPM score **0.42309**

The ratio is **1.99913x**, and the lower-octave candidate wins by **0.23728**. The previous runtime only used event-family correction when spectral confidence was below 0.10, so this high-confidence octave error escaped correction.

## Tempo fix

Added a conservative octave-down gate:
- initial/event-family ratio 1.90–2.10
- event-family score >= 0.58
- event-family score margin over the candidate nearest the initial BPM >= 0.12

Proof satisfies all three conditions.

The refined candidate is:
- BPM **99.076668**
- source `audio-event-octave-corrected`

This is not a generic “halve fast BPMs” rule. The correction requires the independent kick/snare event-family evidence to beat the 2x candidate by a substantial margin.

## GMD bar-phase model

A dedicated model was trained from the **official GMD train split only** and stored at:

- `models/gmd-kst/bar-phase-discriminative-v1.json`

Three hypotheses were compared on a deterministic internal holdout carved only from GMD train:

| Hypothesis | Bar accuracy | Performance accuracy |
|---|---:|---:|
| phase log probability | 58.74% | 62.65% |
| Bernoulli presence | 58.42% | 60.24% |
| logistic rotation | **61.99%** | **66.27%** |

The logistic model was selected before examining official validation/test.

Official held-out results are report-only:
- validation performance accuracy: **54.10%**
- test performance accuracy: **75.86%**

Therefore this model is **not trusted as a general bar-line detector**.

Runtime policy is deliberately narrow: it is queried only after the high-confidence 2x tempo correction above has fired. It can never create, delete, move, or reclassify drum hits; it only ranks 4/4 phase hypotheses.

On the saved full-song 99-BPM Proof transcription:
- selected phase: **0.123011 s**
- runner-up phase: 1.088172 s
- margin: **0.77551**
- usable windows: 93
- coverage: **88.57%**

Runtime gates are margin >= 0.55 and coverage >= 0.55, so Proof passes.

A previous full-browser v34 prototype of the same WAV reached:
- BPM **99.076668**
- bar phase **0.127742 s**
- bar source `gmd-kst-gated`
- grid `1/16+1/32`
- 426 tempo events
- tempo range 98.710–100.389 BPM
- raw→preview median 3.36 ms
- p95 15.03 ms

## Instrumental / off-vocal evidence

The instrumental was analyzed independently for large arrangement/timbre changes using 0.75 s frames, 0.375 s hop and local novelty.

For 10 strong section-change candidates:
- old 99-BPM bar phase 1.039 s: median distance to nearest bar line **895.9 ms**
- GMD phase 0.123 s: median distance **366.9 ms**

Thus the instrumental supports the new phase much better than the old phase.

However section novelty alone does not identify a unique bar phase reliably. Arrangement boundaries may be offset or blurred, and the analysis hop is coarse relative to a beat. Therefore off-vocal/instrumental structure remains **auxiliary evidence**, not a forced downbeat source.

## Five-song fresh regression

Real Chromium workflow:
- run `35846141342`
- result: **success**

Fresh results:

| Song | BPM | Tempo source | GMD phase fired |
|---|---:|---|---|
| arcaround | 132.002953 | audio | no |
| diamondvirgin | 135.075370 | audio | no |
| kaiju | 180.006816 | audio | no |
| nanairo | 125.006439 | audio-event-corrected | no |
| ray | 131.999934 | audio | no |

The note counts and transcription results remained identical to baseline:
- Precision **0.911**
- Recall **0.743**
- F1 **0.818**
- grid failures **0**
- max exported grid residual **0.0 beat**

This is intentional: the new GMD phase correction did not activate on any of the existing five songs.

## Files

Runtime:
- `transcribe.js`
- `gmd-bar-phase.js`
- `models/gmd-kst/bar-phase-discriminative-v1.json`

Training / audit:
- `experiments/gmd-kst/train_bar_phase_model.py`
- `experiments/gmd-kst/results-gmd-bar-phase-heldout-v1.json`
- `experiments/results-proof-v34.json`

## Caveat

A final local full-WAV run using the repository-packaged runtime exceeded the execution cap. This is not counted as a completed fresh validation.

The evidence used for promotion is:
1. a prior full-browser v34 prototype on the same complete WAV,
2. replay of the final tempo and GMD gates against saved full-song events,
3. an unchanged five-song real-Chromium regression suite.

The next time the Proof WAV is run in the public UI, its exported MIDI should be checked by ear against the supplied instrumental as the final user-facing acceptance test.
