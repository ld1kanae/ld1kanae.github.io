# Alternating Hi-Hat Review v50

Prediction uses drums audio only. chart.mid is opened after prediction for scoring.

| Variant | HH macro F1 | Closed F1 | Open F1 | collapsed HH/Ride F1 | metal macro F1 | K delta | S delta | T delta | changed | removed | rescued |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| off | 0.736356 | 0.843895 | 0.628817 | 0.812081 | 0.507017 | +0.000000 | +0.000000 | +0.000000 | 0 | 0 | 0 |
| articulation | 0.644050 | 0.798046 | 0.490054 | 0.808571 | 0.445479 | +0.000000 | +0.000000 | +0.000000 | 450 | 0 | 0 |
| metal-grid | 0.629657 | 0.769259 | 0.490054 | 0.790219 | 0.435884 | +0.000000 | +0.000000 | +0.000000 | 450 | 142 | 0 |
| guarded-rescue | 0.628683 | 0.766832 | 0.490534 | 0.799336 | 0.435235 | +0.000000 | +0.000000 | +0.000000 | 450 | 142 | 176 |

Guardrails:
- Kick/snare/tom must be exactly non-regressing.
- H1 changes articulation only.
- H2 may remove off-grid metal inside strongly detected alternating-eighth runs.
- H3 may add only broad-metal/audio-supported slots and preserves the two-hand guard.
