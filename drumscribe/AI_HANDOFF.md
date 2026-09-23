# DrumScribe AI Handoff

> **AI / 別チャット向けの最小コンテキスト。まずこのファイルだけ読む。**
>
> 内容確認日: 2026-09-23。**commit SHAを固定の正解とせず、毎回「1. 最初に現行を確定する手順」で `main` HEADから再判定する。**
>
> 詳細な試行錯誤は `VALIDATION.md` にあるが、最初から全文を読まないこと。必要な節だけ参照する。

## 0. 目的と優先順位

DrumScribe は、**ドラム単独音源**（WAV / MP3 等）をブラウザ内で解析し、GM percussion channel 10 の MIDI を作る試作。

現在の優先順位は **kick / snare / tom > hi-hat / cymbal**。金物の改善のために kick/snare/tom を悪化させない。

予測時に `chart.mid` を読んではいけない。参照MIDIは**生成後の評価だけ**に使う。

### GMD / E-GMD の実験利用方針

このプロジェクトでは、**GMD / E-GMD 関連のMIDI・音声・学習済み補助モデル・そこから作った集計priorを、採譜精度改善の検証、学習、比較実験、ablation、候補生成に自由に用いてよい。**
必要なら既存のGMD/E-GMD資産を組み合わせたり、新しい派生モデルを作って `experiments/` で比較してよい。

ただし、外部データそのものをリポジトリへ再配布・複製する場合は元データ/モデルのライセンス条件を確認すること。**「検証に自由に使ってよい」というプロジェクト方針と、第三者データの再配布条件は別問題**として扱う。

---

## 1. 最初に「現行」を確定する手順

このプロジェクトには、現行コード・過去の候補・不採用実験・比較用MIDI・検証ブランチ由来URLが同居している。
**ファイルが存在するだけでは現行採用とは判断しない。**

現行判定は次の順序で行う。

### 1-1. `main` の最新状態を確認する

まず `main` のHEADと、`drumscribe/` に対する直近commitを見る。

確認例:

```text
git log -n 20 -- drumscribe/
```

またはGitHub API / connectorで
`commits?path=drumscribe&sha=main`
を確認する。

このファイルに書かれたcommitより新しい変更があれば、以降の手順でruntimeを再確認する。

### 1-2. 実ブラウザのentry pointを確認する

`index.html` の末尾を見る。

現時点では:

```html
<script src="vendor/ort/ort.wasm.min.js?v=1.30.0"></script>
<script type="module" src="app.js?v=20260923-egmd-kst-v4"></script>
```

cache-busting文字列は「変更時期の手掛かり」であり、仕様のsource of truthではない。
実際の仕様は読み込まれるJSを追う。

### 1-3. runtime import chainを追う

現時点の主経路:

```text
index.html
  -> app.js
      -> transcribe.js
          -> adtof.js
              -> adtof-worker.js
          -> hat-forest.js
          -> fft-worker.js
      -> meter.js
      -> rhythm-grid.js
      -> midi.js
```

**このimport chain上にない実験コードは、原則runtimeではない。**

### 1-4. runtimeが実際にfetchしているmodel/dataだけを採用資産とみなす

`import`, `fetch(...)`, `new URL(...)` を検索する。

現時点でruntimeから直接参照される主要資産:
- `transcribe.js` -> `templates-v2.json`
- `transcribe.js` -> `models/gmd-metal-prior.json`
- `adtof.js` -> `models/adtof-model.json`
- `adtof.js` -> `models/adtof-filterbank.f32`
- `adtof.js` -> `models/adtof-frame-rnn.onnx`
- `adtof.js` -> `models/egmd-kst-reclassifier-v4.json`（snare低信頼candidateの第二判定）
- `hat-forest.js` -> `models/hat-extra-trees-v11.json`
- `app.js` -> 検証example用 `experiments/beatthis-v17|v18/*.beats`
- `app.js` -> `../DruMaster/assets/drums/*.wav`

`models/` に置かれていてもruntimeから参照されないものは、実験資産または将来候補として扱う。

