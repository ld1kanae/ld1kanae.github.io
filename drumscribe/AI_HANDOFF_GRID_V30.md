# DrumScribe AI Handoff — Grid / Tempo v30

最終更新: 2026-09-23

## 今回の結論

ユーザー要求:
- 通常のドラムノートは8/16/32分へ量子化。
- 音源との同期を保つ必要がある場合、ノートをグリッド外へ残すのではなくBPM/tempo map側を動かす。
- shuffle / swing / tripletはstraight grid強制の対象外。
- GMDジャンル/パターン解析はtriplet判定の補助候補。

現在の `rhythm-grid.js` は以下で実装済み。

1. straight / triplet grid適合度を比較。
2. straightでは16分を原則とする。
3. 16分から0.10 beat超離れ、32分点から0.035 beat以内の場合のみ32分を保持。
4. 局所grid phase driftを推定。
5. note tickは譜面gridへsnap。
6. driftはMIDI tempo meta-eventへ変換。
7. BPMは基準BPMの±3%へclamp。
8. kick/snare等のクラス判定は変更しない。

## 5曲横断テスト

テスト方法:
既存の実ブラウザ生成 `generated-meter-v23` のイベント時刻/ノートを復元し、現行 `rhythm-grid.js` 相当の書き出し層だけを再適用。その後 `chart.mid` と±80msで再採点。

これは今回変更したgrid/tempo export層を隔離した非退行テストで、fresh acoustic transcriptionではない。

| Song | F1 before | F1 after | straight 16 | 32nd only |
|---|---:|---:|---:|---:|
| arcaround | 0.68763 | 0.68763 | 100.00% | 0.00% |
| diamondvirgin | 0.80253 | 0.80253 | 99.63% | 0.37% |
| kaiju | 0.77664 | 0.77664 | 99.92% | 0.08% |
| nanairo | 0.87484 | 0.87484 | 99.89% | 0.11% |
| ray | 0.89229 | 0.89229 | 97.16% | 2.84% |

結果:
- 5/5で総合F1非退行。
- 平均16分格子率 ≈ 99.20%。
- 0.08 beatへ緩める候補も試したが、現行0.10/0.035条件で既に非退行なので変更しなかった。
- 0.08候補は arcaround snare F1 0.59681→0.60137 の微増があったため、将来の候補として残せる。

生データ:
- `drumscribe/experiments/results-grid-tempo-five-v30.json`
- `drumscribe/VALIDATION.md`

## ユーザー提供「君は詩人になった」テスト

入力:
- WAV: ユーザー添付
- 旧DrumScribe MIDI: ユーザー添付

現行runtime相当のgrid/tempo exportへ再投入:
- base BPM 134.007839
- 1,211 notes
- straight判定
- straight16 fit 0.96726
- straight32 fit 0.88475
- triplet8 fit 0.48549
- triplet16 fit 0.69534
- 16分: 99.9174%
- 32分のみ: 0.0826%
- tempo range: 133.7438–134.4343 BPM
- 元MIDI時刻との差: median 2.81ms / p95 8.35ms / max 38.79ms

簡易audio onset sanity check:
- 共通offsetをrobust推定後、
- old MIDI: match share 74.48%, median 3.63ms, p95 9.30ms
- grid MIDI: match share 74.48%, median 3.09ms, p95 8.93ms
- generic energy-flux onset detectorなのでgold採譜ではない。同期悪化がないことのsanity checkのみ。

ローカル成果物:
- `君は詩人になった [drums]-drumscribe-grid-v30.mid`
- `君は詩人になった-grid-v30-analysis.json`

## 制約

実行環境から `https://ld1kanae.github.io/drumscribe/` へのブラウザアクセスは `ERR_BLOCKED_BY_ADMINISTRATOR` となるため、公開GitHub Pages上でのfresh acoustic rerunはこのセッションでは実施できなかった。

ただし今回変更対象はtranscription classifierではなくgrid/tempo export層なので、既存の実ブラウザ生成イベントを再投入する方法で変更層自体は直接検証できている。

## 次に優先すること

1. ユーザー側またはブラウザアクセス可能環境で最新ページから同じWAVをfresh生成し、v30 MIDIと聴感/DAW gridを比較。
2. shuffle / swing実音源を複数追加し、triplet判定のheld-out検証。
3. 32分escape条件0.10/0.035と0.08候補を、32分フィルを含む実曲で比較。
4. grid/tempo変更では楽器クラスを変えないことを維持。

## Commits

- results: 2bd36422604f77af41580714cd6860094652c8a2
- validation: 5d06d64253b3e4ed3eb5b9a2d4d1dcaa6b4fe309
