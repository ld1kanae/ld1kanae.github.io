# Hat context portable gate v56

Uses the v55 song-held-out probabilities. The gate reads only the number of generated Ride candidates; reference MIDI is scoring-only.

| variant | Open F1 | Closed F1 | Ride F1 | HH macro | ΔHH macro |
|---|---:|---:|---:|---:|---:|
| baseline | 0.602285 | 0.843895 | 0.247596 | 0.723090 | +0.000000 |
| minride2 | 0.637331 | 0.843895 | 0.127536 | 0.740613 | +0.017523 |
| minride8 | 0.637331 | 0.843895 | 0.127536 | 0.740613 | +0.017523 |
| minride16 | 0.637331 | 0.843895 | 0.127536 | 0.740613 | +0.017523 |
| minride24 | 0.637331 | 0.843895 | 0.127536 | 0.740613 | +0.017523 |
| minride32 | 0.637331 | 0.843895 | 0.127536 | 0.740613 | +0.017523 |
| minride64 | 0.637331 | 0.843895 | 0.127536 | 0.740613 | +0.017523 |

Per-song gate activity for minride24:
- arcaround: rides=1, enabled=False, changed=0, HH macro=0.448007
- diamondvirgin: rides=186, enabled=True, changed=142, HH macro=0.604460
- kaiju: rides=0, enabled=False, changed=0, HH macro=0.787958
- nanairo: rides=0, enabled=False, changed=0, HH macro=0.914205
- ray: rides=1, enabled=False, changed=0, HH macro=0.791025