### 1-5. 次のファイルを「現行仕様そのもの」と誤認しない

- `VALIDATION.md`: 全履歴。採用・不採用・撤回が混在する。
- `review-manifest.json`: 聴取比較用候補一覧。過去branch URLも含む。
- `experiments/generated*/`: 各時点の生成物。
- `experiments/results-*.json`: 各実験の固定結果。
- `models/` の未参照model: 現行runtimeとは限らない。
- `drumscribe-v2-eval` 等のraw GitHub URL: 比較用ブランチ資産であり、`main` runtimeとは限らない。

### 1-6. README / VALIDATION / runtimeが食い違う場合

優先順位:

1. **`main` の実runtime code**
2. runtime codeが参照するmodel/config
3. そのruntimeから生成した最新の再現可能なbrowser評価結果
4. READMEの要約
5. VALIDATIONの過去節
6. review-manifestの比較候補

READMEやこのhandoffはナビゲーション用。コード更新後に文書更新が遅れる可能性がある。

### 1-7. 現行確認後にこのファイルを更新する

大きな採用変更をしたら最低限:
- 「確認基準」のcommit/date
- runtime import/fetch chain
- 現行採譜ロジック
- 現行5曲score
- 「採用済み / 未採用」の境界

を更新する。

---

## 2. 1分で分かる実行フロー

```text
index.html
  -> app.js
      -> transcribe.js
          -> 11.025 kHz spectral analysis / tempo / beat / bar-head cues
          -> templates-v2.json (legacy/fallback + auxiliary timbre evidence)
          -> adtof.js
              -> adtof-worker.js
              -> models/adtof-filterbank.f32
              -> models/adtof-frame-rnn.onnx
              -> models/egmd-kst-reclassifier-v4.json
              -> ONNX Runtime Web/WASM
          -> kick/snare/tom priority post-processing
          -> hat / pedal-hat / crash / ride post-processing
          -> hat-forest.js
              -> models/hat-extra-trees-v11.json
          -> open-hat.js
              -> models/open-hat-extra-trees-v2.json
              -> models/open-hat-overlay-extra-trees-v1.json
      -> meter.js (example songs only: variable-meter inference path)
      -> rhythm-grid.js (score-grid quantization + local tempo map)
      -> midi.js
      -> preview playback using ../DruMaster/assets/drums/{note}.wav
```

---

## 3. 現行runtimeの責務

| File | 現在の役割 |
|---|---|
| `index.html` | 音源選択、検証曲選択、BPM補正、採譜、MIDI download、原音/MIDI mixer UI |
| `app.js` | AudioContext、`transcribe()` 呼び出し、試聴、solo/mute/volume/seek、MIDI生成 |
| `transcribe.js` | 採譜の中心。低レートspectral補助解析、BPM/beat/bar head、ADTOF統合、K/S/T後処理、metal分類 |
| `adtof.js` | 44.1 kHz / 100 fps ADTOF系 ONNX 推論。kick/snare/tom/hat/cymbal候補を返す |
| `adtof-worker.js` | 2048 FFT + 84-bin filterbank frontend をWeb Workerで計算 |
| `fft-worker.js` | 11.025 kHz側の 1024 FFT を並列計算 |
| `hat-forest.js` | 44.1 kHz ExtraTreesでhi-hat過検出を削る最終フィルタ |
| `open-hat.js` | 残ったhatを42/46へ分類し、2-hand/repetition guard下で欠落Openを保守的に追加 |
| `meter.js` | 外部beat/downbeat補助を使った 4/4・3/4 の小節列推定 |
| `rhythm-grid.js` | straight/triplet格子判定、16分基本＋限定32分、局所phase drift→tempo map、note tick量子化 |
| `midi.js` | SMF type 0 / PPQ 480。quantized note tick、複数tempo meta-event、time signature、pickup/bar alignment、drum note出力 |
| `review.html/js/css` | 候補MIDIを音源と同期試聴する比較UI。研究候補レビュー用 |
| `review-manifest.json` | レビューUIの候補一覧。**履歴候補を含み、現行runtime manifestではない** |
| `VALIDATION.md` | 全実験ログ。**履歴であり、書かれている全候補が現行採用とは限らない** |
| `experiments/` | Python/Node評価、生成MIDI、metric JSON、meter/GMD研究データ |
| `models/` | 現行モデル + 実験資産 |
| `vendor/ort/` | ONNX Runtime Web 1.30.0 のローカル配布物 |

