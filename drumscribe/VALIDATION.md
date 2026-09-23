# 採譜アルゴリズムの検証履歴

## 2026-09-23: 可変拍子のMIDI書き出し・全小節評価

検証ブランチで比較した `fullmix_meter_grid_gate_v22.py` の0.50案を、検証用3曲のfullmix音声から事前抽出したBeatThis小節頭と、ドラム音源から推定済みの打点を使う `meter.js` に移植。固定4/4グリッドに対する音声小節頭のずれが中央値0.5拍以上の場合だけ、3/4と4/4の動的計画法を使う。`chart.mid` は推定器とMIDI書き出しには渡さない。小節頭データのない2曲、およびユーザーが持ち込む音源は現状4/4のままであり、任意の伴奏ファイルをWeb画面で解析する処理は未実装。

既存の実Chromium生成MIDIの打点を入力して5曲のMIDIを再書き出し、元MIDIと打点の音高・ベロシティ・時刻が全曲完全一致することを確認。新MIDIを再読込して拍子イベントと全小節線を参照MIDIのテンポマップ・拍子変更・`song.json` のオフセット込みで採点した。生集計は [`results-meter-v23.json`](experiments/results-meter-v23.json)、試聴用MIDIは [`generated-meter-v23/`](experiments/generated-meter-v23/) に保存。試聴ページではこの候補に限り書き出しオフセットを逆補正する。

| 曲 | 小節頭平均誤差（拍） | 0.25拍以内の小節頭割合 | 推定3/4小節 | 誤った3/4小節 |
|---|---:|---:|---:|---:|
| arcaround | 0.0805 | 95.30% | 10 / 参照20 | 0 |
| diamondvirgin | 0.0101 | 100% | 0 | 0 |
| kaiju | 0.0094 | 100% | 0 | 0 |
| nanairo | 0.0628 | 100% | 0 | 0 |
| ray | 0.0005 | 100% | 0 | 0 |

5曲の曲別平均の平均は **0.0327拍**、小節頭の一致割合の平均は **99.06%**。arcaround の3/4再現率は **50%** で、残る10小節は改善対象。既存の打点は変えていないため、打点F1は旧実Chromium結果と同一の **0.815346**。この一周で実Chromiumから採譜を再実行した数値ではない。事前抽出した小節頭と学習・選定済みの5曲での採点であり、未知曲への一般化性能は示さない。

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
## 2026-09-22 — 聴取レビューを受けた候補145（採用前）

5曲×旧5候補と5曲×新5候補、計50件の添付レビューを確認した。旧候補の数値評価と自由記述が食い違う箇所もあるため、点数を性能の正解として扱わず、記述に繰り返し現れたキック付近のスネア誤認、ハイハットとシンバルの過剰な連打、ライドの位置を優先した。添付レビューの本文は公開しない。

[`human_review_guards.py`](experiments/human_review_guards.py) は候補144の音源由来MIDIと `song.json` のBPMだけから新候補を出力し、出力MIDIを再読込してから参照 `chart.mid` と照合する。スネア条件は曲名ではなく、キックと同時刻にあるスネアが1拍間隔で頻発するかで切り替える。ただしこれは同じ5曲のレビューと参照譜面を見て作った探索案で、未知音源への性能を保証しない。テンポ変化には未対応。

| 候補 | 5曲F1（80ms） | キック→スネア誤認（全曲） | アルクアラウンドの同誤認 | 同曲の正解スネアTP / 推定 |
|---|---:|---:|---:|---:|
| A / v6統合（元候補） | 0.7208 | 42 | 39 | 125 / 234 |
| F / スネア抑制 | 0.7210 | 21 | 18 | 118 / 200 |
| G / 連打も抑制 | 0.7245 | 21 | 18 | 118 / 200 |
| H / キック優先・強 | 0.7209 | 4 | 1 | 104 / 165 |

GはハイハットのTP / 推定が2851 / 4354から2846 / 4278へ、ライドは148 / 416から93 / 232へ変わる。ライドの誤音と同時に正しい音も55件失う。Hはキック周辺のスネア誤認をさらに減らすが、同曲の正しいスネアを21件失う。いずれも**聴取による再評価前であり、アプリの既定方式には採用していない**。比較用MIDIは [`generated-review-guards/`](experiments/generated-review-guards/) の `adaptive_snare` / `review_strict` / `kick_veto` に保存。全方式の曲別・楽器別結果は [`results-human-review-guards.json`](experiments/results-human-review-guards.json)。


