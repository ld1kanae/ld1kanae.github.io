# Generic synchronized-context Hi-Hat v59

No user review ranges, song identity or alternating parity are used. The review-trained sequence repair is explicitly disabled.

| variant | Closed F1 | Open F1 | HH macro | delta | K delta | S delta | T delta | guard |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| off | 0.846168 | 0.634770 | 0.740469 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | False |
| closed-open-995 | 0.828364 | 0.554286 | 0.691325 | -0.049144 | +0.000000 | +0.000000 | +0.000000 | False |
| closed-open-990 | 0.822602 | 0.547802 | 0.685202 | -0.055267 | +0.000000 | +0.000000 | +0.000000 | False |
| closed-open-highgap | 0.788086 | 0.507188 | 0.647637 | -0.092832 | +0.000000 | +0.000000 | +0.000000 | False |
| bidirectional-extreme | 0.827443 | 0.542869 | 0.685156 | -0.055313 | +0.000000 | +0.000000 | +0.000000 | False |

Per-song HH macro:
- off: arcaround=0.452341, diamondvirgin=0.609254, kaiju=0.814238, nanairo=0.912904, ray=0.795022
- closed-open-995: arcaround=0.421012, diamondvirgin=0.476133, kaiju=0.650252, nanairo=0.879441, ray=0.746720
- closed-open-990: arcaround=0.418829, diamondvirgin=0.464580, kaiju=0.626306, nanairo=0.874737, ray=0.740932
- closed-open-highgap: arcaround=0.404652, diamondvirgin=0.339628, kaiju=0.536402, nanairo=0.832789, ray=0.721994
- bidirectional-extreme: arcaround=0.421012, diamondvirgin=0.476133, kaiju=0.650252, nanairo=0.879441, ray=0.732145

- Prediction stage did not read chart.mid.
- K/S/T exact non-regression is required.
- No reviewed-song-specific runtime model is part of this benchmark.
