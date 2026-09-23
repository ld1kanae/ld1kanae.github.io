# DrumScribe arrangement analysis

This directory is the canonical shared location for **off-vocal / instrumental arrangement structure analysis**.

## What it currently does

`analyzeSections()` detects large-scale structural boundaries from local timbre and energy changes, then groups sufficiently similar repeated sections as `A`, `B`, `C`, ...

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

Structural group `A` is therefore **not automatically equal to Aメロ**. It only means “a section acoustically similar to the other sections assigned group A”.

Any future semantic classifier should consume this module's output rather than duplicate its feature extraction / boundary detection.

## Canonical API

Import only from:

```js
import {analyzeSections, extractSectionFeatures} from './arrangement/index.js';
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
  - `group`
  - `repeatSimilarity`
  - internal feature `vector`
- `novelty`
- `featureTimes`
- `featureSchema`
- `method`

## Runtime status

As of 2026-09-23 this module is **available as shared infrastructure but is not part of the production transcription path**. The Proof validation used the same algorithm diagnostically to test whether instrumental structure supported one bar-phase candidate over another.

Do not describe DrumScribe as currently detecting Aメロ/Bメロ/サビ from off-vocal until a semantic classifier has been separately implemented and validated.
