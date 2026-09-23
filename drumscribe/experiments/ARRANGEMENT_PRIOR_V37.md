# DrumScribe Arrangement Prior v37

offvocal structure is inferred before opening reference chart.mid. Reference MIDI is used only for the evaluation below.

## Three structure hypotheses

1. H1 boundary-cymbal prior: structural boundaries should have more crash/cymbal support than ordinary bar heads.
2. H2 family-repetition prior: A/A' corresponding bars should be more similar than different-family bars.
3. H3 GMD general prior: use GMD only for generic downbeat-cymbal and repeated-groove statistics; GMD has no section labels.

## Five-song results by segmentation mode

| mode | boundary crash lift | boundary cymbal lift | K/S/T repeat margin | metal repeat margin |
|---|---:|---:|---:|---:|
| conservative | 0.5499 | 0.5853 | 0.2573 | 0.4638 |
| balanced | 0.8791 | 0.8772 | -0.0961 | -0.0166 |
| sensitive | 0.7551 | 0.7193 | 0.2883 | 0.2122 |

## GMD generic prior

- Files used: 230; bars used: 13573
- Adjacent-bar full-pattern F1: 0.6664
- Same-style cross-file first-bar F1: 0.3713
- Adjacent repetition margin: 0.2951
- Crash downbeat lift vs beats 2-4: 3.1407
- Cymbal downbeat lift vs beats 2-4: 1.2088

## Interpretation guard

- A/B/C are structural-family labels only; A' is a recurrence of A.
- GMD does not provide verse/pre-chorus/chorus labels or paired offvocal audio.
- No production note is added or deleted by this experiment.
- The next stage may use only priors that are supported here, and must validate kick/snare/tom non-regression before runtime adoption.
