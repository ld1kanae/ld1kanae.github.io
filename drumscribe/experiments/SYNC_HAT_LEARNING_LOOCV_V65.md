# Synchronized Hi-Hat Learning LOOCV v65

Date: 2026-09-24

## Scope

- Inputs: five user-supplied, tempo-mapped synchronized WAV/MIDI pairs: arcaround, diamondvirgin, kaiju, nanairo, ray.
- Candidate generation reads WAV only. The synchronized MIDI is used only for candidate labeling and scoring.
- Validation is leave-one-song-out: each held-out song is excluded from model fitting and threshold selection.
- Candidate-to-reference labeling is one-to-one within ±80 ms.
- Positive class: Open HH (GM 46). Negative class in H2: Closed HH, Pedal HH, Ride, Crash, and unmatched/false candidates.
- Runtime feature family: per-hit attack/decay/tail/choke vector plus existing Open probability, detector score/confidence, and current articulation. No song name, review interval, beat parity, or reference MIDI is a runtime input.

## Dataset

- `arcaround`: 990 candidates; labels `{'false': 516, 'closed': 180, 'crash': 62, 'open': 92, 'pedal': 88, 'ride': 52}`
- `diamondvirgin`: 1322 candidates; labels `{'false': 531, 'crash': 61, 'open': 407, 'closed': 200, 'ride': 120, 'pedal': 3}`
- `kaiju`: 955 candidates; labels `{'crash': 80, 'false': 66, 'closed': 561, 'open': 22, 'pedal': 7, 'ride': 219}`
- `nanairo`: 1343 candidates; labels `{'closed': 805, 'false': 180, 'crash': 24, 'open': 240, 'pedal': 94}`
- `ray`: 1678 candidates; labels `{'crash': 52, 'pedal': 123, 'false': 170, 'open': 321, 'closed': 1012}`

Total candidates: 6,288.

## Hypotheses

- H1 `clean_logreg`: learn Open vs Closed only; ignore Ride/Pedal/Crash/false candidates during fitting.
- H2 `allneg_extra`: learn Open vs every non-Open candidate with ExtraTrees.
- H3 `allneg_localnorm`: H2 plus within-song rank and robust-z normalization.

## Aggregate leave-one-song-out results

| variant | Closed F1 | Open F1 | HH macro | delta HH | Hat/Ride onset F1 | Metal macro |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.644092 | 0.612691 | 0.628392 | +0.000000 | 0.769563 | 0.257940 |
| H1_clean_logreg | 0.758754 | 0.616988 | 0.687871 | +0.059479 | 0.769563 | 0.281732 |
| H2_allneg_extra | 0.652164 | 0.761117 | 0.706640 | +0.078249 | 0.769563 | 0.289239 |
| H2_allneg_extra_t55 | 0.652781 | 0.766220 | 0.709501 | +0.081109 | 0.769563 | 0.290384 |
| H2_allneg_extra_t60 | 0.648331 | 0.728238 | 0.688284 | +0.059893 | 0.769563 | 0.281897 |
| H2_allneg_extra_t65 | 0.644995 | 0.694565 | 0.669780 | +0.041389 | 0.769563 | 0.274495 |
| H3_allneg_localnorm | 0.640576 | 0.652442 | 0.646509 | +0.018118 | 0.769563 | 0.265187 |

Best fixed policy: `H2_allneg_extra_t55`. It improves HH macro F1 from **0.628392 to 0.709501 (+0.081109)**. Open F1 rises from **0.612691 to 0.766220**. Closed F1 rises from **0.644092 to 0.652781**. Collapsed Hat/Ride onset F1 is exactly unchanged at **0.769563**, confirming that this stage changes articulation only.

## Per-song HH macro F1 — fixed H2 threshold 0.55

- `arcaround`: 0.220755 -> **0.609167** (+0.388412)
- `diamondvirgin`: 0.190570 -> **0.289575** (+0.099004)
- `kaiju`: 0.367628 -> **0.642780** (+0.275152)
- `nanairo`: 0.901732 -> **0.917965** (+0.016233)
- `ray`: 0.869218 -> **0.910562** (+0.041344)

All five held-out songs improve; no per-song HH macro regression was observed.

## Compact-model sweep

- 500 trees / depth 14: HH macro 0.709501; serialized model about 4.6 MB.
- 100 trees / depth 12: HH macro 0.696128; all five songs still improve; serialized model about 0.75 MB.
- 80 trees / depth 10: HH macro 0.686972, but diamondvirgin regresses slightly versus baseline, so it is rejected.

The 100-tree/depth-12 model is the current portable production candidate. The 500-tree model remains the accuracy ceiling for this experiment.

## Data identity

- Candidate JSON SHA-256: `d0a74a14a1d365c854cccb65eddc5cca23efb6d933f4b96682a704c0fdd8d3ef`
- Result JSON SHA-256: `05cd9409247430b663709bf4488c20800aa96ffeee178d89ffe02b78e9a698fc`
- Pair hashes are recorded in the project handoff for exact re-identification.

## Current status

- Learning/validation: complete.
- Production runtime integration: not yet enabled in main at this point in the chronology.
- Required next step: serialize the 100-tree H2 model, add an audio-only runtime rescoring stage after v57 Ride rescue, then run browser replay and K/S/T exact non-regression checks before enabling by default.
