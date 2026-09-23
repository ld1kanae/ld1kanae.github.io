# DrumScribe synchronized Hi-Hat learning handoff v65

Date: 2026-09-24

## What was done

Five user-supplied tempo-mapped synchronized WAV/MIDI pairs were processed directly:

- `アルクアラウンド_tempo-mapped_sync.wav/.mid` -> `arcaround`
- `ダイヤモンドヴァージン_tempo-mapped_sync.wav/.mid` -> `diamondvirgin`
- `怪獣_tempo-mapped_sync.wav/.mid` -> `kaiju`
- `なないろ_tempo-mapped_sync.wav/.mid` -> `nanairo`
- `Ray_tempo-mapped_sync.wav/.mid` -> `ray`

Current DrumScribe was run on the synchronized WAV files with `hatSequenceVariant:'off'` and `hatFusionVariant:'off'`. The normal v57 Ride rescue remained in the baseline pipeline. Candidate generation did not read MIDI.

For each generated GM42/46 candidate, the synchronized MIDI supplied a one-to-one label within ±80 ms: Closed, Open, Pedal, Ride, Crash, or false/unmatched. Total labeled candidate rows: 6,288.

## Main result

Five-fold leave-one-song-out validation selected an ExtraTrees Open-vs-all-non-Open classifier:

- positive: Open HH (GM46)
- negative: Closed HH, Pedal HH, Ride, Crash, and false/unmatched candidates
- features: 14 attack/decay/tail/choke acoustic values, existing Open probability, detector score, detector confidence, and current Open/Closed state
- fixed Open threshold: 0.55
- fixed Closed threshold: 0.45

Aggregate held-out metrics:

- Closed F1: `0.644092 -> 0.652781`
- Open F1: `0.612691 -> 0.766220`
- HH macro F1: `0.628392 -> 0.709501` (`+0.081109`)
- collapsed Hat/Ride onset F1: exactly unchanged at `0.769563`
- K/S/T: structurally unaffected because the stage only relabels existing GM42/46 events

Per-song HH macro F1:

- arcaround: `0.220755 -> 0.609167`
- diamondvirgin: `0.190570 -> 0.289575`
- kaiju: `0.367628 -> 0.642780`
- nanairo: `0.901732 -> 0.917965`
- ray: `0.869218 -> 0.910562`

All five held-out songs improved.

## Hypotheses compared

1. `H1_clean_logreg`: Open vs Closed only. Aggregate HH macro `0.687871`.
2. `H2_allneg_extra`: Open vs all non-Open candidate types. Best fixed-threshold result `0.709501`.
3. `H3_allneg_localnorm`: H2 plus within-song ranks/robust-z. Aggregate HH macro `0.646509`.

Therefore the useful lesson is not merely “learn Open and Closed timbres.” The model must explicitly see Pedal/Ride/Crash/false candidates as non-Open negatives.

## Portable model sweep

- 500 trees / depth 14: HH macro `0.709501`; approximately 4.6 MB.
- 100 trees / depth 12: HH macro `0.696128`; approximately 0.75 MB; every held-out song still improves.
- 80 trees / depth 10: rejected because diamondvirgin regressed slightly.

Use the 100-tree/depth-12 configuration as the current browser-portable production candidate. Keep the 500-tree model as the experiment accuracy ceiling.

## Exact input identity

- arcaround MIDI: `3fcc1115bbe73c8d1e7219f458df3b22a1145b7597f441e34a1ed46768a840f8`
- arcaround WAV: `83dc2d1ca0af3af6de093b55b56626433146062b8322ce171d5710f43cbea4ab`
- diamondvirgin MIDI: `44a4d08e43b2fdae95caed0b6c1f0389f7015abc06c2da048ac5c38f1fb05644`
- diamondvirgin WAV: `1afb2d93354d33f14fdf47ead02b771d84d0bd59d98053f04461771f48596443`
- kaiju MIDI: `a765a9103abb0ab77ab6674de1f52a23a3b3df14164de5778e396c72c1288662`
- kaiju WAV: `e900dde8c874dd7ba54c9eba309c9e72e071ae84de14ae34e1db39622aeba372`
- nanairo MIDI: `ab4a84377bfd678192040fbb00e17face55cf6aed5528a4699bf9ffa47b898a0`
- nanairo WAV: `d07eefee87cb9a78518cb856228ce3e2032c96c226184bca2ff83af54c2baf50`
- ray MIDI: `226c34c28ec9dd111b9fee4c4a24017466b3bf52af1bab83f137d44ef4195b45`
- ray WAV: `ec87d768c61688cdd51c0d2a1e8cd74da4141b1a6e500c673ddccfc6dc3b7019`
- generated candidate JSON: `d0a74a14a1d365c854cccb65eddc5cca23efb6d933f4b96682a704c0fdd8d3ef`
- result JSON before report expansion: `05cd9409247430b663709bf4488c20800aa96ffeee178d89ffe02b78e9a698fc`

## Repository record

- Validation report: `drumscribe/experiments/SYNC_HAT_LEARNING_LOOCV_V65.md`
- Report commit: `6cccb5a78242a3772eb2462fd9ece3456dcbee21`

## Next implementation step

Serialize the 100-tree H2 model, add an audio-only rescoring function after v57 Ride rescue and before optional v61 fusion, run a fresh browser replay, verify exact K/S/T non-regression, and only then enable it by default.