## 2026-09-22 — BPM / beat / bar-grid auto estimation

ユーザー確認で、従来の生成MIDIはBPMと小節頭を自動推定せず、検証曲では `song.json` のBPMに依存していたことを確認した。以後、採譜入力として `song.json` / `chart.mid` を使わず、予測後の採点だけに使用するタイミング探索を追加した。

### BPM探索

音声のみから以下を順に比較した。

1. onset自己相関 / interval histogram / local consensus
2. snare recurrenceによるhalf/double tempo解消
3. snare recurrenceを粗BPMとし、全曲長のkick/snare phase coherenceとrobust grid fitで精密化
4. ブラウザ実装ではband近似差によるoutlierを、予測kick/snare event interval consensusで検出して再精密化

Python v3の5曲結果:
- arcaround: 132.0032 vs reference 132.0001
- diamondvirgin: 135.0754 vs 135.2012
- kaiju: 180.0068 vs 180.0050
- nanairo: 125.0069 vs 125.0300
- ray: 131.9999 vs 132.0001

real Chromium最終結果:
- mean BPM error **0.0230%**
- max BPM error **0.0931%**
- nanairoでは初回ブラウザ推定167.632 BPMをevent-family consensusが125.25側へ戻し、最終 **125.0064 BPM**。

### beat phase / bar head

beat phaseは予測kick eventのGaussian phase alignmentを基準とした。4/4のbar headは次を比較した。

- kick/snare共通周期
- kick=1/3拍・snare=2/4拍のrole構造
- crash template anchor
- kick/snare候補 + crash tie-break
- 最終ブラウザ版: snare parityが強い場合は2/4拍構造で候補を絞り、kick accentで1拍目/3拍目を選択。parityが弱い場合はlow-band measure-head energyへfallback。

real Chromium最終5曲:
- arcaround bar error **0.0325 beat**
- diamondvirgin **0.0407 beat**
- kaiju **0.2512 beat**
- nanairo **0.0082 beat**
- ray **0.0494 beat**
- mean **0.0764 beat**
- max **0.2512 beat**

書き出しMIDIでは検出bar phaseをMIDI measure boundaryへ移し、tempo meta eventと4/4 time-signature meta eventを付加する。検証5曲のexport grid residualは **0 beat**。

途中でbar-phase refactor時に `estimateBeatPhase()` 本体が消える実装欠落が発生した。JS構文チェックでは検出できなかったため復元し、real-browser validatorも「採譜できませんでした」を即時failureとして扱うよう変更した。最終real Chromium validationは成功。

タイミング修正後のブラウザ総合F1は **0.639**。これはタイミングの問題ではなく主に分類/過検出の差で、特にhat predicted/reference **1.457** が次の主要修正対象。


## Cycles 195–197 — browser core + retained ride/pedal component fusion

土台は実Chromiumで生成した `generated-v2-browser`。browser base は overall F1 **0.801947** で、kick/snare/hat/tom/crashは強い一方、pedal-hat F1 **0.3155**、ride F1 **0.2461** が弱かった。

別系列 `component-merge-v7` は総合では弱いが、pedal-hat F1 **0.5222**、ride F1 **0.3503** と金物部品が強いため、browser baseへ金物だけ差し替えるPDCAを実施した。全候補は実MIDIを書き出し、再読込後に `chart.mid` と照合。

Cycle 195 — 最低3案以上:
- browser base維持
- ride部品のみ
- pedal-hat部品のみ
- ride + pedal-hat

勝者は pedal-hat部品のみ。overall F1 **0.805448**。pedal-hat F1は **0.3155 → 0.5222**、hat/crashは維持。

Cycle 196 — ride差替え3案:
- ride-only
- hat+ride pair
- periodic rideのみ

`periodic` が勝者。rideは **TP174 / predicted356 / reference644**, precision **0.4888**, recall **0.2702**, F1 **0.3480**。hat pair全面置換はhat回帰のためguard不合格。

Cycle 197 — pedal-hat差替え3案:
- component pedal全採用
- periodic pedal
- browser pedal + component pedal merge

