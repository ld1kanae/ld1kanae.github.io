# DrumScribe AI Handoff

## CURRENT AUTHORITATIVE STATUS — Ride→Open HH threshold UI merge (2026-09-24)

ユーザー向けUIでは `Ride→Open HH` と `Ride文脈→Open HH` を別表示しない。両者は内部的には別段階（音色モデル側の約0.60 gate / context-choke rescue側の0.99 gate）だが、最終動作はいずれも Ride候補をOpen HHへ丸めるため、UIは **「Ride→Open HH（音色＋文脈）」1項目** に統合する。

`app.js` ではUIの `rideOpen` 倍率を読み、`rideContextOpen=rideOpen` として同じ倍率を両内部gateへ渡す。デフォルト1.0なら従来閾値を変更しない。

## CURRENT AUTHORITATIVE STATUS — Pedal HH output collapse (2026-09-24)

ユーザー要件: **Closed HH と Pedal HH は採譜出力上で区別しない。Pedal HH候補も Closed HH (GM42) として丸める。**

実装方針:
- 内部では pedal_hat をOpen-HH choke/contextや手足制約の補助情報として保持してよい。
- 最終 `transcribe()` 出力では `pedal_hat -> group:'hat', note:42` に正規化する。
- MIDIにGM44を出さない。
- UIの「ペダルHH」閾値倍率は削除。ユーザーに独立クラスとして見せない。
- 結果サマリーのClosed HH数には内部pedal_hat由来のGM42も含め、Pedal HH個別カウントは表示しない。

## CURRENT AUTHORITATIVE STATUS — User threshold multipliers (2026-09-24)

ユーザー調整用の「採譜感度を調整」を production UI に追加。全項目のデフォルトは **1.0** で、1.0時は既存閾値を変更しない。

UI範囲は 0.50–1.50 / step 0.05。原則として倍率を上げるほど判定を厳しくし、下げるほど拾いやすくする。BPM推定のための旧spectral detectorやtiming windowは変更しない。

現行キー:
- K/S/T: `kick`, `snare`, `snareRescue`, `egmdSnare`, `tom`
- metal: `hat`, `hatCollision`, `hatFilter`, `openHat`, `rideOpen`, `rideContextOpen`, `openHatOverlay`, `pedalHat`, `cymbal`, `cymbalGate`

主な適用先:
- `adtof.js`: kick/snare/tom/hat/cymbal activation threshold、低閾値snare rescue、E-GMD snare model gate
- `transcribe.js`: snare rescue floor、hat collision suppressor、pedal-hat score gate、Crash post gate、各hat分類器への倍率受け渡し
- `hat-forest.js`: high-resolution hat probability threshold
- `open-hat.js`: Closed/Open probability threshold、Ride→Open threshold、overlay rescue probability/score gates
- `hat-context-v57.js` 呼び出し: production Ride-context→Open threshold 0.99 に倍率を適用

実装上、UI値は `app.js` で `thresholdMultipliers` として `transcribe()` に渡す。解析結果の `globalThis.__drumscribeResult.thresholdMultipliers` にも保存する。

静的構文検査は app/adtof/transcribe/hat-forest/open-hat の全変更ファイルで通過。現時点では倍率1.0のfresh 5曲browser回帰はまだ実施していないため、精度非退行の最終確認は別途必要。

## CURRENT AUTHORITATIVE STATUS — Hi-Hat context production v58 (2026-09-24)

- production `transcribe.js` now imports `hat-context-v57.js` and enables `global-ride-rescue-v57` by default after the existing open-hat + sequence stages.
- portable gate: generated Ride candidates < 24 => exact no-op. Otherwise only global synchronized-corpus Open probability >= 0.99 is changed from Ride to Open HH.
- runtime inputs are audio + generated candidates only. `chart.mid` is never read during prediction.
- Arcaround reference Ride notes are arrangement-only for the current HH objective. Evaluation masks reference Ride zones (±80 ms) for Arcaround and does not use Arcaround Ride F1 for adoption.
- v54 full replacement failed badly (HH macro about 0.723 -> 0.580); do not use full 42/46 replacement.
- v55 song-held-out additive rescue succeeded. Best high-confidence Ride-only rescue improved HH macro from about 0.72309 to 0.74031.
- v56 adds a reference-free Ride-count domain gate. With Arcaround Ride masking, held-out p>=.99 + min 24 Ride candidates changed only diamondvirgin and improved HH macro **0.725598 -> 0.743121 (+0.017523)**. Other four songs were unchanged.
- portable global model replay on the same fresh browser candidates changed 170 diamondvirgin Ride candidates: reference matches within ±80 ms = 79 Open, 87 Ride, 2 Closed, 1 Crash, 1 unmatched. Under the project rule that Ride may be rounded to HH, this is acceptable.
- exact five-song replay using the global model + min24/p>=.99 gate:
  - Closed F1 **0.848910 -> 0.848910**
  - Open F1 **0.602285 -> 0.628817**
  - HH macro **0.725598 -> 0.738864 (+0.013266)**
  - collapsed Hat/Ride onset F1 **0.813038 -> 0.813038**
  - Kick/Snare/Tom: exact non-regression
  - per-song HH macro: Arcaround/Kaiju/Nanairo/Ray unchanged; diamondvirgin **0.505017 -> 0.597619**
