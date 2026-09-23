# Alternating Hi-Hat Review v50

Prediction uses drums audio only. chart.mid is opened after prediction for scoring.

| Variant | HH macro F1 | Closed F1 | Open F1 | collapsed HH/Ride F1 | metal macro F1 | K delta | S delta | T delta | changed | removed | rescued |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| off | 0.723090 | 0.843895 | 0.602285 | 0.812081 | 0.564592 | +0.000000 | +0.000000 | +0.000000 | 0 | 0 | 0 |
| articulation | 0.630352 | 0.798046 | 0.462658 | 0.808571 | 0.500694 | +0.000000 | +0.000000 | +0.000000 | 467 | 0 | 0 |
| metal-grid | 0.615958 | 0.769259 | 0.462658 | 0.790219 | 0.491099 | +0.000000 | +0.000000 | +0.000000 | 467 | 142 | 0 |
| guarded-rescue | 0.615707 | 0.766832 | 0.464581 | 0.799336 | 0.490931 | +0.000000 | +0.000000 | +0.000000 | 467 | 142 | 176 |

Guardrails:
- Kick/snare/tom must be exactly non-regressing.
- H1 changes articulation only.
- H2 may remove off-grid metal inside strongly detected alternating-eighth runs.
- H3 may add only broad-metal/audio-supported slots and preserves the two-hand guard.
