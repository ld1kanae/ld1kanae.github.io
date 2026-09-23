# GMD / E-GMD K/S/T experiments

Purpose: improve DrumScribe kick, snare, and tom transcription without regressing any of those three parts.

## Data discipline

- GMD train split: may be used to build genre/style/rhythm knowledge.
- GMD validation/test: held out for external evaluation.
- E-GMD train/validation/test: retain official sequence splits; kit-level robustness must also be reported.
- DruMaster `chart.mid`: post-generation scoring only. Never use it to select GMD/E-GMD thresholds or to generate predictions.

## Current assets

`../../models/gmd-kst/knowledge-v1.json` is a reproducible train-only knowledge base with:
- global K/S/T statistics
- primary-genre statistics
- exact `primary/secondary` style statistics
- genre × beat/fill statistics
- genre × tempo-band statistics
- 16th-grid phase distributions
- K/S/T same-slot co-occurrences
- occupied-slot transitions
- velocity summaries

Sparse genres are expected. Runtime consumers must shrink low-support genre experts toward the global GMD distribution rather than trust them independently.

## Section-local context

`../../section-analysis.js` accepts an off-vocal AudioBuffer (or mono samples) and estimates local arrangement sections from timbre/energy novelty. It also clusters repeated sections into structural groups A/B/C/... .

The structural groups are **not** automatically named Verse / Pre-Chorus / Chorus. That semantic mapping requires additional evidence. A song-wide genre label is explicitly avoided: later genre mixtures will be estimated independently per section and crossfaded at boundaries.

`../../gmd-kst-prior.js` consumes a local genre mixture and returns bounded K/S/T evidence. It cannot create notes by itself.

## Initial hypotheses for the next K/S/T validation round

1. **Global prior**: use only GMD global K/S/T rhythmic evidence on acoustically plausible candidates.
2. **Section-local genre mixture**: blend GMD genre experts per detected off-vocal section, with sparse-genre shrinkage.
3. **Section-local genre + beat/fill**: combine genre mixture with local beat/fill state, especially for tom rescue near arrangement transitions.
4. **E-GMD acoustic ensemble**: use E-GMD only as an acoustic reclassifier on candidates already admitted by the detector; do not replace K/S/T wholesale.

Promotion rule: a candidate must improve at least one of kick/snare/tom while not reducing the retained best F1 of either of the other two. Marginal gains that depend on one song only require additional held-out evidence before promotion.
