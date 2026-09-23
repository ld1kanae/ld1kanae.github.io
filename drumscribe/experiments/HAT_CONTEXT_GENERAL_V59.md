# Generic synchronized-context Hi-Hat v59

No user review ranges, song identity or alternating parity are used. The review-trained sequence repair is explicitly disabled.

| variant | Closed F1 | Open F1 | HH macro | delta | K delta | S delta | T delta | guard |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| off | 0.817175 | 0.628817 | 0.722996 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | False |
| closed-open-995 | 0.803267 | 0.547504 | 0.675385 | -0.047610 | +0.000000 | +0.000000 | +0.000000 | False |
| closed-open-990 | 0.797984 | 0.540541 | 0.669262 | -0.053734 | +0.000000 | +0.000000 | +0.000000 | False |
| closed-open-highgap | 0.773856 | 0.504418 | 0.639137 | -0.083859 | +0.000000 | +0.000000 | +0.000000 | False |
| bidirectional-extreme | 0.802644 | 0.536082 | 0.669363 | -0.053633 | +0.000000 | +0.000000 | +0.000000 | False |

Per-song HH macro:
- off: arcaround=0.440195, diamondvirgin=0.599122, kaiju=0.787166, nanairo=0.894759, ray=0.771133
- closed-open-995: arcaround=0.407444, diamondvirgin=0.478785, kaiju=0.637559, nanairo=0.854189, ray=0.723592
- closed-open-990: arcaround=0.405381, diamondvirgin=0.467290, kaiju=0.612833, nanairo=0.849110, ray=0.717724
- closed-open-highgap: arcaround=0.397747, diamondvirgin=0.340272, kaiju=0.534893, nanairo=0.801400, ray=0.723592
- bidirectional-extreme: arcaround=0.407444, diamondvirgin=0.478785, kaiju=0.637559, nanairo=0.854189, ray=0.709645

- Prediction stage did not read chart.mid.
- K/S/T exact non-regression is required.
- No reviewed-song-specific runtime model is part of this benchmark.
