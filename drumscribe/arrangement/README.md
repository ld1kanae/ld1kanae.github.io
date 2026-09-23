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

As of 2026-09-23 this module is **available as shared infrastructure but is not part of the production transcription path**. The Proof validation used the same algorithm diagnostically to test whether instrumental structure supported one bar-phase candidate over another.

Do not describe DrumScribe as currently detecting Aメロ/Bメロ/サビ from off-vocal until a semantic classifier has been separately implemented and validated.


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

The compact GMD prior used by the v39D research candidate is:
`../models/gmd-kst/slot-prior-v1.json`.

As of this documentation update, the rescoring API exists as shared infrastructure. Runtime adoption still depends on fresh-browser non-regression validation.
