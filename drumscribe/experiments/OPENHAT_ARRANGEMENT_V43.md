# Open/Closed Hi-Hat + Arrangement v43

Reference chart.mid is scoring-only. Prediction uses drums.mp3 plus offvocal.mp3 structure; no reference MIDI is loaded in the browser stage.

## Exact synchronized nanairo teacher observation

- GM42 closed and GM46 open are strongly separated by 5–18 kHz decay in the supplied synchronized pair.
- That pair contains 240 GM46 events but zero open->open transitions, so it is not used as sole evidence for open-only runs.

## Five-song browser comparison

| variant | strict HH macro F1 | closed F1 | open F1 | collapsed hat/ride onset F1 | arrangement changes |
|---|---:|---:|---:|---:|---:|
| base | 0.721402 | 0.816609 | 0.626195 | 0.796110 | 0 |
| decay | 0.722199 | 0.816892 | 0.627507 | 0.796110 | 0 |
| arrangement | 0.720031 | 0.815840 | 0.624222 | 0.796110 | 5 |
| decay-arrangement | 0.720830 | 0.816122 | 0.625538 | 0.796110 | 5 |
| ride-acoustic-arrangement | 0.710302 | 0.792814 | 0.627789 | 0.801213 | 6 |
| ride-decay-arrangement | 0.711130 | 0.793080 | 0.629179 | 0.801213 | 6 |

## Reference-only structural learning check

- same-family corresponding-slot articulation agreement: 0.8809 (n=1125)
- cross-family corresponding-slot articulation agreement: 0.7057 (n=7889)
- same-family lift: +0.1752

## Guardrails

- Arrangement rescoring changes 42/46 articulation only; it creates no new hit.
- Ride-rounding variants are scored both strictly and with ride accepted as a hat-family onset.
- Kick/snare/tom must remain unchanged before any production adoption.
- A/A' are structural-family labels, not verse/chorus semantics.
