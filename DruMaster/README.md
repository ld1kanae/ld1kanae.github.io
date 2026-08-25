# DruMaster

スマートフォン／PC向けブラウザ・ドラム音楽ゲームです。

GitHub Pages: <https://ld1kanae.github.io/DruMaster/>

## ディレクトリ

- `index.html` — 本番エントリ
- `preview.html` — UI／譜面プレビュー
- `css/` — 表示・レイアウト
- `js/` — ゲーム、音声、譜面、入力、判定
- `assets/` — ドラムセット画像・ゲーム内ドラム音源
- `songs/` — 曲ごとのMIDI／ステム
- `_archive-candidates/` — 現在の本番／Previewから読み込まれていない旧ファイル。削除候補だが、確認用に保持

## 主な調整箇所

### 曲設定
`js/song-manager.js`

曲ごとの以下の値をまとめています。

- `chart.pixelsPerQuarter` — 4分音符あたりの譜面移動px
- `playback.stemOffsetSec` — MP3ステムを何秒地点から再生するか
- `mix.base / vocals / drums` — 曲別ミックス
- MIDI／ステムのパス、サイズ、SHA-256

現在:

- なないろ: 80 px/♩、stem offset 0 ms
- Ray: 40 px/♩、stem offset 30 ms、offvocal 70% / vocals 60% / Guide Drums 70%

### ドラムセット表示

- `css/kit-layout.css` — ドラム画像・当たり判定の幾何配置
- `css/game-visual.css` — バスドラム画像、キック発光、HUD微調整
- `js/controls.js` — PCキー、スマホタップ、kit-stage管理

### スマートフォン

- `css/mobile-game.css` — 固定横長ゲーム画面と譜面領域
- `css/mobile-offset.css` — 全体位置の端末向け補正
- `js/mobile-lane-alignment.js` — スマホ譜面レーン名の中央揃え

端末の画面回転状態は判定せず、最初から横長の固定ステージとして描画します。

### 譜面・判定

- `js/chart-core.js` — 共通譜面描画・MIDIテンポ／拍子処理
- `js/chart-speed.js` — 曲別 `pixelsPerQuarter` の適用
- `js/game-chart.js` — 本番ゲームと共通描画エンジンの接続
- `js/judgement.js` — 判定文字／ゴール線発光の配置
- `css/judgement.css` — 判定エフェクトの見た目

### 音声

- `js/audio.js` — ステム／ゲーム内ドラムの読込と再生
- `js/song-playback.js` — 曲開始時の同期再生
- `js/hihat-choke.js` — Open HHのチョーク
- `js/manifest-fallback.js` — ゲーム内ドラム音源manifestの組込みフォールバック

### リザルト・モード

- `js/mode-ui.js` / `css/mode-ui.css` — Hidden Mode、PCマスター音量
- `js/result-screen.js` / `css/result-ui.css` — リザルトと曲別ランキング
- `css/hidden-mark.css` — Hidden Mode記録のブラインドマーク

## 保守方針

2026-08-26に `DruMuster/` から `DruMaster/` へ改名し、CSS／JSを用途別フォルダへ整理しました。見た目・操作感・判定幅・現在の音量／タイミング値は変更せず、パスと保守用設定の整理のみ行っています。
