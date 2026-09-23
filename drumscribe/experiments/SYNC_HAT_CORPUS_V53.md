# Synchronized Hi-Hat Corpus v53

## Scope

Three newly supplied fully synchronized WAV/MIDI pairs were analyzed:

- Kaiju
- Arukuaround
- Ray

This experiment is an **oracle synchronized hat-event articulation study**. It evaluates Open/Closed classification at reference hat onset times. It is not yet a complete browser transcription benchmark because onset detection errors are outside this stage.

Reference MIDI is used only for offline teacher extraction and scoring.

## Teacher distribution

| song | Closed | Open | Pedal | Ride | Open→Open | Open→Closed | Open→Pedal |
|---|---:|---:|---:|---:|---:|---:|---:|
| kaiju | 572 | 22 | 9 | 431 | 6 | 7 | 9 |
| arcaround | 200 | 93 | 91 | 58 | 0 | 2 | 91 |
| ray | 1075 | 322 | 312 | 0 | 6 | 199 | 116 |

Roles:

- Kaiju: Ride-heavy control.
- Arukuaround: strong Open→Pedal choke control.
- Ray: Closed-heavy and Open→Closed/Pedal control.
- Existing Diamond Virgin: Open→Open teacher.
- Existing Nanairo: Open→Closed/Pedal teacher.

## Compared hypotheses

### H1 — local single-hit model

Local attack/decay windows only, song-held-out logistic regression.

Aggregate:

- Precision 0.3611
- Recall 0.9908
- F1 0.5293
- AUC 0.8667

The local sound has useful ranking signal, but cross-song calibration is poor and it over-predicts Open.

### H2 — local + next-hit persistence/choke model

ExtraTrees using:

- attack / early / mid / late / tail spectra
- 5–18 kHz and 10–20 kHz energy
- pre-next tail energy
- post-next energy
- next-hit gap
- persistence and choke ratios

Fixed threshold 0.50, song-held-out aggregate:

- Precision 0.6411
- Recall 0.9771
- F1 0.7743
- AUC 0.9907

The AUC is high, so the model generally orders Open above Closed correctly. The remaining issue is probability calibration changing by song.

### H3 — naive transition Viterbi

H2 probabilities plus a transition matrix learned from the other songs.

Aggregate F1: 0.6965

This was worse than H2. Transition distributions differ too much between Kaiju, Arukuaround and Ray, so a global Open/Closed Markov prior is not safe.

### H4 — song-local high-confidence calibration

The H2 ranker is retained, but the threshold is selected reference-free from the largest probability gap in the high-confidence range `[0.35, 0.98]`.

Aggregate:

- Precision 1.0000
- Recall 0.9291
- F1 0.9632
- AUC 0.9907

Per song:

| song | threshold | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| kaiju | 0.6843 | 1.0000 | 0.3636 | 0.5333 |
| arcaround | 0.6012 | 1.0000 | 0.8602 | 0.9249 |
| ray | 0.7703 | 1.0000 | 0.9876 | 0.9938 |

This calibration is highly precise, but Kaiju recall remains low because Open events are extremely rare and form no large stable cluster.

## Most useful features

The leading features were:

1. high-frequency energy immediately before the next articulation
2. early RMS relative to attack
3. spectral centroid immediately before the next articulation
4. pre-next zero-crossing rate
5. early/mid-band energy
6. late 5–18 kHz energy
7. long tail energy relative to attack

This directly supports the requested distinction:

- Open→Open: high-frequency tail remains before the next hit.
- Open→Closed/Pedal: the tail is interrupted around the next articulation.

## Decision

Do not replace production v49/v52 yet.

The new corpus demonstrates that the context/choke ranker is strong, but the following production checks remain necessary:

1. Apply it to actual browser-detected Closed/Open/Ride candidates, not oracle MIDI onset times.
2. Confirm that it rescues missing Open events without converting Closed or Ride false positives.
3. Keep K/S/T unchanged.
4. Use a song-local calibration method with a rare-Open fallback for Kaiju-like songs.
5. Re-run the five-song fresh Chromium benchmark before adoption.

## Assets

- `analyze_sync_hat_corpus_v53.py`
- `results-sync-hat-corpus-v53.json`
- `reference-sync/README.md`
