# GMD KST / Hi-Hat learning assets

This directory is the canonical location for **GMD-derived learning data** used by DrumScribe.

Source-separation rule:
- GMD-derived symbolic/style data lives here.
- DruMaster `songs/*` audio/chart training remains a separate source.
- The uploaded synchronized `なないろ_tempo-mapped_sync.wav/.mid` teacher remains a separate source.
- Do not concatenate rows from those sources into one training set unless an experiment explicitly asks for source pooling.
- Score-level fusion between independently trained/derived sources is allowed only when the experiment records that provenance explicitly.

Hi-hat label mapping for GMD:
- Open: Roland/GMD pitches 26, 46
- Closed: pitches 22, 42, 44
- Pedal hi-hat (44) is evaluated as Closed for the Open/Closed task.
- This label mapping does **not** mean that GMD, DruMaster songs, and synchronized-teacher training rows are merged.

Generated / retained assets:
- `hihat-style-patterns-v1.json`: primary-genre 16th-slot Open/Closed rates, transitions, and representative 1-bar patterns.
- `hihat-sequence-patterns-v2.json`: GMD-only sequential/context asset. Adds 9-slot local HH occupancy contexts, local kick/snare contexts, 2/3/4-event articulation n-grams, transition-by-gap statistics, Open-run lengths, 1-bar patterns, and 2-bar patterns.
- `hihat-arrangement-patterns-v3.json`: GMD-only genre/arrangement proxy asset. Keeps event-level Open/Closed transitions separate from quantized bar-level recurrence statistics, and records cymbal/hat incidence at ordinary bar heads, groove-change heads, fill-following heads, and repeated-bar heads. These are groove/phrase priors only; GMD does not provide semantic verse/pre-chorus/chorus labels.
- `kst-prior-v1.json`: legacy kick/snare/tom symbolic prior, moved here from the old models root without changing its data.
- `kst-prior-v1-LICENSE.txt`: attribution note for the legacy KST prior.
- `LICENSE-GMD-CC-BY-4.0.txt`: attribution/license note for this directory.

Generators:
- v1: `drumscribe/experiments/build_gmd_hihat_style_patterns.py`
- v2: `drumscribe/experiments/build_gmd_hihat_sequence_patterns_v2.py`
- v3: `drumscribe/experiments/build_gmd_hihat_arrangement_patterns_v3.py`

The v2/v3 builders read only the official GMD MIDI-only archive. It does not read `DruMaster/songs/*` or the synchronized Nanairo WAV/MIDI pair.
