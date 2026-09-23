# Hi-Hat Articulation Fusion Model v61

Production model trained after five-song leave-one-song-out selection.

- Inputs: existing single-hit Open probability + synchronized-corpus tail/choke probability + per-song rank/robust normalization + next-articulation gap.
- No alternating parity, review range, song filename, or user review label is a runtime feature.
- Teacher chart.mid is used only offline to label the five training songs.
- Labeled detected candidates: 3138 (Closed 2539, Open 599).
- Decision: probability >= 0.55 => Open, <= 0.45 => Closed; middle band keeps existing articulation.
- Model family/hyperparameters were selected using five-song LOOCV in HAT_FUSION_LOOCV_V60.md.
