# Arrangement E-GMD domain calibration v45

Every calibrated variant starts from the already validated fixed v39D rescues; calibration is allowed only to add extra candidates.

| variant | KST F1 | delta | kick delta | snare delta | tom delta | total added TP/FP |
|---|---:|---:|---:|---:|---:|---:|
| fixed_v39d | 0.938852 | 0.001118 | 0.000568 | 0.001899 | 0.006870 | 9/0 |
| C1_rank_extreme | 0.938852 | 0.001118 | 0.000568 | 0.001899 | 0.006870 | 9/0 |
| C2_robust_extreme | 0.938976 | 0.001242 | 0.000757 | 0.001899 | 0.006870 | 10/0 |
| C3_soft_rank_loocv | 0.938852 | 0.001118 | 0.000568 | 0.001899 | 0.006870 | 9/0 |

Guardrails:
- fixed v39D rescues are preserved; E-GMD calibration never vetoes them.
- calibration is song-local and reference-free at prediction time.
- C3 is song-held-out for threshold selection.
- production adoption requires beating fixed v39D without per-part regression, then fresh browser rhythm-grid/MIDI validation.