- production integration commit: `86edf8fe336a18589e5d3c7a87636526a281757c`.
- while wiring v58, malformed ternaries already present in concurrent Crash code and one literal `\\n` import separator caused browser syntax failures. They were repaired in commits `05cdd186...`, `9f741001...`, and `daadf426...`.
- direct fresh Chromium production-vs-off validator:
  - `experiments/browser_hat_context_production_v58.mjs`
  - `experiments/evaluate_hat_context_production_v58.py`
  - workflow `.github/workflows/drumscribe-hat-context-production-v58.yml`
  - latest run at this handoff update: `35879732718`, queued because GitHub Actions concurrency was saturated. Do not claim fresh v58 PASS until that run (or a rerun at the same logic) completes successfully.
- older “CURRENT AUTHORITATIVE STATUS — Open/Closed Hi-Hat v47” below is historical and is superseded by this section for current production state.

Key result files:
- `experiments/results-sync-hat-corpus-v53.json`
- `experiments/results-hat-context-runtime-v54.json`
- `experiments/results-hat-context-heldout-v55.json`
- `experiments/results-hat-context-portable-gate-v56.json`
- pending fresh production result: `experiments/results-hat-context-production-v58.json`


## 2026-09-23 E-GMD domain calibration v45 / Open-hat strict v46

### K/S/T domain calibration v45

目的:
- E-GMD probabilityの絶対閾値ではなく、曲内・楽器内rank / robust-zでdomain shiftを補正。
- fixed v39Dの既存9 TP / 0 FPは必ず保持し、追加救済だけ許可。

結果:
- fixed v39D: KST F1 0.938852, 9 TP / 0 FP
- C1 rank extreme: 0.938852, 9 / 0
- C2 robust extreme: **0.938976**, **10 TP / 0 FP**
  - diamondvirgin Kick 219.05sを1音追加で正解救済
  - Kick F1 0.963139 -> **0.963328**
- C3 soft-rank LOOCV: 0.938852, 9 / 0

判断:
- 曲内robust calibration自体には有効信号あり。
- ただし改善したC2はhand-set static heuristicで、song-held-out C3では追加救済0。一般化確認前なのでproduction未採用。
- 次回はC2条件を新曲/外部holdoutで再確認するか、held-outで学べるだけのpaired songを増やす。

資産:
- `experiments/ARRANGEMENT_DOMAIN_CALIBRATION_V45.md`
- `experiments/results-arrangement-domain-calibration-v45.json`

### Open-hat default vs combined v46

fresh browserでstrict Rideを含めて再採点。

| variant | Closed F1 | Open F1 | Ride F1 | Hat macro | Metal macro incl Ride | collapsed hat/ride onset F1 |
|---|---:|---:|---:|---:|---:|---:|
| default decay-rescue | 0.843895 | 0.598647 | 0.246117 | 0.721271 | 0.562886 | 0.812081 |
| ride-open-decay-rescue | 0.843895 | **0.647770** | **0.000000** | 0.745832 | 0.497222 | 0.817466 |

解釈:
- Open F1 +0.0491 / hat macro +0.0246 は大きい。
- しかしcombinedはride候補をall-to-openで丸めるためRide F1が0になり、metal macroは -0.0657。
- Open改善のかなりの部分がRide->Open relabeling。**combined v46はproduction不採用**。
- collapsed onset F1は +0.0054 なので、onset検出自体には改善余地あり。
- 次の有望方向は「Rideを全部Openへ変える」のではなく、Rideを維持しつつ、強いOpen音響証拠 + decay + repeated articulation evidenceがある候補だけ42/46再分類すること。

資産:
- `experiments/OPENHAT_DEFAULT_VS_COMBINED_V46.md`
- `experiments/results-openhat-default-vs-combined-v46.json`

## CURRENT AUTHORITATIVE STATUS — Open/Closed Hi-Hat v47

- production既定: `ride-open-decay-rescue`
- 音響減衰 + open-run救済 + Ride→Open HH丸めを採用
- 5曲fresh Chromium: HH macro F1 **0.719507 → 0.745832**、Open F1 **0.595722 → 0.647770**
- K/S/T非退行
- A/A'による42/46再判定は悪化したため不採用
- strict Ride精度は意図的に優先しない。下記v46節は、Ride保持を優先した場合の過去評価であり、現行方針を上書きしない
- Diamond Virgin完全同期対照の識別情報・検証結果: `experiments/reference-sync/README.md`