---

## 4. 現行採譜の重要ロジック

### A. ADTOF

`adtof.js`:
- sample rate 44.1 kHz
- hop 441 = 100 fps
- FFT 2048
- 84 features
- classes: kick / snare / tom / hat / cymbal
- base thresholds: 0.22 / 0.24 / 0.32 / 0.22 / 0.30
- production threshold scale: 1.15
- backend: ONNX Runtime Web / WASM
- 長音源は 3000 core frames + 200 overlap frames で分割
- snareだけ通常出力とは別に scale 0.50 の低閾値streamも返す。これは直接出力しない。
- さらにE-GMD v3再分類器用に scale 0.20 のsnare candidateを作り、曲内95 percentile正規化したADTOF activation/residual/local context/class-ratioから確率を返す。これも直接出力しない。

### B. kick / snare / tom優先補正

`transcribe.js` で ADTOF 後に実施。

**snare rescue**
- song-level gateが成立した曲だけ
- 既存の手書き低閾値経路:
  - 既存snareから35 ms以内を除外
  - kickから40 ms以内
  - low activation >= 0.12
  - low snare activation >= 0.25 × kick activation
  - 同じ16分slotの反復支持 >= 2
- E-GMD v4第二判定経路:
  - E-GMD snare probability >= 0.67
  - 既存snareから35 ms以内を除外
  - kickから35 ms以内
  - 同じ16分slotで反復支持 >= 1
  - E-GMD側では旧absolute activation floorを重ねない（v4モデル入力に正規化activation/residual/class-ratioを含む）
- E-GMD modelからkick/tomは追加しない
- 現5曲では主に arcaround の欠落snare救済として選定

**tom bleed veto**
- kickから30 ms以内
- 弱いtomのみ
- 45–240 ms以内に別tomがあるtom runは残す
- confidence >= 1.45 は残す
- 目的はkick bleed由来の「弱く孤立したtom」だけを削ること

kick/snareを相互排他にはしない。実参照ではkick+snare同時打撃が普通に存在する。

### C. hi-hat / pedal / cymbal

1. 低解像度template証拠 + ADTOF hatを使った collision/periodicity filter
2. `models/gmd-metal-prior.json` + 高域decayで一部hatを pedal_hat に変換
3. cymbalはADTOF候補をbar-head/periodicity/raw spectral evidenceで crash/ride に絞る
4. snare/tom/hat/crash/ride は35 ms cluster内で最大2打（2 hands）。kick/pedal_hatは除外
5. 最後に `hat-forest.js` の ExtraTrees でhatをさらに削る
6. `open-hat.js` の GMD128学習モデルで残ったhatを42/46へ分類。threshold 0.575、曖昧ならClosed 42。
7. `open-hat-overlay-extra-trees-v1.json` は既存kick/snare/metalを置換せず、repeat evidence + 2-hand制約を満たす高信頼欠落OpenだけGM46として追加する。

Open HH production:
- base articulation: `open-hat-extra-trees-v2.json`
- external augmentation: GMD 128 open + 128 closed
- fixed threshold: 0.575
- missing-candidate rescue: `repeat_gate_2hands`
- held-out development estimate: Open TP423 / Pred646 / Ref1179, P 0.6548 / R 0.3588 / F1 0.4636
- Closed F1 0.8065
- kick/snare/tomはOpen rescueで削除・置換しない

出力note:
- kick 36
- snare 38
- closed hat 42
- open hat 46
- pedal hat 44
- tom 45
- crash 49
- ride 51

---

## 5. BPM / 小節 / 可変拍子

### BPM / bar head