`c197_merge` が勝者。**新しい正式土台**:
- overall: TP **7784**, predicted **9221**, reference **10086**
- precision **0.84416**
- recall **0.77176**
- F1 **0.80634**
- kick→snare **2**
- two-limb violation **0**
- kick F1 **0.96257**
- snare F1 **0.88585**
- hat F1 **0.79559**
- pedal_hat F1 **0.55923**
- tom F1 **0.76243**
- crash F1 **0.45601**
- ride F1 **0.34800**

曲別の主要弱点:
- arcaround: snare F1 **0.597**, hat **0.482**, crash **0.049**, ride **0**, pedal_hat **0**
- diamondvirgin: snare **0.966**, ride **0.543** は強いがhat recall不足
- kaiju: kick/snare/hat/tomは非常に強い。crash **0.343**, ride **0.232** が弱い
- nanairo: overall **0.833**。snare precision不足
- ray: overall **0.889**。snare **0.983**, hat **0.907**, crash **0.905**, pedal_hat **0.715** と強い

生データ:
- `results-iterative-browser-component-fusion.json`
- `generated-search-browser-component-fusion/`

## 外部分類・構造補完の直近不採用結果

### GMD + frozen ADTOF metal classifier

外部GMD rock/punkのみで学習した4クラス分類器は、外部validationでは:
- hat F1 **0.955**
- pedal_hat **0.864**
- ride **0.909**
- crash **0.679**

しかしDruMaster 5曲へ既存hat/rideの再ラベル用途で転移すると、固定4案・nested LOOともほぼbrowser baseから変化しなかった。DruMaster上でtrue rideがhatとして出ている事例の多くを依然hatと判定しており、分布差が大きい。

したがって **外部分類器単独のhat↔ride置換は不採用**。表現特徴は補助特徴として保持する。

生データ:
- `results-gmd-adtof-metal-logreg.json`
- `results-browser-gmd-adtof-metal-transfer.json`
- `generated-gmd-adtof-metal-transfer/`

### ADTOF structural crash augmentation

browser base crash:
- TP127 / predicted167 / reference390
- precision **0.7605**
- recall **0.3256**
- F1 **0.4560**

小節頭 + generic cymbal activation + kick/fill条件を多数探索したが、最良固定案でも TP **+1** 程度、crash F1 **0.4588**。nested LOOでは逆にF1 **0.4374**へ低下。

**現行crashを維持**。単純な構造追加はほぼ頭打ち。

### ride-state / ride-section propagation

nested LOO ride-stateは ride predicted407 / TP0 となり失敗。
ADTOF section propagationも ride TP153 / predicted678 / F1 **0.2315** で、rayにreference 0にもかかわらず252 rideを生成する重大な誤検出があった。

したがって全面的なride section置換は不採用。rideは c197 の periodic component（F1 **0.3480**）を現時点の部品ベストとして保持する。

### MDX6 separated metal — kaiju単曲診断

MDX6/DrumSep型6ステムはkaijuで:
- baseline F1 **0.763**
- best candidate F1 **0.789**
- crash: TP30/pred30 → **TP73/pred74**
- ride: 0 → **TP18/pred22**（別設定ではTP33/pred38）

分離自体には金物候補生成源として明確な価値がある。一方、1曲の分離だけで約682秒、全処理約1073秒と重い。またride recallは依然低い。

結論: **全パート置換には使わず、将来のcrash/ride補完専用候補として保持**。ブラウザ必須経路にそのまま載せるのは現時点では非現実的。\n

## Cycles 198–224 — browser hat / pedal再統合と44.1 kHz nested-LOO hat分類

Cycle 197以後の結果JSON/生成MIDIを再確認し、未記録だった後半系列を補足した。ここでいうLOO/nested-LOOは、held-out曲の `chart.mid` を予測器の学習・閾値選択に使わず、最終採点だけに使う。

### Cycles 198–200 — hat meta LOO

`results-iterative-hat-meta-loo.json`:
- Cycle 198: logistic
- Cycle 199: threshold探索
- Cycle 200: repeat rescue
- 最終 overall F1 **0.807468**
- hat F1 **0.798064**
- hat FDR **0.139108**

hat precisionは上がったが、曲別worst F1が悪化するため、この系列単独を最終土台にはしない。

### Cycles 207–209 — prediction-density adaptive hat

