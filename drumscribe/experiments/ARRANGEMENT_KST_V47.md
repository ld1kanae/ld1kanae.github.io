# Arrangement + E-GMD residual Snare runtime v47

Fresh Chromium validation of the reusable arrangement rescoring module. Generated MIDI passes through the normal rhythm-grid and MIDI exporter before scoring against chart.mid.

| variant | KST F1 | delta | kick delta | snare delta | tom delta | all F1 delta | rescued | hand-grid delta | meter changes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| V39_D_runtime | 0.857108 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0 | none |
| V46_R1_runtime | 0.857108 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0 | none |
| V46_R1_no_hand_guard | 0.857108 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0 | none |

Baseline KST F1: 0.857108
Baseline all-class F1: 0.650279

Guardrails:
- chart.mid is scoring-only and is never loaded in the browser prediction stage.
- Every rescued note originates from a low-threshold acoustic K/S/T candidate.
- A/A' are structural-family labels, not verse/chorus semantics.
- max_grid_residual_ticks must remain 0 for an adoptable candidate.
- A candidate must not increase hand-grid violations or change inferred meter relative to baseline.
