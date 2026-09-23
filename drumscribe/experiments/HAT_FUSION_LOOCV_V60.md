# Five-song held-out Hi-Hat fusion v60

Review-song labels/ranges are not used. Each song is held out while the other four songs train the articulation fusion.

| variant | Closed F1 | Open F1 | HH macro | delta | K delta | S delta | T delta | guard |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | 0.817175 | 0.628817 | 0.722996 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | False |
| H1_logistic | 0.817107 | 0.630189 | 0.723648 | +0.000652 | +0.000000 | +0.000000 | +0.000000 | False |
| H2_extratrees | 0.817048 | 0.629524 | 0.723286 | +0.000290 | +0.000000 | +0.000000 | +0.000000 | True |
| H3_logit_fusion | 0.810404 | 0.591716 | 0.701060 | -0.021936 | +0.000000 | +0.000000 | +0.000000 | False |

Per-song HH macro:
- baseline: arcaround=0.440195, diamondvirgin=0.599122, kaiju=0.787166, nanairo=0.894759, ray=0.771133
- H1_logistic: arcaround=0.437978, diamondvirgin=0.598680, kaiju=0.821117, nanairo=0.894759, ray=0.771133
- H2_extratrees: arcaround=0.440195, diamondvirgin=0.599122, kaiju=0.805023, nanairo=0.894759, ray=0.771133
- H3_logit_fusion: arcaround=0.331076, diamondvirgin=0.519011, kaiju=0.787166, nanairo=0.894758, ray=0.769448

- Candidate features are audio/runtime-derived only.
- K/S/T exact non-regression is mandatory.
- No specific review song is used for training or threshold selection.
