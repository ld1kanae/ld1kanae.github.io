# Alternating Hi-Hat Review v51 — inversion-gated

Prediction uses drums audio only. chart.mid is opened after prediction for scoring.

| Variant | HH macro F1 | Closed F1 | Open F1 | collapsed HH/Ride F1 | metal macro F1 | K delta | S delta | T delta | gated songs | changed | removed | rescued |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| off | 0.723090 | 0.843895 | 0.602285 | 0.812081 | 0.564592 | +0.000000 | +0.000000 | +0.000000 | 0 | 0 | 0 | 0 |
| inversion-articulation | 0.723090 | 0.843895 | 0.602285 | 0.812081 | 0.564592 | +0.000000 | +0.000000 | +0.000000 | 0 | 0 | 0 | 0 |
| inversion-metal-grid | 0.723090 | 0.843895 | 0.602285 | 0.812081 | 0.564592 | +0.000000 | +0.000000 | +0.000000 | 0 | 0 | 0 | 0 |
| inversion-guarded-rescue | 0.723090 | 0.843895 | 0.602285 | 0.812081 | 0.564592 | +0.000000 | +0.000000 | +0.000000 | 0 | 0 | 0 | 0 |

Song-local gate diagnostics:

- arcaround: gate=False, samples=119, parityDelta=-0.3823909909186273, maxP=0.7624211329389078, openRatio=0.08455882352941177
- diamondvirgin: gate=False, samples=160, parityDelta=-0.018437505761608297, maxP=0.7445808248558129, openRatio=0.16538461538461538
- kaiju: gate=False, samples=88, parityDelta=-0.060406598606787654, maxP=0.7047577818472184, openRatio=0.018803418803418803
- nanairo: gate=False, samples=89, parityDelta=-0.5518117525619288, maxP=0.9498351538287506, openRatio=0.2611717974180735
- ray: gate=False, samples=201, parityDelta=-0.45759803486909234, maxP=0.9223670053154425, openRatio=0.3164852255054432

Guardrails:
- No song/file identity or review time range is used at runtime.
- Gate requires compressed legacy probabilities, low current Open ratio, and negative legacy-vs-sequence parity correlation.
- Kick/snare/tom must remain exactly unchanged.
