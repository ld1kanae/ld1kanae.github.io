# Arrangement K/S/T runtime v40

Fresh Chromium validation of the reusable arrangement rescoring module. Generated MIDI passes through the normal rhythm-grid and MIDI exporter before scoring against chart.mid.

| variant | KST F1 | delta | kick delta | snare delta | tom delta | all F1 delta | rescued | hand-grid delta | meter changes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| V39_A_runtime | 0.938852 | 0.001118 | 0.000757 | 0.001520 | 0.006870 | 0.000588 | 9 | 0 | none |
| V39_D_runtime | 0.938852 | 0.001118 | 0.000568 | 0.001899 | 0.006870 | 0.000588 | 9 | 0 | none |
| V39_D_no_hand_guard | 0.938852 | 0.001118 | 0.000568 | 0.001899 | 0.006870 | 0.000588 | 9 | 0 | none |

Baseline KST F1: 0.937734
Baseline all-class F1: 0.804107

Guardrails:
- chart.mid is scoring-only and is never loaded in the browser prediction stage.
- Every rescued note originates from a low-threshold acoustic K/S/T candidate.
- A/A' are structural-family labels, not verse/chorus semantics.
- max_grid_residual_ticks must remain 0 for an adoptable candidate.
- A candidate must not increase hand-grid violations or change inferred meter relative to baseline.
