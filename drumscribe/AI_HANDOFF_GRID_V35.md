# DrumScribe AI Handoff — Tempo map v35

最終更新: 2026-09-23

## 変更内容

ユーザー要望:
- BPM変化だけ変更
- 1拍ごとのtempo eventをやめる
- 最低1小節単位にする

v35では、内部のbeat-level tempo推定は維持しつつ、MIDI/previewで使用するtempo mapを**小節単位**へ集約する。

各小節について:
1. beat-level BPMが作る小節総時間を計算
2. 同じ総時間になるduration-equivalent BPMを1つ計算
3. 小節頭だけにtempo eventを置く
4. preview `timeForScore()` も同じbar-level tempoを使う

変更しないもの:
- note ticks
- straight/triplet判定
- 16th/32nd判定
- BPM基準推定
- bar/downbeat判定
- 楽器分類

## Proof v34 tempo-only比較

既存 `candidate-v34.mid` のtempo metadataだけを同方式で変換:
- tempo events 426 -> **110**
- note ticks変更なし
- note playback time差 median 0.054 ms
- p95 0.521 ms
- max 1.166 ms
- bar boundary累積差 max 0.010 ms
- BPM range 98.735–100.369

## 5曲 fresh Chromium regression

run: `35849808016` success

tempo events:
- arcaround 549 -> **139**
- diamondvirgin 589 -> **149**
- kaiju 594 -> **153**
- nanairo 491 -> **127**
- ray 557 -> **142**

全曲:
- `tempoResolution = "bar"`
- min tempo event gap = **1920 ticks** (PPQ480 4/4の1小節)
- tempo gap violations = **0**
- grid failures = 0
- max grid residual = 0.0 beat

aggregate:
- Precision .911
- Recall .743
- F1 .818

## CI

`experiments/validate_grid_browser.py` にbar-tempo invariantを追加:
- `tempoResolution == "bar"` のとき
- consecutive tempo meta eventが現拍子の1小節未満ならfailure

## Runtime files

- `rhythm-grid.js`
- `app.js`
- `midi.js`
- `index.html`

## Validation

- `experiments/TEMPO_BAR_V35.md`
- `experiments/results-tempo-bar-v35.json`

