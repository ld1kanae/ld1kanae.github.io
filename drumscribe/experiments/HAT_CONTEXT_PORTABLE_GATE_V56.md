# Hat context portable gate v56

Uses the v55 song-held-out probabilities. The gate reads only the number of generated Ride candidates; reference MIDI is scoring-only. Arcaround Ride zones are ignored in HH scoring as arrangement-only.

| variant | Open F1 | Closed F1 | Ride F1 | HH macro | ΔHH macro |
|---|---:|---:|---:|---:|---:|
| baseline | 0.602285 | 0.848910 | 0.266150 | 0.725598 | +0.000000 |
| minride2 | 0.637331 | 0.848910 | 0.139241 | 0.743121 | +0.017523 |
| minride8 | 0.637331 | 0.848910 | 0.139241 | 0.743121 | +0.017523 |
| minride16 | 0.637331 | 0.848910 | 0.139241 | 0.743121 | +0.017523 |
| minride24 | 0.637331 | 0.848910 | 0.139241 | 0.743121 | +0.017523 |
| minride32 | 0.637331 | 0.848910 | 0.139241 | 0.743121 | +0.017523 |
| minride64 | 0.637331 | 0.848910 | 0.139241 | 0.743121 | +0.017523 |

Per-song gate activity for minride24:
- arcaround: rides=1, enabled=False, changed=0, HH macro=0.468501
- diamondvirgin: rides=186, enabled=True, changed=142, HH macro=0.604460
- kaiju: rides=0, enabled=False, changed=0, HH macro=0.787958
- nanairo: rides=0, enabled=False, changed=0, HH macro=0.914205
- ray: rides=1, enabled=False, changed=0, HH macro=0.791025
