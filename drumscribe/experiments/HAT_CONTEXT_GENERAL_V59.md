# Generic synchronized-context Hi-Hat v59

No user review ranges, song identity or alternating parity are used. The review-trained sequence repair is explicitly disabled.

| variant | Closed F1 | Open F1 | HH macro | delta | K delta | S delta | T delta | guard |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| off | 0.843895 | 0.628817 | 0.736356 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | False |
| closed-open-995 | 0.826611 | 0.552428 | 0.689519 | -0.046837 | +0.000000 | +0.000000 | +0.000000 | False |
| closed-open-990 | 0.820996 | 0.545748 | 0.683372 | -0.052984 | +0.000000 | +0.000000 | +0.000000 | False |
| closed-open-highgap | 0.786865 | 0.506255 | 0.646560 | -0.089796 | +0.000000 | +0.000000 | +0.000000 | False |
| bidirectional-extreme | 0.825709 | 0.540970 | 0.683339 | -0.053017 | +0.000000 | +0.000000 | +0.000000 | False |

Per-song HH macro:
- off: arcaround=0.448007, diamondvirgin=0.597619, kaiju=0.787958, nanairo=0.914205, ray=0.791025
- closed-open-995: arcaround=0.415580, diamondvirgin=0.476133, kaiju=0.640658, nanairo=0.879441, ray=0.743098
- closed-open-990: arcaround=0.413419, diamondvirgin=0.464580, kaiju=0.615350, nanairo=0.874737, ray=0.737336
- closed-open-highgap: arcaround=0.404652, diamondvirgin=0.339628, kaiju=0.536402, nanairo=0.832789, ray=0.718512
- bidirectional-extreme: arcaround=0.415580, diamondvirgin=0.476133, kaiju=0.640658, nanairo=0.879441, ray=0.728499

- Prediction stage did not read chart.mid.
- K/S/T exact non-regression is required.
- No reviewed-song-specific runtime model is part of this benchmark.
