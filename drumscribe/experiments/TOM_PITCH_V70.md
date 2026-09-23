# Tom pitch v70 — E-GMD second-stage classifier

Tom onset detection is unchanged. This experiment classifies only already-known tom hits.

## E-GMD held-out validation

| method | exact | 4-tier |
|---|---:|---:|
| fixed45 | 0.212 | 0.212 |
| median_peak | 0.318 | 0.318 |
| class_profile | 0.470 | 0.470 |
| multinomial_logreg | 0.512 | 0.512 |

## DruMaster transfer (selection-independent)

| method | exact | 4-tier |
|---|---:|---:|
| fixed45 | 0.359 | 0.359 |
| median_peak | 0.326 | 0.326 |
| class_profile | 0.467 | 0.467 |
| multinomial_logreg | 0.359 | 0.359 |

DruMaster chart.mid was used only after the E-GMD model was frozen.
No production runtime change is made by this experiment.