`results-iterative-hat-adaptive-v2.json`:
- whole-song hat/kick ratio 1.2 / 1.5 / 1.8
- local 8-bar ratio
- block size 4 / 8 / 16 bar
- cross-cycle best overall F1 **0.808955**
- hat F1 **0.801860**

この時点のwhole-song判定では arcaround のhat/kick比 **0.6593**、diamondvirgin **0.3441** のため、1.2以上の高密度曲だけがfilter対象だった。arcaroundのhat過剰はこのguardでは残った。

### Cycles 210–212 — pedal sparse gate

`results-iterative-pedal-sparse-gate.json`:
- cross-cycle overall F1 **0.806967**
- pedal_hat F1 **0.565476**
- hat F1 **0.795587**

pedal部品としては改善し、後段のbest-mergeで再利用する。

### Cycles 213–215 — multiclass hat LOO

`results-iterative-hat-multiclass-loo.json`:
- overall F1 **0.809006**
- hat F1 **0.801969**
- hat FDR **0.144515**

改善幅は小さく、単独でbest-mergeを置き換えるほどではなかった。

### Cycles 216–218 — best merge v8

`results-iterative-best-merge-v8.json`:
- Cycle 216: hat / pedal / bothを比較。bothが勝者
- Cycle 217: hat threshold 1.2 / 1.5 / 1.8
- Cycle 218: pedal minimum count 5 / 20 / 50
- cross-cycle best overall: TP **7752**, predicted **9062**, reference **10086**
- precision **0.855440**
- recall **0.768590**
- F1 **0.809693**
- hat F1 **0.801860**
- pedal_hat F1 **0.566964**
- kick→snare **2**
- two-limb violation **0**

この時点のcanonical scoreは **0.583224**。

### 44.1 kHz hat ExtraTrees size sweep

`results-browser-hat-44k-size-loo.json` は `generated-v2-browser` を土台に、44.1 kHzのスペクトル + browser-native rhythm特徴を使うExtraTreesをfully nested LOOで比較した。

medium (160 trees / depth 12 / min leaf 4):
- overall F1 **0.804157**
- hat precision **0.857380**
- hat recall **0.754754**
- hat F1 **0.802800**

micro 32-treeでもhat F1 0.800207まで出ており、将来のbrowser model軽量化候補として残す。

### Cycles 219–221 — nested 44.1 kHz hat fusion v9

`results-iterative-hat-nested-fusion-v9.json`。

Cycle 219（最低3案）:
- classifier hat全面replace
- current hatとのintersection
- union
- 変更なしbaseもguard用に併記

Cycle 220:
- micro / medium / full forest

Cycle 221:
- no repeat rescue
- repeat 0.75 + 35 ms
- repeat 1.00 + 60 ms

Cycle 221 `c221_rep100_w60`:
- overall F1 **0.811196**
- hat TP **3032** / predicted **3427** / reference **4102**
- hat precision **0.884739**
- hat recall **0.739152**
- hat F1 **0.805419**
- hat FDR **0.115261**
- hat worst-song F1 **0.404211**
- canonical score **0.584611**

aggregateでは改善したが、diamondvirginのhatを削り過ぎ、hat worst-song F1がbaseの0.473526から0.404211へ低下。したがって全曲一律適用は最終採用しない。

### Cycles 222–224 — low-density guard v10

`results-iterative-hat-density-guard-v10.json`。

Cycle 222は、Cycle 221のnested filterを使うかどうかを**予測MIDIだけから得る whole-song hat/kick比**で決める。曲名ルールやtarget chartは使用しない。

比較:
- threshold 0.45
- threshold 0.55
- threshold 0.65

5曲では3閾値が完全に同一出力になった。理由はbase比率が:
- arcaround **0.6593** → filter ON
- diamondvirgin **0.3441** → filter OFF
- kaiju **1.5359** → ON
- nanairo **2.2716** → ON
- ray **2.2215** → ON

となり、0.45–0.65の全候補でON/OFF集合が同じため。結果JSON上は0.65がwinnerだが、**0.65自体が他の2値より優れている証拠ではなくtie**である。

Cycle 222 whole-song guard:
- overall TP **7725** / predicted **8900** / reference **10086**
- precision **0.867978**
- recall **0.765913**
- overall F1 **0.813758**
- hat TP **3077** / predicted **3478** / reference **4102**
- hat precision **0.884704**
- hat recall **0.750122**
- hat F1 **0.811873**
- hat FDR **0.115296**
- hat worst-song F1 **0.473526**
- canonical score **0.587469**
- kick→snare **2**
- two-limb violation **0**

