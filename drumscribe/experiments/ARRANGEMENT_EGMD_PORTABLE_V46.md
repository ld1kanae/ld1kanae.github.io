# Arrangement + E-GMD portable residual gate v46

Goal: reproduce the v45 held-out Extra Trees residual gain with a small JS-portable rule.

**Caveat:** the rule family was proposed after v45 inspection on the same five-song development set. Treat this as internal development validation, not independent generalization.

| rule | KST F1 | vs fixed | snare vs fixed | total TP/FP additions |
|---|---:|---:|---:|---:|
| R1_p93_conf55_lift165 | 0.939224 | 0.000372 | 0.001136 | 12/0 |
| R2_p95_conf55_lift165 | 0.939100 | 0.000248 | 0.000758 | 11/0 |
| R3_p93_conf70_lift165 | 0.938976 | 0.000124 | 0.000379 | 10/0 |

All variants are additive on top of fixed v39D; Kick/Tom decisions are unchanged.
