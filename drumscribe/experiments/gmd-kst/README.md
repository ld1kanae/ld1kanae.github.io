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

Sparse genres are expected. Runtime consumers must shrink low-support experts toward the global GMD distribution rather than trust them independently.

## Section-local context

`../../section-analysis.js` accepts an off-vocal AudioBuffer (or mono samples) and estimates local arrangement sections from timbre/energy novelty. It clusters repeated sections into structural groups A/B/C/... .

The structural groups are **not** automatically named Verse / Pre-Chorus / Chorus. A song-wide genre label is explicitly avoided. Sections may change rhythmic character independently, and repeated A/B/C sections may still differ later in the song.

## Held-out finding: semantic genre labels are not the runtime target

A train-only GMD profile was tested on official held-out validation/test rows using K/S/T only.

- validation primary-genre Top-1: 19/111 = 17.1%; Top-3: 41/111 = 36.9%
- test primary-genre Top-1: 43/124 = 34.7%; Top-3: 70/124 = 56.5%

Therefore DrumScribe must **not** assert a section is “rock”, “pop”, etc. from K/S/T alone. Genre/style labels remain provenance for learned experts, not semantic truth about the input song.

## Held-out finding: local exact-style mixtures are useful rhythmic evidence

A more relevant continuation test uses the first half of each held-out GMD performance to select similar train-derived experts, then predicts occupied K/S/T 16th-grid positions in the second half.

Validation macro AUC:
- global GMD prior: 0.6505
- primary-genre mixture: 0.7339
- exact `primary/secondary` style mixture: **0.7621**

Validation exact-style AUC:
- kick 0.8079
- snare 0.7742
- tom 0.7041

Test macro AUC:
- global GMD prior: 0.6239
- primary-genre mixture: 0.7039
- exact style mixture: **0.7293**

Test exact-style AUC:
- kick 0.7970
- snare 0.7670
- tom 0.6240

No DruMaster data is used in this selection/evaluation.

Conclusion: the preferred runtime representation is a **section-local mixture of similar GMD exact-style experts**, not one genre label. Labels remain visible for traceability only.

## Runtime safety rule

`../../gmd-kst-prior.js` returns bounded K/S/T evidence and cannot create notes by itself. GMD rhythmic knowledge is only applied to acoustically plausible candidates. It must never force a note onto a “typical” beat merely because GMD often contains one there.

## Current browser-transfer hypotheses

The real-Chromium matrix keeps the current production path as a baseline and compares independently:

1. **E-GMD kick supplement** — frozen E-GMD v4 kick candidates only.
2. **E-GMD tom supplement** — frozen E-GMD v4 tom candidates only.
3. **E-GMD kick+tom supplement** — both external acoustic candidate streams.
4. **E-GMD + global GMD gate** — only candidates with neutral-or-positive global GMD rhythmic evidence.
5. **E-GMD + section-local exact-style GMD gate** — off-vocal defines local arrangement sections, preliminary strong K/S/T events choose an exact-style mixture inside each section, then the mixture supplies bounded rhythmic evidence.

The existing v4 snare path is left unchanged during this matrix so kick/tom effects can be measured independently.

Promotion rule: a candidate must improve at least one of kick/snare/tom while not reducing the retained best F1 of either of the other two. Marginal gains that depend on one song only require additional held-out evidence before promotion.
