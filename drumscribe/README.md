# DrumScribe

ドラム単独音源をブラウザ内で解析して Standard MIDI File（チャンネル10）を作る試作です。[アプリを開く](https://ld1kanae.github.io/drumscribe/)。WAV / MP3 などの音源を選び、原音と作成MIDIを重ねて再生できます。両トラックの音量・ソロ・ミュート、シーク、プレビュー用のMIDI時間補正、MIDIダウンロードに対応します。参考音源は既存の `../DruMaster/assets/drums/` のサンプルを同一サイトから読み込みます。音声ファイルはサーバーへ送信しません。

基準BPMは任意入力です。入力すると反復判定とMIDIのテンポに使い、空欄なら音声の周期から拍を推定します。秒単位の音符時刻はどちらも保ちます。プレビューでは奏法候補としてオープンハイハット46、ライド51、タム48、その他打楽器60も扱い、既存のドラムサンプルを読み込みます。

## 方法

1. Web Audio API で11,025 Hzのモノラルへ変換し、1,024サンプルのHann窓、110サンプル刻みで短時間フーリエ変換します。
2. 約20 ms前との正の差を低音（35–140 Hz）、中低音（140–900 Hz）、中高音（900–3,000 Hz）、高音（3,000–5,500 Hz）に集約します。ローカル基準値を引き、曲内98パーセンタイルで正規化します。
3. [DruMasterのサンプル](../DruMaster/assets/drums/samples.json)と音源自身の残差スペクトルから6成分の非負モデルを作り、キック・スネア・タム・金物（ハイハット／シンバルを別々の帯域で判定）・その他の攻撃成分をソフトマスクで分けます。これは近似的な楽器群分離であり、独立した音声ステムを復元する処理ではありません。
4. 群別の立ち上がりと従来の帯域検出を組み合わせます。反復する拍位置、1小節先の同種候補、タムの近接を手掛かりに、根拠の弱いシンバルだけを間引きます。奏法の細分類は音色の持続と局所的な連続性から推定します。
5. 推定時刻を秒単位で保持し、入力BPMまたは未入力時の120 BPM / PPQ 480へ換算して書き出します。グリッドへの強制吸着はしません。

PythonとWebモジュールで行った実験の詳細、実測値、限界は[検証履歴](VALIDATION.md)を参照してください。Webモジュールの数値検証はFFmpegでデコードした音源を使っています。実ブラウザでのリサンプリング差を含む全曲精度ではありません。

## 検証の再現

Python 3.12、NumPy、SciPy、FFmpeg が必要です。各楽曲の `drums.mp3`、`chart.mid`、`song.json` と `DruMaster/assets/drums/*.wav` を、たとえば `data/<song>/` と `data/samples/` に配置します。ユーザーの曲のコピーはこのフォルダへ含めていません。

```sh
python drumscribe/experiments/evaluate.py --data data --seconds 80 --diagnostic --output drumscribe/experiments/results-80s.json
python drumscribe/experiments/evaluate.py --data data --seconds 0 --patterns bands band-rhythm band-precision --output drumscribe/experiments/results-full.json
python drumscribe/experiments/export.py --data data --output drumscribe/experiments/generated
python drumscribe/experiments/separated.py --data data --seconds 0 --output drumscribe/experiments/results-separated-full.json
node drumscribe/experiments/export-browser.mjs data drumscribe/experiments/generated-v2
```

評価時に参照MIDIは予測器へ渡しません。予測後、楽器クラスが一致し、時刻差が80 ms以内の音符を1対1で対応付けます。F1は全曲の真陽性・予測数・参照数を集計してから算出します。オフセットは検証だけに使い、一般のアップロード音源に適用しません。

## 既知の制約

- タム・シンバルはこの検証で弱く、ハイハットの開閉、クラッシュとライド、タムの細分類は音色からの暫定推定です。これらの奏法別の正解率は未検証です。同時打撃の音量も正確には再現できません。
- この方法は**ドラム単独の音源**を想定します。楽曲全体からの分離は実装していません。
- 推定MIDIは原曲のBPMやテンポ変化を復元しません。秒単位の時刻を固定テンポのMIDIに写します。
- 15分を超える音源は読み込みを拒否します。長い音源ではブラウザのメモリと解析時間が増えます。