## 2026-09-23 Open Hat / Ride strict check v46 — historical strict-Ride evaluation

Open F1が大きく伸びた `ride-open-decay-rescue` を、Closed/OpenだけでなくRideも含めfresh browser再評価。

Default `decay-rescue`:
- Closed F1 0.843895
- Open F1 0.598647
- Ride F1 0.246117
- Hat macro 0.721271
- metal macro (Closed/Open/Ride) 0.562886
- collapsed Hat/Ride onset F1 0.812081

`ride-open-decay-rescue`:
- Closed F1 0.843895
- Open F1 0.647770 (+0.049123)
- **Ride F1 0.000000 (-0.246117)**
- Hat macro 0.745832 (+0.024561)
- **metal macro 0.497222 (-0.065665)**
- collapsed onset F1 0.817466 (+0.005385)
- K/S/T delta 0 / 0 / 0

当時のstrict-Ride評価:
- Open改善のかなりの部分は既存RideをOpenへ丸めたことによる。
- Rideを独立クラスとして守る評価軸ではmetal macroが低下した。
- その後、ユーザー要件としてRide識別を優先せずOpen/Closed HHへ丸めてよいことが明示されたため、この不採用判断はv47で上書きされた。
- 現行productionは `ride-open-decay-rescue`。

詳細:
- `experiments/OPENHAT_DEFAULT_VS_COMBINED_V46.md`
- `experiments/results-openhat-default-vs-combined-v46.json`

## 2026-09-23 E-GMD song-local domain calibration v45 — research candidate

v44で確認したE-GMD domain shiftを、曲内候補分布だけでreference-free calibrationできるか検証。

原則:
- production採用済みfixed v39Dの9 TP / 0 FPは必ず保持
- E-GMD calibrationは追加候補だけに使用し、v39D救済をvetoしない
- song/group内E-GMD probability rank、logit probabilityのmedian/MAD robust z、acoustic confidence rank、GMD slot liftを利用

結果:
- fixed v39D: KST F1 0.938852, +0.001118, 9 TP / 0 FP
- C1 percentile extreme: 同値
- **C2 robust extreme: KST F1 0.938976, +0.001242, 10 TP / 0 FP**
- C3 soft-score song-LOOCV: fixed v39Dと同値

C2の追加1音:
- diamondvirgin Kick 219.05 s
- E-GMD raw p=.9125 / external threshold=.40
- acoustic confidence=2.0190
- GMD slot lift=2.5040
- A/A' supportは0（family H単発）
- referenceではTP

判断:
- domain calibration自体は有効性あり。
- ただしC2閾値は固定仮説でありsong-held-outで追加救済を再現したものではない。C3 LOOCVは追加0。
- **現時点ではproductionへ自動採用しない**。次にfresh runtime統合する場合は、このKickがなぜbaseline後段で落ちたか確認し、post-filter-origin guardを追加してから行う。

資産:
- `experiments/ARRANGEMENT_DOMAIN_CALIBRATION_V45.md`
- `experiments/results-arrangement-domain-calibration-v45.json`

## 2026-09-23 Arrangement + E-GMD KST v44-v48 — production v46R1採用

E-GMD v4の外部音響reclassifierを5曲の低閾値K/S/T候補へ付与し、A/A' fixed rescoringとの統合を検証。

外部E-GMD v4:
- training candidate total 18,936
- Kick 4,422 / Snare 6,580 / Tom 7,934
- E-GMDモデルはDruMaster chartを見ずに凍結済み

v44:
- E-GMD acoustic-onlyはK/S/T F1 0.933968で悪化。不採用。
- A/A' + E-GMDをmandatory gateにすると0.938231でfixed v39D 0.938852未満。不採用。
- 理由: fixed v39Dの正解候補の一部はE-GMD probabilityが低く、E-GMDを必須条件にすると良い救済を落とす。

v45 residual Snare:
- fixed v39Dを凍結し、その後に残ったSnare候補だけE-GMDで追加救済。
- residual pool 63 / recoverable positive 9。
- Extra Trees song-LOOCV: K/S/T F1 0.939100、fixed比 +0.000248、11 TP / 0 FP。

v46 portable R1:
- Extra Treesのheld-out傾向を小さいruntime gateへ圧縮。
- residual Snare条件: E-GMD p>=0.93 / acoustic confidence>=0.55 / GMD snare slot lift>=1.65。
- fixed v39Dへadditive-only。Kick/Tomは変更しない。
- 5曲dev上: K/S/T F1 **0.939224**、Snare F1 **0.903070**、12 TP / 0 FP。
- 追加のresidual Snareは arcaround 204.44s、ray 67.74s / 247.74s の3音。
- **注意:** R1条件はv45の同じ5曲を観察した後に仮定したため、未知曲一般化の独立証拠ではない。

