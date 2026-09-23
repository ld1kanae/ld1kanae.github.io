# DrumScribe AI Handoff — Synchronized Hi-Hat Corpus v53

Date: 2026-09-23

## New synchronized reference pairs

Three fully synchronized WAV/MIDI pairs were supplied and directly analyzed:

- `怪獣_tempo-mapped_sync.wav/.mid`
- `アルクアラウンド_tempo-mapped_sync.wav/.mid`
- `Ray_tempo-mapped_sync.wav/.mid`

Exact sizes, durations, SHA-256 values and teacher distributions are recorded in:

- `experiments/reference-sync/README.md`
- `experiments/results-sync-hat-corpus-v53.json`

The large binaries are not committed because the current connector cannot guarantee byte-perfect binary transfer. Do not create a partial or text-encoded backup. Verify bytes and SHA-256 before adding them through another route.

## Teacher roles

- Diamond Virgin: Open→Open continuation teacher; 468 transitions.
- Nanairo: Open→Closed/Pedal choke teacher.
- Kaiju: Ride-heavy and rare-Open control; 431 Ride, 22 Open.
- Arukuaround: strong Open→Pedal choke control; 91 transitions.
- Ray: Closed-heavy control; 1,075 Closed, 199 Open→Closed, 116 Open→Pedal.

## v53 hypotheses

H1 local single-hit logistic:
- song-held-out Open F1 0.5293
- AUC 0.8667
- over-predicts Open across recording domains

H2 local + pre-next/post-next context ExtraTrees, threshold 0.50:
- song-held-out Open F1 0.7743
- AUC 0.9907
- ranking is strong but probability calibration moves by song

H3 global transition Viterbi:
- Open F1 0.6965
- worse than H2
- do not use a single global Open/Closed transition matrix; song arrangements differ too much

H4 H2 + reference-free song-local high-gap calibration:
- Precision 1.0000
- Recall 0.9291
- F1 0.9632
- Ray F1 0.9938
- Arukuaround F1 0.9249
- Kaiju F1 0.5333 because Open is very rare

Important limitation: v53 uses **reference MIDI hat onset times**. It proves articulation ranking, not full production onset transcription accuracy.

## Strong features

Most useful signals:

1. 5–18 kHz energy immediately before the next articulation
2. early RMS relative to attack
3. pre-next spectral centroid and zero-crossing rate
4. late high-frequency energy
5. pre-next / post-next energy ratio
6. gap to the next articulation

This supports the requested physical interpretation:

- Open→Open: tail remains through the next articulation interval.
- Open→Closed/Pedal: the tail is interrupted by choke.

## Current production status

Do not change production from this handoff alone.

Current main observed during v53:

- Open/Closed variant: `ride-selective60-decay-rescue`
- sequence repair: `inversion-guarded-rescue`

The v53 ExtraTrees/context classifier is **research only** until it is applied to actual browser-detected Closed/Open/Ride candidates and passes five-song fresh Chromium non-regression.

## Next implementation step

1. Collect current browser metal candidates for the five songs, preserving their original open-hat probabilities and groups.
2. Extract v53 context/choke features at those candidate times from `drums.mp3` or synchronized WAV where available.
3. Train with song-held-out folds. Reference chart is scoring-only.
4. Apply the v53 model as articulation-only rescoring; do not create a new hit initially.
5. Add a rare-Open fallback for Kaiju-like songs. The high-gap calibrator alone is too conservative there.
6. Compare against current v49/v52 runtime for Closed, Open, Ride-collapsed onset, K/S/T and overall F1.
7. Adopt only if K/S/T is unchanged and the five-song fresh-browser result improves.

## Assets

- `experiments/analyze_sync_hat_corpus_v53.py`
- `experiments/results-sync-hat-corpus-v53.json`
- `experiments/SYNC_HAT_CORPUS_V53.md`
- `experiments/reference-sync/README.md`