`transcribe.js` が音声だけから推定。
- low/mid spectral peak recurrence
- kick/snare event recurrence
- phase coherence
- robust grid fit
- kick/snare role + low-band evidenceから4候補のbar headを選ぶ

### 可変拍子

`app.js` では **arcaround / diamondvirgin / kaiju の検証用exampleだけ**、
`experiments/beatthis-v17|v18/*-fullmix.beats` を読み `meter.js` に渡す。

これは `chart.mid` ではなく fullmix audio 由来のBeatThis beat labels。

**任意アップロード曲は現在この外部beat label経路を通らず、基本4/4。**
したがって5曲のmeter精度を「未知曲の可変拍子対応精度」と解釈しない。

current meter v25 validation:
- mean song bar error: 0.02084 beat
- mean bar recall @0.25 beat: 0.99891
- mean signature accuracy @0.25 beat: 0.99891
- arcaroundの参照3/4 20小節は20/20一致
- 残課題としてkaijuに最大約0.251 beatの1小節誤差

GMDの一般リズムpriorで現行bar selectorを置換する案は悪化したため撤回。
v26では diamondvirgin / nanairo / ray だけで再検証し、GMDは「beat 1 vs beat 3」の長期補助証拠として有望だが、**runtime overrideは未実装**。

---

## 6. 現行の5曲スコア

`drums.mp3` -> 実Chromium採譜 -> `chart.mid` と ±80 ms 1対1照合。

| Part | TP / Pred / Ref | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| kick | 2636 / 2765 / 2712 | 0.9533 | 0.9720 | 0.9626 |
| snare | 1301 / 1421 / 1470 | 0.9156 | 0.8850 | 0.9000 |
| tom | 69 / 84 / 92 | 0.8214 | 0.7500 | 0.7841 |

all classes（Open HH overlayを含む最新main実Chromium）:
- TP 7492 / Pred 8225 / Ref 10086
- Precision 約0.911
- Recall 約0.743
- F1 約0.818

Open/Closed articulationのmain train-all動作確認:
- Closed: TP2357 / Pred2667 / Ref2923, P 0.8838 / R 0.8064 / F1 0.8433
- Open: TP571 / Pred738 / Ref1179, P 0.7737 / R 0.4843 / F1 0.5957
- macro F1 0.7195
- これは5曲を含むtrain-allモデルの動作確認値。未知曲相当の判断には上記held-out Open F1 0.4636を優先する。

注意:
- 同じ5曲を見ながら改善してきたので未知曲保証ではない。
- tomはRef 92と母数が小さい。
- snare rescueの未知曲一般化は未確認。

---

## 7. 評価データと時刻合わせ

検証元:
`../DruMaster/songs/<song>/`
- `drums.mp3`
- `chart.mid`
- `song.json`

評価時のaudio/MIDI local-time shift:

```text
song.json.playback.stemOffsetSec + midiOffsetSec (存在時)
```

重要:
- このshiftは評価で使う。
- `chart.mid` は予測生成には使わない。
- diagnostic alignment sweep を本スコアに混ぜない。

主要評価コード:
- `experiments/evaluate.py`: dependency-light baseline / spectral candidate detector / MIDI parser / ±80 ms scoring
- `experiments/separated.py`: spectrogram separation / onset系比較
- `experiments/results-*.json`: 実験結果の固定スナップショット
- `experiments/generated*/`: 生成MIDI、meter付MIDIなど

---

## 8. GMD / E-GMDモデルと実験資産の場所

GMD系は用途ごとに置き場所が分かれている。**「GMDモデルは全部 `models/`」ではない。**

### 8-1. production runtimeが直接参照するGMD / E-GMD

- `models/egmd-kst-reclassifier-v4.json`
  - E-GMD audio+MIDIから学習した低信頼K/S/T再分類器。
  - 現runtimeでは **snare第二判定だけproduction採用**。
  - `adtof.js` が直接fetchする。
  - license: `models/egmd-kst-reclassifier-LICENSE.txt`
