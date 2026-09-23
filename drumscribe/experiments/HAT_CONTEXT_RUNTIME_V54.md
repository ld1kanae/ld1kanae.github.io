# Hi-hat context runtime v54

Five-song fresh Chromium comparison. The synchronized-corpus logistic model was trained offline; reference chart.mid is scoring-only in this runtime test.

| variant | closed F1 | open F1 | ride F1 | HH macro | collapsed onset F1 | changed |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.843895 | 0.602285 | 0.247596 | 0.723090 | 0.812081 | 0 |
| hats50 | 0.771390 | 0.388912 | 0.247596 | 0.580151 | 0.812081 | 1009 |
| hats55 | 0.773731 | 0.386383 | 0.247596 | 0.580057 | 0.812081 | 998 |
| selective55 | 0.773731 | 0.420016 | 0.000000 | 0.596873 | 0.812081 | 1186 |
| binary55 | 0.773731 | 0.420016 | 0.000000 | 0.596873 | 0.812081 | 1186 |

## Deltas vs baseline

- hats50: HH macro -0.142939; Open -0.213372; Closed -0.072506; Ride +0.000000; onset +0.000000; K/S/T +0.000000/+0.000000/+0.000000
- hats55: HH macro -0.143033; Open -0.215902; Closed -0.070164; Ride +0.000000; onset +0.000000; K/S/T +0.000000/+0.000000/+0.000000
- selective55: HH macro -0.126217; Open -0.182269; Closed -0.070164; Ride -0.247596; onset +0.000000; K/S/T +0.000000/+0.000000/+0.000000
- binary55: HH macro -0.126217; Open -0.182269; Closed -0.070164; Ride -0.247596; onset +0.000000; K/S/T +0.000000/+0.000000/+0.000000

Production adoption guard: K/S/T must remain exactly non-regressed and the chosen hat variant must improve HH macro without reducing collapsed hat/ride onset F1.
