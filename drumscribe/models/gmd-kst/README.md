# GMD K/S/T knowledge base

This directory stores **derived learning assets** for DrumScribe kick/snare/tom inference.

## Source

- Google Magenta Groove MIDI Dataset (GMD) v1.0.0, CC BY 4.0
- MIDI-only archive: https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0-midionly.zip
- Expected SHA256: `651cbc524ffb891be1a3e46d89dc82a1cecb09a57c748c7b45b844c4841dcc1e`

The original GMD archive is not committed here. Only reproducible derived statistics/models are kept.

## Split discipline

`knowledge-v1.json` is generated from **GMD train split only**. Validation/test rows are reserved for external evaluation and must not be used to tune production thresholds.

DruMaster `chart.mid` files are never inputs to this build. They remain post-generation evaluation references only.

## Hierarchy

The knowledge base keeps separate aggregates for:

- global
- primary genre
- exact GMD style (`primary/secondary`)
- primary genre × `beat_type` (`beat` / `fill`)
- primary genre × tempo band

This is intentionally compatible with section-local inference: a song can mix different genre experts across intro / verse / pre-chorus / chorus / bridge / outro rather than receiving one song-wide genre label.

## Stored K/S/T features

- hit counts and relative rates
- 16th-grid phase counts
- K/S/T same-slot co-occurrence masks
- local occupied-slot transitions
- velocity histograms and mean velocity
- sample counts / duration / BPM statistics

Pitch grouping follows the GMD Roland mapping:

- kick: 36
- snare: 37, 38, 40
- tom: 43, 45, 47, 48, 50, 58

## Runtime rule

These assets are priors / evidence only. They must not create or force notes merely because a genre commonly places a kick, snare, or tom at a particular position. Runtime use must begin from an acoustically plausible candidate and use GMD knowledge only to resolve ambiguity.

## Rebuild

See `../../experiments/gmd-kst/build_gmd_kst_knowledge.py` and the corresponding GitHub Actions workflow.
