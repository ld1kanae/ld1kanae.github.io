# Raw per-hit acoustic Hi-Hat LOOCV v63

No alternating-grid parity or review-specific label/range is used. Features are attack/decay/tail/choke acoustics extracted from each detected hit.

| variant | Closed F1 | Open F1 | HH macro | delta | guard |
|---|---:|---:|---:|---:|---|
| baseline | 0.843895 | 0.628817 | 0.736356 | +0.000000 | False |
| H1_raw | 0.836627 | 0.616521 | 0.726574 | -0.009782 | False |
| H2_raw_base | 0.843895 | 0.628817 | 0.736356 | +0.000000 | False |
| H3_raw_localnorm | 0.844047 | 0.629471 | 0.736759 | +0.000402 | True |

Per-song HH macro:
- baseline: arcaround=0.448007, diamondvirgin=0.597619, kaiju=0.787958, nanairo=0.914205, ray=0.791025
- H1_raw: arcaround=0.414598, diamondvirgin=0.587545, kaiju=0.769705, nanairo=0.913542, ray=0.776103
- H2_raw_base: arcaround=0.448007, diamondvirgin=0.597619, kaiju=0.787958, nanairo=0.914205, ray=0.791025
- H3_raw_localnorm: arcaround=0.448007, diamondvirgin=0.597619, kaiju=0.807963, nanairo=0.914205, ray=0.791025
