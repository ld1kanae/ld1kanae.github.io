# Open-hat default vs combined v46

Fresh browser comparison. Reference MIDI is scoring-only.

| variant | closed F1 | open F1 | ride F1 | hat macro | metal macro | collapsed hat/ride onset F1 |
|---|---:|---:|---:|---:|---:|---:|
| default | 0.843895 | 0.598647 | 0.246117 | 0.721271 | 0.562886 | 0.812081 |
| combined | 0.843895 | 0.647770 | 0.000000 | 0.745832 | 0.497222 | 0.817466 |

Combined minus default:
- hat macro: +0.024561
- metal macro incl. ride: -0.065665
- open F1: +0.049123
- ride F1: -0.246117
- collapsed hat/ride onset F1: +0.005385
- K/S/T deltas: kick +0.000000, snare +0.000000, tom +0.000000

Guardrail: do not adopt combined if Open gain is merely a Ride-to-Open relabeling that materially lowers strict Ride/metal macro accuracy.
