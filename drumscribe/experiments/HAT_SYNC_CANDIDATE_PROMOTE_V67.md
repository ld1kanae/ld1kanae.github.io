# Synchronized Candidate Hi-Hat Promote-Only Replay v67

Model was trained offline from five fully synchronized WAV/MIDI pairs. Open threshold 0.55 and promote-only behavior were fixed from synchronized leave-one-song-out before this repository-MP3 replay.

| variant | Closed F1 | Open F1 | HH macro | K | S | T |
|---|---:|---:|---:|---:|---:|---:|
| off | 0.843895 | 0.628817 | 0.736356 | 0.962571 | 0.900035 | 0.784091 |
| on | 0.840224 | 0.615959 | 0.728091 | 0.962571 | 0.900035 | 0.784091 |

- HH macro delta: -0.008265
- K/S/T event lists exact: True
- Hat/Ride onset lists exact: True
- No per-song HH macro regression: False
- Production guard: False

- arcaround: 0.448007 -> 0.443091, changes=0, promoted=0, demoted=0
- diamondvirgin: 0.597619 -> 0.569253, changes=0, promoted=0, demoted=0
- kaiju: 0.787958 -> 0.750012, changes=0, promoted=0, demoted=0
- nanairo: 0.914205 -> 0.911580, changes=0, promoted=0, demoted=0
- ray: 0.791025 -> 0.785412, changes=0, promoted=0, demoted=0
