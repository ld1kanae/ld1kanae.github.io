# DrumScribe synchronized reference data

完全同期した音声/MIDI対照データと、そのデータから抽出した再学習用成果物の一覧です。

これらは **prediction runtimeの入力ではなく、教師・検証専用** です。参照MIDIを採譜時に読むことは禁止し、生成後評価またはoffline学習にのみ使用します。

## Diamond Virgin

ユーザー提供の完全同期ペア:

- original WAV: `ダイヤモンドヴァージン_tempo-mapped_sync.wav`
  - 44.1 kHz / stereo / 264.863560 sec
  - bytes: `46,722,668`
  - SHA-256: `1afb2d93354d33f14fdf47ead02b771d84d0bd59d98053f04461771f48596443`
- exact synchronized MIDI backup:
  - `diamondvirgin/diamondvirgin_tempo-mapped_sync.mid`
  - bytes: `29,853`
  - SHA-256: `44a4d08e43b2fdae95caed0b6c1f0389f7015abc06c2da048ac5c38f1fb05644`
- acoustic validation result:
  - `results-diamondvirgin-sync-openhat-v47.json`
- per-hit teacher features:
  - `diamondvirgin-sync-hat-features-v47.csv.gz`
  - CSV columns include timestamp, MIDI articulation, velocity, next articulation, gap, four high-band decay windows, and next-hit persistence/choke features.

重要な教師分布:

- GM42 Closed: 253
- GM44 Pedal: 4
- GM46 Open: 502
- Open→Open: 468
- Open→Closed: 29
- Open→Pedal: 4

Diamond Virginは、なないろ同期ペアに存在しなかった **連続Open（open→open）** の主要教師です。

WAV本体は現在のGitHub接続から大容量バイナリとして直接コミットできないため、MIDI、完全な打点特徴、検証結果、WAVのサイズ・SHA-256を保存しています。元WAVを別経路でリポジトリへ追加した場合は、このREADMEのWAVパスを更新してください。

## Nanairo

既存の完全同期ペア:

- original WAV: `なないろ_tempo-mapped_sync.wav`
  - SHA-256: `d07eefee87cb9a78518cb856228ce3e2032c96c226184bca2ff83af54c2baf50`
- original MIDI: `なないろ_tempo-mapped_sync.mid`
  - SHA-256: `ab4a84377bfd678192040fbb00e17face55cf6aed5528a4699bf9ffa47b898a0`
- validation result:
  - `../results-nanairo-sync-openhat-v40.json`

教師分布:

- GM42 Closed: 823
- GM44 Pedal: 260
- GM46 Open: 240
- Open→Open: 0
- Open→Closed: 154
- Open→Pedal: 86

Nanairoは **open→closed / pedal choke側** の教師として使用します。open-only runの教師には使用しません。

## Reproduction

同期ペア単体の基本解析:

```bash
python drumscribe/experiments/analyze_sync_hat_pair.py \
  pair.wav pair.mid \
  --out result.json
```

Diamond Virgin v47では追加で、現Openから次のhat articulationがOpen継続かClosed/Pedal chokeかを、次打前後の5–18 kHz tailでblocked-time CV評価しています。

## Runtime adoption

2026-09-23時点のproduction既定は `ride-open-decay-rescue` です。

- 局所減衰による42/46判定
- open→open runの保守的救済
- RideをOpen HHへ丸める
- A/A'による42/46再判定は検証で悪化したため不採用

詳細:

- `../results-openhat-combined-v44.json`
- `../OPENHAT_DEFAULT_VS_COMBINED_V46.md`
