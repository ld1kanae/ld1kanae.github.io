# DrumScribe synchronized reference data

完全同期した音声/MIDI対照データと、そのデータから得た検証成果物の一覧です。

これらは **prediction runtimeの入力ではなく、教師・検証専用** です。参照MIDIを採譜時に読むことは禁止し、生成後評価またはoffline学習にのみ使用します。

## Diamond Virgin

ユーザー提供の完全同期ペアを2026-09-23に直接解析しました。

### 元ファイルの識別情報

- WAV: `ダイヤモンドヴァージン_tempo-mapped_sync.wav`
  - 44.1 kHz / stereo / 264.863560 sec
  - bytes: `46,722,668`
  - SHA-256: `1afb2d93354d33f14fdf47ead02b771d84d0bd59d98053f04461771f48596443`
- MIDI: `ダイヤモンドヴァージン_tempo-mapped_sync.mid`
  - bytes: `29,853`
  - SHA-256: `44a4d08e43b2fdae95caed0b6c1f0389f7015abc06c2da048ac5c38f1fb05644`

### リポジトリ内に保存した検証成果物

- `results-diamondvirgin-sync-openhat-v47.json`
  - 音声/MIDIメタデータ
  - ノート数
  - open→open / open→closed / open→pedal分布
  - 5–18 kHz減衰統計
  - blocked-time CV結果
  - 元ファイルのサイズとSHA-256

重要な教師分布:

- GM42 Closed: 253
- GM44 Pedal: 4
- GM46 Open: 502
- Open→Open: 468
- Open→Closed: 29
- Open→Pedal: 4

Diamond Virginは、なないろ同期ペアに存在しなかった **連続Open（open→open）** の主要教師です。

## Kaiju

- WAV: `怪獣_tempo-mapped_sync.wav`
  - 44.1 kHz / stereo / 242.404490 sec
  - bytes: `42,760,888`
  - SHA-256: `e900dde8c874dd7ba54c9eba309c9e72e071ae84de14ae34e1db39622aeba372`
- MIDI: `怪獣_tempo-mapped_sync.mid`
  - bytes: `24,415`
  - SHA-256: `a765a9103abb0ab77ab6674de1f52a23a3b3df14164de5778e396c72c1288662`

教師分布:

- GM42 Closed: 572
- GM44 Pedal: 9
- GM46 Open: 22
- GM51 Ride: 431
- Open→Open: 6
- Open→Closed: 7
- Open→Pedal: 9

Kaijuは **Ride主体かつOpenが希少な曲** の対照です。曲内Open率が極端に低い場合の校正・Ride誤吸収防止に使います。

## Arukuaround

- WAV: `アルクアラウンド_tempo-mapped_sync.wav`
  - 44.1 kHz / stereo / 258.755533 sec
  - bytes: `45,645,212`
  - SHA-256: `83dc2d1ca0af3af6de093b55b56626433146062b8322ce171d5710f43cbea4ab`
- MIDI: `アルクアラウンド_tempo-mapped_sync.mid`
  - bytes: `19,822`
  - SHA-256: `3fcc1115bbe73c8d1e7219f458df3b22a1145b7597f441e34a1ed46768a840f8`

教師分布:

- GM42 Closed: 200
- GM44 Pedal: 91
- GM46 Open: 93
- GM51 Ride: 58
- Open→Open: 0
- Open→Closed: 2
- Open→Pedal: 91

Arukuaroundは **OpenをPedalで切る明確なchoke列** の主要教師です。

## Ray

- WAV: `Ray_tempo-mapped_sync.wav`
  - 44.1 kHz / stereo / 268.749728 sec
  - bytes: `47,408,188`
  - SHA-256: `ec87d768c61688cdd51c0d2a1e8cd74da4141b1a6e500c673ddccfc6dc3b7019`
- MIDI: `Ray_tempo-mapped_sync.mid`
  - bytes: `26,473`
  - SHA-256: `226c34c28ec9dd111b9fee4c4a24017466b3bf52af1bab83f137d44ef4195b45`

教師分布:

- GM42 Closed: 1,075
- GM44 Pedal: 312
- GM46 Open: 322
- Open→Open: 6
- Open→Closed: 199
- Open→Pedal: 116

Rayは **Closed主体かつOpen→Closed/Pedalが多い曲** の対照です。

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

## バイナリ保存について

現在利用しているGitHub接続では、大容量WAVや任意バイナリをローカル作業領域から完全一致を保証した状態で転送できません。破損したバックアップを残さないため、上記の新規WAV/MIDI本体はリポジトリへ保存していません。

別経路で追加する場合は、このREADMEのbytesとSHA-256が一致することを必ず確認してください。配置候補:

```text
drumscribe/experiments/reference-sync/diamondvirgin/
drumscribe/experiments/reference-sync/kaiju/
drumscribe/experiments/reference-sync/arcaround/
drumscribe/experiments/reference-sync/ray/
drumscribe/experiments/reference-sync/nanairo/
```

## Reproduction

同期ペア単体の基本解析:

```bash
python drumscribe/experiments/analyze_sync_hat_pair.py \
  pair.wav pair.mid \
  --out result.json
```

複数曲をsong-held-outで比較するv53:

```bash
python drumscribe/experiments/analyze_sync_hat_corpus_v53.py \
  --pair kaiju kaiju.wav kaiju.mid \
  --pair arcaround arcaround.wav arcaround.mid \
  --pair ray ray.wav ray.mid \
  --out results-sync-hat-corpus-v53.json
```

詳細:

- `../SYNC_HAT_CORPUS_V53.md`
- `../results-sync-hat-corpus-v53.json`

## Runtime adoption

2026-09-23時点のproductionは次の構成です。

- Open/Closed: `ride-selective60-decay-rescue`
- 局所減衰とopen-run救済
- Open音響確率が高いRide候補だけOpenへ丸める
- sequence repair: `inversion-guarded-rescue`

v53の新しいcontext/choke ExtraTreesは、参照hat onset上では強い順位付け性能を示しましたが、実ブラウザ候補へ適用した非退行確認が未完了です。productionにはまだ入れていません。
