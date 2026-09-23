# Synchronized Candidate Hi-Hat Production Replay v66

Model was trained offline from five fully synchronized WAV/MIDI pairs. Runtime inputs are audio + generated candidates only.

| variant | Closed F1 | Open F1 | HH macro | K | S | T |
|---|---:|---:|---:|---:|---:|---:|
| off | 0.817175 | 0.628817 | 0.722996 | 0.962571 | 0.900035 | 0.784091 |
| on | 0.792822 | 0.366646 | 0.579734 | 0.962571 | 0.900035 | 0.784091 |

- HH macro delta: -0.143262
- K/S/T event lists exact: True
- Hat/Ride onset lists exact: True
- No per-song HH macro regression: False
- Production guard: False

- arcaround: 0.440195 -> 0.278751, changes=28, promoted=9, demoted=19
- diamondvirgin: 0.599122 -> 0.512950, changes=50, promoted=19, demoted=31
- kaiju: 0.787166 -> 0.610856, changes=10, promoted=4, demoted=6
- nanairo: 0.894759 -> 0.802650, changes=95, promoted=4, demoted=91
- ray: 0.771133 -> 0.487921, changes=376, promoted=11, demoted=365
