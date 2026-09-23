# Arrangement K/S/T rescoring v38

A/A' structural-family support is used only to rescore low-threshold acoustic candidates. No note is copied from another section. Reference chart.mid is scoring-only.

## Hypotheses

- H1 strict family: acoustic confidence >= 0.72, same-family support >= 50%, family similarity >= 0.90.
- H2 family consensus: acoustic confidence >= 0.55, same-family support >= 67%, family similarity >= 0.92.
- H3 family + GMD: acoustic confidence >= 0.50, same-family support >= 50%, family similarity >= 0.90, GMD slot lift >= 0.80.

GMD slot prior: 228 train files / 13550 4/4 bars.

## Aggregate all-five-song comparison

| segmentation | policy | KST F1 | delta | kick delta | snare delta | tom delta |
|---|---|---:|---:|---:|---:|---:|
| conservative | H1_strict_family | 0.8581 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| conservative | H2_family_consensus | 0.8581 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| conservative | H3_family_gmd | 0.8581 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| balanced | H1_strict_family | 0.8581 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| balanced | H2_family_consensus | 0.8581 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| balanced | H3_family_gmd | 0.8581 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| sensitive | H1_strict_family | 0.8581 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| sensitive | H2_family_consensus | 0.8581 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| sensitive | H3_family_gmd | 0.8581 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Simple three-song comparison (diamondvirgin / nanairo / ray)

| segmentation | policy | KST F1 | delta | kick delta | snare delta | tom delta |
|---|---|---:|---:|---:|---:|---:|
| conservative | H1_strict_family | 0.8623 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| conservative | H2_family_consensus | 0.8623 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| conservative | H3_family_gmd | 0.8623 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| balanced | H1_strict_family | 0.8623 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| balanced | H2_family_consensus | 0.8623 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| balanced | H3_family_gmd | 0.8623 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| sensitive | H1_strict_family | 0.8623 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| sensitive | H2_family_consensus | 0.8623 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| sensitive | H3_family_gmd | 0.8623 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Guardrails

- This round is rescue-only: it never deletes an existing production K/S/T note.
- A/A' is a structural-family relationship, not verse/chorus semantics.
- arcaround and kaiju are retained in all-five reporting but the simple3 aggregate is also shown because the current arrangement experiment assumes a 4/4 bar correspondence.
- Production adoption requires non-regression of kick/snare/tom individually and a fresh real-browser run.
