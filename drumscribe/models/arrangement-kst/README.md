# Arrangement K/S/T learning assets

This directory stores **research data/models for arrangement-aware Kick/Snare/Tom rescoring**.

Production status:
- Production runtime currently uses the validated fixed v39D-style rule in `../../arrangement/kst-rescore.js`.
- The learned v42/v43 models are **not production models**.
- Do not replace the fixed runtime rule with `learned-rescore-v43.json` without a new song-grouped validation and fresh Chromium non-regression run.

Files:
- `training-candidates-v43.json`
  - 83 labeled low-threshold acoustic candidates from the five validation songs.
  - Features are prediction-time features from drums audio, A/A' structural-family analysis and the GMD slot prior.
  - Labels are derived from `chart.mid` only for training/evaluation.
  - Current recoverable positives: Kick 5, Snare 7, Tom 2.
- `learned-rescore-v43.json`
  - Research-only Logistic Regression export.
  - Only Snare has enough examples for a full-data fit; Kick/Tom are disabled for insufficient class support.
  - Five-song leave-one-song-out did not generalize strongly enough to rescue held-out candidates.

When adding new paired validation songs:
1. Generate transcription candidates without reading reference MIDI.
2. Generate A/A' structural families from offvocal/accompaniment.
3. Append prediction-time features and chart-derived labels using the v43 schema.
4. Re-run song-grouped or leave-one-song-out validation.
5. Require per-part K/S/T non-regression and fresh-browser rhythm-grid/MIDI validation before runtime adoption.

See:
- `../../experiments/ARRANGEMENT_KST_LEARNED_V43.md`
- `../../experiments/results-arrangement-kst-learned-v43.json`