- `models/gmd-metal-prior.json`
  - GMD train由来のsymbolic metal prior。
  - 現runtimeでは hat -> pedal_hat 判定の補助に使用。
  - `transcribe.js` が直接fetchする。
  - license: `models/gmd-metal-prior-LICENSE.txt`

ADTOF本体やhat filterもproduction modelだがGMD系ではない:
- `models/adtof-model.json`
- `models/adtof-filterbank.f32`
- `models/adtof-frame-rnn.onnx`
- `models/hat-extra-trees-v11.json`

### 8-2. 小節頭 / 一般リズムGMD実験は `experiments/`

- `experiments/gmd-raw-bar-model-v26.json`
  - raw GMD MIDIから作ったbar/downbeat研究用モデル。
  - 現runtimeのbar selectorは置換していない。
- `experiments/results-gmd-simple3-v26.json`
  - diamondvirgin / nanairo / ray の3曲限定GMD検証結果。
- `experiments/gmd-pattern-bagging-v27/`
  - GMD groove patternをgenre/pattern mixture・bagging方向で再検証する現在の研究資産。
  - `batch1.json`, `batch2.json`, `batch3.json` 等。
  - **research artifactであり、現時点ではproduction runtimeから参照されない。**

### 8-3. E-GMD K/S/T学習・転移評価コードも `experiments/`

- `experiments/train_egmd_kst_reclassifier.py`
- `experiments/train_egmd_kst_reclassifier_v2.py`
- `experiments/train_egmd_kst_reclassifier_v3.py`
- `experiments/train_egmd_kst_reclassifier_v4.py`
- `experiments/benchmark_egmd_kst_transfer.py`
- `experiments/benchmark_egmd_kst_transfer_v2.py`
- `experiments/benchmark_egmd_kst_transfer_v3.py`
- `experiments/benchmark_egmd_kst_transfer_v4.py`
- `experiments/results-egmd-kst-reclassifier-v1.json`
- `experiments/results-egmd-kst-reclassifier-v2.json`
- `experiments/results-egmd-kst-reclassifier-v3.json`
- `experiments/results-egmd-kst-reclassifier-v4.json`
- `experiments/results-egmd-kst-transfer-v1.json`
- `experiments/results-egmd-kst-transfer-v2.json`
- `experiments/results-egmd-kst-transfer-v3.json`
- `experiments/results-egmd-kst-transfer-v4.json`

### 8-4. 旧GMD metal実験モデル（現runtime未参照）

- `models/gmd-adtof-metal-logreg.json`
- `models/gmd-metal-acoustic-logreg.json`
- `models/gmd-metal-repetition-prior.json`
- `models/gmd-metal-style-prior.json`

これらは削除対象という意味ではない。**現行採用と断定しない**という意味。

### 8-5. 古い履歴記述への注意

`VALIDATION.md` の過去節には `drumscribe/models/gmd-kst-prior.json` へ集計priorを保存したという記述があるが、**現在の `main` treeではそのファイルは存在しない**。
現在のGMD/E-GMD資産の場所を知りたい場合は、この節よりも必ず `main` treeとruntimeのfetch先を優先する。

### 8-6. GMD / E-GMDは検証に自由に使ってよい

このプロジェクトではGMD / E-GMD関連資産を、**新しい採譜アルゴリズムの仮説検証、学習、再分類器、prior、bar/downbeat推定、候補順位付け、ablation、held-out比較に自由に使用してよい**。
既存のproductionモデルを壊さない限り、`experiments/` に新しい派生モデル・集計・結果を追加して比較してよい。

ただし外部データの再配布・同梱は元ライセンス条件を確認すること。元MIDI/音声を保存せず、必要な集計値・学習済み軽量model・評価結果だけをrepoへ置く運用も可。


---

## 9. 直近の重要な検証判断

### kick/snare/tom production補正

`VALIDATION.md` の:
`2026-09-23: kick / snare / tom 優先のproduction補正`

採用:
- layered low-threshold snare rescue
- weak isolated kick/tom veto

### GMD / E-GMD KST実験

