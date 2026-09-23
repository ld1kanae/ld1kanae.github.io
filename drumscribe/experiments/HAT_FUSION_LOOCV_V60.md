# Five-song held-out Hi-Hat fusion v60

Review-song labels/ranges are not used. Each song is held out while the other four songs train the articulation fusion.

| variant | Closed F1 | Open F1 | HH macro | delta | K delta | S delta | T delta | guard |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | 0.843895 | 0.628817 | 0.736356 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | False |
| H1_logistic | 0.843941 | 0.630189 | 0.737065 | +0.000709 | +0.000000 | +0.000000 | +0.000000 | False |
| H2_extratrees | 0.843784 | 0.629524 | 0.736654 | +0.000298 | +0.000000 | +0.000000 | +0.000000 | True |
| H3_logit_fusion | 0.836576 | 0.591716 | 0.714146 | -0.022210 | +0.000000 | +0.000000 | +0.000000 | False |

Per-song HH macro:
- baseline: arcaround=0.448007, diamondvirgin=0.597619, kaiju=0.787958, nanairo=0.914205, ray=0.791025
- H1_logistic: arcaround=0.445861, diamondvirgin=0.597121, kaiju=0.821917, nanairo=0.914205, ray=0.791025
- H2_extratrees: arcaround=0.448007, diamondvirgin=0.597619, kaiju=0.805817, nanairo=0.914205, ray=0.791025
- H3_logit_fusion: arcaround=0.338461, diamondvirgin=0.517438, kaiju=0.787958, nanairo=0.914183, ray=0.789246

- Candidate features are audio/runtime-derived only.
- K/S/T exact non-regression is mandatory.
- No specific review song is used for training or threshold selection.
