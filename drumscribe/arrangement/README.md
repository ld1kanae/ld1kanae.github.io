# DrumScribe arrangement analysis

This directory is the canonical shared location for **off-vocal / instrumental arrangement structure analysis**.

## What it currently does

`analyzeSections()` detects large-scale structural boundaries from local timbre and energy changes, then groups sufficiently similar repeated sections into structural families `A`, `B`, `C`, ... . Repeated appearances keep the same family key and receive occurrence labels such as `A`, `A'`, `A''`.

Current descriptors:
- log RMS
- crest factor
- normalized first-difference RMS
- zero-crossing rate
- low / mid / high energy ratios

The analyzer can optionally snap structural boundary candidates toward an already-estimated musical grid when `bpm` and `barPhaseSec` are supplied.

## What it does **not** do

It does **not** currently claim semantic Japanese song-form labels such as:
- Aメロ
- Bメロ
- サビ
- 間奏
- Cメロ

Structural family `A` is therefore **not automatically equal to Aメロ**. It only means “a section acoustically similar to the other sections assigned family A”. A later recurrence can be displayed as `A'`, but both `A` and `A'` retain `group: "A"` so downstream analysis knows they belong to the same family.

Any future semantic classifier should consume this module's output rather than duplicate its feature extraction / boundary detection.

## Canonical API

Import only from:

```js
import {
  analyzeSections,
  extractSectionFeatures,
  rescoreKstByArrangement,
} from './arrangement/index.js';
```

Example with a WebAudio `AudioBuffer`:

```js
const result = analyzeSections(offvocalDecoded, {
  analysisSampleRate: 8000,
  bpm: 99.1,
  barPhaseSec: 0.12,
  numerator: 4,
  denominator: 4,
  frameSec: 0.75,
  hopSec: 0.375,
  contextSec: 4.5,
  minSectionSec: 7,
  noveltyStd: 0.72,
  maxSections: 18,
});

console.log(result.boundaries);
console.log(result.sections.map(s => ({
  start: s.startSec,
  end: s.endSec,
  group: s.group,
  label: s.label,
  occurrence: s.occurrence,
  repeatSimilarity: s.repeatSimilarity,
})));
```

## Output contract

`analyzeSections()` returns:
- `duration`
- `boundaries`
- `sections[]`
  - `index`
  - `startSec`
  - `endSec`
  - `duration`
  - `group` — stable structural family key, e.g. `A`
  - `label` — occurrence label, e.g. `A`, `A'`, `A''`
  - `occurrence` — 1-based occurrence count within the family
  - `repeatSimilarity`
  - internal feature `vector`
- `novelty`
- `featureTimes`
- `featureSchema`
- `method`

## Runtime status

As of 2026-09-23 this module is **part of the production transcription path when an offvocal / accompaniment source is supplied**. The normal drum-only path remains unchanged when no arrangement source is provided.

Production uses the structural-family output only as supporting evidence for low-threshold K/S/T acoustic candidates. It still does not assign semantic labels such as Aメロ/Bメロ/サビ.

Do not describe DrumScribe as detecting Aメロ/Bメロ/サビ from off-vocal unless a separate semantic classifier is later implemented and validated.


## Arrangement-aware K/S/T rescoring

`rescoreKstByArrangement()` is the shared entry point for the A/A' repetition experiment.

It accepts:
- final baseline transcription events,
- low-threshold acoustic K/S/T diagnostics from `transcribe(..., {diagnosticKst:true})`,
- `analyzeSections()` output,
- BPM / meter context,
- an optional GMD 16th-slot prior.

Guardrails:
- it never copies a note from A to A';
- a target-time acoustic candidate must already exist;
- A/A' remains a structural-family relation, not verse/chorus semantics;
- Snare/Tom candidates already above the production threshold but removed downstream are not resurrected by default;
- a two-hand guard rejects a new hand-played event when it would create a third simultaneous hand event.

The compact GMD slot prior is:
`../models/gmd-kst/slot-prior-v1.json`.

The current production policy is exported as `arrangementKstPolicyCurrent` and currently points to `arrangementKstPolicyV46R1`.

It preserves the validated v39D A/A' family rescue and adds a **Snare-only residual E-GMD gate** for candidates not already rescued by the family rule:
- frozen E-GMD v4 Snare probability >= 0.93;
- acoustic confidence >= 0.55;
- GMD Snare slot lift >= 1.65;
- the candidate must already exist acoustically and must remain below the production threshold;
- the two-hand guard still applies.

Fresh Chromium v47 passed normal rhythm-grid / MIDI export non-regression, and v48 exercised the actual `index.html -> app.js` production path. v48 K/S/T F1 is 0.939224, all-class F1 is 0.819080, grid residual is 0 and hand-grid violations are 0.

The v46R1 portable thresholds were proposed after inspecting earlier results on the same five-song development set, so these results do **not** establish unknown-song generalization. Keep that distinction when interpreting the production gain.

Validation details:
- `../experiments/ARRANGEMENT_KST_V47.md`
- `../experiments/ARRANGEMENT_APP_V48.md`
