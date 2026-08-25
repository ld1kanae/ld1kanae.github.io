# DruMaster2

新規実装のWebドラムリズムゲームです。旧DruMusterのコード・データ・UIは参照していません。

## 現在の楽曲
- なないろ
- 譜面は提供された最新版 `なないろ（ゲーム用）(1).mid` から生成した `chart.js` を使用
- MIDI channel 10 の 36 / 38 / 42 / 44 / 46 / 49 を使用
- Kick (36) と Pedal Hi-Hat (44) はAUTO

## 音源配置先
GitHub Pagesで自動読込する場合は以下へ配置します。

- `assets/audio/nanairo-offvocal.wav`
- `assets/audio/nanairo-vocals.wav`
- `assets/audio/nanairo-guide-drums.wav`
- `assets/audio/drumsound2.wav`

未配置でも、Settingsから端末内のWAVを一時読み込みして動作確認できます。

## 操作
PC:
- F: Snare
- J: Closed Hi-Hat
- K: Open Hi-Hat
- L: Crash
- Space: Play/Pause

スマートフォン:
- 横画面
- ドラム上に透明の広いタップ判定領域を配置
- 判定領域自体は描画しない

## UI方針
- ドラムセットを画面下側に大きく描画
- シンバルは大幅な見切れを許容
- 譜面をドラムセット上に重ねる
- 操作しないKick、Pedal、未使用Tom/Ride等は暗所に沈める
- 右→左の4レーン譜面
- Kick/Pedal HHは淡色のAUTOノーツ

## 打音
`drumsound2.wav` はBPM60、MIDI 35〜81を約2秒間隔で収録したスプライトとして扱います。各発音は独立Sourceで重ね、Open Hi-HatのみClosed/Pedal Hi-Hatでチョークします。音源未配置時にはWeb Audioの簡易合成音へフォールバックします。
