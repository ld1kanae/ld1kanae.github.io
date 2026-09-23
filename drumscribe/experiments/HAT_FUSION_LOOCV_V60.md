# Five-song held-out Hi-Hat fusion v60

Review-song labels/ranges are not used. Each song is held out while the other four songs train the articulation fusion.

| variant | Closed F1 | Open F1 | HH macro | delta | K delta | S delta | T delta | guard |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | 0.846168 | 0.634770 | 0.740469 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | False |
| H1_logistic | 0.846168 | 0.634770 | 0.740469 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | False |
| H2_extratrees | 0.846168 | 0.634770 | 0.740469 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | False |
| H3_logit_fusion | 0.843889 | 0.623014 | 0.733452 | -0.007017 | +0.000000 | +0.000000 | +0.000000 | False |

Per-song HH macro:
- baseline: arcaround=0.452341, diamondvirgin=0.609254, kaiju=0.814238, nanairo=0.912904, ray=0.795022
- H1_logistic: arcaround=0.452341, diamondvirgin=0.609254, kaiju=0.814238, nanairo=0.912904, ray=0.795022
- H2_extratrees: arcaround=0.452341, diamondvirgin=0.609254, kaiju=0.814238, nanairo=0.912904, ray=0.795022
- H3_logit_fusion: arcaround=0.338461, diamondvirgin=0.607174, kaiju=0.814238, nanairo=0.914205, ray=0.791848

- Candidate features are audio/runtime-derived only.
- K/S/T exact non-regression is mandatory.
- No specific review song is used for training or threshold selection.
