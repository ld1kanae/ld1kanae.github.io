# GMD KST / Hi-Hat learning assets

This directory is the canonical location for **GMD-derived learning data** used by DrumScribe.

Source-separation rule:
- GMD-derived symbolic/style data lives here.
- DruMaster `songs/*` audio/chart training remains a separate source.
- The uploaded synchronized `なないろ_tempo-mapped_sync.wav/.mid` teacher remains a separate source.
- Do not concatenate rows from those sources into one training set unless an experiment explicitly asks for source pooling.

Hi-hat label mapping for GMD:
- Open: Roland/GMD pitches 26, 46
- Closed: pitches 22, 42, 44
- Pedal hi-hat (44) is evaluated as Closed, following the GMD paper mapping.
- Ride/crash are not required to remain distinct for the Open/Closed HH task.

Generated / retained assets:
- `hihat-style-patterns-v1.json`: primary-genre symbolic Open/Closed pattern statistics derived directly from GMD MIDI.
- `kst-prior-v1.json`: legacy kick/snare/tom symbolic prior, moved here from the old models root without changing its data.
- `kst-prior-v1-LICENSE.txt`: attribution note for the legacy KST prior.
- `LICENSE-GMD-CC-BY-4.0.txt`: attribution/license note for this directory.

The generator is `drumscribe/experiments/build_gmd_hihat_style_patterns.py`.