`VALIDATION.md` の:
`2026-09-23: GMD / E-GMD を kick・snare・tom 改善へ試験利用`

結論:
- GMD symbolic priorを現行低閾値snare rescueへ直結するruntime変更は効果0で撤回済み
- その後E-GMD audio+MIDIで低信頼K/S/T候補再分類器をv1→v4まで実装
- v1は負例不足でtomが暴発し不採用
- v2はhard negativeで安全化したがproduction追加0
- v3はclip normalization + sequence/kit-held-out外部校正でsnare第二判定をproduction採用
- v4は8 train kit / 5 held-out kitへ増量し、3学習仮説を比較
- snareは意外にも targeted weighting ではなく **単純データ増量(scale)** がheld-out最良: P 0.950166 / R 0.858859 / F1 0.902208、threshold 0.67
- tomは targeted weighted がheld-out最良: P 0.956897 / R 0.304110 / F1 0.461538。ただし5曲production vetoは変更0なのでruntime tomは現行維持
- **v4 snare第二判定だけproduction採用**
- main実Chromium: snare **1301 / 1421 / 1470**, F1 **0.900035**。kick F1 0.962571 / tom F1 0.784091 は不変
- E-GMDからkick/tomを追加する処理は不採用
- tomについては「kick+tomを一般論として抑制しすぎない」ことが重要

### GMD pattern bagging v27

参照:
- `experiments/gmd-pattern-bagging-v27/`

位置づけ:
- raw GMD groove patternをgenre/pattern mixture / bagging方向で増量検証している研究系列
- batch JSONは `experiments/` 配下
- **現時点ではruntime未採用**
- runtimeへ入れる場合は必ず現行bar selectorとの非退行比較を先に行う

### meter / GMD bar prior

参照:
- `experiments/results-meter-fresh-v25.json`
- `experiments/results-gmd-simple3-v26.json`
- `experiments/gmd-raw-bar-model-v26.json`

結論:
- current selector維持
- GMDを4択selectorの置換にはしない
- long-windowの beat-1 vs beat-3 補助証拠として将来候補
- 現時点でruntime overrideなし

---

## 10. UI / Preview

`app.js`:
- user audio upload
- example 5曲
- optional BPM override
- original audio + generated MIDI simultaneous preview
- independent volume
- solo / mute
- seek
- MIDI playback offset correction
- MIDI download

MIDI preview音源:
`../DruMaster/assets/drums/{36,38,42,44,45,46,49,51}.wav`

---

## 11. MIDI export

`rhythm-grid.js`:
- straight / triplet grid適合度を比較
- straightは16分を基本とし、16分から0.10 beat超かつ32分点から0.035 beat以内の打点だけ32分保持
- note startはscore gridへsnap
- 局所grid phase driftをtempo mapへ変換
- BPMは基準BPM±3%へclamp

`midi.js`:
- Standard MIDI File type 0
- channel 10 percussion
- PPQ 480
- quantized note tick
- 複数のtempo meta event
- time signature meta event
- variable meter changesをbar boundaryへ書く
- detected bar phaseをMIDI measure boundaryへalign
- downbeatより前のnoteはpickup measureとしてwhole-bar pad
- note lengthは約70 ms

`app.js` はraw `events` を保持したまま、同じ `rhythmGrid.eventTicks` と `timeForScore()` から `midiEvents` を作る。
プレビュー/タイムラインは `midiEvents`、download MIDIも同じ `rhythmGrid` を使うため、previewとexportのtiming経路は一致する。

---

## 12. 他AIが作業を再開するときの最小読書順

**通常の採譜改善なら:**
1. この `AI_HANDOFF.md`
2. `transcribe.js` の対象箇所
3. `adtof.js` または `hat-forest.js` など対象module
4. `VALIDATION.md` の関連する最新節だけ
5. 該当する `experiments/results-*.json`

**小節/BPMなら:**
1. このファイル
2. `transcribe.js` の tempo/bar functions
3. `meter.js`
4. `results-meter-fresh-v25.json`
5. `results-gmd-simple3-v26.json`

