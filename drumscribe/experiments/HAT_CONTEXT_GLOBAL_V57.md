# Hat context global v57

Portable global model trained on the synchronized corpus. Runtime does not use song identity or reference MIDI. Arcaround Ride zones are ignored in HH scoring as arrangement-only.

No variant passed the production guard.

| variant | Closed F1 | Open F1 | Ride F1 | HH macro | collapsed onset | ΔHH macro |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.850749 | 0.635674 | 0.052980 | 0.743211 | 0.813038 | +0.000000 |
| v57-min24-p99 | 0.850749 | 0.635674 | 0.052980 | 0.743211 | 0.813038 | +0.000000 |
| v57-min16-p99 | 0.850749 | 0.635674 | 0.052980 | 0.743211 | 0.813038 | +0.000000 |
| v57-min24-p98 | 0.850749 | 0.635674 | 0.052980 | 0.743211 | 0.813038 | +0.000000 |

## Per-song HH macro

- baseline: arcaround=0.476099, diamondvirgin=0.609254, kaiju=0.814238, nanairo=0.912904, ray=0.795022
- v57-min24-p99: arcaround=0.476099, diamondvirgin=0.609254, kaiju=0.814238, nanairo=0.912904, ray=0.795022
- v57-min16-p99: arcaround=0.476099, diamondvirgin=0.609254, kaiju=0.814238, nanairo=0.912904, ray=0.795022
- v57-min24-p98: arcaround=0.476099, diamondvirgin=0.609254, kaiju=0.814238, nanairo=0.912904, ray=0.795022

Production guard: K/S/T unchanged; collapsed onset non-regression; aggregate HH macro improvement; no per-song HH macro regression after the Arcaround Ride masking rule.
