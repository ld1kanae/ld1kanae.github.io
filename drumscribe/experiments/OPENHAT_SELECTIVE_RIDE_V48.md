# Open-hat selective Ride→Open v48

Fresh browser comparison. Reference MIDI is scoring-only. Ride candidates are converted to Open only above the selected acoustic probability; all other Ride events remain Ride.

| variant | closed F1 | open F1 | ride F1 | hat macro | metal macro | collapsed hat/ride onset F1 |
|---|---:|---:|---:|---:|---:|---:|
| default | 0.843895 | 0.598647 | 0.246117 | 0.721271 | 0.562886 | 0.812081 |
| selective55 | 0.843895 | 0.612953 | 0.225000 | 0.728424 | 0.560616 | 0.812507 |
| selective60 | 0.843895 | 0.602285 | 0.247596 | 0.723090 | 0.564592 | 0.812081 |
| selective65 | 0.843895 | 0.598647 | 0.246117 | 0.721271 | 0.562886 | 0.812081 |

Deltas versus default:
- selective55: hat macro +0.007153; metal macro -0.002270; Open +0.014306; Ride -0.021117; onset +0.000427; K/S/T +0.000000/+0.000000/+0.000000
- selective60: hat macro +0.001819; metal macro +0.001706; Open +0.003638; Ride +0.001479; onset +0.000000; K/S/T +0.000000/+0.000000/+0.000000
- selective65: hat macro +0.000000; metal macro +0.000000; Open +0.000000; Ride +0.000000; onset +0.000000; K/S/T +0.000000/+0.000000/+0.000000

Guardrail: production adoption requires Open gain without material Ride/metal-macro regression and with K/S/T unchanged.
