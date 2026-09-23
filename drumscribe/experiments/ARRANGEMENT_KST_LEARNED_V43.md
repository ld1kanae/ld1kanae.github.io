# Arrangement K/S/T learned rescoring v43

Five-song leave-one-song-out (LOOCV). Each held-out song is predicted by models trained and threshold-tuned on the other four songs only.

Candidate rows in repeated A/A' families after post-filter-origin safety: **83**.

| variant | KST F1 | delta | kick delta | snare delta | tom delta | added TP/FP |
|---|---:|---:|---:|---:|---:|---:|
| fixed v39D replay | 0.938852 | 0.001118 | 0.000568 | 0.001899 | 0.006870 | 9/0 |
| logistic LOOCV | 0.937734 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0/0 |
| extra_trees LOOCV | 0.937734 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0/0 |
| random_forest LOOCV | 0.937734 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0/0 |

Dataset by group:
- kick: 6 candidates / 5 recoverable-reference labels
- snare: 36 candidates / 7 recoverable-reference labels
- tom: 41 candidates / 2 recoverable-reference labels

Guardrails:
- Held-out chart.mid is not used to train or tune that fold.
- Every candidate already has an acoustic event and belongs to a structural family with another occurrence. same-position support, including zero support, is learned as a feature.
- Snare/Tom candidates with confidence >= 1 that were removed downstream stay excluded.
- This is an offline learned-gate experiment. Runtime adoption requires a separate fresh Chromium rhythm-grid/MIDI non-regression run.
