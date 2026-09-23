# Hat context held-out v55

Each held song uses a context logistic model trained on the other four synchronized WAV/MIDI pairs. Runtime sees only audio + generated events; chart.mid is scoring-only.

Best eligible: **ride-rescue@0.99**

| variant | closed F1 | open F1 | ride F1 | HH macro | collapsed onset | ΔHH macro |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.843895 | 0.602285 | 0.247596 | 0.723090 | 0.812081 | +0.000000 |
| hat-rescue@0.80 | 0.785556 | 0.479843 | 0.247596 | 0.632700 | 0.812081 | -0.090390 |
| hat-rescue@0.90 | 0.792829 | 0.489567 | 0.247596 | 0.641198 | 0.812081 | -0.081892 |
| hat-rescue@0.95 | 0.803388 | 0.498358 | 0.247596 | 0.650873 | 0.812081 | -0.072217 |
| hat-rescue@0.98 | 0.811769 | 0.505882 | 0.247596 | 0.658826 | 0.812081 | -0.064264 |
| hat-rescue@0.99 | 0.819691 | 0.513722 | 0.247596 | 0.666707 | 0.812081 | -0.056383 |
| ride-rescue@0.80 | 0.843895 | 0.630320 | 0.068966 | 0.737108 | 0.812081 | +0.014018 |
| ride-rescue@0.90 | 0.843895 | 0.631831 | 0.083333 | 0.737863 | 0.812081 | +0.014773 |
| ride-rescue@0.95 | 0.843895 | 0.632438 | 0.089021 | 0.738167 | 0.812081 | +0.015077 |
| ride-rescue@0.98 | 0.843895 | 0.634569 | 0.108664 | 0.739232 | 0.812081 | +0.016142 |
| ride-rescue@0.99 | 0.843895 | 0.636715 | 0.127907 | 0.740305 | 0.812081 | +0.017215 |
| both@0.80 | 0.785556 | 0.508824 | 0.068966 | 0.647190 | 0.812081 | -0.075900 |
| both@0.90 | 0.792829 | 0.519608 | 0.083333 | 0.656218 | 0.812081 | -0.066872 |
| both@0.95 | 0.803388 | 0.528913 | 0.089021 | 0.666151 | 0.812081 | -0.056939 |
| both@0.98 | 0.811769 | 0.538127 | 0.108664 | 0.674948 | 0.812081 | -0.048142 |
| both@0.99 | 0.819691 | 0.547658 | 0.127907 | 0.683674 | 0.812081 | -0.039416 |

Guard: K/S/T unchanged, collapsed onset non-regression, HH macro improvement. Threshold sweep is development analysis; any production threshold remains subject to fresh validation on new paired songs.
