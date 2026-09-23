# Arrangement + E-GMD K/S/T fusion v44

Frozen E-GMD v4 acoustic probabilities are attached to fresh browser low-threshold K/S/T candidates, then combined with A/A' structural evidence.

External E-GMD v4 training candidates: **18,936** (Kick 4,422 / Snare 6,580 / Tom 7,934).
Five-song transfer candidate pool after baseline/post-filter safety: **0**.

| variant | KST F1 | delta | kick delta | snare delta | tom delta | added TP/FP |
|---|---:|---:|---:|---:|---:|---:|
| fixed_v39d | 0.858076 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0/0 |
| H1_egmd_acoustic_only | 0.858076 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0/0 |
| H2_arrangement_plus_egmd | 0.858076 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0/0 |
| H3_logistic_fusion_loocv | 0.858076 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0/0 |
| H4_extra_trees_fusion_loocv | 0.858076 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0/0 |

Candidate pool by group:
- kick: 0 rows / 0 recoverable positives
- snare: 0 rows / 0 recoverable positives
- tom: 0 rows / 0 recoverable positives

Guardrails:
- E-GMD model is frozen before DruMaster scoring.
- H3/H4 are leave-one-song-out; held-out chart never tunes that fold.
- Snare/Tom candidates with confidence >= 1 that were removed downstream remain excluded.
- No note is copied from A to A'.
- Production remains unchanged until a candidate beats fixed v39D and passes fresh rhythm-grid/MIDI/hand-constraint validation.
