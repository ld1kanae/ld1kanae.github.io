# Open-hat selective Ride→Open v47

Fresh browser comparison. Reference MIDI is scoring-only. Ride candidates are converted to Open only above the selected acoustic probability; all other Ride events remain Ride.

| variant | closed F1 | open F1 | ride F1 | hat macro | metal macro | collapsed hat/ride onset F1 |
|---|---:|---:|---:|---:|---:|---:|
| default | 0.843895 | 0.598647 | 0.246117 | 0.721271 | 0.562886 | 0.812081 |
| selective70 | 0.843895 | 0.598647 | 0.246117 | 0.721271 | 0.562886 | 0.812081 |
| selective80 | 0.843895 | 0.598647 | 0.246117 | 0.721271 | 0.562886 | 0.812081 |
| selective90 | 0.843895 | 0.598647 | 0.246117 | 0.721271 | 0.562886 | 0.812081 |

Deltas versus default:
- selective70: hat macro +0.000000; metal macro +0.000000; Open +0.000000; Ride +0.000000; onset +0.000000; K/S/T +0.000000/+0.000000/+0.000000
- selective80: hat macro +0.000000; metal macro +0.000000; Open +0.000000; Ride +0.000000; onset +0.000000; K/S/T +0.000000/+0.000000/+0.000000
- selective90: hat macro +0.000000; metal macro +0.000000; Open +0.000000; Ride +0.000000; onset +0.000000; K/S/T +0.000000/+0.000000/+0.000000

Guardrail: production adoption requires Open gain without material Ride/metal-macro regression and with K/S/T unchanged.
