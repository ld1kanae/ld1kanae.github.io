# DrumScribe

ドラム単独音源（WAV / MP3など）をブラウザ内で解析し、Standard MIDI File（チャンネル10）を生成する試作です。[アプリを開く](https://ld1kanae.github.io/drumscribe/)。

原音と生成MIDIの同時再生、個別音量、ソロ、ミュート、シーク、MIDIダウンロードに対応します。音声ファイルはサーバーへ送信せず、推論はブラウザ内で行います。

> AI / 別チャットで作業を引き継ぐ場合は、まず [AI向け引き継ぎガイド](AI_HANDOFF.md) を参照してください。現行runtimeの見分け方、主要ファイルの責務、採用済み/実験資産の区別、最小読書順をまとめています。

## 現在の採譜方式

1. 音声からテンポ・拍・小節位置と補助的なスペクトル特徴を推定します。従来の11,025 Hz帯域解析は、テンポ/構造推定、金物の補助証拠、ニューラル推論が使えない場合のfallbackとして残しています。
2. kick / snare / tom / hi-hat / cymbal の主要打点は、44.1 kHz・100 fpsの特徴量を使うADTOF系モデルをONNX Runtime Web/WASMで実行します。モデル資産は `drumscribe/models/`、ブラウザ実装は `adtof.js` / `adtof-worker.js` です。
3. **kick / snare / tom を優先**して後処理します。
   - kickは高精度ADTOF出力を基本的に維持します。
   - snareは通常閾値を維持しつつ、snare不足が強く示唆される曲だけ低閾値候補を限定救済します。既存の同時kick＋小節反復ルールに加え、E-GMDの別sequence・別kitで校正した小型ロジスティック再分類器を第二判定器として使い、モデル確率と反復支持がある候補だけを追加します。
   - tomは、kickとほぼ同時で弱く孤立した候補だけをkick bleedとして抑制し、強いtomとtom runは残します。
4. hi-hatは44.1 kHzの追加特徴を使うExtraTreesフィルタで過検出を抑えます。pedal hi-hat、crash、rideは音響候補と周期/小節位置を組み合わせて推定します。
5. 推定したBPM・小節情報を使ってMIDIを書き出します。検証曲の可変拍子処理も実装していますが、任意アップロード曲の拍子推定はまだ限定的です。

出力ノートは主に kick 36、snare 38、hi-hat 42、pedal hi-hat 44、tom 45、crash 49、ride 51 を使用します。

## 現在の実ブラウザ検証

5曲の `drums.mp3` を実Chromiumで採譜し、生成MIDIを `chart.mid` と±80 msで1対1照合した現在値です。参照MIDIは予測生成には使用しません。

| Part | TP / Pred / Ref | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| kick | 2636 / 2765 / 2712 | 0.9533 | 0.9720 | **0.9626** |
| snare | 1276 / 1394 / 1470 | 0.9154 | 0.8680 | **0.8911** |
| tom | 69 / 84 / 92 | 0.8214 | 0.7500 | **0.7841** |

全クラス合計は TP 7464 / Pred 8197 / Ref 10086、Precision 0.9106、Recall 0.7400、F1 **0.8165** です。

詳細な仮説、各周回、曲別値、失敗した候補、評価上の注意は [検証履歴](VALIDATION.md) を参照してください。

## 主なファイル

- `transcribe.js`: 採譜パイプライン、テンポ/小節推定、構造優先後処理
- `adtof.js` / `adtof-worker.js`: ADTOF ONNX推論
- `hat-forest.js`: 高解像度hi-hat過検出フィルタ
- `models/`: ONNX、filterbank、学習済み補助モデル（E-GMD K/S/T再分類器を含む）
- `midi.js`: MIDI書き出し
- `experiments/`: 検証コード、生成MIDI、数値結果、履歴

## 既知の制約

- 現在の数値は同じ5曲を使いながら改善を反復した結果であり、未知曲で同じ精度を保証しません。
- tomは参照92打と母数が小さいため、追加曲での検証が必要です。
- E-GMD snare再分類器自体は別sequence・別kitで外部検証していますが、最終的なsong-level救済ポリシーは現5曲でも確認しているため、未知曲でのproduction一般化は追加検証が必要です。
- crash / ride / pedal hi-hatはkick/snare/tomより精度が低く、今後の改善対象です。
- 基本対象は**ドラム単独音源**です。楽曲全体からドラムを分離する処理は現在のWebアプリには含めていません。
