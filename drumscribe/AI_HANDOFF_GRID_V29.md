# DrumScribe AI Handoff — Grid/Tempo v29

最終整理日: 2026-09-23

このファイルは、別チャットが今回の「ノート量子化＋可変BPM」対応を低負荷で引き継ぐための差分要約です。
全体の既存引継ぎは `drumscribe/AI_HANDOFF.md` を参照してください。

## 今回のユーザー指摘

生成MIDIをDAW等で確認すると、ドラム音が拍グリッドから微妙に外れていた。

要求:
- 通常は8分 / 16分 / 32分音符へ量子化する。
- 量子化で音源と合わなくなる場合、ノートをグリッド外へ戻すのではなくBPM側を変動させる。
- shuffle / swing / triplet系はstraight gridを強制しない。
- GMDジャンル別解析は三連系の補助情報として検討する。

## 原因

旧 `midi.js` は以下の方式だった。

```text
raw detected seconds
  -> fixed BPM 1個
  -> seconds * ticksPerSecond
  -> MIDI tick
```

そのため、音源に追従した微小タイミング差がそのまま「譜面グリッド外のtick」として保存されていた。

## 現行runtime経路

```text
index.html?v=grid-v29
  -> app.js
      -> transcribe.js           # 打音検出・楽器分類
      -> meter.js                # 小節/拍子
      -> rhythm-grid.js          # NEW: 格子選択、量子化、局所tempo map
      -> midi.js                 # quantized ticks + tempo meta-events
```

### 重要

`rhythm-grid.js` / `midi.js` はkick/snare等の楽器分類を変更しない。
変更対象はMIDI上のnote tickとtempo meta-eventだけ。

## rhythm-grid.js の仕様

1. 検出イベントを基準BPM上のbeat座標へ変換。
2. straight 8/16/32 と triplet 8/16 の周期集中度を比較。
3. triplet系はstraight系を明確に上回る場合だけ採用。
4. straight曲は16分を基本にする。
5. 16分位置から十分離れ、32分位置へ明確に近い打点だけ32分として残す。
6. 4beat間隔・±8beat窓でgrid phase driftを推定。
7. ノートはscore gridへsnap。
8. phase driftの微分を四分音符BPMへ変換し、tempo meta-eventとして出力。
9. BPMは基準BPMの±3%へ保守的にclamp。
10. MIDI tick 0 / 小節頭位相は動かさない。

## app.js の仕様

- `events`: 音源上のraw検出時刻。
- `midiEvents`: rhythm-grid + tempo mapを適用した書き出しMIDIと同じ再生時刻。
- プレビュー、タイムライン描画とも `midiEvents` を使用。
- したがって試聴とdownload MIDIの時刻経路が一致する。
- `globalThis.__drumscribeResult.rhythmGridInfo` に以下を保存:
  - subdivision
  - tempoMin / tempoMax / tempoMean
  - tempoEvents
  - straight16Share / straight32OnlyShare
  - previewMedianDifferenceMs / previewP95DifferenceMs

## 参照chart.midから確認した設計

| Song | tempo events | reference 16分格子一致 |
|---|---:|---:|
| diamondvirgin | 527 | 99.54% |
| nanairo | 419 | 100% |
| ray | 1 | 100% |

旧generated-meter-v23の16分格子一致:
- diamondvirgin: 4.03%
- nanairo: 0%
- ray: 0.50%

参照譜面は、ノートをグリッドへ置き、必要な演奏揺れをtempo mapで表現している。

## アップロード曲テスト

入力:
- `君は詩人になった [drums].wav`
- `君は詩人になった [drums]-drumscribe.mid`

旧MIDI:
- base BPM: 134.007839
- notes: 1,211
- tempo events: 1
- 16分格子完全一致: 3.80%

判定:
- straight 16 fit: 0.9673
- straight 32 fit: 0.8847
- triplet 8 fit: 0.4855
- triplet 16 fit: 0.6953
- 結論: straight 16

確認用再構成MIDI:
- `君は詩人になった [drums]-drumscribe-grid-v28.mid`
- 16分格子一致: 100%
- tempo events: 391
- BPM range: 133.744–134.434
- 元MIDI再生時刻との差:
  - median abs 2.81 ms
  - p95 abs 8.44 ms
  - max abs 50.00 ms

注意:
この確認用MIDIは「以前の生成MIDI」を再構成したもの。
最新runtimeでWAVからfresh transcriptionした結果ではない。

## GMD shuffle / swing 調査

GMD `beat` metadata 503件中、style名にshuffle/swing/tripletがあるものは21件。

- jazz: 11
- rock: 4
- blues: 4
- funk: 1
- neworleans: 1

現runtimeではgenre名だけでtripletにしない。
実打点のtriplet fitがstraight fitを明確に超えることが必要。
GMD genre/pattern priorはborderline時の弱い補助候補。

## GitHub変更

- `drumscribe/rhythm-grid.js`
- `drumscribe/midi.js`
- `drumscribe/app.js`
- `drumscribe/index.html`
- `drumscribe/experiments/results-grid-tempo-v28.json`
- `drumscribe/experiments/GRID_TEMPO_V28.md`

主なcommit:
- `42d95b5151bc1da2ca2c18d233b835e859dca4d5` mixed 16/32 grid
- `47e45458fcd60e113b23d55f156cc3f8935a5fd7` MIDI cache v29
- `947d8112f2467d20fa38b2ffad6045ad945c80d8` app preview/cache v29
- `bb24048169afa610713e9ac8a54b286913650605` index cache v29

## 未完了 / 次に行うこと

1. 最新GitHub PagesでアップロードWAVをfresh transcriptionする。
2. download MIDIをDAWまたはMIDI parserで確認:
   - note tickが16/32またはtriplet grid上か
   - tempo meta-event数
   - 音源との同期
3. diamondvirgin / nanairo / rayをfresh browser生成し直す。
4. chart.midとのpart別F1が非退行か確認する。
   - 量子化はclassを変えないが、±80ms照合結果はわずかに変わり得る。
5. shuffle / swing音源をheld-outで増やし、triplet判定閾値を校正する。
6. 問題があれば `rhythm-grid.js` だけを戻せる。transcribeの楽器分類ロジックには触れていない。

## 検証ファイル

- `drumscribe/experiments/GRID_TEMPO_V28.md`
- `drumscribe/experiments/results-grid-tempo-v28.json`
