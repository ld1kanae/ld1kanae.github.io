# Open-hat selective Ride→Open v48

Fresh browser comparison. Reference MIDI is scoring-only. Ride candidates are converted to Open only above the selected acoustic probability; all other Ride events remain Ride.

| variant | closed F1 | open F1 | ride F1 | hat macro | metal macro | collapsed hat/ride onset F1 |
|---|---:|---:|---:|---:|---:|---:|
| default | 0.843895 | 0.628817 | 0.048338 | 0.736356 | 0.507017 | 0.812081 |
| selective55 | 0.843895 | 0.630176 | 0.042424 | 0.737036 | 0.505499 | 0.812507 |
| selective60 | 0.843895 | 0.628817 | 0.048338 | 0.736356 | 0.507017 | 0.812081 |
| selective65 | 0.843895 | 0.628817 | 0.048338 | 0.736356 | 0.507017 | 0.812081 |

Deltas versus default:
- selective55: hat macro +0.000680; metal macro -0.001518; Open +0.001359; Ride -0.005914; onset +0.000427; K/S/T +0.000000/+0.000000/+0.000000
- selective60: hat macro +0.000000; metal macro +0.000000; Open +0.000000; Ride +0.000000; onset +0.000000; K/S/T +0.000000/+0.000000/+0.000000
- selective65: hat macro +0.000000; metal macro +0.000000; Open +0.000000; Ride +0.000000; onset +0.000000; K/S/T +0.000000/+0.000000/+0.000000

Guardrail: production adoption requires Open gain without material Ride/metal-macro regression and with K/S/T unchanged.
