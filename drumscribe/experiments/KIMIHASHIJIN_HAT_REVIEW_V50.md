# 君は詩人になった — Alternating Hi-Hat Review v50

Source: uploaded `君は詩人になった [drums].wav` (181.791 s).

Reference is the user's ten review ranges, aligned to the supplied BPM/bar phase eighth-note grid. This song has no gold chart.mid; short-range grid alignment is an explicit evaluation interpretation and is not encoded as song/time-specific runtime logic.

## Root cause

- Current open-hat probabilities are compressed (target maximum ≈ 0.656), leaving zero trusted-open anchors; therefore the existing decay self-calibration and GMD open-run rescue do not bootstrap.
- In alternating open→closed passages, the current-hit classifier often attributes the previous open tail to the following closed hit. It therefore systematically reverses the 42/46 parity in this domain.
- Some reviewed slots are lost before articulation classification (high-hat suppressor / cymbal selection), while extra sixteenth-note metal candidates remain in other passages.

## Target review aggregate

| Variant | Exact 42/46 F1 | Exact precision | Exact recall | Onset F1 | Pred / Ref |
|---|---:|---:|---:|---:|---:|
| off | 0.357143 | 0.415020 | 0.313433 | 0.755102 | 253 / 335 |
| articulation | 0.751701 | 0.873518 | 0.659701 | 0.755102 | 253 / 335 |
| metal-grid | 0.779541 | 0.952586 | 0.659701 | 0.783069 | 232 / 335 |
| guarded-rescue | 0.877193 | 0.941781 | 0.820896 | 0.880383 | 292 / 335 |

## Three hypotheses

- H1 `articulation`: no onset count change; reassign 42/46 inside strongly detected alternating eighth-note runs.
- H2 `metal-grid`: H1 plus convert in-run crash/ride candidates to hats and remove off-eighth metal.
- H3 `guarded-rescue`: H2 plus restore a missing slot only when broad ADTOF metal evidence or strong high-band onset exists and the two-hand guard allows it.

## K/S/T guard

All four variants retained exactly the same target K/S/T event counts: kick 418, snare 260, tom 18.

## Training check

The 20-feature sequence articulation model uses pre-hit energy, current tail, energy immediately before the next eighth, and post-next-hit energy in four bands (3–6, 6–10, 10–16, 16–21 kHz). Leave-one-review-range-out results: precision 0.9023, recall 0.9458, F1 0.9235, accuracy 0.9224.

Production adoption remains blocked until the five-song chart-only regression result is known.