**UI/MIDIなら:**
1. このファイル
2. `index.html`
3. `app.js`
4. `midi.js`

`VALIDATION.md` 1750+ linesを最初から全部読む必要は通常ない。

---

## 13. 変更時の非退行ルール

新方式を試すとき:
1. 最低3仮説を比較する。
2. 生成前にreference MIDIを読ませない。
3. 生成後にpart別 TP / Pred / Ref / Precision / Recall / F1 を比較する。
4. overall F1だけで採用しない。
5. 現在重要な kick / snare / tom を個別に非退行確認する。
6. 僅差なら旧方式を残して比較可能にする。
7. 不採用候補も結果JSON/VALIDATIONへ理由を残す。
8. 採用後はmainのruntimeとこのhandoffを一致させる。

---

## 14. 既知の制約

- 基本対象はドラム単独音源。楽曲全体からのstem separationはWeb本体に未搭載。
- `offvocal.mp3` はOpen HHのteacher/diagnosticとして検証中。production必須入力にはしていない。
- DrumSep/MDX23CのHH分離はoffline teacherとして有望だが、外部checkpointはWeb本体へ同梱せず蒸留studentを研究中。
- 現スコアは5曲へ反復最適化しており未知曲保証ではない。
- tom母数が小さい。
- E-GMD v4 classifier自体はsequence/kit-held-outで校正したが、最終song-level snare rescue policyは5曲で採否確認しており、未知曲post-selection validationは必要。
- crash / ride / pedal-hatはK/S/Tより弱い。
- 任意uploadの可変拍子推定は限定的。
- example曲で使うBeatThis labelsはfullmix由来で、一般uploadには存在しない。

---

## 15. 主要リンク

- App: https://ld1kanae.github.io/drumscribe/
- Review: https://ld1kanae.github.io/drumscribe/review.html
- Repo folder: https://github.com/ld1kanae/ld1kanae.github.io/tree/main/drumscribe
- Detailed history: `VALIDATION.md`



---

## 2026-09-23 Grid / Tempo v31 fresh browser validation

- `DruMaster/songs` 5曲を現行mainの実Playwright Chromiumでfresh acoustic transcription。
- workflow run `35833299223`、head `dd048ea92c2df1fb6e1b1e999379acd647cdda6c`、success。
- 5曲すべて選択gridからのMIDI note tick残差 **0 ticks**。
- runtime報告tempo event数とMIDI内 `set_tempo` 数が5曲すべて一致。
- raw検出→tempo-map preview差: median最大 5.72 ms、p95最大 17.82 ms。
- aggregate chart score: TP 7492 / Pred 8225 / Ref 10086、P 0.911 / R 0.743 / F1 0.818。
- `experiments/validate_grid_browser.py` をCIへ追加。
- `rhythm-grid.js` / `midi.js` の変更でも5曲fresh browser validationが自動起動するようworkflow triggerを修正。
- raw result: `experiments/results-grid-tempo-five-fresh-v31.json`
- detailed handoff: `AI_HANDOFF_GRID_V31.md`

## 2026-09-23 Open HH / DrumSep 最新追記

### main production
- `open-hat-extra-trees-v2.json`: GMD128補助の42/46分類、threshold 0.575。
- `open-hat-overlay-extra-trees-v1.json`: repeat_gate_2hands。既存K/S/T/metalは置換せずGM46だけ追加。
- main real Chromium validation成功。
- overall: TP 7492 / Pred 8225 / Ref 10086, F1 約0.818。
- train-all Open: 571 / 738 / 1179, P 0.7737 / R 0.4843 / F1 0.5957。
- held-out development estimateはOpen F1約0.4636。train-all値を未知曲精度と解釈しない。

### offvocal diagnostic
- 全曲平均ではdrums-onlyより良くない。
- ただし diamondvirgin では drums+offvocal fusion AUC 0.7434 でdrums-only 0.6959を上回った。
- production必須入力ではなく privileged/teacher feature候補。