base Cycle 216–218のoverall F1 0.809693 → **0.813758**、hat F1 0.801860 → **0.811873**、hat FDR 0.147253 → **0.115296**。worst-song hat F1は **0.473526** を維持した。

Cycle 223のlocal 8-bar guardとCycle 224の4/8/16-bar比較は、diamondvirginの一部区間を再び削り、hat F1 0.8055–0.8069程度へ回帰したため不採用。**whole-song low-density guardを現時点の評価上の最良候補とする。**

workflow初回2回は依存パッケージ不足（numpy、次にscipy）で採譜処理開始前に停止した。workflowを修正し、3回目は全candidate生成・MIDI再読込・採点・結果commitまで成功した。失敗runはアルゴリズム結果として数えない。

生成物:
- `results-iterative-hat-nested-fusion-v9.json`
- `generated-search-hat-nested-fusion-v9/`
- `results-iterative-hat-density-guard-v10.json`
- `generated-search-hat-density-guard-v10/`

注意: Cycles 219–224は**offline検証アルゴリズムの更新**であり、44.1 kHz ExtraTrees本体はまだ `transcribe.js` のbrowser production pathへ移植していない。公開アプリの精度がこの数値へ更新済みという意味ではない。
\n


## Cycles 225–227 — production-deployable fixed-threshold 44.1 kHz hat filter

Cycles 219–224のnested-LOOでは、held曲ごとに「他4曲だけ」を使って確率閾値を選んでいた。評価リークではないが、未知曲のproductionでは曲ごとの最適閾値を選べないため、Cycles 225–227では**全held曲で同一の固定確率閾値・repeat rescue・時間窓・density guard**を使う条件へ厳しくした。各held曲のExtraTrees学習は他4曲のみ、held `chart.mid` は最終採点のみ。

`results-iterative-hat-fixed-threshold-v11.json`。

Cycle 225 — medium forest、固定probability threshold:
- 0.35: overall F1 0.811694 / hat F1 0.806771 / hat FDR 0.134153
- 0.45: overall F1 0.812795 / hat F1 0.809486 / hat FDR 0.124929
- 0.55: overall F1 0.812767 / hat F1 0.809379 / hat FDR 0.113722
- 0.65: overall F1 0.807046 / hat F1 0.794747 / hat FDR 0.106273

overall F1だけなら0.45が僅かに高いが、canonical scoreは0.55が **0.586994** で最良。以後0.55を採用。

Cycle 226 — model capacity（probability 0.55固定）:
- micro 32 trees: overall 0.807884 / hat 0.796926 / canonical 0.584502
- small 96 trees: overall 0.812355 / hat 0.808336 / canonical 0.586814
- medium 160 trees: overall **0.812767** / hat **0.809379** / canonical **0.586994**
- full 260 trees: overall 0.812662 / hat 0.809114 / canonical 0.586916

精度優先ではmedium 160-tree。96-treeとの差は小さいので、productionでモデルサイズ/速度が問題になった場合の軽量fallbackとしてsmallを保持する。

Cycle 227 — temporal rescue/window:
- repeat 0.75 / 35 ms: overall 0.812428 / hat 0.808577
- repeat 1.00 / 60 ms: overall **0.812767** / hat **0.809379**
- repeat 1.00 / 80 ms: 60 msとこの5曲では同一出力
- rescueなし: overall 0.802768 / hat 0.783474

production候補の固定設定:
- ExtraTrees medium: 160 trees, max_depth 12, min_samples_leaf 4
- global probability threshold **0.55**
- repeat rescue **1.00**
- intersection window **60 ms**
- whole-song hat/kick density guard **0.55**

5曲aggregate:
- overall F1 **0.812767**
- hat TP **3055** / predicted **3447** / reference **4102**
- hat precision **0.886278**
- hat recall **0.744759**
- hat F1 **0.809379**
- hat FDR **0.113722**
- hat worst-song F1 **0.473526**
- canonical score **0.586994**

これはheld-out LOOの性能値であり、未知曲に使える固定ルールへ落とした後の値。held曲別閾値を許したCycle 222の0.813758より僅かに低いが、production実装条件としてはこちらを採用する。