v47 fresh runtime:
- baseline K/S/T 0.937734
- V39D 0.938852
- V46R1 **0.939224** (+0.001490 vs baseline)
- Kick 0.963139 / Snare **0.903070** / Tom 0.790960
- all-class F1 **0.819080**
- rescued 12 (A/A' family 9 + E-GMD residual Snare 3)
- max grid residual 0 / hand-grid violation 0 / meter change none
- two-hand guardなしvariantと結果同一。productionではguardを維持。

v48 actual production UI:
- `index.html -> app.js` の実経路で5曲を選択・offvocal自動読込・採譜・MIDI downloadまでfresh Chromium実行。
- policy `family-gmd-plus-egmd-residual-v46r1` を全曲で確認。
- exported MIDI TP/pred/refがv47と完全一致。
- K/S/T F1 **0.939224** / all F1 **0.819080** / rescued 12 / residual Snare 3。

現行runtime:
- `arrangementKstPolicyCurrent = arrangementKstPolicyV46R1`
- offvocal/伴奏がある場合のみ arrangement KST assistを使用。未指定時は従来baseline。
- chart.midはpredictionで読まない。

詳細:
- `experiments/ARRANGEMENT_EGMD_FUSION_V44.md`
- `experiments/ARRANGEMENT_EGMD_RESIDUAL_V45.md`
- `experiments/ARRANGEMENT_EGMD_PORTABLE_V46.md`
- `experiments/ARRANGEMENT_KST_V47.md`
- `experiments/ARRANGEMENT_APP_V48.md`

## 2026-09-23 Arrangement + E-GMD KST fusion v44 — production据え置き

目的:
- frozen E-GMD v4 acoustic reclassifierを、A/A' arrangement rescoringと融合できるか検証。
- fresh browserで5曲の低閾値K/S/T候補へKick/Snare/Tom別E-GMD probabilityを付与。

外部E-GMD v4学習量:
- Kick 4,422 candidates
- Snare 6,580
- Tom 7,934
- total 18,936

5曲transfer candidate pool:
- total 141
- Kick 11 / recoverable positive 9
- Snare 68 / positive 14
- Tom 62 / positive 2

比較:
- fixed_v39d: KST F1 **0.938852** (+0.001118), 9 TP / 0 FP
- H1 E-GMD acoustic only: 0.933968 (-0.003766), 18 TP / 55 FP
- H2 A/A' + E-GMD hard gate: 0.938231 (+0.000497), 4 TP / 0 FP
- H3 Logistic fusion LOOCV: 0.936762 (-0.000972), 1 TP / 10 FP
- H4 Extra Trees fusion LOOCV: 0.938012 (+0.000278), 4 TP / 2 FP

重要な観察:
- E-GMD acoustic model単独はdomain transferでFPが多く、production rescue gateには不適。
- hard E-GMD thresholdをA/A'救済へ追加するとprecisionは保てるが、fixed v39Dの真陽性を落とす。
- 実際にfixed v39Dで正解だった一部候補はE-GMD probabilityが低い:
  - arcaround Kick 29.18s p=.356 (<.40), 54.43s p=.048, 143.08s p=.114
  - nanairo Snare 78.25s p=.142 (<.67), 228.00s p=.483
- よってE-GMD probabilityはhard vetoではなく、将来のsoft feature / calibration候補として扱う。
- H4はheld-out songでも4 TP/2 FPを拾い、v43の0 rescueより前進したが、fixed v39Dの9 TP/0 FPには届かない。

採否:
- **v44融合案はproduction不採用**。
- productionはfresh Chromium v40合格済みfixed v39D-style arrangement rescoringを維持。
- `adtof.js` のdiagnostic KST candidatesにはE-GMD probabilityを付与するようになったが、通常production判定ロジックは変更していない。

資産:
- `experiments/results-arrangement-kst-candidates-v44.json`
- `experiments/results-arrangement-egmd-fusion-v44.json`
- `experiments/ARRANGEMENT_EGMD_FUSION_V44.md`

## 2026-09-23 Arrangement KST learned v42/v43 — research only, production据え置き

固定v39D rescoringを楽器別学習器へ置換できるか検証。

方式:
- 5曲leave-one-song-out (LOOCV)
- held-out曲のchart.midは予測確定後の採点だけ
- 比較: per-instrument Logistic Regression / Extra Trees / Random Forest
- prediction-time features: acoustic confidence/score/broad confidence, family quality, A/A' same-position support rate/count, eligible occurrences, GMD slot lift, 16分slot sin/cos, occurrence, repeat similarity, bar index, section length, residual
- Snare/Tomのproduction閾値以上だが後段vetoで落ちたcandidateは学習候補から除外

v42:
- same-position support>=1まで事前filterしたため12 candidatesのみ
- kick 5/5 positive, snare 6 candidates/5 positive, tom 1/1 positive
- 3学習器ともデータ不足でLOOCV rescue 0

v43:
- repeated familyに属するcandidateを広げ、support=0も負例/弱証拠として保持
- corpus 83 candidates
  - kick 6 / positives 5
  - snare 36 / positives 7
  - tom 41 / positives 2
- fixed v39D replay: KST F1 0.938852 (+0.001118), added 9 TP / 0 FP
- Logistic / Extra Trees / Random Forest LOOCV: 全て KST F1 0.937734 (baseline同値), rescue 0
- training folds内ではSnareモデルが改善候補を見つけるが、held-out songでは閾値を超えず、曲跨ぎ一般化を確認できなかった

判断:
- **learned v42/v43はproduction不採用**。
- productionはfresh Chromium v40合格済みのfixed v39D-style rescoringを維持。
- 「学習が無効」ではなく、現在のrecoverable positiveが少なく曲偏在している。特にKick/Tomは分類器を学習するには不足。
- 新しいpaired songを追加したら同じfeature schemaでcorpusへ追加し、LOOCVまたはsong-grouped CVを再実行する。

蓄積資産:
- `models/arrangement-kst/training-candidates-v43.json` — 83 labeled candidate rows
- `models/arrangement-kst/learned-rescore-v43.json` — research-only logistic export (Snareのみ学習可能、runtime未使用)
- `experiments/ARRANGEMENT_KST_LEARNED_V42.md`
- `experiments/ARRANGEMENT_KST_LEARNED_V43.md`

## 2026-09-23 Arrangement KST v40/v41 — production採用済み

v38/v39のA/A' acoustic candidate rescueを、通常のrhythm-grid/MIDI exportまで通すfresh Chromiumで再検証し、production appへ統合済み。

採用方式:
- offvocal/伴奏を任意の構造解析補助入力として使用
- 検証5曲では `DruMaster/songs/<id>/offvocal.mp3` を自動読込
- sensitive segmentation: frame .75s / hop .375s / context 3s / minSection 6s / noveltyStd .55 / maxSections 28
- A/A' family support + GMD 16分slot prior + post-filter-origin guard
- **他区間からnoteをcopyしない。対象時刻に低閾値K/S/T acoustic candidateが存在するときだけ昇格**
- Snare/Tomはproduction閾値以上なのに後段で落ちたcandidateをarrangementだけで復活させない
- 二手制約を維持

fresh Chromium v40:
- baseline KST F1 0.937734 -> **0.938852** (+0.001118)
- kick F1 0.962571 -> **0.963139** (+0.000568)
- snare F1 0.900035 -> **0.901934** (+0.001899)
- tom F1 0.784091 -> **0.790960** (+0.006870)
- all-class F1 0.818306 -> **0.818886** (+0.000581)
- rescued 9 notes
- max grid residual ticks 0
- hand-grid violation delta 0
- meter changed songs: none

runtime:
- `app.js` -> `arrangement/index.js` / `rescoreKstByArrangement()`
- `models/gmd-kst/slot-prior-v1.json`
- UI: `#arrangementFile` から offvocal / 伴奏を任意指定可能
- offvocal未指定時は従来baselineのドラム単独採譜を維持

検証:
- `experiments/ARRANGEMENT_KST_V40.md`
- `experiments/results-arrangement-kst-runtime-v40.json`

## 2026-09-23 Arrangement KST v38/v39 — A/A' acoustic rescue

v37で確認したsame-family repetitionを、実ブラウザの低閾値K/S/T acoustic candidate rescoringへ接続して検証。

前提:
- A/A'は構造familyでありsemantic verse/chorusではない。
- AのnoteをA'へcopyしない。対象時刻に低閾値音響candidateが存在する場合だけ候補昇格。
- browser prediction stageはchart.midを読まない。chart.midはPython scoring stageのみ。
- GMD symbolic slot priorはtrain 228 files / 13,550 barsから集約。

v38 best:
- sensitive H1: KST F1 0.937734 -> 0.938866 (+0.001132)
- sensitive H3 family+GMD: 同じoverall KST F1 0.938866
- H1追加: kick 4/4 TP, snare 5 TP + 1 FP, tom 1/1 TP
- H3追加: kick 3/3 TP, snare 6 TP + 1 FP, tom 1/1 TP
- 共通の唯一FPは diamondvirgin snare 205.88s。candidate confidence 1.92でproduction閾値自体は既に超えていたため、「弱候補の欠落」ではなく後段vetoをA/A'が覆した可能性が高い。

v39 post-filter:
- V39_A_subthreshold_hand: F1 0.938852, +0.001118, added TP/FP 9/0
- V39_D_symbolic_gmd_plus_postfilter: F1 0.938852, +0.001118, added TP/FP 9/0
- V39_D part delta:
  - kick +0.000568
  - snare +0.001899
  - tom +0.006870
- V39_Dを主候補。V39_Aを比較候補として保持。
- Snare/Tomはproduction閾値以上なのにfinalから落ちているcandidateをarrangementだけで復活させない。
- reusable API: `arrangement/rescoreKstByArrangement()`
- compact GMD prior: `models/gmd-kst/slot-prior-v1.json`

完了:
- v40で二手制約 + normal rhythm-grid/MIDI exportまで通したfresh Chromium non-regressionを確認済み。
- v39D系をproduction appへ統合済み。offvocal/伴奏が与えられた場合だけarrangement assistを有効化する。

詳細:
- `experiments/ARRANGEMENT_KST_V38.md`
- `experiments/ARRANGEMENT_KST_V39.md`


## 2026-09-23 Arrangement prior v37 — A/A' repetition evidence

5曲の `offvocal.mp3` を `arrangement/` で構造解析し、`chart.mid` は解析後の評価にのみ使用。

確定結果:
- A/B/C はsemantic labelではなく構造family。再登場は A' / A''。
- conservative segmentation:
  - same-family K/S/T F1 0.6733
  - cross-family K/S/T F1 0.4160
  - repeat margin **+0.2573**
- sensitive segmentation:
  - same-family K/S/T F1 0.6781
  - cross-family K/S/T F1 0.3898
  - repeat margin **+0.2883**
- balanced segmentationは K/S/T repeat margin **-0.0961** で、区切り/cluster精度が重要。
- GMD train 230 files / 13,573 bars:
  - adjacent-bar full-pattern F1 0.6664
  - same-style cross-file first-bar F1 0.3713
  - repetition margin **+0.2951**
- GMDではCrashのbeat-1率はbeats 2–4平均の約3.14倍。
- しかし5曲のoffvocal構造境界そのものではCrash/Cymbal liftは1未満。
  - conservative boundary crash lift 0.5499
  - balanced 0.8791
  - sensitive 0.7551

採否:
- **採用候補**: A/A' same-family repetitionを低信頼K/S/T候補のrescoring証拠として使う。
- **不採用**: 「offvocal構造境界だからCrashを追加する」規則。
- ノートの強制コピーは行わない。必ず音響candidateが存在する場合だけrescoringする。

詳細:
- `experiments/results-arrangement-structure-v37.json`
- `experiments/results-arrangement-prior-v37.json`
- `experiments/ARRANGEMENT_PRIOR_V37.md`


> **AI / 別チャット向けの最小コンテキスト。まずこのファイルだけ読む。**
>
> 内容確認日: 2026-09-23。**commit SHAを固定の正解とせず、毎回「1. 最初に現行を確定する手順」で `main` HEADから再判定する。**
>
> 詳細な試行錯誤は `VALIDATION.md` にあるが、最初から全文を読まないこと。必要な節だけ参照する。

## 2026-09-23 Arrangement/offvocal shared module

offvocal / instrumental の構造解析コードを `drumscribe/arrangement/` に集約。

正式な参照入口:
```js
import {analyzeSections, extractSectionFeatures} from './arrangement/index.js';
```

現行機能:
- timbre / energy novelty から構造境界候補を検出
- 類似した反復セクションを `A/B/C/...` の構造ファミリへグループ化
- 再登場は `A -> A' -> A''` のように occurrence label を付ける
- `section.group` は安定したファミリキー（A'でも group は A）、`section.label` が表示ラベル、`section.occurrence` が出現回数
- 既知の BPM / barPhaseSec があれば境界候補を拍・小節側へsnap可能
- 合成 `A -> B -> A -> B` テストでは boundaries `[0,6,12,18,24]`、labels `[A,B,A',B']` を確認済み

重要:
- `A/B/C/A'/...` は構造ラベルであり、**Aメロ/Bメロ/サビの意味ラベルではない**
- production transcription pathへ接続済み。offvocal/伴奏が与えられた場合にのみA/A'構造をK/S/T acoustic candidate rescoringへ使用
- Proof v34では同系統の解析をinstrumentalの補助的な小節位相検証に使用した
- 将来semantic section classifierを実装する場合はこのmoduleの出力を入力にし、特徴抽出や境界検出を重複実装しない

詳細: `arrangement/README.md`

## 2026-09-23 Tempo map v35 — 1小節単位

ユーザー要望によりBPM変化だけを変更。内部beat-level tempo推定は残し、preview/exportに使うtempo mapを**小節単位のduration-equivalent BPM**へ集約。

- note ticks変更なし
- quantize family/subdivision変更なし
- BPM基準推定変更なし
- bar/downbeat判定変更なし
- 楽器分類変更なし

Proof v34 tempo-only比較:
- tempo events 426 -> 110
- note time差 median .054 ms / p95 .521 ms / max 1.166 ms
- bar boundary差 max .010 ms

5曲fresh Chromium run `35849808016`:
- tempo events 127–153
- 全曲min tempo gap 1920 ticks = 4/4 1小節
- violations 0
- Precision .911 / Recall .743 / F1 .818
- grid residual 0

CIでbar-tempo間隔を直接検査。

詳細: `AI_HANDOFF_GRID_V35.md`, `experiments/TEMPO_BAR_V35.md`, `experiments/results-tempo-bar-v35.json`

## 2026-09-23 Proof v34 — tempo octave / GMD bar phase

Proof WAVで現行mainの198.164 BPM倍取りを再現。内部event-familyは99.125 BPMを最上位にしていたため、**高信頼な2x tempo octave errorだけを補正するgate**を追加。

Proof:
- initial 198.163894
- event-family 99.125
- ratio 1.99913
- family score .66037 vs 2x candidate .42309
- margin .23728
- corrected BPM ≈ 99.076668

GMD train-onlyから `models/gmd-kst/bar-phase-discriminative-v1.json` を学習。単独精度は十分高くないため、`audio-event-octave-corrected` の場合だけbar phase補助として使用する。

Proof full-song event replay:
- phase .123011 s
- runner 1.088172 s
- margin .77551
- coverage .8857
- gate pass

instrumental section noveltyも旧1.039 s位相より新.123 s位相を支持するが、単独決定には使わない。

5曲fresh Chromium run `35846141342`:
- F1 .818 / P .911 / R .743
- grid residual 0
- note counts baselineと同一
- 新GMD bar-phase発火 0/5

詳細: `AI_HANDOFF_GRID_V34.md`, `experiments/PROOF_V34.md`, `experiments/results-proof-v34.json`

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


---

## 2026-09-23 Preview hi-hat choke v36

- 対象: `drumscribe/app.js` のMIDIプレビュー再生のみ。採譜・MIDI書き出しロジックは変更していない。
- GM46 (Open Hi-Hat) の再生中に GM42 (Closed Hi-Hat) または GM44 (Pedal Hi-Hat) が来た場合、先行するOpen HHをchokeする。
- choke量は `DruMaster/js/hihat-choke.js` に合わせ、choke時刻から **65 msで指数減衰し、80 msでsource停止**。
- DrumScribeのlook-ahead schedulerでも実イベント時刻にchokeが掛かるよう、現在時刻ではなく各MIDI eventのscheduled `when` にgain rampを予約する。
- pause / seek / stop時にはOpen HH voice参照もクリアする。
- `index.html` のapp cache-busterを `20260923-hihat-choke-v36` に更新。
- app commit: `cee4817ca3cbd2ead9847a08e648fa676ef42b4c`
- cache-buster commit: `8e4570c708166009bd10d380753cc0419bed3570`


---

## 2026-09-23 Waveform viewport / range review UI v1

- UI/preview only。採譜class判定・`rhythm-grid.js`・MIDI export algorithmは変更していない。
- 通常ページ `index.html` に拡大率 / 表示位置 / 全体表示を追加。
- 共通viewport: `timeline-view.js`
  - wheel = 前後移動
  - Ctrl/Cmd + wheel = pointer-anchor zoom
  - `pxPerSec / viewStart`方式
  - 再生中playhead auto-follow
- Timing Correction参照元:
  - `DruMaster/song-sync-editor-v2.html`
  - `DruMaster/js/song-sync-history.js`
- 新規 `feedback.html` + `feedback.js`:
  - 波形dragで時間範囲選択
  - 分類＋コメントを複数保存
  - 選択範囲再生
  - 編集 / 削除
  - 5段undo/redo
  - Ctrl/Cmd+Z, Ctrl/Cmd+Y, Ctrl/Cmd+Shift+Z
  - AI修正依頼textをcopy
  - `drumscribe-review-v1` JSON download
  - localStorage保存
- 通常previewとreview pageは同じ `app.js` を使うため、採譜結果分岐なし。
- appは `globalThis.DrumScribeTimeline` と `drumscribe:* ` custom eventsをreview UIへ公開。
- 詳細: `drumscribe/UI_REVIEW_WORKFLOW.md`


## 2026-09-23 Range review UI v2
- `feedback.html` now keeps the lower **範囲レビュー** card as a saved-review log only.
- Dragging on the waveform opens an anchored speech-bubble editor directly over the selected range.
- Review ranges snap to the preview/export musical beat grid in **1-beat units**. `app.js` exposes beat-boundary helpers based on the same `rhythmGrid.timeForScore()` tempo map used for MIDI preview/export, rather than assuming a fixed seconds-per-beat across the song.
- Pressing **保存** appends the review to the chronological log and closes the editor. Saved blocks can be played, reopened/rewritten, or deleted.
- Existing localStorage persistence, 5-level undo/redo, AI prompt copy, and JSON export remain.


## 2026-09-23 Timeline interaction v6
- Concrete feedback-page startup bug fixed: `app.js` previously unconditionally bound `#arrangementFile`, but `feedback.html` did not contain that element. This stopped module initialization before `DrumScribeTimeline` was exposed. The binding is now optional.
- Review range selection is deliberately **not beat-snapped**. Dragging the waveform stores the raw selected time interval. This is independent from the musical grid.
- Manual playback seeking is beat-snapped instead: the transport seek slider and normal timeline click move to the nearest beat boundary generated from the same rhythm-grid tempo mapping used by preview/export. Alt+click bypasses snap.
- The preview now draws musical beat grid lines.
- MIDI preview visualization is four lanes, top to bottom: シンバル / ハイハット・ライド / スネア・タム / バスドラム.
- Note colors follow the DruMaster performance-page palette where applicable: snare #ff3d73, cymbal #ffd45a, hi-hat #52dfcf, ride #63d66f, kick #aeb9c7; toms are unified to requested purple #d76bff.
- Feedback range browser smoke test now verifies free-drag selection and beat-snapped click seeking, and the workflow uses concurrency cancellation so only the latest smoke run matters.


---

## 2026-09-23 Open/Closed Hi-Hat production v47

production既定を `ride-open-decay-rescue` に更新。

採用内容:
- 5–18 kHz帯を中心とした局所減衰・tail persistenceをborderline 42/46判定に使用
- GMD aggregate transition priorでopen→open runをrecall方向にのみ救済
- Ride判定を重視しない要件に基づき、残存Ride候補をOpen HHへ丸める
- A/A'による42/46 rescoringはv43で悪化したためproduction不採用
- onset追加・削除は行わず、hat-family articulationのみ変更

5曲fresh Chromium:
- HH macro F1 0.719507 -> **0.745832** (+0.026325)
- Closed F1 0.843292 -> **0.843895**
- Open F1 0.595722 -> **0.647770**
- collapsed hat/ride onset F1 0.812081 -> **0.817466**
- Kick/Tom非退行、同一fresh run基準でK/S/Tへの悪影響なし

注意:
- strict Ride F1は0になる。これはRideをOpenへ丸める明示要件に沿った設計判断。
- `OPENHAT_DEFAULT_VS_COMBINED_V46.md` のstrict metal macro guardrailは、Rideを保持する用途ではcombinedを採用しないという意味。現在の用途ではRide識別を優先しない。
- 完全同期Diamond Virgin pairはopen→open教師468件を含む。保存場所は `experiments/reference-sync/README.md`。


## 2026-09-24 Review voice dictation
- `feedback.html` review popover has `#reviewVoice` microphone control next to playback/cancel/save.
- `feedback.js` uses `SpeechRecognition || webkitSpeechRecognition` with `lang='ja-JP'`, continuous recognition, and interim results.
- Voice input appends to the existing review textarea instead of replacing prior text, so it also works while editing a saved review.
- Starting voice input pauses DrumScribe playback to reduce microphone bleed.
- The microphone button toggles to a stop state while listening. Unsupported browsers disable the button; permission/no-speech errors are shown in the review status line.
- Closing the editor or saving aborts any active recognizer while preserving the text currently visible in the textarea.
- Browser smoke injects a fake SpeechRecognition implementation and verifies recognized Japanese text reaches `#reviewText`.

## 2026-09-24 — review-trained alternating HH runtime removal

- The review-specific alternating hi-hat repair from v50-v52 was removed from the production runtime, not merely disabled.
- Removed production import/call of `hat-sequence.js` from `transcribe.js`.
- Removed `drumscribe/hat-sequence.js` and `models/alternating-hi-hat-review-v1.json` from runtime locations; historical copies live only under `drumscribe/experiments/archive/`.
- Reason: the sequence algorithm could choose the opposite alternating phase (Open→Closed where the performance is Closed→Open). It is not a valid general transcription rule.
- Also fixed stale browser cache keys: `app.js` now imports `transcribe.js?v=20260924-remove-review-hat-v67`, and `index.html` points to the corresponding fresh `app.js` URL.
- Production Open/Closed work must use general per-hit acoustic models trained/validated on synchronized multi-song data; no review-song parity/range is permitted.


## 2026-09-24 Open-hi-hat playback choke
- MIDI preview playback already had a choke path for closed HH (42) / pedal HH (44) against open HH (46), but the old behavior faded for 65 ms and stopped at 80 ms, which was too long perceptually.
- Runtime playback now tracks each open-hat voice with its scheduled start time and level.
- On note 42 or 44, all already-started/scheduled-prior open-hat voices are choked at that exact scheduled hit time with a 12 ms anti-click linear fade and source stop at 14 ms.
- Future open-hat voices are not accidentally killed.
- Both index.html and feedback.html use cache buster `app.js?v=20260924-hihat-choke-v1`.
