# Raw Acoustic Hi-Hat Model v64

- Selected from five-song leave-one-song-out H3_raw_localnorm.
- Features: per-hit attack/decay/tail/choke vector, per-song rank/robust-z of those acoustic features, existing single-hit probability, score/confidence.
- No review range, alternating parity, section label or song filename is a runtime input.
- Training labeled candidates: 3138 (Open 599, Closed 2539).
- Runtime threshold: >=0.55 Open, <=0.45 Closed; otherwise keep current articulation.