注意: この数値はc216統合MIDI（土台に後段ride/pedal部品を含む）上のoffline評価。公開browser `transcribe.js` はまだこの44.1 kHz ExtraTrees、およびc216の全ride/pedal統合を再現していない。production browserの性能として0.812767を主張しない。



## 2026-09-23 — c225–227 production条件の実Chromium完走確認

Cycles 225–227で固定した44.1 kHz hi-hat ExtraTrees production条件を、実際の `drumscribe/transcribe.js` に統合し、real Chromiumで5曲を `drums.mp3 -> MIDI` 生成してから `chart.mid` と再照合した。

統合直後の最初のbrowser validationは採譜アルゴリズムの重さではなく実装不具合で失敗した。

- `transcribe.js` 先頭のimport間に改行ではなくリテラル `\\n` が混入し、moduleがロードされずAnalyze有効化待ちでtimeout。
- これを修正後、`pruned` を `const` で宣言したままhigh-res hat結果を再代入しており、`Assignment to constant variable` で停止。
- `pruned` をmutable bufferへ修正。
- JS syntax workflow成功。
- real Chromium workflowで5曲のMIDI生成、参照比較、結果commitまで成功。

### 実browser結果

旧real-browser baseline:
- TP **7495** / predicted **8606** / reference **10086**
- precision **0.8710**
- recall **0.7431**
- F1 **0.801947**
- hat TP **3163** / predicted **3829** / reference **4102**
- hat precision **0.826064** / recall **0.771087** / F1 **0.797630**
- hat FDR **0.173936**

44.1 kHz fixed-threshold hat filter統合後:
- TP **7449** / predicted **8186** / reference **10086**
- precision **0.909968**
- recall **0.738548**
- F1 **0.815346**
- hat TP **3117** / predicted **3409** / reference **4102**
- hat precision **0.914344**
- hat recall **0.759873**
- hat F1 **0.829983**
- hat FDR **0.085656**
- kick→snare **2**
- snare→kick **28**

旧browserからの差分:
- overall F1 **+0.013399**
- overall precision **+0.039064**
- overall recall **-0.004561**
- predicted notes **-420**
- TP **-46**
- hat F1 **+0.032353**
- hat precision **+0.088280**
- hat recall **-0.011214**
- hat FDR **0.173936 -> 0.085656**

hat以外のkick / snare / tom / crash / ride / pedal-hatの集計値は旧browser baselineから変化していない。したがって今回のoverall改善は、主に不要hatを削った効果。

曲別hat F1:
- arcaround: **0.482353 -> 0.507881**
- diamondvirgin: **0.484127 -> 0.484127**（hat/kick density guardでfilter非適用）
- kaiju: **0.869702 -> 0.910941**
- nanairo: **0.859347 -> 0.913043**
- ray: **0.907052 -> 0.928811**

production filterの実際の発動:
- arcaround: 387 -> **278** hats
- diamondvirgin: 253 -> **253** hats（low-density skip）
- kaiju: 680 -> **585** hats
- nanairo: 1141 -> **1007** hats
- ray: 1368 -> **1286** hats

BPM/bar推定は従来browser validationと同一:
- mean BPM error **0.023032%**
- max BPM error **0.093078%**
- mean bar error **0.076402 beat**
- max bar error **0.251224 beat**
- export grid residual max **0 beat**
- 全MIDI 4/4 time signature付与確認

### 採用判定

今回の実browser統合版を、旧browser版より良いproduction実装として残す。hat以外を悪化させず、hat F1とFDR、overall F1が改善したため。

ただしこのreal-browser 5曲値 **0.815346** は、Cycles 225–227でproduction hyperparameterをLOO選定した後、最終配布モデルを5曲全体で再学習した重みを同じ5曲に適用した値であり、未知曲への独立推定値ではない。未知曲相当のheld-out指標としては、固定production ruleのLOO値 **overall F1 0.812767 / hat F1 0.809379** を引き続き採用する。

今回の一周では新しいアルゴリズム系列へ進まず、c225–227で既に選抜済みのproduction候補を実browserで成立させるところまでで停止する。

## 2026-09-23: kick / snare / tom 優先のproduction補正

ユーザー判断により、金物より **バスドラム・スネア・タムの採譜を優先**する。既存production browser（44.1 kHz hat filter統合後）を基準に、kick/snare/tomを個別に確認してから限定的な後処理を追加した。参照 `chart.mid` は予測生成には使用せず、仮説の失敗分析と生成後の採点だけに使用した。

