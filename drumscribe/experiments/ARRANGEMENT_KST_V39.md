# Arrangement K/S/T post-filter v39

v38 sensitive family rescue was the starting point. This round tests whether the one observed false-positive Snare can be rejected without losing the true A/A' rescues.

| variant | KST F1 | delta | kick delta | snare delta | tom delta | added TP/FP |
|---|---:|---:|---:|---:|---:|---:|---:|
| V39_A_subthreshold_hand | 0.938852 | 0.001118 | 0.000757 | 0.001520 | 0.006870 | 9/0 |
| V39_B_egmd_snare_gate | 0.938742 | 0.001008 | 0.000757 | 0.001209 | 0.006870 | 9/1 |
| V39_C_subthreshold_and_egmd | 0.938728 | 0.000994 | 0.000757 | 0.001140 | 0.006870 | 8/0 |
| V39_D_symbolic_gmd_plus_postfilter | 0.938852 | 0.001118 | 0.000568 | 0.001899 | 0.006870 | 9/0 |

Interpretation rules:
- chart.mid remains scoring-only.
- no variant copies a note from A to A'; all additions originate from low-threshold acoustic candidates.
- V39_A/C/D treat a hand candidate already above production threshold but absent from final output as a downstream-veto case rather than a missing-threshold case.
- Production integration still requires a fresh browser non-regression run.
