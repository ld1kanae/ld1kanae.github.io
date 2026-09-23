# DrumScribe Waveform Review Workflow

更新: 2026-09-23

## 目的

通常の DrumScribe プレビューに、Timing Correction 系と同じ考え方の拡大・縮小・横移動を追加し、別ページで時間範囲レビューを作れるようにした。

この変更は UI / preview layer の変更であり、`transcribe.js`、ADTOF、K/S/T分類、`rhythm-grid.js`、MIDI export の採譜ロジック自体は変更していない。

## 現行ページ

- 通常採譜: `drumscribe/index.html`
- 範囲レビュー: `drumscribe/feedback.html`
- 研究候補比較: `drumscribe/review.html`（別用途。混同しない）

## 波形 viewport

共通実装:

- `drumscribe/timeline-view.js`
- `drumscribe/app.js` から利用

操作:

- 拡大率 slider
- 表示位置 slider
- 「全体表示」
- 波形上ホイール: 前後移動
- Ctrl/Cmd + ホイール: マウスポインタ位置をanchorに拡大・縮小
- 再生中にplayheadがviewport外へ出た場合は自動追従

参照した DruMaster 実装:

- `DruMaster/song-sync-editor-v2.html`
- `DruMaster/js/song-sync-history.js`

Timing Correction側の `pxPerSec / viewStart` 構造と、wheel navigation / Ctrl(Cmd)+wheel zoom の挙動を DrumScribe のcanvasへ合わせて移植した。

## 範囲レビュー

実装:

- `drumscribe/feedback.html`
- `drumscribe/feedback.js`

手順:

1. 音源を選択して通常どおり自動採譜する。
2. 波形上をドラッグし、問題がある時間範囲を選ぶ。
3. 分類とレビュー文を入力する。
4. 複数レビューを追加する。
5. 「AI修正依頼をコピー」または「レビューJSONを書き出す」を使う。

レビューはブラウザの `localStorage` に音源ファイル名＋duration単位で保存する。

レビュー編集履歴は5段階:

- Ctrl/Cmd + Z: undo
- Ctrl/Cmd + Y: redo
- Ctrl/Cmd + Shift + Z: redo

これは Timing Correction の履歴ショートカットに合わせた。

## AIへ渡すデータ

`feedback.js` は `drumscribe-review-v1` schema を生成する。

主な項目:

- source file name
- exampleId（検証用楽曲の場合）
- duration
- BPM / time signature / barPhaseSec
- rhythm-grid subdivision
- tempo map range / event count
- review startSec / endSec
- category
- comment

「AI修正依頼をコピー」は、人間向け指示文と machine-readable JSON を一緒に生成する。

任意のローカル音源はこのページから外部へ送信されないため、別チャットのAIに実音源そのものを確認させる場合は、その音源ファイルも別途添付する必要がある。

## app.js のレビュー連携API

`globalThis.DrumScribeTimeline` を公開する。

主なAPI:

- `seek(sec)`
- `play()`
- `pause()`
- `getCurrentTime()`
- `getDuration()`
- `clientXToTime(x)`
- `setSelection(start,end)`
- `clearSelection()`
- `focusRange(start,end)`
- `getAnalysis()`

イベント:

- `drumscribe:file-selected`
- `drumscribe:analysis-complete`
- `drumscribe:timeline-ready`

レビューUIはこのAPIだけを通して通常previewと連携する。

## 注意

- `feedback.html` でも採譜処理は `app.js` と同じ。レビュー用に別の採譜結果を作らない。
- 通常ページではcanvas clickがseek。
- レビューページではcanvas dragがrange selection、短いclickはseek。
- wheel操作は両ページ共通。
- `review.html` は研究候補比較UIであり、今回のユーザーレビュー収集ページではない。
