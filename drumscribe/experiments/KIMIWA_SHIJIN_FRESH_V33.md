# 君は詩人になった — current main fresh browser validation v33

Date: 2026-09-23

## Scope

The uploaded WAV was transcribed from zero through the complete current production path:

`WAV -> decodeAudioData -> transcribe.js / ADTOF -> meter -> rhythm-grid -> midi.js -> downloaded SMF`

Runtime: `main` commit `6b59d489f979e849fea16ac03bf68452e038ccc8`.
The test used a policy-free Playwright Chromium locally; the reference chart was not used.

## Input

- WAV: 44.1 kHz, 16-bit stereo
- Duration: 181.791 s
- SHA-256: `2a27998b8c38f0a80bfacc6605ba8a2e9674a6739cb4f3e96b03cac30993bda0`
- Byte-identical to the previous upload in this conversation.

## Fresh result

- BPM: **134.007729**
- Meter: **4/4**
- Notes: **1,252**
- Kick 418 / snare 260 / tom 18 / closed HH 470 / open HH 26 / pedal HH 34 / crash 26 / ride 0
- Grid family: **straight**
- Subdivision: **1/16 + one 1/32-only event**
- Tempo events: **396**
- Export BPM range: **133.749083–134.433554**
- Mean export BPM: **134.006419**

## Grid fit

| Grid | Fit |
|---|---:|
| straight 8 | 0.727197 |
| straight 16 | **0.967234** |
| straight 32 | 0.884649 |
| triplet 8 | 0.484340 |
| triplet 16 | 0.696640 |

The production triplet rule requires `bestTriplet >= 0.72` and a margin of more than `0.10` over the best straight fit. This audio clearly remains straight: best straight = 0.967234, best triplet = 0.696640.

## Tick and timing checks

- 99.9201% of notes are exactly on the 16th grid.
- 100% of notes are exactly on the 32nd grid.
- Maximum 32nd-grid residual: **0 ticks**.
- Preview/export mapped time vs raw detected event time: median **2.832 ms**, p95 **8.159 ms**.

Independent audio diagnostic (not a gold transcription score): for 869 unique MIDI onset times, the nearest strong multiband spectral-flux maximum within ±60 ms had median absolute residual **9.812 ms** and p95 **22.073 ms**. The four song quarters remained similar, with median residuals 9.13 / 10.73 / 9.68 / 9.64 ms, so no progressive end-of-song timing drift was observed in this diagnostic.

## Interpretation

The previously reconstructed-MIDI result is now confirmed through the complete fresh browser path. The straight/triplet decision, tempo-map range, and preview timing are consistent with the earlier reconstruction.

The note count increased from the earlier old MIDI's 1,211 to 1,252 under the current runtime. This is a detector-version difference, not a quantization change. Because this song has no gold `chart.mid`, part-level precision/recall for kick, snare, tom, hats, and cymbals is still unknown.
