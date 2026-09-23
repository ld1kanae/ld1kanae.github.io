# DrumScribe AI Handoff — Proof / Grid v34

最終更新: 2026-09-23

## 重要結論

Proof音源で「クオンタイズが大きくずれる」原因は、note snap自体より前段の **tempo octave error + bar phase error** だった。

入力:
- drums: `1_1_Proof v6 (Add Vocal)_(Instrumental)_(Drums).wav`
- instrumental: `1_Proof v6 (Add Vocal)_(Instrumental).wav`
- user reference: BPM約99、微変動

旧main:
- auto BPM 198.163894
- bar phase 1.092027 s
- event-familyは99.125 BPMを最上位にしていた

## v34 runtime

### 1. Tempo octave gate

`transcribe.js` で、次を全て満たす場合だけ2x→1xへ補正:
- initial/event-family ratio 1.90–2.10
- event-family score >= .58
- event-family best - initial付近candidate score >= .12

Proof:
- 198.163894 / 99.125 = 1.99913
- 99.125 score .66037
- 198.25 score .42309
- margin .23728
- => gate fires
- refined BPM ≈ 99.076668
- source `audio-event-octave-corrected`

既存5曲ではこの新gateは0/5。

### 2. GMD bar-phase model

Model:
- `models/gmd-kst/bar-phase-discriminative-v1.json`

Trainer:
- `experiments/gmd-kst/train_bar_phase_model.py`

Data discipline:
- GMD official train split only for model fitting
- 3 hypotheses selected on deterministic internal train holdout
- official validation/test are report-only
- no DruMaster chart MIDI used for training

Internal train holdout:
- phase log probability: perf acc .6265
- Bernoulli presence: .6024
- logistic rotation: **.6627** selected

Official report-only:
- validation perf acc .5410
- test perf acc .7586

Because this is not strong enough as a universal downbeat model, runtime use is restricted to `audio-event-octave-corrected` cases only.

Proof saved full-song 99-BPM events:
- selected phase .123011 s
- runner-up 1.088172 s
- margin .77551
- coverage .8857
- runtime gate .55/.55 => accepted

A prior full-browser v34 prototype on the complete WAV:
- BPM 99.076668
- bar phase .127742 s
- source `gmd-kst-gated`
- grid 1/16+1/32
- tempo events 426
- BPM range 98.710–100.389
- raw→preview median 3.36 ms / p95 15.03 ms

### 3. Instrumental / off-vocal

Instrumental arrangement novelty is useful as an auxiliary long-range clue.

Strong section-change candidates (10):
- old manual-99 bar phase 1.039 s: nearest-barline median 895.9 ms
- GMD phase .123 s: 366.9 ms

Do not use section novelty alone to force bar phase. It is not precise enough and some arrangement changes need not occur exactly at a bar line.

## 5-song non-regression

Fresh Chromium run: `35846141342`, success.

BPM:
- arcaround 132.002953
- diamondvirgin 135.075370
- kaiju 180.006816
- nanairo 125.006439
- ray 131.999934

GMD bar-phase gate fired: 0/5.

Aggregate:
- Precision .911
- Recall .743
- F1 .818
- grid failures 0
- max grid residual 0.0 beat
- note counts identical to baseline

## Files added/changed

Runtime:
- `transcribe.js`
- `gmd-bar-phase.js`
- `app.js`
- `index.html`

Model / reproducibility:
- `models/gmd-kst/bar-phase-discriminative-v1.json`
- `experiments/gmd-kst/train_bar_phase_model.py`
- `experiments/gmd-kst/results-gmd-bar-phase-heldout-v1.json`

Validation:
- `experiments/PROOF_V34.md`
- `experiments/results-proof-v34.json`
- `VALIDATION.md`

## Post-promotion triplet regression

main head `9c363cd4d951f4ce79e344d555a91840dacaa4bb` でGMD held-out triplet workflow `35847387266` も再実行し成功。

- auto: 14/24 = 58.33%
- auto triplet recall: 2/12 = 16.67%
- auto straight controls: 12/12 = 100%
- oracle BPM: 14/24 = 58.33%
- oracle triplet recall: 2/12 = 16.67%
- oracle straight controls: 12/12 = 100%

v32と同値。今回のtempo-octave / GMD bar-phase修正によるtriplet branchの回帰は確認されなかった。

## Caveat

Repository-packaged runtimeの最終full-WAVローカルrerunは実行上限を超えたため完了扱いにしない。
ただし:
1. 同じ全WAVの先行full-browser v34 prototypeが存在
2. 最終tempo/GMD gateを保存済みfull-song eventへ再適用し両方pass
3. 5曲real-browser regressionは完全非退行

次回public UIでProof WAVを再生成し、instrumentalと重ねて耳で最終確認する。