### DrumSep fast diagnostic
- diamondvirginのopen-dense 35秒でHH stem candidateが参照Open 134/134をcoverage。
- nanairoもOpen 67/67、Closed 112/115。
- 単純tailだけのOpen/Closed識別は弱いので、DrumSepはarticulation classifierよりHH-onset teacher向き。

### DrumSep蒸留v1
`experiments/results-open-hat-drumsep-distill-loo.json`

3仮説:
1. acoustic_only
2. acoustic_student
3. acoustic_student_gmd

いずれもproduction guard不通過。不採用。

重要診断:
- diamondvirgin held-outでdrums-only student candidate streamは参照Open 502中 **477** をdistinct coverage。
- しかしinner validationが安全側threshold 1.01を選び、rescueは0。
- つまり「Open HH候補が存在しない」問題はほぼ解けた一方、「未知曲でどのcandidateをOpenとして採用するか」が現在の主ボトルネック。
- 次段はframe単発分類ではなく、bar/beat位置、反復周期、neighbor hat、同時kick/snare、DrumSep teacher confidence、offvocal cross-viewを利用したsequence/ranking型selectorが有力。


---

## 2026-09-23 Open HH contextual ranking — latest eval snapshot

production mainは現行の `open-hat-extra-trees-v2.json` + `open-hat-overlay-extra-trees-v1.json` を維持。
以下は `drumscribe-v2-eval` の研究結果で、**まだmain未統合**。

### independent HF candidate coverage

`experiments/results-open-hat-hf-coverage.json`

- Ref Open: 1179
- existing-hat matched: 612
- independent-HF matched: 644
- union matched: **1155**
- union recall: **0.979644**
- HF candidates: 8424

diamondvirgin:
- Ref Open 502
- HF coverage 467
- existing+HF union **493/502 = 0.9821**

したがって現在の主ボトルネックはcandidate generationではなく、false HF transientを落とすselector/ranking。

### contextual ranking

DrumSep-distilled candidate:
`experiments/results-open-hat-context-rank-loo.json`

baselineProductionApprox Open:
- 428 / 652 / 1179
- P 0.656442 / R 0.363020 / F1 **0.467504**

strict 3方式:
- forest_context F1 0.464558
- linear_context F1 0.435180
- forest_repeat_rank F1 0.464558

=> strict improvementなし、retainedStrict=`none`。

Independent HF candidate:
`experiments/results-open-hat-hf-context-rank-loo.json`

baselineProductionApprox:
- Open F1 **0.467504**
- Closed F1 **0.808042**
- macro F1 **0.637773**

strict `forest_context`:
- Open **433 / 655 / 1179**
- P **0.661069**
- R **0.367260**
- F1 **0.472192**
- Closed F1 **0.808042**
- macro F1 **0.640117**

=> baselineよりstrict LOOで小幅改善。retainedStrict=`forest_context`。
現時点でmain未統合のOpen HH最新best研究候補。

### grid residual追加の結果

HF contextual + rhythmic-grid residual:
- run `35836237602`
- completed / success
- result commit `e229999d827e9978be3bffb07e575e55c63d5f4a`
- retainedStrict=`none`

baseline Open F1 **0.467504** に対し:
- forest_context **0.436641**
- linear_context **0.421208**
- forest_repeat_rank **0.431807**

すべて悪化。**不採用**。

悪化runで旧bestを失わないよう、non-grid HF contextual bestを
`experiments/results-open-hat-hf-context-rank-best-v1.json`
へ保存した。
保存commit: `0d13fc07db705d1a1b460cc4d03c4d8c74b81425`

完了済み研究bestは引き続き:
- Open F1 **0.472192**
- P **0.661069**
- R **0.367260**
- TP / Pred / Ref **433 / 655 / 1179**

DrumSep contextual + rhythmic-grid residual:
- run `35836222414`
- この更新時点ではin progress

次チャットはまずrun `35836222414` を確認し、0.472192を超えない限り旧bestを維持する。
採用時はstrict LOOだけでなく grouped hat / K/S/T non-regression / real Chromiumを必ず確認する。
