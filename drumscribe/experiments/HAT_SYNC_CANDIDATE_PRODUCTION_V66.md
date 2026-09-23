# Synchronized Candidate Hi-Hat Production Replay v66

Model was trained offline from five fully synchronized WAV/MIDI pairs. Runtime inputs are audio + generated candidates only.

| variant | Closed F1 | Open F1 | HH macro | K | S | T |
|---|---:|---:|---:|---:|---:|---:|
| off | 0.843895 | 0.628817 | 0.736356 | 0.962571 | 0.900035 | 0.784091 |
| on | 0.816725 | 0.366646 | 0.591685 | 0.962571 | 0.900035 | 0.784091 |

- HH macro delta: -0.144671
- K/S/T event lists exact: True
- Hat/Ride onset lists exact: True
- No per-song HH macro regression: False
- Production guard: False

- arcaround: 0.448007 -> 0.286102, changes=28, promoted=9, demoted=19
- diamondvirgin: 0.597619 -> 0.511188, changes=50, promoted=19, demoted=31
- kaiju: 0.787958 -> 0.611639, changes=10, promoted=4, demoted=6
- nanairo: 0.914205 -> 0.820456, changes=95, promoted=4, demoted=91
- ray: 0.791025 -> 0.504445, changes=376, promoted=11, demoted=365