### 変更前の実browser基準

|Part|TP / Pred / Ref|Precision|Recall|F1|
|---|---:|---:|---:|---:|
|kick|2636 / 2765 / 2712|0.953345|0.971976|0.962571|
|snare|1261 / 1377 / 1470|0.915759|0.857823|0.885845|
|tom|69 / 89 / 92|0.775281|0.750000|0.762431|

曲別では `arcaround` のsnareが 131 / 147 / 292 と再現率不足、tomが 7 / 22 / 12 と過検出だった。一方 kaiju のtomは 22 / 22 / 23 で良好だったため、全曲共通のtom閾値強化は避けた。

参照MIDIの同一tick共起を確認すると、kick+tomは5曲合計4回（arcaround 1、diamondvirgin 3、kaiju/nanairo/ray 0）なのに対し、kick+snareは arcaround 172、diamondvirgin 13、kaiju 3、nanairo 103、ray 133 回あった。したがって kick と tom の衝突は誤認抑制材料として使いやすいが、kick と snare を相互排他にするのは不適切と判断した。

### 仮説A: kick bleedによる弱いtomだけを除去

ADTOFのtomがkickから30 ms以内にあり、tom run（45–240 ms内の別tom）にも属さず、tom confidence < 1.45 の場合だけ除去する。強いtomと連続tomは残す。

実Chromium 5曲再生成後:

- kick: 変更なし
- snare: 変更なし
- tom: **69 / 84 / 92**
- tom precision: **0.821429**
- tom recall: **0.750000**
- tom F1: **0.784091**
- arcaround tom: 7 / 22 / 12 → **7 / 17 / 12**

5件のfalse positiveを除去し、true positiveは失わなかったため採用。

### 仮説B: 同時kickに埋もれたsnareを低閾値ADTOFから限定救済

通常snare閾値は維持したまま、ADTOF内部から低閾値snare候補を別ストリームとして取得する。直接出力はせず、以下をすべて満たす場合だけ追加する。

- low-threshold snare scale: **0.50**
- 既存snareから35 ms以内に無い
- kickから40 ms以内
- song-level rescue density = low candidates / base snares >= **1.24**
- song-level snare/kick count ratio <= **0.30**
- activation >= **0.12**
- activation >= **0.25 × 同時kick activation**
- 同じ16分位置の低閾値候補が近傍±8小節内に **2件以上**ある

このsong-level gateは現5曲では arcaround のみ発火した（rescue density 1.2721、snare/kick 0.2504）。他4曲は変更しなかった。

周回結果:

|Round|変更|arcaround snare TP / Pred / Ref|5曲snare F1|判断|
|---|---|---:|---:|---|
|1|rescue scale 0.86、保守条件|131 / 147 / 292|0.885845|候補不足、追加0|
|2|rescue scale 0.50、density gate 1.40|131 / 147 / 292|0.885845|候補187件まで増えたがgate不発|
|3|density gate 1.24、同位置反復3件|139 / 155 / 292|0.888967|追加8件が8件ともTP|
|4|同位置反復2件|**143 / 159 / 292**|**0.890521**|追加12件が12件ともTP、採用|

最終5曲snareは **1273 / 1389 / 1470**、precision **0.916487**、recall **0.865986**、F1 **0.890521**。kickは **F1 0.962571のまま不変**、tomは **F1 0.784091**を維持した。

現行hat等も含む最終実browser全体は **TP 7461 / Pred 8192 / Ref 10086、precision 0.910767、recall 0.739738、F1 0.816391**。今回の採用判断はoverallだけでなく、最優先のkick/snare/tomが悪化していないことを条件にした。

### production反映

- `drumscribe/adtof.js`: 低閾値snare候補ストリームを追加。通常イベントには直接混ぜない。
- `drumscribe/transcribe.js`: song-adaptive layered snare rescue と weak isolated kick/tom veto を追加。
- 検証ブランチでreal Chromium 5曲生成・比較を完走後、`main` へ反映した。

この5曲を見ながらルールを選定しているため、未知曲で同じ改善幅を保証しない。特にsnare rescueのsong-level gateは未知曲での誤発火を今後追加曲で検証する必要がある。

