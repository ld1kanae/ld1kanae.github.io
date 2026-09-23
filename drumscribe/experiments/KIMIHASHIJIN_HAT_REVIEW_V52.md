# 君は詩人になった — Alternating Hi-Hat Runtime v52

## Source and evaluation basis

- Source: uploaded `君は詩人になった [drums].wav`
- Duration: 181.79104166666667 sec
- SHA-256: `2a27998b8c38f0a80bfacc6605ba8a2e9674a6739cb4f3e96b03cac30993bda0`
- Fresh runtime BPM: 134.00772874831776
- Fresh runtime bar phase: 0.012158813638728061 sec
- No gold chart.mid exists for this song.
- Expected eighth-note slots are derived from the user's ten review comments and the supplied BPM/bar phase. Exact short-range grid alignment is an evaluation interpretation, not a runtime rule.

## Root cause

1. The pre-v52 Open classifier produced compressed probabilities on this source: maximum 0.656499 and current Open ratio 0.052419. It produced no trusted-Open anchors, so the existing decay self-calibration and GMD open-run rescue could not bootstrap.
2. In the reviewed alternating passages, legacy Open probability was lower on the sequence model's Open parity than on its Closed parity: mean 0.382673 vs 0.481576, delta -0.098903. The previous current-hit classifier was therefore systematically reversed in this acoustic domain.
3. The problem was not articulation-only. Some eighth-note slots had been removed before articulation classification, some were emitted as Crash, and some extra sixteenth-note metal events remained.

## Implemented runtime

- `models/alternating-hi-hat-review-v1.json`
  - 20 sequence features from 3–6, 6–10, 10–16 and 16–21 kHz.
  - Features include pre-hit energy, current tail, energy before the next eighth note, and energy after the next articulation/choke.
  - Leave-one-review-range-out: precision 0.9023, recall 0.9458, F1 0.9235, accuracy 0.9224.
- `hat-sequence.js`
  - Detects strongly supported alternating eighth-note runs.
  - Reassigns 42/46 articulation.
  - Converts in-run Crash/Ride candidates to HH when the sequence evidence requires it.
  - Removes off-eighth metal inside the accepted run.
  - Restores a missing slot only when broad ADTOF metal evidence or a strong high-band onset exists and the two-hand guard allows it.
- Song-local inversion gate:
  - no song name, filename or review time range is used;
  - requires enough legacy probability samples;
  - requires negative legacy-vs-sequence parity correlation;
  - requires compressed maximum legacy Open probability;
  - requires a low current Open ratio.

## Three-hypothesis comparison on the ten reviewed ranges

| Variant | Exact 42/46 F1 | Exact precision | Exact recall | Onset F1 | Pred / Ref |
|---|---:|---:|---:|---:|---:|
| off | 0.357143 | 0.415020 | 0.313433 | 0.755102 | 253 / 335 |
| inversion-articulation | 0.751701 | 0.873518 | 0.659701 | 0.755102 | 253 / 335 |
| inversion-metal-grid | 0.779541 | 0.952586 | 0.659701 | 0.783069 | 232 / 335 |
| **inversion-guarded-rescue** | **0.877193** | **0.941781** | **0.820896** | **0.880383** | **292 / 335** |

## Per-review exact 42/46 matches

| Review | Reference hits | Before exact TP | v52 exact TP | v52 onset TP |
|---:|---:|---:|---:|---:|
| 1 | 8 | 2 | **7** | 7 |
| 2 | 2 | 1 | **2** | 2 |
| 3 | 4 | 2 | **4** | 4 |
| 4 | 125 | 35 | **87** | 88 |
| 5 | 55 | 22 | **48** | 48 |
| 6 | 2 | 1 | **2** | 2 |
| 7 | 26 | 7 | **24** | 24 |
| 8 | 8 | 2 | **7** | 7 |
| 9 | 52 | 14 | **49** | 49 |
| 10 | 53 | 19 | **45** | 45 |

The result is a large improvement but not a claim of complete recovery. Long Review 4 still has substantial missed eighth-note slots; Review 8 still contains extra predicted metal events.

## Fresh default-runtime target check

- Default variant: `inversion-guarded-rescue`
- Gate: true
- accepted windows: 425
- runs: 17
- selected eighth slots: 581
- articulation/class changes: 211
- Crash/Ride-to-HH conversions: 18
- off-grid metal removals: 25
- guarded rescues: 96
- final event count: 1323
- final target K/S/T counts: kick 418 / snare 260 / tom 18 — unchanged from baseline
- Default-runtime event list exactly matched the selected v51 H3 candidate.

## Existing five-song non-regression

Fresh default-runtime validation on `arcaround / diamondvirgin / kaiju / nanairo / ray`:

- inversion gate fired on 0 / 5 songs;
- exact event-list equality versus the previous default baseline: true;
- kick F1 0.962571, delta 0;
- snare F1 0.900035, delta 0;
- tom F1 0.784091, delta 0;
- Closed HH F1 0.843895, delta 0;
- Open HH F1 0.602285, delta 0;
- collapsed HH/Ride F1 0.812081, delta 0.

Prediction did not read chart.mid. Reference MIDI was opened only by the post-generation scorer.

## Rejected experiment

Ungated v50 rewrote 467 events across the five reference songs and reduced HH macro F1 from 0.723090 to 0.630352–0.615707. It was rejected. The v51 inversion gate is what made production adoption acceptable.
