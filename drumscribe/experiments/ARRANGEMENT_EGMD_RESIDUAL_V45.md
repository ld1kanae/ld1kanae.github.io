# Arrangement + E-GMD residual Snare v45

Frozen v39D remains the base. Only candidates not already rescued by v39D are eligible for an additional E-GMD-informed Snare rescue.

Residual Snare pool: **63** rows / **9** recoverable positives.

| variant | KST F1 | vs baseline | vs fixed v39D | kick vs fixed | snare vs fixed | tom vs fixed | added TP/FP total |
|---|---:|---:|---:|---:|---:|---:|---:|
| H5_fixed_plus_logistic_residual | 0.937865 | 0.000131 | -0.000987 | 0.000000 | -0.002794 | 0.000000 | 9/9 |
| H6_fixed_plus_extra_trees_residual | 0.939100 | 0.001366 | 0.000248 | 0.000000 | 0.000758 | 0.000000 | 11/0 |
| H7_fixed_plus_interpretable_egmd_rule | 0.938866 | 0.001132 | 0.000014 | 0.000000 | 0.000068 | 0.000000 | 10/1 |

Guardrails:
- fixed v39D is never removed; v45 is additive-only on residual Snare candidates.
- All learned/rule thresholds are selected without the held-out song.
- No Kick/Tom change is permitted in this round.
- Runtime adoption still requires a full-data portable rule/model plus fresh Chromium rhythm-grid/MIDI/two-hand validation.
