# Arrangement + E-GMD K/S/T fusion v44

Frozen E-GMD v4 acoustic probabilities are attached to fresh browser low-threshold K/S/T candidates, then combined with A/A' structural evidence.

External E-GMD v4 training candidates: **18,936** (Kick 4,422 / Snare 6,580 / Tom 7,934).
Five-song transfer candidate pool after baseline/post-filter safety: **141**.

| variant | KST F1 | delta | kick delta | snare delta | tom delta | added TP/FP |
|---|---:|---:|---:|---:|---:|---:|
| fixed_v39d | 0.938852 | 0.001118 | 0.000568 | 0.001899 | 0.006870 | 9/0 |
| H1_egmd_acoustic_only | 0.933968 | -0.003766 | 0.000960 | -0.010316 | -0.020650 | 18/55 |
| H2_arrangement_plus_egmd | 0.938231 | 0.000497 | 0.000000 | 0.001140 | 0.006870 | 4/0 |
| H3_logistic_fusion_loocv | 0.936762 | -0.000972 | 0.000000 | -0.002722 | 0.000000 | 1/10 |
| H4_extra_trees_fusion_loocv | 0.938012 | 0.000278 | 0.000000 | 0.000897 | 0.000000 | 4/2 |

Candidate pool by group:
- kick: 11 rows / 9 recoverable positives
- snare: 68 rows / 14 recoverable positives
- tom: 62 rows / 2 recoverable positives

Guardrails:
- E-GMD model is frozen before DruMaster scoring.
- H3/H4 are leave-one-song-out; held-out chart never tunes that fold.
- Snare/Tom candidates with confidence >= 1 that were removed downstream remain excluded.
- No note is copied from A to A'.
- Production remains unchanged until a candidate beats fixed v39D and passes fresh rhythm-grid/MIDI/hand-constraint validation.
