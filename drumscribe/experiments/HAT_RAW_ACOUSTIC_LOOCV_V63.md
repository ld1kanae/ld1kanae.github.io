# Raw per-hit acoustic Hi-Hat LOOCV v63

No alternating-grid parity or review-specific label/range is used. Features are attack/decay/tail/choke acoustics extracted from each detected hit.

| variant | Closed F1 | Open F1 | HH macro | delta | guard |
|---|---:|---:|---:|---:|---|
| baseline | 0.817175 | 0.628817 | 0.722996 | +0.000000 | False |
| H1_raw | 0.809816 | 0.616521 | 0.713168 | -0.009827 | False |
| H2_raw_base | 0.817175 | 0.628817 | 0.722996 | +0.000000 | False |
| H3_raw_localnorm | 0.817316 | 0.629471 | 0.723393 | +0.000398 | True |

Per-song HH macro:
- baseline: arcaround=0.440195, diamondvirgin=0.599122, kaiju=0.787166, nanairo=0.894759, ray=0.771133
- H1_raw: arcaround=0.407129, diamondvirgin=0.589103, kaiju=0.768910, nanairo=0.894072, ray=0.756115
- H2_raw_base: arcaround=0.440195, diamondvirgin=0.599122, kaiju=0.787166, nanairo=0.894759, ray=0.771133
- H3_raw_localnorm: arcaround=0.440195, diamondvirgin=0.599122, kaiju=0.807170, nanairo=0.894759, ray=0.771133
