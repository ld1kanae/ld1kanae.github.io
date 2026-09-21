# DrumScribe

ドラム単独音源をブラウザ内で解析して Standard MIDI File（チャンネル10、キック36・スネア38・ハイハット42・タム45・シンバル49）を作る試作です。[アプリを開く](https://ld1kanae.github.io/drumscribe/)。WAV / MP3 などの音源を選び、原音と作成MIDIを重ねて再生できます。両トラックの音量・ソロ・ミュート、シーク、プレビュー用のMIDI時間補正、MIDIダウンロードに対応します。参考音源は既存の `../DruMaster/assets/drums/{36,38,42,45,49}.wav` を同一サイトから読み込みます。音声ファイルはサーバーへ送信しません。

## 方法

1. Web Audio API で11,025 Hzのモノラルへ変換し、1,024サンプルのHann窓、110サンプル刻みで短時間フーリエ変換します。
2. 約20 ms前との正の差を低音（35–140 Hz）、中低音（140–900 Hz）、中高音（900–3,000 Hz）、高音（3,000–5,500 Hz）に集約します。ローカル基準値を引き、曲内98パーセンタイルで正規化します。
3. 各帯域のピークを候補にし、キック・スネアには帯域比、タム・シンバルには[DruMasterのサンプル](../DruMaster/assets/drums/samples.json)から作ったスペクトルテンプレートとの類似度を条件にします。近すぎるピークは音量の大きい方を残します。
4. 推定時刻を秒単位で保持し、MIDIの120 BPM / PPQ 480へ変換して書き出します。グリッドへの強制吸着はしません。

Pythonで行った実験の詳細、実測値、限界は[検証履歴](VALIDATION.md)を参照してください。Web実装は同じ閾値とFFT設定を使用しますが、ローカル中央値を高速化のため間引いて計算し、ブラウザの音声リサンプリングを使うため、Python側のスコアと完全に同一ではありません。

## 検証の再現

Python 3.12、NumPy、SciPy、FFmpeg が必要です。各楽曲の `drums.mp3`、`chart.mid`、`song.json` と `DruMaster/assets/drums/*.wav` を、たとえば `data/<song>/` と `data/samples/` に配置します。ユーザーの曲のコピーはこのフォルダへ含めていません。

```sh
python drumscribe/experiments/evaluate.py --data data --seconds 80 --diagnostic --output drumscribe/experiments/results-80s.json
python drumscribe/experiments/evaluate.py --data data --seconds 0 --patterns bands band-rhythm band-precision --output drumscribe/experiments/results-full.json
python drumscribe/experiments/export.py --data data --output drumscribe/experiments/generated
```

評価時に参照MIDIは予測器へ渡しません。予測後、楽器クラスが一致し、時刻差が80 ms以内の音符を1対1で対応付けます。F1は全曲の真陽性・予測数・参照数を集計してから算出します。オフセットは検証だけに使い、一般のアップロード音源に適用しません。

## 既知の制約

- タム・シンバルはこの検証で弱く、細かな奏法、ハイハットの開閉、クラッシュとライドの区別、同時打撃の音量再現はできません。
- この方法は**ドラム単独の音源**を想定します。楽曲全体からの分離は実装していません。
- 推定MIDIは原曲のBPMやテンポ変化を復元しません。秒単位の時刻を固定テンポのMIDIに写します。
- 15分を超える音源は読み込みを拒否します。長い音源ではブラウザのメモリと解析時間が増えます。

