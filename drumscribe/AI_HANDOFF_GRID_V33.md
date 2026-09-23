# DrumScribe grid / tempo handoff v33

Date: 2026-09-23

## What was completed

The user re-uploaded `君は詩人になった [drums](1).wav`. The file was successfully mounted and is byte-identical to the prior upload:

- SHA-256: `2a27998b8c38f0a80bfacc6605ba8a2e9674a6739cb4f3e96b03cac30993bda0`
- 44.1 kHz / 16-bit / stereo
- duration 181.791 s

A complete fresh browser transcription was run using the current `main` runtime at commit:

`6b59d489f979e849fea16ac03bf68452e038ccc8`

The runtime was bundled from GitHub Actions and executed locally with a policy-free Playwright Chromium. No reference MIDI was supplied.

## Result

- BPM: 134.007729
- meter: 4/4
- variable meter: false
- total notes: 1,252
- kick 418
- snare 260
- tom 18
- closed HH 470
- open HH 26
- pedal HH 34
- crash 26
- ride 0

Grid:

- family: straight
- subdivision: `1/16+1/32`
- straight 16 fit: 0.967234
- best triplet fit: 0.696640
- triplet production gate was not met

Tempo map:

- events: 396
- range: 133.749083–134.433554 BPM
- mean: 134.006419 BPM

Tick checks:

- 16th-grid exact share: 99.9201%
- 32nd-grid exact share: 100%
- maximum 32nd-grid residual: 0 ticks

Timing:

- preview/export mapped time vs raw event time: median 2.832 ms, p95 8.159 ms
- independent multiband spectral-onset diagnostic: median 9.812 ms, p95 22.073 ms across 869 unique MIDI onset positions
- no progressive timing drift was observed across four song quarters in that diagnostic

## Interpretation

The old reconstructed-MIDI result is now confirmed through the complete production path:

`WAV -> transcribe -> rhythm-grid -> tempo map -> MIDI`

This song is clearly straight, not shuffle/triplet. The current triplet branch does not falsely activate here.

The current runtime detected 1,252 notes versus 1,211 in the earlier old MIDI. This is a detector-version difference. It is not caused by quantization, which does not change note classes or event count.

There is no gold `chart.mid` for this song, so part-level precision/recall remains unknown. Do not describe the note-class result as proven accurate.

## Files

- `drumscribe/experiments/KIMIWA_SHIJIN_FRESH_V33.md`
- `drumscribe/experiments/results-kimiwa-shijin-fresh-v33.json`

No production threshold or runtime code was changed in v33.
