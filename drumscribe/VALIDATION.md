# 採譜アルゴリズムの検証履歴

実験に使った元データ: [DruMaster/songs](https://github.com/ld1kanae/ld1kanae.github.io/tree/main/DruMaster/songs) の5曲の `drums.mp3`・`chart.mid`・`song.json`、[DruMaster/assets/drums](https://github.com/ld1kanae/ld1kanae.github.io/tree/main/DruMaster/assets/drums) のサンプル。検証時のリポジトリHEADは `0dd72153931f5a396575be175234a8124bf8fd07`。参照MP3のSHA-256はすべて各 `song.json` の記載値と一致するものを使用した。

## 時間軸と採点

既存の[タイミング編集画面](../DruMaster/song-sync-editor-v2.html)は音声の読み出し位置を `logicalTime + stemOffsetSec`、MIDIノートの論理位置を `midiTime + midiOffsetSec` としている。よって音声ファイルの時刻に変換した参照ノートは `midiTime + midiOffsetSec + stemOffsetSec`。`midiMeasureOffset` をさらに足すと二重計上になる。以下の数値は固定された公開設定を使い、診断用の最適シフト探索は採点に使用していない。

| 曲 | 加算した秒数 | 参照ノート数（全曲） |
|---|---:|---:|
| arcaround | +2.147815 | 1,400 |
| diamondvirgin | −1.219000 | 2,389 |
| kaiju | +2.030668 | 1,797 |
| nanairo | +0.033500 | 2,009 |
| ray | +0.005000 | 2,491 |

楽器はキック35/36、スネア37–40、ハイハット42/44/46、タム41/43/45/47/48/50、シンバル49/51/52/53/55/57/58/59へまとめた。チャンネル10のノートについて、同じ楽器群かつ時刻差80 ms以内の1対1対応を真陽性とする。適合率＝真陽性/推定数、再現率＝真陽性/参照数、F1＝その調和平均。譜面は制作されたMIDIであり、音源中の打撃を一つ残らず注釈した絶対的な正解とは限らない。

## 仮説・仮実装・比較の記録

| 段階 | 仮説と実装 | 5曲の先頭80秒の合計F1 | 曲全体の合計F1 | 判断 |
|---|---|---:|---:|---|
| 1A | 帯域別の正のスペクトル変化（`bands`） | 0.494 | 0.496 | 比較の基準 |
| 1B | 参考ドラムサンプルとの白色化コサイン類似度（`templates`） | 0.345 | 未測定 | 音色差に弱い |
| 1C | 1Aと1Bの加重和（`fusion`） | 0.469 | 未測定 | 1Aより低い |
| 2 | 帯域比とタム/シンバルだけの類似度判定（`band-gated`） | 0.564 | 未測定 | 不要な多重検出を抑制 |
| 2の候補 | 帯域閾値を調整（`band-balanced` / `band-rhythm`） | 0.606 / 0.614 | 未測定 / 0.609 | 僅差のため両方残した |
| 3 | 閾値を調整して誤検出を抑制（`band-precision`） | 0.626 | **0.615** | Web試作へ採用 |
| 4 | タム/シンバルをさらに厳しくした候補（`band-conservative` / `band-controlled`） | 未測定 | 0.645 / 0.651 | **不採用**。後者はタム・シンバルの一致がともに0件 |

80秒は各音声ファイルの冒頭から取得し、予測後に固定オフセットを加算した参照時刻が区間内の音符だけを評価した。曲全体は5曲の実ファイルの全長で再実行した。詳細な生の集計は [`results-80s.json`](experiments/results-80s.json)、[`results-full.json`](experiments/results-full.json)、[`results-targeted.json`](experiments/results-targeted.json)。採用設定で音源から実際に書き出したMIDIは [`experiments/generated/`](experiments/generated/) にあり、書き出した5ファイルをMIDIとして再読み込みして音符数と時刻の往復一致を確認した。

| 曲 | 初期帯域方式 F1 | 採用方式 適合率 | 採用方式 再現率 | 採用方式 F1 | 推定数 / 参照数 |
|---|---:|---:|---:|---:|---:|
| arcaround | 0.449 | 0.433 | 0.723 | 0.542 | 2,335 / 1,400 |
| diamondvirgin | 0.572 | 0.614 | 0.779 | 0.687 | 3,029 / 2,389 |
| kaiju | 0.486 | 0.558 | 0.568 | 0.563 | 1,827 / 1,797 |
| nanairo | 0.489 | 0.641 | 0.707 | 0.673 | 2,217 / 2,009 |
| ray | 0.455 | 0.636 | 0.528 | 0.577 | 2,069 / 2,491 |
| **5曲合計** | **0.496** | **0.578** | **0.657** | **0.615** | **11,477 / 10,086** |

楽器別の採用方式の真陽性 / 推定数 / 参照数は、キック2,640 / 2,888 / 2,712、スネア1,328 / 1,890 / 1,470、ハイハット2,549 / 5,096 / 4,778、タム1 / 383 / 92、シンバル112 / 1,220 / 1,034。したがってタムとシンバルの精度が実用上の主な課題である。高い総合F1を理由にその二群を実質的に捨てる候補を採用しなかった。

## 再現性について

- `arcaround` と `kaiju` の現行 `chart.mid` のSHA-256/バイト数は、同階層の `song.json` に書かれた `midiSha256` / `midiBytes` と一致しない。**GitHub上の現行 `chart.mid`** を比較対象にした。検証時に参照MIDIを変更していない。
- 初回の `ray/drums.mp3` 取得は途中で切れていた。`song.json` のSHA-256不一致を検出して再取得し、合致したファイルで全曲スコアを再計算した。途中で切れたファイルで得た数値は上記に含めていない。
- 検証曲を見ながら閾値を調整しているため、掲載のF1は独立した未知曲での性能を保証しない。ブラウザはPythonとほぼ同じ方式だが、局所中央値の間引きと音声デコードの実装が異なる。ブラウザ上の全曲F1は未計測。

## 公開Webアプリの動作確認

公開ページで検証用の `kaiju/drums.mp3` を選び、ブラウザ内で採譜を実行すると1,865ノートを表示した。原音とMIDIの再生操作、時間表示の進行、MIDIのソロと音量65%、原音のミュートと音量35%を画面上で確認した。書き出した `kaiju-drums-drumscribe.mid` は15,320バイトで `MThd` / `MTrk` ヘッダーを持ち、再解析でノートオン1,865件を確認した。この1,865件はPython検証器が同曲へ出した1,827件とは異なるため、PythonのF1をWebアプリの実測値とみなしていない。音を聴き取っての主観評価は行っていない。


## 2026-09-22: v2見直し開始 — 評価軸の訂正と3周検証

### 見直しの発端

ユーザーから、公開Webアプリの実使用上の問題として次の2点が報告された。

1. **バスドラムをスネアとして誤検出する問題が重大である。**
2. **シンバルの推定量が過剰になる曲がある。**

従来の検証履歴では、楽器別の「真陽性 / 推定数 / 参照数」を根拠に「タムとシンバルの精度が実用上の主な課題」と記録していた。しかし、この評価は **kick→snare / snare→kick のクラス間誤分類を明示的に集計していなかった**。そのため、総合F1や楽器別precision/recallだけでは、実用上重大な誤分類を十分に捉えられていなかった。従来記録は当時の評価結果として残すが、v2ではこの評価軸を追加して再検証する。

### 現行コードで確認したkick / snare競合

transcribe.js の現行 band-precision 相当ロジックでは、kickとsnareは同一のオンセット候補に対して独立に採否を決めている。

- kick: band[0] >= 0.48 * band[1]
- snare: band[1] >= 0.62 * band[0]

この2条件には広い重複領域があり、同一時刻がkickとsnareの両方として採用され得る。また、その後に相互排他またはクラス競合処理がない。v2では、kick / snareを独立検出ではなく **同一オンセット上で競合判定する**方式へ変更して評価する。

### 生成MIDIと正規MIDIのシンバル量比較

既存の drumscribe/experiments/generated/*.mid と各曲の現行 chart.mid をMIDIとして直接解析し、シンバル群49/51/52/53/55/57/58/59のノートオン数を比較した。

| 曲 | 生成MIDI | 正規MIDI | 生成 / 正規 |
|---|---:|---:|---:|
| arcaround | 168 | 136 | 1.24 |
| diamondvirgin | 289 | 225 | 1.28 |
| kaiju | 247 | 576 | 0.43 |
| nanairo | 236 | 45 | **5.24** |
| ray | 280 | 52 | **5.38** |
| **合計** | **1,220** | **1,034** | **1.18** |

合計値だけを見ると1.18倍だが、kaiju の大幅不足が nanairo / ray の過剰検出を相殺している。したがって、シンバル閾値を一律に上下させるだけでは曲間差を解決できない。

既存の band-conservative / band-controlled ではシンバル閾値を厳しくすると総推定数は減る一方、真陽性もほぼ消失する曲があったため、単純な閾値強化のみは採用しない。

### crash / ride分離

ユーザー判断により、v2ではシンバルを少なくとも **crash / ride** に分離する。

正規MIDI5曲で確認したところ、crash系49/52/55/57は小節頭に集中する傾向がある一方、ride系51/53/59は小節頭以外にも規則的に出現する。よって次の異なる事前ルールを用いる。

- **crash**: 小節頭を強く優遇。小節頭以外は高い音響確信度またはフィル/アクセント等の追加根拠を要求する。
- **ride**: 小節頭制約を掛けず、4分・8分等の周期反復を肯定材料とする。

このルールはハードフィルタではなく、音響スコアに対する事前確率・後処理として検証する。

### 端末内推論と将来のサーバー処理

当面は **端末内処理を維持**する。学習・評価は事前に実施し、Webアプリでは軽量モデルまたはブラウザ実装可能な特徴抽出・後処理を用いる。

ただし、最低3周の検証後も精度が不十分で、モデル容量・音源分離・推論速度などブラウザ制約が主要因と判断できた場合は、サーバーGPUによる高精度推論を次の選択肢として検討する。

### v2の評価指標

v2では従来の総合precision / recall / F1に加え、最低限次を毎周記録する。

- 楽器別precision / recall / F1または真陽性 / 推定数 / 参照数
- **kick→snare誤分類**
- **snare→kick誤分類**
- **kick / snareの同一オンセット二重検出数**
- 各クラスの **推定ノート数 / 正規MIDIノート数**
- crash / rideを分離したノート数比
- 曲別の偏り（合計値だけで相殺しない）
- BPM既知条件と、後に行うBPM自動推定条件の差

正規MIDIは予測生成には使用せず、予測完了後の採点にのみ使用する。

### 最低3周の検証計画

drumscribe-v2-eval ブランチ上で、本番 main を変更せずにフル尺5曲を評価する。

| 周 | 主目的 | 変更内容 |
|---|---|---|
| 1 | 音響分類の基準作成 | kick/snare競合判定、crash/ride分離。音楽的後処理は最小限 |
| 2 | 音楽構造の導入 | BPM、小節位置、crash小節頭優遇、ride周期反復を追加 |
| 3 | 誤検出抑制の再調整 | 1・2周の失敗例を踏まえ、二重検出・連打・孤立誤検出等を再調整 |

「3種類のパラメータを同時に試す」ことは3周とは数えない。各周ごとに全5曲の音源から予測を生成し、同じ評価器で再採点する。

生の評価結果は drumscribe/experiments/results-v2.json に保存し、採用・不採用にかかわらず各周の数値と判断理由をこの検証履歴へ追記する。


### v2予備検証（Round 0、正式な3周には数えない）

最初の評価器で、音響候補→小節/周期後処理→追加抑制の3段階を同一実行内で比較した。これは結果を確認してから次のアルゴリズムへ修正した3回の反復ではないため、ユーザー指定の「最低3周」には数えない。

| 予備段階 | Precision | Recall | F1 | kick/snare同一オンセット | crash数比 | ride数比 |
|---|---:|---:|---:|---:|---:|---:|
| Stage 1 | 0.417 | 0.463 | 0.439 | 223 | 5.410 | 3.460 |
| Stage 2 | 0.468 | 0.456 | 0.462 | 223 | 2.136 | 3.345 |
| Stage 3 | 0.470 | 0.455 | 0.462 | 222 | 2.000 | 3.345 |

現行公開方式の既存検証F1 0.615を下回ったため、この予備案は本番採用しない。小節頭優遇はcrash総数の抑制には効いたが、crash真陽性も大きく減少し、ride過検出はほぼ残った。hatは参照数4,778に対して推定1,543（数比0.323）まで落ち、候補生成自体を作り直す必要がある。

また、予備評価の混同行列は「予測音に最も近い正解音を1つ選ぶ」実装だった。この方式ではkickとsnareが正解として同時発音している場合にも、正しいsnare予測をkick→snare誤分類として数える可能性がある。したがって予備段階で表示されたkick→snare件数318は、そのまま実誤分類数とはみなさない。

正式Round 1からは、次のように評価器を修正する。

- 同クラス正解が許容時間内にあれば、他クラス正解が同時に存在しても誤分類には数えない。
- kick/snare二重検出は、正解側にもkick+snare同時打ちが存在する場合を「支持された同時打ち」とし、それ以外だけを「不要な二重検出」として数える。
- 候補生成は現行 band-precision を基準へ戻し、既存F1を失わない状態からkick/snare競合処理とcrash/ride分離を追加する。

予備結果の生データは experiments/results-v2-pilot.json に固定保存する。


### 正式Round 1 — 現行band-precision基準 + kick/snare競合 + 音響crash/ride分離

予備案を破棄し、公開方式の band-precision 候補生成を基準へ戻した。変更は主に次の2点へ限定した。

- 同一時刻のkick/snare候補を競合させ、無条件の二重採用を避ける。
- 従来のcymbal候補をcrash / rideへ分割する。

結果:

| 指標 | 現行公開方式（既存検証） | Round 1 |
|---|---:|---:|
| Precision | 0.578 | 0.569 |
| Recall | 0.657 | 0.608 |
| F1 | **0.615** | **0.588** |
| 推定ノート数 | 11,477 | 10,788 |

Round 1の楽器別ノート数比（推定 / 参照）は、kick 0.933、snare 1.053、hat 1.067、tom 4.163、crash 3.154、ride 0.000だった。

kick→snare誤分類は評価器の改良後の定義で176件、snare→kickは26件。うちkick→snareは arcaround が174件を占めた。arcaroundではkick数比が0.589まで落ちており、競合処理がkick候補をsnare側へ寄せ過ぎている。

crash / ride分離も失敗した。nanairoのcrash数比は5.244、rayは5.385で従来の過剰検出を解消できず、一方rideは5曲合計で0件になった。したがって「シンバル候補をcrash/rideのテンプレート類似度だけで二分する」方式は不採用とする。

Round 1の生データは experiments/results-v2-round1.json に保存した。

**Round 2での修正方針:** kick/snare競合では低域比をより強く使い、kickを誤って落とさない。シンバルは音色テンプレート主導ではなく、既知BPMから得る小節位置と周期反復を主要特徴にする。小節頭付近はcrash、一定周期で連続する候補はride、それ以外の弱いシンバル候補は棄却する。


### 正式Round 2 — 低域優先kick/snare競合 + BPM/小節/周期によるシンバル整理

Round 1の失敗を受け、kick/snare競合は曖昧時にkickを優先し、シンバルは音色テンプレートだけでcrash/rideを二分せず、既知BPMから推定した小節位置と周期反復を主要条件に変更した。

結果:

| 指標 | 現行公開方式 | Round 1 | Round 2 |
|---|---:|---:|---:|
| Precision | 0.578 | 0.569 | **0.616** |
| Recall | 0.657 | 0.608 | 0.609 |
| F1 | **0.615** | 0.588 | **0.613** |
| kick→snare | 未集計 | 176 | **42** |
| snare→kick | 未集計 | 26 | 27 |
| 不要なkick+snare二重検出 | 未集計 | 19 | **0** |

Round 2では総合F1が現行方式とほぼ同水準まで回復し、kick→snare誤分類はRound 1の176件から42件へ減少した。kick数比は1.031で、Round 1の0.933より参照量へ近づいた。一方snare数比は0.773まで下がり、arcaround 0.565、ray 0.495など、競合処理がsnareを削り過ぎる曲が残った。

シンバル量は大きく改善した。crash数比は全体0.869で、nanairoは5.244→1.889、rayは5.385→1.788。ただしcrash真陽性は7 / 339 / 390、rideは26 / 229 / 644に留まり、「量を合わせる」だけで正しい打点・クラスを取れていない。

誤分類内訳を見ると、本物のシンバルがhatとして検出されている例が多い。特に kaiju では crash→hat 156件、ride→hat 76件、diamondvirginでは crash→hat 69件、ride→hat 90件だった。このため、Round 3では「cymbal_rawだけを分類する」方式をやめ、既存hat候補も含めて高域候補全体を後段再分類する。

Round 2の生データは experiments/results-v2-round2.json に保存した。

**Round 3での修正方針:**
- kick/snare候補を音響段階で早期削除せず、BPMから推定した拍位置を加えて競合解決する。
- 2拍・4拍付近ではsnareを優遇して、Round 2で失ったsnareを復元する。
- 小節頭付近のhat候補でcrash音色の支持があるものをcrashへ再分類する。
- 規則的に反復しride音色の支持があるhat候補をrideへ再分類する。
- nanairo / rayのようにride参照がない曲でrideを大量生成しないよう、曲単位のride支持量も条件にする。


### 正式Round 3 — 拍位置でsnare復元 + hatを含む高域候補のcrash/ride再分類

Round 2のsnare不足と、真のcrash/rideがhatへ誤分類されている問題を同時に直すため、kick/snare競合を拍位置まで遅延し、hat候補もcrash/rideへの再分類対象にした。

結果:

| 指標 | 現行公開方式 | Round 1 | Round 2 | Round 3 |
|---|---:|---:|---:|---:|
| Precision | 0.578 | 0.569 | **0.616** | 0.586 |
| Recall | **0.657** | 0.608 | 0.609 | 0.559 |
| F1 | **0.615** | 0.588 | **0.613** | 0.572 |
| kick→snare | 未集計 | 176 | **42** | 160 |
| snare→kick | 未集計 | 26 | 27 | 23 |
| 不要なkick+snare二重検出 | 未集計 | 19 | **0** | 7 |

Round 3ではsnare数比が1.064まで回復し、ride数比も0.988と量だけは参照へ近づいた。しかしride真陽性は52 / 636 / 644に留まり、hat→rideの誤変換が増えた。crashも49 / 564 / 390で、Round 2より真陽性は増えたものの誤検出増加の方が大きかった。

また、拍位置によるsnare復元は arcaround で再びkick候補をsnareへ寄せ、kick→snareが158件発生した。一般的な「2拍・4拍はsnare」という事前知識を強く掛けると、曲固有の同時打ちやキック配置を誤って上書きすることが確認できた。

したがってRound 3は不採用。生データは experiments/results-v2-round3.json に保存した。

### 正式3周終了時点の判断

最低3周の再検証を完了した。3周の中ではRound 2が最良で、総合F1 0.613と現行公開方式0.615にほぼ並びながら、kick→snareを42件まで抑え、nanairo / rayのcrash過剰量を約5.2倍/5.4倍から約1.9倍/1.8倍へ減らした。

ただしRound 2でもcrash / rideの真陽性率が低く、snare再現率低下が残る。このため、この時点では本番 main へ移植しない。

次段階では、ユーザーから提案された「音源と正規MIDIを照合した学習型音色分類」を検証する。5曲だけを同時に学習・評価するとリークするため、まず **leave-one-song-out**（1曲を完全に評価用へ外し、残り4曲だけで学習）を5通り行い、未知曲相当での一般化を確認する。ブラウザ搭載を想定し、最初は軽量な特徴量＋小規模分類器を対象とする。


### 学習型予備実験 — 5曲leave-one-song-out

音源＋正規MIDIから軽量な二値ロジスティック分類ヘッドを学習する実験を行った。各foldでは評価対象1曲のMIDIを学習・閾値選択に一切使わず、残り4曲だけで学習した。

候補オンセット生成のoracle recallは、kick/snare/crashではほぼ全曲1.0、hat/rideも多くの曲で0.7〜0.9以上だった。したがって、現状の主問題は「打点候補を見つけられない」より「未知音色へのクラス分類が一般化しない」側にある。

5-fold合計:

| 指標 | 値 |
|---|---:|
| Precision | 0.526 |
| Recall | 0.708 |
| F1 | 0.604 |
| kick→snare | 123 |
| snare→kick | 82 |
| 不要なkick+snare二重検出 | 481 |

曲別F1は arcaround 0.474、diamondvirgin 0.586、kaiju 0.527、nanairo 0.662、ray 0.741。曲間差が大きく、4曲だけから学習した軽量分類器をそのまま本番搭載するのは不適切と判断した。

学習型方式そのものを否定する結果ではない。候補oracle recallが高いため、より多様な音色を含む外部データで分類器を学習すれば改善余地がある。次にE-GMD等の大規模データで学習済みの既存ドラム転写モデルを、本アプリ5曲へそのまま適用して一般化性能を確認する。

生データは experiments/results-ml-loo.json に保存した。


## 2026-09-22: 評価基盤の固定 — 全曲×全パート詳細比較と部品ベスト保存

以後のPDCAは、必ず次の順序で実施する。

1. 同一の土台から最低3候補を仮定する。
2. 各候補を実装し、5曲すべての `drums.mp3` から実際のMIDIファイルを生成する。
3. 生成したMIDIを再読み込みし、対応する `chart.mid` と比較する。参照MIDIは予測生成には使用しない。
4. 全曲×全パートについて詳細指標を保存する。
5. 総合性能だけでなく、パート別に突出した候補を component bank に保存する。
6. 総合勝者を次サイクルの土台にする。僅差候補は残す。総合敗者でも特定パートで突出した場合は部品候補として残す。
7. 再び最低3候補を派生させ、同じ手順を複数サイクル繰り返す。

### 正式な詳細指標

標準評価器は `experiments/detailed_metrics.py` とする。同一クラスかつ80 ms以内の1対1対応をTPとし、曲×パートごとに最低限次を記録する。

- reference / predicted / TP / FP / FN
- precision / recall / F1
- false discovery rate（余計な打音 / 予測打音）
- miss rate（取りこぼし / 正解打音）
- predicted / reference のノート数比
- 一致した打音のsigned mean timing error
- 一致した打音のabsolute median timing error
- 一致した打音のabsolute p90 timing error
- unmatched predictionから最も近い同クラス正解までの距離
- 160 ms以上離れた明確な余計打音数
- クラス間誤分類行列

全パートは kick / snare / hat / pedal_hat / tom / crash / ride / other を分離して記録する。補助診断として hat family、cymbal family、kick+snare、手で叩くパート群も集計する。

### 再現可能な履歴データ

- `experiments/validation-history.json`: 既存の全 `results*.json` を自動収集し、候補名、cycle、params、曲別指標、結果ファイルのGit commit、実装スクリプトとそのGit commitを保存する。
- `experiments/component-bank.json`: 各パートについて候補を横断比較し、aggregate F1だけでなく mean-song F1 / worst-song F1 を使って、全曲で安定した部品候補を残す。
- `experiments/detailed/*.json`: 実MIDIを再解析して得た標準詳細指標。
- 各 `results-*.json`: 各探索固有の生結果。削除せず履歴として保持する。
- 各 `generated-search-*/`: 生成MIDI。可能な限り結果JSONと対応するディレクトリを保持する。

## Cycles 40–42 — 明示的スペクトログラム分離 → 従来分類器

旧方式は `drums.mp3` 全体から直接候補を生成していたため、分離を先に行う方式へ変更した。soft / sharp / temporal-smooth の最低3方式を比較した。各方式で kick / snare / tom / hat / cymbal のスペクトログラムストリームを作り、その後に既存のLOSO分類器と音楽制約を適用した。

Cycle 40の勝者は `smooth`。Cycle 41ではレビューで問題になったkick/hatの異常連打を抑える後処理を3案比較し `moderate` が勝者。Cycle 42ではsnare競合を3案比較し `snare_roll_recall` が勝者となった。

最終結果:
- 総合 F1: **0.6146**
- kick F1: **0.9510**、count ratio 1.0037
- snare F1: **0.7296**
- hat F1: **0.4921**
- tom F1: **0.5960**、precision 0.7627
- crash F1: **0.2931**、precision 0.5302
- ride F1: **0.0000**
- pedal_hat F1: **0.0369**
- two-limb violation: **0**

総合F1だけなら旧方式と同程度だが、kick / tom / crashには明確な部品改善がある。一方でhat・ride・pedal_hatは不十分なため、この結果を丸ごと本番採用せず、部品候補として保持する。生データは `results-iterative-separation.json`。

## Cycles 43–45 — 実WAV 5ステム分離（HPSS / frequency masking）→単純onset

`cukas/drumsep` を用い、`drums.mp3` を kick / snare / toms / hihat / cymbals の実WAVへ先に分離してからonsetを検出した。Cycle 43でprecision/balanced/recall、Cycle 44でcrash幅/ride、Cycle 45でkick/hat guardを最低3案ずつ比較した。

結果は不採用。最良付近でも総合F1は約0.54で、特にtomが reference 92に対し predicted 約2,800–3,400となった。これは「分離WAVのすべてのtransientをそのまま該当楽器とみなす」ことが誤りであり、**分離そのものと分離後の打点分類を別問題として扱う必要がある**ことを示す。

ただしkickはF1約0.89、snare recall約0.82を保っており、分離フロントエンド全体を否定する結果ではない。分離後の専用分類器へ進む。

## Cycles 46–48 — 実5ステム分離 + 11.025 / 22.05 / 44.1 kHz比較

高域情報の欠落を検証するため、実5ステム分離後の解析サンプルレートを最低3案比較した。

Cycle 46:
- 11,025 Hz: overall F1 **0.5330**, hat F1 **0.5548**
- 22,050 Hz: overall F1 **0.5732**, hat F1 **0.6603**
- 44,100 Hz: overall F1 **0.5770**, hat F1 **0.6702**

44.1 kHzが勝者、22.05 kHzは僅差として保持する。11.025 kHzは高域情報不足によりhatで明確に劣るため、今後の高域分類の基準から外す。

Cycle 47では44.1 kHz上でprecision/balanced/recallを比較し、precision案が勝者:
- overall F1 **0.5850**
- kick F1 **0.8922**
- snare F1 **0.6760**
- hat F1 **0.6638**
- tom F1 **0.0518**
- crash F1 **0.1192**
- ride F1 **0**

Cycle 48のkick/hat guardはoverallを改善しなかったため、Cycle 47のprecision条件を維持する。

重要な部品ヒント:
- **hatは44.1 kHz分離でF1 0.6702まで上がり、11.025 kHzより明確に高い。高域保持は有効。**
- kickはどのsample rateでも安定して高く、周波数分離+onsetの部品として有望。
- tomは単純onsetでは全く使えない。Cycle 40–42の学習型tom処理を組み合わせるべき。
- crash/rideは単純cymbal stem onsetでは不十分。専用分離または専用分類が必要。

生データは `results-iterative-drumsep-rate.json`。

## Cycles 49–51 — 分離フロントエンド + 楽器別LOSO分類（実行系）

次段階は、分離後のtransientを無条件採用せず、**各パート専用の学習型打点分類器**へ通す。

Cycle 49では最低3つの分離フロントエンドを比較する:
1. DSP/HPSS 5-stem
2. MDX23C neural 6-stem（kick/snare/toms/hh/ride/crash）
3. neural + DSP ensemble

Cycle 50では勝者分離器上で logistic / random forest / extra trees の3分類器を比較する。

Cycle 51では勝者を土台に precision / balanced / recall+rhythm の3案を比較する。

すべてleave-one-song-outで、評価対象曲の `chart.mid` はそのfoldの学習に使用しない。各候補は実MIDIを書き出し、標準詳細評価器で全曲×全パートを採点する。

また次の音楽制約は全候補で維持する。
- crashは推定小節頭付近のみ採用。
- snare / hat / tom / crash / ride は同時最大2音。3音以上なら確率上位2音のみ。
- kickとpedal hi-hatは上記2音制約の対象外。
- rideは単発音色だけで決めず、周期継続を主要根拠にする。


## Cycles 52–54 — component bank hybrid

過去の全候補から「総合勝者ではないが特定パートで強い」部品を抽出し、実際の生成MIDI同士をパート単位で再構成した。参照 `chart.mid` は合成には使用せず、合成MIDIを書いた後の採点だけに使用した。

Cycle 52では最低3案:
- `c52_robust`: 全曲安定性を重視したkick/snare/hat/tom/crash部品
- `c52_precision`: precision寄りのkick/crash部品
- `c52_recall`: recall寄りのsnare/hatにride候補も追加

勝者 `c52_robust`:
- overall F1 **0.6954** / precision 0.7523 / recall 0.6465
- kick F1 **0.9590**
- snare F1 **0.7642**
- hat F1 **0.6445**
- tom F1 **0.6345**
- crash F1 **0.3511**
- pedal_hat F1 **0.1735**
- ride F1 **0.0000**
- kick→snare 38

旧総合約0.615を明確に上回ったため、component hybridを新しい本線に採用する。

Cycle 53では two-hands / priority / no-poly-filter の3案を比較。two-handsとpriorityは同値、no-filterは僅かに低下したため、製品要件通り**手で叩く音は同時最大2音**を維持する。

Cycle 54では crash source / measure-head tight / measure-head balanced の3案を比較。小節頭だけに後段で強く限定するとcrash recallが大幅に落ちたため、単純なhard rejectは不採用。小節頭prior自体は維持するが、**acoustic evidenceと組み合わせたsoft priorとして使う**。

曲別の重要点:
- arcaround: snare recall 0.363、hat precision 0.297、crash F1 0.057が弱点。
- diamondvirgin: kick F1 0.943、snare F1 0.920で強い。
- kaiju: kick 0.976、snare 0.973、tom 0.757と強い一方、ride 431 referenceに対し0予測。
- nanairo: kick 0.999、hat 0.714。snare recall 0.355が弱点。
- ray: crash F1 0.832で非常に強い。snare recall 0.429が弱点。

この結果から、今後は「全曲一律閾値」よりも**強い核を保持し、不足部だけ別部品で補完する**方針を優先する。

## Cycles 55–57 — loop / repetition consensus

元の要件「フィル以外は反復することが多い」を、4/8小節相当の反復支持として後処理に導入した。global / local / multiresの最低3案、窓幅3案、support閾値3案を比較した。

最高は `c57_support1`:
- overall F1 **0.6931**
- precision 0.7542 / recall 0.6411
- kick F1 0.9590
- snare F1 0.7642
- hat F1 0.6445
- tom F1 0.6345
- crash F1 0.1876
- ride 0

component hybridの0.6954を超えなかったため、**全パート共通の反復削除フィルタとしては不採用**。特にcrashを反復/小節位置で後段削除するとrecall低下が大きい。

ただし反復情報そのものは有用であり、以下に限定して部品利用する:
- snare補完候補の支持
- rideの継続区間判定
- hatの孤立誤検出抑制
- fill区間の保護

## Cycles 61–63 — targeted recall repair

component hybridの高precision核を保持し、LOSO-ML予測・DSP分離予測・反復支持から不足パートだけ補完した。

Cycle 61 snare補完:
- `snare_raw`: snare F1 0.8127 / recall 0.8810、ただし kick→snare 109
- `snare_consensus`: snare F1 **0.8096** / precision 0.8181 / recall 0.8014、kick→snare **42**
- `snare_pattern`: snare F1 **0.8224** / precision 0.7727 / recall 0.8789、ただし kick→snare 103

総合選択では `snare_consensus` を採用する。理由は、ユーザーが明示したkick→snare誤認を大幅に抑えながらsnare recallを0.666→0.801へ上げたため。ただし `snare_pattern` は**snare単体の最良部品**としてcomponent bankに保持し、後段でkick vetoと組み合わせる。

Cycle 62 tom補完:
- raw: tom F1 0.6250
- consensus: tom F1 **0.6369** / precision 0.7692 / recall 0.5435
- fill-only: tom F1 0.6216

既存tom F1 0.6345に対して僅差だが、consensusでrecallが0.500→0.543へ改善したため保持する。precisionは0.868→0.769へ低下しているので、旧tom核もcomponent bankに残す。

Cycle 63 pedal-hat:
- keep: pedal_hat F1 **0.1735**
- periodic: 0.1175
- off: 0.0000

pedal-hatをoffにするとoverall F1だけは0.7082へ上がるが、1パートを完全放棄するため不採用。**全パート評価**に合わせて選択スコアへpedal_hatを明示的に含め、`keep` を正式勝者とした。

正式なCycle 63勝者:
- overall F1 **0.7039**
- precision **0.7455**
- recall **0.6667**
- kick F1 **0.9590**
- snare F1 **0.8096**
- hat F1 **0.6451**
- tom F1 **0.6369**
- crash F1 **0.3517**
- pedal_hat F1 **0.1735**
- ride F1 **0.0000**
- kick→snare **42**

この時点で主な未解決は、ride、crash、pedal_hat、hat false positives。snareは実用候補域まで改善したが、arcaround/nanairo/rayの弱い曲を個別に確認し続ける。

## Cycles 64+ — 次の分岐

次の探索を並列化する。

- Cycles 64–66: `snare_pattern` の高recallを使いつつ、kick同時刻veto / DSP consensus / backbeat+repeat rescueの最低3案でkick→snare誤認を抑える。
- Cycles 67–69: 44.1kHz high-resolution hat / guarded hat / consensusの最低3案でhat false positivesとrecallを比較。
- Cycles 49–51: MDX23C neural 6-stem / DSP 5-stem / ensembleを比較中。特にride/crashを専用stemで改善できるか確認する。
- neural結果取得後は、全体を置換せず、ride/crashなど**ニューラル分離が既存部品より明確に強いパートだけ融合**する。


## Cycles 64–66 — snare recall + kick-confusion veto

Cycle 61の高recall snareをそのまま採るとkick→snare誤認が100件超まで増えるため、kick同時刻veto・DSP snare合意・backbeat/repetition rescueを最低3案比較した。

最良 `c66_repeat1`:
- overall F1 **0.7040**
- snare F1 **0.8107**
- snare precision **0.8203**
- snare recall **0.8014**
- snare count ratio **0.9769**
- kick→snare **42**

Cycle 61の `snare_pattern` はsnare F1 0.8224と高いがkick→snare 103。veto版はsnare F1を僅かに落とす代わりに誤認を42まで戻した。ユーザーが以前問題視したkick→snare誤認を考慮し、veto版を実用部品として優先し、pattern版も高recall部品として保存する。

## Cycles 67–69 — 44.1 kHz hi-hat fusion

guarded hat、44.1 kHz high-resolution hat、両者consensusの最低3案を比較した。

Cycle 67:
- guarded: hat F1 0.6447
- 44.1kHz: hat F1 **0.6705**, recall 0.7474
- consensus: hat F1 0.6445

44.1 kHz高域保持はhat検出に明確な改善要素。続いて、high-resolution候補を反復支持でrescueする3案を比較した。

Cycle 69 `repeat3`:
- overall F1 **0.7148**
- hat F1 **0.6731**
- hat precision 0.6148
- hat recall **0.7435**
- hat false-discovery rate **0.3852**
- hat count ratio 1.2094

総合とrecallは大きく改善したが、余計なhatも増えた。特に arcaround はhat reference 293に対しpredicted 837。よってこの段階では「最高総合F1」だけを理由に確定採用しない。

## Cycles 70–72 — crash detector consensus + soft downbeat prior

単純なmeasure-head hard rejectはCycle 54で失敗したため、soft/strict/balanced複数crash検出器の合意、小節頭prior、crash間隔を組み合わせた。

最良 `c72_head18`:
- overall F1 **0.7051**
- crash F1 **0.3734**
- crash precision **0.6689**
- crash recall 0.2590
- crash false-discovery rate **0.3311**
- crash count ratio 0.3872

旧crash部品:
- F1 0.3517
- precision 0.5723
- false-discovery 0.4277

したがって「小節頭では採用、それ以外では不採用をベースにする」というpriorは、**複数音響検出器の合意を優先し、小節頭をsoft rescue条件として使う**形なら有効。ただし最悪曲F1が0であるため、全曲固定置換せず旧crash部品も保持する。

## Cycles 73–75 — hi-hat false-positive repair

Cycle 69のhat recall改善を保持しつつ、余計打音を減らすため、
- source consensus + repetition
- adaptive bar density
- strict adaptive
を比較し、さらに密度閾値と反復supportを3案ずつ比較した。

最良 `c75_repeat5`:
- overall F1 **0.7156**
- precision 0.7309 / recall 0.7010
- hat F1 **0.6744**
- hat precision **0.6216**
- hat recall **0.7370**
- hat false-discovery rate **0.3784**
- hat miss rate 0.2630
- hat count ratio 1.1855

Cycle 69に比べ、hat recallを少し下げてfalse positivesを減らし、hat F1とoverall F1を僅かに上げた。現時点のhat部品候補として保持する。

依然としてhat false-discovery約38%は高いため、今後も「総合F1」と「外れて鳴るhat率」を別指標で監視する。


## Cycles 76–78 — pedal hi-hat repair

過去のpedal-hat専用候補を現在の本体へ再投入し、current / strict / recall の最低3案を比較。その後、周期支持閾値3案とhand-hat競合除去3案を比較した。

最良部品 `c77_per75`:
- pedal_hat F1 **0.3865**
- precision **0.3441**
- recall **0.4408**
- count ratio 1.2811

旧現行pedal_hat:
- F1 0.1735
- precision 0.2440
- recall 0.1346

pedal-hat単体としては大幅改善。ただし全体へ無条件注入すると予測数が増え、overall precisionを落とす。よって「pedal部品として保持」はするが、総合候補では再評価してから採用する。

hand-hatと近いpedal候補を単純除去する案は大幅悪化した。pedalとhand-hatの近接自体は十分起こりうるため、このhard conflict ruleは不採用。

## Cycles 79–81 — first multi-component fusion

Cycle 69 high-recall hatを土台に、crash / snare / pedalの強い部品を順に融合した。

Cycle 79 crash:
- base crash: overall F1 0.7148 / crash F1 0.3517
- precision crash: overall F1 **0.7158** / crash F1 **0.3734**
- recall crash: overall F1 0.7148 / crash F1 **0.3824** だがfalse positives増加

全体選択ではprecision crashを採用。

Cycle 80 snare:
- existing base snare: snare F1 **0.8130**, kick→snare 42
- veto snare: 0.8107, kick→snare 42
- pattern snare: **0.8253** だがkick→snare **103**

ユーザーが問題視したkick→snare誤認を優先し、base snareを維持。pattern snareは高recall部品としてのみ保持。

Cycle 81 pedal:
- base pedal: overall F1 **0.7158**
- strict pedal: overall 0.7015
- balanced pedal: overall 0.6946

pedal単体は改善しても、無条件融合すると全体precision低下が大きい。Cycle 79–81の正式勝者は:
- overall F1 **0.7158**
- kick F1 0.9590
- snare F1 0.8130
- hat F1 0.6731
- tom F1 0.6369
- crash F1 0.3734
- pedal_hat F1 0.1735
- ride F1 0
- kick→snare 42

次段ではhat false-positive修正版とperiodic pedalを同時に含めた all-part fusion v2 を比較する。


## Cycles 82–84 — all-part fusion v2

直近のパート別勝者を同時融合した。
- kick/tom: stable component
- snare: kick-confusion veto
- hat: high-resolution + repetition precision repair
- crash: detector consensus + soft downbeat prior
- pedal_hat: strict historical component + periodic support 0.75
- ride: この時点では未解決のため0

Cycle 82で robust / balanced / recall の最低3案、Cycle 83でhat部品3案、Cycle 84でpedal部品3案を比較した。

正式勝者 `c84_pedal75`:
- overall F1 **0.7193**
- precision **0.7170**
- recall **0.7217**
- kick F1 **0.9590** / FDR 0.0512
- snare F1 **0.8107** / precision 0.8203 / recall 0.8014 / kick→snare 42
- hat F1 **0.6744** / precision 0.6216 / recall 0.7370 / FDR 0.3784
- pedal_hat F1 **0.3865** / precision 0.3441 / recall 0.4408 / FDR 0.6559
- tom F1 **0.6369** / precision 0.7692 / recall 0.5435
- crash F1 **0.3734** / precision 0.6689 / recall 0.2590 / FDR 0.3311
- ride F1 **0.0000** / reference 644
- kick→snare **42**, snare→kick 25

曲別:
- arcaround: overall F1 0.585。hat 210/797/293、snare 125/234/292、crash 3/28/78。最大の弱点。
- diamondvirgin: overall 0.748。kick/snareは強いがprecision crash部品が crash 0/0/70 と全損。
- kaiju: overall 0.637。kick/snare/tomは強いがride 0/431。
- nanairo: overall 0.749。hat 0.744、snare 0.656、pedal_hat recallが低い。
- ray: overall 0.799。hat 0.763、snare 0.857、crash 0.843、pedal_hat 0.698。

この結果から平均だけでなく「最悪曲」を正式な次サイクルの判断材料に加える。

## 打点タイミング精度の完全詳細評価

`experiments/materialize_current_details.py` で主要候補の全曲×全パートについて完全版 `detailed_metrics.py` 結果を `experiments/detailed-current/` に保存した。

c84の一致打音について、多くの曲・パートで absolute timing error median は約 **6–15 ms**、p90も多くが **15–30 ms**。例:
- arcaround kick median 8.58 ms / p90 16.87 ms
- diamondvirgin snare 8.63 / 20.04 ms
- kaiju snare 6.77 / 15.06 ms
- ray hat 9.74 / 15.42 ms
- ray crash 11.63 / 16.36 ms

例外としてnanairo kickは median 35.91 ms / p90 54.57 msだが80 ms評価窓内には大半が入る。

したがって現状の主要ボトルネックはonset時刻そのものより、**クラス誤認・余計打音・取りこぼし**。今後の探索は分離/分類/部品融合を優先する。

また unmatched prediction は正解打点から大きく離れる例が多い。特に arcaround hat はFP 587のうち500件が同クラス正解から160 ms超離れており、単なる微小タイミングずれではなく明確な余計打音である。

## Cycles 88–90 — adaptive crash fallback

Cycle 82–84のprecision crashがdiamondvirginで0予測になる問題を受け、予測密度だけでfallbackする方式を比較した。曲名や参照MIDIは分岐に使用しない。

Cycle 88:
- precision only: crash F1 0.3734 / P 0.6689 / R 0.2590 / worst-song F1 0
- zero→old-base fallback: crash F1 **0.3891** / P 0.5816 / R 0.2923 / worst-song F1 **0.0566**
- sparse→recall fallback: crash F1 0.3824 / worst 0.0566

zero-fallbackは1曲全損を防ぎ、crash F1自体も上がる一方、overall F1は0.7190でprecision-only 0.7193と僅差。よって、
- **precision crash** = 平均precision優先部品
- **zero-fallback crash** = 最悪曲耐性優先部品
として両方を保持する。

Cycle 89のratio 0.10/0.25/0.50はこのデータでは同一結果。Cycle 90のgap rescueも改善なし。密度fallbackの有効部分は「0または極端な疎さを検知して別crash部品へ切替える」点に限定される。


## Cycles 85–87 — 44.1 kHz ride section classifier

fusion-v2 (Cycle 84) を土台に、44.1 kHz原音から高域スペクトル・金物onset周期・区間密度を抽出し、held-out曲以外4曲でride-dominant区間を学習した。

比較:
- Cycle 85: 2 / 4 / 8 beat window
- Cycle 86: logistic / random forest / ExtraTrees
- Cycle 87: strict / balanced / recall threshold

結果:
- ExtraTreesはride TPをほぼ作れず、最終strictではride TP=0。
- RFはride TP=5 / predicted 69 / F1 0.014。
- logisticはride TP **151** / predicted **1233** / precision **0.1225** / recall **0.2345** / F1 **0.1609**まで拾えたが、hatを大量にrideへ誤変換し overall F1は **0.6603**まで低下。
- recall案でもride TP=6 / predicted 259 / F1 0.0133。

結論:
**44.1 kHzの区間特徴だけではride/hat分離は不十分。**
rideはニューラル6ステム分離、または複数独立detectorのconsensusへ進める。
結果は `results-iterative-ride-hires.json`。

## Cycles 91–93 — cross-stem hi-hat bleed suppression（実行系）

5WAV実分離を再実行し、hihat stemのonsetをkick/snare stemの同時onset強度と比較する。目的は、特にarcaroundで残るhat大量誤検出が他stem bleed由来かを検証すること。

Cycle 91: loose / balanced / strict cross-stem gate  
Cycle 92: periodic rescue なし / 0.50 / 0.75  
Cycle 93: hat onset threshold 0.24 / 0.30 / 0.36

## Cycles 94–96 — adaptive crash fallback

precision crashが曲単位で0または極端に少ない場合のみ、base/recall crashを予測密度からfallbackする。参照MIDIはfallback判断に使用しない。

旧番号での先行試験では:
- zero fallback: crash F1 **0.3891**まで上昇
- sparse recall: crash F1 0.3824
- precision維持: crash F1 0.3734
- ただしoverallではprecision維持 **0.7193** が最高

したがって「crash単体F1向上」と「全体精度」のトレードオフを部品として保持し、正式には91以降と重ならない番号で再実行する。

## Cycles 97–99 — structural pedal-hi-hat（実行系）

pedal-hat候補を単純音色だけで決めず、以下を利用する。

1. hand-supported: snare/tom/crash/rideと同時で、かつ周期的
2. poly-rescue: kick+handまたは複数hand hitと同時で、足で鳴らすと解釈すると2-hand制約を自然に満たす候補
3. gap-repeat: hand-hatが無い反復slotを周期的に埋める候補

Cycle 98でperiodicity閾値、Cycle 99でstrict/recall/union候補源を比較する。

## Cycles 100–102 — multi-detector ride consensus（実行系）

独立したride検出器:
- 44.1 kHz section logistic
- 旧composite ride-recall
- 旧section logistic

を組み合わせる。

Cycle 100:
- highres単独
- 3者intersection
- 2-of-3 consensus

Cycle 101: 時刻一致窓 35 / 60 / 90 ms  
Cycle 102: 周期支持 0.25 / 0.50 / 0.75

単一detectorのride precisionが低いため、複数系統の合意でfalse positiveを落とせるか検証する。


## Exhaustive experiment log

全候補・全cycleの実験履歴は、手作業の追記漏れを避けるため自動生成する。

- Human-readable: `drumscribe/experiments/EXPERIMENT_LOG.md`
- Machine-readable: `drumscribe/experiments/experiment-log.json`
- Reproducibility index: `drumscribe/experiments/validation-history.json`
- Per-part retained leaders: `drumscribe/experiments/component-bank.json`
- Song-by-song raw metrics: each `results*.json`
- Canonical detailed re-score: `drumscribe/experiments/detailed-history/`

各cycleは最低3候補、勝者、僅差候補、全パートF1、kick→snare / snare→kick、実装script/commit、result commit、params参照を記録する。生成MIDIが残る候補は標準評価器で再採点可能とする。


## 2026-09-22 checkpoint — component fusion / part-specific repair / ride recovery

正式な候補IDは result file + cycle + candidate name とする。過去に異なる探索系列でcycle番号が重複したため、cycle番号単独では識別しない。

### Component fusion 系

複数の過去候補からパート単位の勝ち要素を再利用した結果、直接分類/単一探索系列より総合性能が明確に向上した。

- results-iterative-best-fusion.json
  - final c81_pedal_base: overall F1 0.7158
  - kick F1 0.9590
  - snare F1 0.8130
  - hat F1 0.6731
  - pedal_hat F1 0.1735
  - tom F1 0.6369
  - crash F1 0.3734
  - ride F1 0
- results-iterative-fusion-v2.json
  - final c84_pedal75: overall F1 0.7193
  - pedal_hat F1 0.3865 まで改善し、全体バランスも維持
- results-iterative-tom-consensus.json
  - final c105_density7: overall F1 0.7197
  - tom F1 0.6667 / precision 0.7534 / recall 0.5978
  - 現状のbalanced base候補として保持

### 「総合F1だけ高い」候補の扱い

results-iterative-pedal-structural.json には overall F1 0.7205 付近の候補があるが、pedal_hat F1が約0.01–0.03まで崩れる。このため総合F1最高値だけを理由に本採用しない。全パート評価を優先する。

### Hi-hat

44.1 kHz高域保持が11.025 kHzより有効だった結果を引き継ぎ、hat fusion / precision / cross-stem bleed suppressionを複数cycleで比較した。

- current balanced hat: F1 約0.674
- false discovery rate 約0.38
- recall 約0.74
- 改善はしたがFPが依然多く、レビュー指摘の「細かい不要連打」は未解決として保持

### Snare

高recall部品では:
- results-iterative-best-fusion.json : c80_snare_pattern
- snare F1 0.8253 / precision 0.7778 / recall 0.8789
- ただし kick→snare が42→103へ増加

したがって丸ごと採用せず、高精度baseに安全な追加snareだけを足す探索へ移行。results-iterative-snare-veto.jsonではkick→snareを42へ戻せたが、snare F1は0.8107まで戻ってしまった。Cycles 112–114でより細かい kick近傍 veto / independent snare consensus / backbeat rescue を検証中。

### Crash

crash fallback / consensusを比較した結果、部品ベストは概ね:
- crash F1 約0.389
- precision 約0.58
- recall 約0.29

小節頭優先を維持するとprecisionは確保できるが、recallが低い。総合候補ではprecision重視のcrashを使用し、別部品としてrecall候補も保持する。

### Ride

rideは長く最大の弱点だったが、0検出状態は突破した。

1. ride consensus / grid:
   - ride F1 約0.03–0.05
2. ride song-gate:
   - TP 36 / predicted 121 / reference 644
   - precision 0.2975 / recall 0.0559 / F1 0.0941
3. ride seed-expand:
   - c109_radius8 は ride TP 56 / predicted 358 / reference 644
   - precision 0.1564 / recall 0.0870 / F1 0.1118
   - 総合F1は0.7102なので丸ごとは採用しないが、現時点のride部品として保持
   - final c111_seed3はride F1 0.0917だが、全体precisionとのバランスで探索系列内winner

曲別には:
- diamondvirgin: rideを一定量回収可能
- kaiju: expanded rideで改善するがreference 431に対しまだ大幅不足
- arcaround: rideをまだ拾えていない
- nanairo / ray: reference ride 0で、不要rideを出さないことを維持

Cycles 115–117では、予測由来の seed ride数 / hat数により tight / expanded / off を曲ごとに切り替える方式を検証中。

### Logging / reproducibility

自動ログ生成を導入済み。

- experiments/EXPERIMENT_LOG.md: 全result / 全cycle / 全candidateの人間向けログ
- experiments/experiment-log.json: params、script/commit、result commit、aggregate part metricsを保持
- experiments/validation-history.json: 生resultsへの索引
- experiments/component-bank.json: 総合敗者も含むパート別保持候補
- experiments/detailed-history/: 生成済みMIDIを標準評価器で再採点した全曲×全パート詳細データ

2026-09-22時点でEXPERIMENT_LOG生成workflowは成功しており、直近生成時は43 result files / 350 candidatesを収録した。今後の完了cycleも同じ形式へ追記する。


## Candidate selection non-regression policy

Cycles 97以降で、overall F1だけを見ると難しいパートを丸ごと消す候補が有利になる問題を確認したため、`experiments/selection_policy.py` にhard gateを追加した。

all-part baseへ昇格する候補は:
- 今回のtarget partを許容幅以上悪化させない。
- baselineでF1 >= 0.10の既存パートを0へ崩壊させない。
- 既存の意味のあるパートを原則0.05 F1以上悪化させない。
- baselineのtwo-limb violationが0なら0を維持する。
- FDRがsummaryに直接無い場合もTP/predictedから再計算してhat/pedal/crash/ride誤打音ペナルティを適用する。

条件に落ちた候補は削除せずcomponent bankへ残すが、all-part baseにはしない。

## Cycles 97–99 — structural pedal-hi-hat

hand-supported / poly-rescue / gap-repeatを比較し、periodicityと候補源も3案ずつ評価した。

旧scoreでは `c99_recall` がoverall **0.7203** で勝ったが、pedal-hatは:
- TP 11 / predicted 42 / reference 676
- precision 0.2619
- recall 0.0163
- F1 **0.0306**

baseline pedal-hat F1 0.3865から大幅悪化しているため、**all-part候補として不採用**。この結果がhard non-regression policy導入の直接理由。

## Cycles 100–102 — multi-detector ride consensus

3つの独立ride検出器を highres / intersection / 2-of-3 で比較した。

主結果:
- highres単独: ride TP151 / predicted1230 / F1 **0.1612**。誤爆が多くoverall 0.6606。
- 2-of-3: TP69 / predicted796 / F1 0.0958。まだ誤爆過多。
- intersection 35ms: TP14 / predicted79 / F1 0.0387。
- intersection + periodic 0.25: TP11 / predicted54 / precision 0.2037 / recall 0.0171 / F1 **0.0315**、overall 0.7176。

安全にrideを0から戻せたが現行baseを超えないため、ride componentとして保持。

## Cycles 103–105 — tom multi-model consensus

current tomを核に、RF / ExtraTrees / logisticのtom候補をfill文脈と合意で補完した。

Cycle 103:
- extra: tom F1 0.6550
- consensus: 0.5641
- fill: **0.6587**

Cycle 104:
- matching window 40/60/80msはいずれも同等。

Cycle 105:
- density3: tom F1 0.6215
- density5: 0.6587
- density7: **0.6667**

最終 `c105_density7`:
- overall F1 **0.7197**
- tom TP55 / predicted73 / reference92
- precision **0.7534**
- recall **0.5978**
- F1 **0.6667**
- 他パートはほぼ維持

よってtom部品として正式採用候補。

## Cycles 106–108 — song-confidence gated ride

高recall highres rideと安全なintersection rideの一致率を、参照MIDIを使わない曲単位confidenceとして利用した。

confidence:
- arcaround 0
- diamondvirgin 0.1214
- kaiju 0.0323
- nanairo 0
- ray 0.0147

Cycle 106 ratio gateでdiamondvirgin/kaijuを中心にrideを有効化:
- TP151 / predicted468
- precision 0.3226 / recall 0.2345 / ride F1 **0.2716**
- overall 0.7170

局所化・periodic supportを加えた最終 `c108_per50`:
- ride TP36 / predicted121 / reference644
- precision **0.2975**
- recall 0.0559
- F1 **0.0941**
- overall 0.7176
- hat F1 0.6715
- pedal-hat F1 0.3868

overallはcurrent baseより少し下がるため単独でbaseにはしないが、ride部品としては従来の安全候補より強い。

## Cycles 109–111 — guarded all-part fusion

Cycle 109で current base / +tom / +ride / +tom+ride を比較。全候補がhard non-regression gateを通過。

- base overall 0.7194, tom 0.6369, ride 0
- +tom overall 0.7197, tom **0.6667**
- +ride overall 0.7177, ride **0.0941**
- +tom+ride overall 0.7180, tom **0.6667**, ride **0.0941**

旧FDR計算前scoreではcoverageを優先して+tom+rideを選択したが、selection policyでFDR fallback計算の不足を発見したため再評価を実行中。

Cycle 110ではsnare base/pattern/vetoを比較。patternはsnare F1 0.8253だがkick→snare率が高い。

Cycle 111ではcrash precision/recall/zero-fallbackを比較。zero-fallbackはcrash F1 **0.3891**、ride/tomを含むcoverage candidateではoverall 0.7177。

最終winnerはFDR修正版selection policyで再判定する。

## Cycles 112–114 — additive snare with strict kick veto

base snareを変更せず、高recall pattern由来の「追加snare」だけを検討し、base kickと近い追加候補を禁止した。

最終 `c114_repeat3`:
- overall F1 **0.7200**
- snare TP1202 / predicted1486 / reference1470
- precision **0.8089**
- recall **0.8177**
- snare F1 **0.8133**
- kick→snare **45**

baseのsnare F1 0.8107 / recall 0.8014 / kick→snare42に対し、小さい誤分類増加でrecallとoverallを改善。高recall pattern版のkick→snare103より大幅に安全。

## Cycles 115–117 — kick-overlap-only hat cross-stem gate（実行中）

全hatをcross-stem版へ置換せず、base hatのうちpredicted kickと同時刻のものだけcross-stem支持を要求する。

目的:
- arcaroundの大量kick→hat誤認を狙い撃ち
- off-kickの正常hat刻みは現行のまま保持

Cycle 115: cross-stem support window 25/45/70ms  
Cycle 116: kick overlap window 20/35/55ms  
Cycle 117: removed hitのrepeat rescue 2/3/4 bars

## Cycles 118–120 — strongest-component fusion v3（実行中）

current baseに:
- tom `c105_density7`
- snare `c114_repeat3`
- ride `c108_per50` / `c102_per25`
- crash precision / recall / zero-fallback

を順次差し替える。

全cycleでhard non-regression policyとFDR fallback計算済みcanonical scoreを用いる。
