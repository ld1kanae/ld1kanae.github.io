# DrumScribe 全実験ログ

このファイルは build_experiment_log.py で自動生成する。候補を手作業で省略しない。

- 集録 result files: 130
- 集録 candidates: 894
- 生の曲別データ: 各 results*.json
- 標準詳細評価: detailed_metrics.py / detailed-history/
- 再現用索引: validation-history.json
- パート別保持候補: component-bank.json

## 評価規則

- 予測生成時に評価対象曲の chart.mid を参照しない。学習型はLOSOを基本とする。
- drums.mp3 から実MIDIを生成し、そのMIDIを再読み込みして chart.mid と照合する。
- 同一パート80 ms以内の1対1対応を基本TPとし、P/R/F1、FP/FN、ノート数比、時間誤差、クラス間誤認を保持する。
- 総合勝者だけでなく、特定パートで突出した候補を component bank に残す。
- pedal-hat / ride等をゼロにして総合F1だけ上げた候補は、それだけで本採用しない。

## 現在の総合上位候補

|候補|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|results-v2-browser.json:None:result|0.8160|0.9110|0.7400|0.9626|0.8909|0.8302|0.3152|0.7841|0.4560|0.2461|
|results-meter-v23.json:None:result|0.8150|0.9100|0.7390|0.9626|0.8858|0.8300|0.3155|0.7624|0.4560|0.2461|
|results-iterative-hat-density-guard-v10.json:222:c222_r045|0.8138|0.8680|0.7659|0.9626|0.8858|0.8119|0.5670|0.7624|0.4560|0.3480|
|results-iterative-hat-density-guard-v10.json:222:c222_r055|0.8138|0.8680|0.7659|0.9626|0.8858|0.8119|0.5670|0.7624|0.4560|0.3480|
|results-iterative-hat-density-guard-v10.json:222:c222_r065|0.8138|0.8680|0.7659|0.9626|0.8858|0.8119|0.5670|0.7624|0.4560|0.3480|
|results-iterative-hat-density-guard-v10.json:223:c223_whole_best|0.8138|0.8680|0.7659|0.9626|0.8858|0.8119|0.5670|0.7624|0.4560|0.3480|
|results-iterative-hat-density-guard-v10.json:224:c224_prev_best|0.8138|0.8680|0.7659|0.9626|0.8858|0.8119|0.5670|0.7624|0.4560|0.3480|
|results-iterative-hat-fixed-threshold-v11.json:225:c225_p45|0.8128|0.8643|0.7671|0.9626|0.8858|0.8095|0.5670|0.7624|0.4560|0.3480|
|results-iterative-hat-fixed-threshold-v11.json:225:c225_p55|0.8128|0.8685|0.7637|0.9626|0.8858|0.8094|0.5670|0.7624|0.4560|0.3480|
|results-iterative-hat-fixed-threshold-v11.json:226:c226_medium|0.8128|0.8685|0.7637|0.9626|0.8858|0.8094|0.5670|0.7624|0.4560|0.3480|
|results-iterative-hat-fixed-threshold-v11.json:227:c227_prev|0.8128|0.8685|0.7637|0.9626|0.8858|0.8094|0.5670|0.7624|0.4560|0.3480|
|results-iterative-hat-fixed-threshold-v11.json:227:c227_rep100_w60|0.8128|0.8685|0.7637|0.9626|0.8858|0.8094|0.5670|0.7624|0.4560|0.3480|

## 現在のパート別保持候補

|Part|Candidate|F1|Precision|Recall|Mean-song F1|Worst-song F1|
|---|---|---:|---:|---:|---:|---:|
|kick|results-iterative-adtof.json:163:c163_recall|0.9633|0.9531|0.9738|0.9670|0.9395|
|snare|results-v2-browser.json:None:result|0.8909|0.9165|0.8667|0.8638|0.6372|
|hat|results-iterative-browser-component-fusion.json:195:c195_ride|0.7795|0.7975|0.7623|0.7100|0.4876|
|pedal_hat|results-iterative-pedal-component.json:64:c64_recall|0.2996|0.1964|0.6317|0.2306|0.0000|
|tom|results-v2-browser.json:None:result|0.7841|0.8214|0.7500|0.7483|0.4828|
|crash|results-iterative-cymbal-template-v2.json:198:c198_precision|0.4632|0.5763|0.3872|0.4884|0.1739|
|ride|results-iterative-ride-fallback.json:119:c119_per50|0.1525|0.2058|0.1211|0.1453|0.0724|
|other|results-iterative-adaptive-refine.json:175:c175_base|0.0000|0.0000|0.0000|-|-|

## 全result / cycle / candidate

### drumscribe/experiments/results-adtof-gmd-tatum-metal-decoder-fast.json

- implementation: -
- script commit: -
- result commit: 85db799571d67767b391622f883e8646f40a7cb0

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-adtof-gmd-tatum-metal-decoder-fast.json / experiment-log.json

### drumscribe/experiments/results-adtof-gmd-tatum-metal-decoder-ultra.json

- implementation: -
- script commit: -
- result commit: cdde7ebdc2ca946aa73294606879ca6b5c5657f6

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-adtof-gmd-tatum-metal-decoder-ultra.json / experiment-log.json

### drumscribe/experiments/results-adtof-gmd-tatum-metal-decoder.json

- implementation: -
- script commit: -
- result commit: 82b273d823b7dbec3294954ecde5a4592fc52a5c

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-adtof-gmd-tatum-metal-decoder.json / experiment-log.json

### drumscribe/experiments/results-adtof-ride-section-propagation.json

- implementation: -
- script commit: -
- result commit: e83a1441a17f1631e87f30dfe5e23ee80c56a700

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-adtof-ride-section-propagation.json / experiment-log.json

### drumscribe/experiments/results-adtof-structural-crash-augmentation.json

- implementation: -
- script commit: -
- result commit: 3df157494cc3f38ded025c79cede54eb7fec121f

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-adtof-structural-crash-augmentation.json / experiment-log.json

### drumscribe/experiments/results-beat-phase-librosa.json

- implementation: -
- script commit: -
- result commit: 6c3aa11ba8bc79d531183cb3d5b9b6824f447920

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-beat-phase-librosa.json / experiment-log.json

### drumscribe/experiments/results-beat-phase.json

- implementation: -
- script commit: -
- result commit: fd0271de068d3514577743ef1bcf1a30a72430d5

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-beat-phase.json / experiment-log.json

### drumscribe/experiments/results-bpm-estimation-v2.json

- implementation: -
- script commit: -
- result commit: 96111c4c8d0f17c23e3af3622a1f28c5d3d61d91

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-bpm-estimation-v2.json / experiment-log.json

### drumscribe/experiments/results-bpm-estimation-v3.json

- implementation: -
- script commit: -
- result commit: a491bdff1c6d2da30da49e7f39333a50fca014bd

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-bpm-estimation-v3.json / experiment-log.json

### drumscribe/experiments/results-bpm-estimation.json

- implementation: -
- script commit: -
- result commit: 0f95b51357fa0e50e79e25d1d7d66a3ad3f57629

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-bpm-estimation.json / experiment-log.json

### drumscribe/experiments/results-browser-cymbal-decay.json

- implementation: -
- script commit: -
- result commit: 7dc8e4a5a0d88f789651621a4cdabe113911102d

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baseline|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-cymbal-decay.json / experiment-log.json

### drumscribe/experiments/results-browser-event-bpm.json

- implementation: -
- script commit: -
- result commit: 23246b5f1a46447e893da9724d50441a7c8f6638

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-event-bpm.json / experiment-log.json

### drumscribe/experiments/results-browser-gmd-adtof-metal-transfer.json

- implementation: -
- script commit: -
- result commit: 48591482314f962b9bdc0a517358579640a2b2ab

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|
|matchedDiagnostic|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-gmd-adtof-metal-transfer.json / experiment-log.json

### drumscribe/experiments/results-browser-gmd-adtof-pedal-transfer.json

- implementation: -
- script commit: -
- result commit: f6e0de6c3e71e9652100967777132ccfe390a10a

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|matchedDiagnostic|-|-|-|-|-|-|-|-|-|-|-|-|-|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-gmd-adtof-pedal-transfer.json / experiment-log.json

### drumscribe/experiments/results-browser-gmd-crash-reclass.json

- implementation: -
- script commit: -
- result commit: c7c2a5052f7140d6a4dae5a461606487c54753d1

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baseline|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-gmd-crash-reclass.json / experiment-log.json

### drumscribe/experiments/results-browser-gmd-pedal-lowcand-fast.json

- implementation: -
- script commit: -
- result commit: e973345a30cd308598712b9fc770e1dc68e4cc3e

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-gmd-pedal-lowcand-fast.json / experiment-log.json

### drumscribe/experiments/results-browser-gmd-pedal-lowcand.json

- implementation: -
- script commit: -
- result commit: 2c8b8259a5e8ae626c471d74124857c926d5fa0b

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-gmd-pedal-lowcand.json / experiment-log.json

### drumscribe/experiments/results-browser-gmd-pedal-style.json

- implementation: -
- script commit: -
- result commit: a5c9743534cd114f80be691827d0a9f5ea20acd8

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baseline|-|-|-|-|-|-|-|-|-|-|-|-|-|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-gmd-pedal-style.json / experiment-log.json

### drumscribe/experiments/results-browser-gmd-pedal.json

- implementation: -
- script commit: -
- result commit: e468f2e030934d0697642534345b847c67df4cac

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baseline|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-gmd-pedal.json / experiment-log.json

### drumscribe/experiments/results-browser-gmd-repetition-decoder.json

- implementation: -
- script commit: -
- result commit: 9ea576022ad884a94cd34404d5a5763b974417fd

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-gmd-repetition-decoder.json / experiment-log.json

### drumscribe/experiments/results-browser-gmd-repetition-metal-only.json

- implementation: -
- script commit: -
- result commit: d4431380f52b2f072bbc593b942d86fe9a43173b

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-gmd-repetition-metal-only.json / experiment-log.json

### drumscribe/experiments/results-browser-hat-cymbal-reclass-v2.json

- implementation: -
- script commit: -
- result commit: 665e9eedac8b79e91edf29023929b4d779b73fcb

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baseline|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-hat-cymbal-reclass-v2.json / experiment-log.json

### drumscribe/experiments/results-browser-hat-meta-nested-loo-fast.json

- implementation: -
- script commit: -
- result commit: 70681d79adaaffe52466e0974c6f613fb24f1df4

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-hat-meta-nested-loo-fast.json / experiment-log.json

### drumscribe/experiments/results-browser-hat-meta-nested-loo.json

- implementation: -
- script commit: -
- result commit: 113d79d2892609db77336bc28a9b22a74d1eb6d2

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-hat-meta-nested-loo.json / experiment-log.json

### drumscribe/experiments/results-browser-pedal-candidates-v2.json

- implementation: -
- script commit: -
- result commit: 7b719bf7c0fbb4dfc9c2aa367a449e561c096567

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baseline|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-pedal-candidates-v2.json / experiment-log.json

### drumscribe/experiments/results-browser-pedal-unsupervised.json

- implementation: -
- script commit: -
- result commit: 1d6bb435513b972959f22ec8c2ae53b505790d7a

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baseline|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-pedal-unsupervised.json / experiment-log.json

### drumscribe/experiments/results-browser-ride-state-nested-loo.json

- implementation: -
- script commit: -
- result commit: 9eaacb7a107a8d7c75d3ce07d2529cef6728420e

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|nestedLOO|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-browser-ride-state-nested-loo.json / experiment-log.json

### drumscribe/experiments/results-downbeat-estimation-v2.json

- implementation: -
- script commit: -
- result commit: d5d356b0891b48a291844aa0676e8e6671b0e668

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-downbeat-estimation-v2.json / experiment-log.json

### drumscribe/experiments/results-downbeat-estimation.json

- implementation: -
- script commit: -
- result commit: 60c17bd3fa03d17717f73b842365ef845b0084eb

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-downbeat-estimation.json / experiment-log.json

### drumscribe/experiments/results-human-review-guards.json

- implementation: -
- script commit: -
- result commit: 0f5e47805fccf5626bdbd36856df85d304612bfb

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|review_strict|-|0.7245|-|-|-|-|-|-|-|-|-|21|-|
|density|-|0.7241|-|-|-|-|-|-|-|-|-|37|-|
|hat|-|0.7231|-|-|-|-|-|-|-|-|-|42|-|
|all|-|0.7227|-|-|-|-|-|-|-|-|-|37|-|
|adaptive_snare|-|0.7210|-|-|-|-|-|-|-|-|-|21|-|
|kick_veto|-|0.7209|-|-|-|-|-|-|-|-|-|4|-|
|baseline|-|0.7208|-|-|-|-|-|-|-|-|-|42|-|
|snare|-|0.7207|-|-|-|-|-|-|-|-|-|37|-|
|metal|-|0.7207|-|-|-|-|-|-|-|-|-|42|-|

詳細params・曲別データ参照: drumscribe/experiments/results-human-review-guards.json / experiment-log.json

### drumscribe/experiments/results-human-review-ui.json

- implementation: -
- script commit: -
- result commit: 0f5e47805fccf5626bdbd36856df85d304612bfb

#### Cycle 145

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c145_rhythm|-|0.7245|-|-|-|-|-|-|-|-|-|21|-|
|c145_snare|-|0.7210|-|-|-|-|-|-|-|-|-|21|-|
|c145_kick_veto|-|0.7209|-|-|-|-|-|-|-|-|-|4|-|

詳細params・曲別データ参照: drumscribe/experiments/results-human-review-ui.json / experiment-log.json

### drumscribe/experiments/results-iterative-adaptive-refine.json

- implementation: drumscribe/experiments/iterative_search_adaptive_refine.py
- script commit: 482b680c9019744905c5b25a780a4a302f45ba95
- result commit: 0ed9a7615e9be0022e62e7e12e6b394d8d75e32d

#### Cycle 175

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c175_strict|winner|0.7934|0.8180|0.7703|0.9626|0.8880|0.7772|0.5021|0.7582|0.3955|0.2742|2|28|
|c175_balanced|-|0.7934|0.8180|0.7703|0.9626|0.8880|0.7772|0.5021|0.7582|0.3955|0.2742|2|28|
|c175_base|part-leader|0.7932|0.8174|0.7705|0.9626|0.8880|0.7768|0.5021|0.7582|0.3955|0.2742|2|28|
|c175_loose|-|0.7932|0.8178|0.7700|0.9626|0.8880|0.7768|0.5021|0.7582|0.3940|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-adaptive-refine.json / experiment-log.json

#### Cycle 176

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c176_bal20|-|0.7947|0.8286|0.7635|0.9626|0.8880|0.7799|0.5021|0.7582|0.3955|0.2742|2|28|
|c176_bal30|-|0.7947|0.8286|0.7635|0.9626|0.8880|0.7799|0.5021|0.7582|0.3955|0.2742|2|28|
|c176_strict20|-|0.7946|0.8356|0.7575|0.9626|0.8880|0.7794|0.5021|0.7582|0.3955|0.2742|2|28|
|c176_vstrict20|winner|0.7946|0.8357|0.7574|0.9626|0.8880|0.7793|0.5021|0.7582|0.3955|0.2742|2|28|
|c176_base|-|0.7934|0.8180|0.7703|0.9626|0.8880|0.7772|0.5021|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-adaptive-refine.json / experiment-log.json

#### Cycle 177

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c177_periodic|winner|0.7947|0.8360|0.7574|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.2742|2|28|
|c177_base|-|0.7946|0.8357|0.7574|0.9626|0.8880|0.7793|0.5021|0.7582|0.3955|0.2742|2|28|
|c177_vote2|-|0.7946|0.8357|0.7574|0.9626|0.8880|0.7793|0.5021|0.7582|0.3955|0.2742|2|28|
|c177_vote3|-|0.7946|0.8357|0.7574|0.9626|0.8880|0.7793|0.5021|0.7582|0.3955|0.2742|2|28|
|c177_vote4|-|0.7946|0.8357|0.7574|0.9626|0.8880|0.7793|0.5021|0.7582|0.3955|0.2742|2|28|
|c177_strict|-|0.7946|0.8357|0.7574|0.9626|0.8880|0.7793|0.5021|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-adaptive-refine.json / experiment-log.json

### drumscribe/experiments/results-iterative-adtof-components.json

- implementation: drumscribe/experiments/iterative_search_adtof_components.py
- script commit: 658efb5ca5ef13e6383767695143dffbade4ecc4
- result commit: a020f7fd8eff0fd5fbaf11dd75665084d2b4d0d7

#### Cycle 166

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c166_precision|winner|0.7765|0.7885|0.7649|0.9590|0.8876|0.7730|0.3933|0.6667|0.3955|0.2742|2|25|
|c166_default|-|0.7763|0.7876|0.7653|0.9590|0.8855|0.7730|0.3933|0.6667|0.3955|0.2742|2|25|
|c166_recall|-|0.7761|0.7864|0.7660|0.9590|0.8833|0.7730|0.3933|0.6667|0.3955|0.2742|2|25|
|c166_base|-|0.7692|0.7829|0.7559|0.9590|0.8379|0.7729|0.3933|0.6667|0.3955|0.2742|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-adtof-components.json / experiment-log.json

#### Cycle 167

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c167_none|winner|0.7765|0.7885|0.7649|0.9590|0.8876|0.7730|0.3933|0.6667|0.3955|0.2742|2|25|
|c167_gap12|-|0.7765|0.7885|0.7649|0.9590|0.8876|0.7730|0.3933|0.6667|0.3955|0.2742|2|25|
|c167_gap16|-|0.7765|0.7885|0.7649|0.9590|0.8876|0.7730|0.3933|0.6667|0.3955|0.2742|2|25|
|c167_gap20|-|0.7765|0.7885|0.7649|0.9590|0.8876|0.7730|0.3933|0.6667|0.3955|0.2742|2|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-adtof-components.json / experiment-log.json

#### Cycle 168

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c168_kick_tom|winner|0.7782|0.7897|0.7670|0.9626|0.8876|0.7730|0.3933|0.7582|0.3955|0.2742|2|28|
|c168_kick|-|0.7774|0.7897|0.7656|0.9626|0.8876|0.7730|0.3933|0.6667|0.3955|0.2742|2|28|
|c168_tom|-|0.7773|0.7885|0.7663|0.9590|0.8876|0.7730|0.3933|0.7582|0.3955|0.2742|2|25|
|c168_base|-|0.7765|0.7885|0.7649|0.9590|0.8876|0.7730|0.3933|0.6667|0.3955|0.2742|2|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-adtof-components.json / experiment-log.json

### drumscribe/experiments/results-iterative-adtof-cymbal-class.json

- implementation: drumscribe/experiments/iterative_search_adtof_cymbal_class.py
- script commit: 1e1c8649827c7dc0ad7904e8721eb8ba7a5fb2c4
- result commit: dcb464cfe92c76171c5900b897ccaa9958986ffe

#### Cycle 169

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c169_base|-|0.7782|0.7897|0.7670|0.9626|0.8876|0.7730|0.3933|0.7582|0.3955|0.2742|2|28|
|c169_strict|winner|0.7782|0.7897|0.7670|0.9626|0.8876|0.7730|0.3933|0.7582|0.3955|0.2742|2|28|
|c169_balanced|-|0.7780|0.7891|0.7672|0.9626|0.8876|0.7730|0.3933|0.7582|0.3956|0.2742|2|28|
|c169_loose|-|0.7750|0.7762|0.7737|0.9626|0.8876|0.7723|0.3933|0.7582|0.3964|0.3339|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-adtof-cymbal-class.json / experiment-log.json

#### Cycle 170

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c170_strict|winner|0.7784|0.7903|0.7669|0.9626|0.8876|0.7736|0.3933|0.7582|0.3955|0.2742|2|28|
|c170_balanced|-|0.7784|0.7903|0.7669|0.9626|0.8876|0.7736|0.3933|0.7582|0.3955|0.2742|2|28|
|c170_loose|-|0.7783|0.7902|0.7668|0.9626|0.8876|0.7734|0.3933|0.7582|0.3947|0.2742|2|28|
|c170_base|-|0.7782|0.7897|0.7670|0.9626|0.8876|0.7730|0.3933|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-adtof-cymbal-class.json / experiment-log.json

#### Cycle 171

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c171_strict_bal|winner|0.7784|0.7903|0.7669|0.9626|0.8876|0.7736|0.3933|0.7582|0.3955|0.2742|2|28|
|c171_bal_strict|-|0.7783|0.7897|0.7671|0.9626|0.8876|0.7736|0.3933|0.7582|0.3956|0.2742|2|28|
|c171_base|-|0.7782|0.7897|0.7670|0.9626|0.8876|0.7730|0.3933|0.7582|0.3955|0.2742|2|28|
|c171_bal_bal|-|0.7782|0.7897|0.7670|0.9626|0.8876|0.7734|0.3933|0.7582|0.3956|0.2742|2|28|
|c171_loose_strict|-|0.7752|0.7768|0.7736|0.9626|0.8876|0.7728|0.3933|0.7582|0.3964|0.3339|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-adtof-cymbal-class.json / experiment-log.json

### drumscribe/experiments/results-iterative-adtof.json

- implementation: drumscribe/experiments/iterative_search_adtof.py
- script commit: 298ee7003a644eae32c65a24f71486f5f6bafaf9
- result commit: ad608817c5e6c6630d12d13bc2aa3ef1b423cd80

#### Cycle 163

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c163_precision|winner|0.7710|0.8113|0.7346|0.9626|0.8876|0.7758|0.0000|0.7582|0.3678|0.0000|2|28|
|c163_default|-|0.7668|0.7893|0.7455|0.9630|0.8855|0.7717|0.0000|0.7164|0.3621|0.0000|2|28|
|c163_recall|part-leader|0.7609|0.7685|0.7535|0.9633|0.8833|0.7655|0.0000|0.6348|0.3571|0.0000|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-adtof.json / experiment-log.json

#### Cycle 164

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c164_replace|winner|0.7666|0.7751|0.7583|0.9590|0.8379|0.7729|0.3933|0.6667|0.3936|0.2841|41|25|
|c164_strict|-|0.7327|0.7557|0.7110|0.9590|0.8379|0.6899|0.3933|0.6667|0.3936|0.2841|41|25|
|c164_balanced|-|0.7317|0.7502|0.7141|0.9590|0.8379|0.6881|0.3933|0.6667|0.3936|0.2841|41|25|
|c164_loose|-|0.7293|0.7427|0.7163|0.9590|0.8379|0.6830|0.3933|0.6667|0.3936|0.2841|41|25|
|c164_base|-|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-adtof.json / experiment-log.json

#### Cycle 165

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c165_strict|-|0.7692|0.7872|0.7520|0.9590|0.8379|0.7729|0.3933|0.6667|0.3413|0.2520|41|25|
|c165_loose|winner|0.7692|0.7829|0.7559|0.9590|0.8379|0.7729|0.3933|0.6667|0.3955|0.2742|41|25|
|c165_balanced|-|0.7687|0.7848|0.7533|0.9590|0.8379|0.7729|0.3933|0.6667|0.3654|0.2522|41|25|
|c165_base|-|0.7666|0.7751|0.7583|0.9590|0.8379|0.7729|0.3933|0.6667|0.3936|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-adtof.json / experiment-log.json

### drumscribe/experiments/results-iterative-anchor.json

- implementation: drumscribe/experiments/iterative_search_anchor.py
- script commit: 4eedceb5dfe97a4c98f506f0b1e57b27f47b7792
- result commit: c2b5b2c618aededa9f51712f6c03738f36d91df8

#### Cycle 7

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c7_early_crash|winner, close|0.6270|0.6513|0.6044|0.9281|0.7604|0.5126|-|0.0000|0.0327|0.0059|35|27|
|c7_all|close|0.6268|0.6503|0.6050|0.9281|0.7642|0.5127|-|0.0000|0.0205|0.0060|35|27|
|c7_section_vote|close|0.6268|0.6513|0.6041|0.9281|0.7596|0.5126|-|0.0000|0.0108|0.0060|41|27|
|c7_top_crash|close|0.6264|0.6503|0.6042|0.9281|0.7613|0.5127|-|0.0000|0.0138|0.0060|35|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-anchor.json / experiment-log.json

#### Cycle 8

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c8_head_005|winner, close|0.6272|0.6516|0.6045|0.9281|0.7613|0.5126|-|0.0000|0.0289|0.0059|35|27|
|c8_head_010|close|0.6257|0.6495|0.6036|0.9281|0.7563|0.5126|-|0.0000|0.0352|0.0059|34|27|
|c8_head_015|close|0.6251|0.6489|0.6030|0.9281|0.7533|0.5126|-|0.0000|0.0347|0.0059|34|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-anchor.json / experiment-log.json

#### Cycle 9

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c9_ride_strict|winner, close|0.6218|0.6459|0.5994|0.9281|0.7351|0.5126|-|0.0000|0.0289|0.0109|35|27|
|c9_ride_medium|close|0.6120|0.6350|0.5905|0.9281|0.6753|0.5121|-|0.0000|0.0292|0.0769|30|27|
|c9_ride_recall|close|0.6051|0.6258|0.5858|0.9281|0.6330|0.5121|-|0.0000|0.0302|0.1178|24|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-anchor.json / experiment-log.json

### drumscribe/experiments/results-iterative-best-fusion.json

- implementation: drumscribe/experiments/iterative_search_best_fusion.py
- script commit: 9dbaeef7d7e28e21fe58ad8ef195aedff6e0f5dd
- result commit: 318ada07215a62bcdefd38b7d0880017cda6fca2

#### Cycle 79

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c79_crash_precision|winner, close|0.7158|0.7282|0.7038|0.9590|0.8130|0.6731|0.1735|0.6369|0.3734|0.0000|42|25|
|c79_crash_base|close|0.7148|0.7263|0.7036|0.9590|0.8130|0.6731|0.1735|0.6369|0.3517|0.0000|42|25|
|c79_crash_recall|close|0.7148|0.7255|0.7044|0.9590|0.8130|0.6722|0.1735|0.6369|0.3824|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-best-fusion.json / experiment-log.json

#### Cycle 80

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c80_snare_pattern|close|0.7190|0.7228|0.7151|0.9590|0.8253|0.6733|0.1735|0.6369|0.3734|0.0000|103|25|
|c80_snare_base|winner, close|0.7158|0.7282|0.7038|0.9590|0.8130|0.6731|0.1735|0.6369|0.3734|0.0000|42|25|
|c80_snare_veto|close|0.7155|0.7276|0.7038|0.9590|0.8107|0.6731|0.1735|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-best-fusion.json / experiment-log.json

#### Cycle 81

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c81_pedal_base|winner, close|0.7158|0.7282|0.7038|0.9590|0.8130|0.6731|0.1735|0.6369|0.3734|0.0000|42|25|
|c81_pedal_strict|close|0.7015|0.6754|0.7298|0.9590|0.8130|0.6731|0.3211|0.6369|0.3734|0.0000|42|25|
|c81_pedal_balanced|-|0.6946|0.6592|0.7339|0.9590|0.8130|0.6731|0.3117|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-best-fusion.json / experiment-log.json

### drumscribe/experiments/results-iterative-best-merge-v8.json

- implementation: drumscribe/experiments/iterative_search_best_merge_v8.py
- script commit: f10eafc68c53a0af8c48c6b1dd28d90f4cddd3de
- result commit: da8ddef75f7503b3601be621c98fa34ab859eecd

#### Cycle 216

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c216_both|winner|0.8097|0.8554|0.7686|0.9626|0.8858|0.8019|0.5670|0.7624|0.4560|0.3480|2|28|
|c216_hat|-|0.8091|0.8540|0.7686|0.9626|0.8858|0.8019|0.5607|0.7624|0.4560|0.3480|2|28|
|c216_pedal|-|0.8071|0.8456|0.7719|0.9626|0.8858|0.7956|0.5670|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-best-merge-v8.json / experiment-log.json

#### Cycle 217

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c217_h12|-|0.8097|0.8554|0.7686|0.9626|0.8858|0.8019|0.5670|0.7624|0.4560|0.3480|2|28|
|c217_h15|winner|0.8097|0.8554|0.7686|0.9626|0.8858|0.8019|0.5670|0.7624|0.4560|0.3480|2|28|
|c217_h18|-|0.8088|0.8524|0.7695|0.9626|0.8858|0.7997|0.5670|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-best-merge-v8.json / experiment-log.json

#### Cycle 218

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c218_p20|-|0.8097|0.8554|0.7686|0.9626|0.8858|0.8019|0.5670|0.7624|0.4560|0.3480|2|28|
|c218_p50|winner|0.8097|0.8554|0.7686|0.9626|0.8858|0.8019|0.5670|0.7624|0.4560|0.3480|2|28|
|c218_p5|-|0.8093|0.8545|0.7686|0.9626|0.8858|0.8019|0.5628|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-best-merge-v8.json / experiment-log.json

### drumscribe/experiments/results-iterative-browser-component-fusion.json

- implementation: drumscribe/experiments/iterative_search_browser_component_fusion.py
- script commit: 3efb0688e8557f5dd73d03ef6e34e0759ff7714f
- result commit: 4c7748b38da663bc9bb1c678e08163f5db7f9df7

#### Cycle 195

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c195_pedal|winner|0.8054|0.8538|0.7622|0.9626|0.8858|0.7976|0.5222|0.7624|0.4560|0.2461|2|28|
|c195_browser_base|-|0.8019|0.8709|0.7431|0.9626|0.8858|0.7976|0.3155|0.7624|0.4560|0.2461|2|28|
|c195_both|-|0.7977|0.8315|0.7665|0.9626|0.8858|0.7795|0.5222|0.7624|0.4560|0.3503|2|28|
|c195_ride|part-leader|0.7941|0.8470|0.7474|0.9626|0.8858|0.7795|0.3155|0.7624|0.4560|0.3503|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-browser-component-fusion.json / experiment-log.json

#### Cycle 196

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c196_periodic|winner|0.8052|0.8477|0.7667|0.9626|0.8858|0.7956|0.5222|0.7624|0.4560|0.3480|2|28|
|c196_ride_only|-|0.8048|0.8441|0.7690|0.9626|0.8858|0.7966|0.5222|0.7624|0.4560|0.3503|2|28|
|c196_pair|-|0.7977|0.8315|0.7665|0.9626|0.8858|0.7795|0.5222|0.7624|0.4560|0.3503|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-browser-component-fusion.json / experiment-log.json

#### Cycle 197

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c197_merge|winner|0.8063|0.8442|0.7718|0.9626|0.8858|0.7956|0.5592|0.7624|0.4560|0.3480|2|28|
|c197_all|-|0.8052|0.8477|0.7667|0.9626|0.8858|0.7956|0.5222|0.7624|0.4560|0.3480|2|28|
|c197_periodic|-|0.8048|0.8492|0.7648|0.9626|0.8858|0.7956|0.5074|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-browser-component-fusion.json / experiment-log.json

### drumscribe/experiments/results-iterative-component-hybrid.json

- implementation: drumscribe/experiments/iterative_search_component_hybrid.py
- script commit: 7b5e7b99a036550911de34d2dcfc4baf67a5c157
- result commit: 9ba2c3d74eb067c38bf01e95714c1899480d7a3f

#### Cycle 52

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c52_robust|winner, close|0.6954|0.7523|0.6465|0.9590|0.7642|0.6445|0.1735|0.6345|0.3511|0.0000|38|25|
|c52_precision|close|0.6944|0.7547|0.6430|0.9578|0.7642|0.6445|0.1735|0.6345|0.2874|0.0000|38|27|
|c52_recall|-|0.6687|0.6281|0.7151|0.9537|0.6759|0.6703|0.1735|0.6345|0.3464|0.0890|51|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-component-hybrid.json / experiment-log.json

#### Cycle 53

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c53_two_hands|winner, close|0.6954|0.7523|0.6465|0.9590|0.7642|0.6445|0.1735|0.6345|0.3511|0.0000|38|25|
|c53_priority|close|0.6954|0.7523|0.6465|0.9590|0.7642|0.6445|0.1735|0.6345|0.3511|0.0000|38|25|
|c53_none|close|0.6952|0.7516|0.6466|0.9590|0.7642|0.6444|0.1735|0.6345|0.3474|0.0000|38|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-component-hybrid.json / experiment-log.json

#### Cycle 54

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c54_crash_source|winner, close|0.6954|0.7523|0.6465|0.9590|0.7642|0.6445|0.1735|0.6345|0.3511|0.0000|38|25|
|c54_crash_head_balanced|close|0.6931|0.7542|0.6411|0.9590|0.7642|0.6445|0.1735|0.6345|0.1876|0.0000|38|25|
|c54_crash_head_tight|close|0.6927|0.7542|0.6405|0.9590|0.7642|0.6445|0.1735|0.6345|0.1649|0.0000|38|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-component-hybrid.json / experiment-log.json

### drumscribe/experiments/results-iterative-component-merge-v7.json

- implementation: drumscribe/experiments/iterative_search_component_merge_v7.py
- script commit: 3f62b3fe39a92697e4c7ab2675bb45103ee769b5
- result commit: ef47bc437d8ed4be636af9c7f467486b8c815b44

#### Cycle 193

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c193_both|winner|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c193_ride|-|0.7963|0.8330|0.7626|0.9626|0.8880|0.7795|0.5033|0.7582|0.3955|0.3503|2|28|
|c193_pedal|-|0.7952|0.8339|0.7599|0.9626|0.8880|0.7793|0.5222|0.7582|0.3955|0.2742|2|28|
|c193_base|-|0.7947|0.8360|0.7574|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-component-merge-v7.json / experiment-log.json

#### Cycle 194

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c194_basecrash|winner|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c194_crashB|-|0.7960|0.8286|0.7658|0.9626|0.8880|0.7795|0.5222|0.7582|0.3951|0.3503|2|28|
|c194_crashA|-|0.7958|0.8280|0.7660|0.9626|0.8880|0.7795|0.5222|0.7582|0.3958|0.3503|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-component-merge-v7.json / experiment-log.json

### drumscribe/experiments/results-iterative-composite-v2.json

- implementation: drumscribe/experiments/iterative_search_composite_v2.py
- script commit: c649582531741a55f6836905b86c8c15f2cdcb6a
- result commit: e42cf97a02006eb6a24b1ebee65a6e1e04ba924c

#### Cycle 37

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c37_precision|winner, close|0.6002|0.6216|0.5802|0.9316|0.7644|0.4554|0.2661|0.6154|0.3093|0.0000|41|27|
|c37_ride_balanced|close|0.5871|0.6081|0.5676|0.9316|0.7644|0.4474|0.2661|0.6154|0.3103|0.0427|41|27|
|c37_ride_recall|-|0.5723|0.5927|0.5532|0.9316|0.7644|0.4323|0.2661|0.6154|0.3103|0.0774|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-composite-v2.json / experiment-log.json

#### Cycle 38

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c38_pedal_recall|winner, close|0.6006|0.6220|0.5806|0.9316|0.7644|0.4556|0.2813|0.6154|0.3093|0.0000|41|27|
|c38_pedal_balanced|close|0.6002|0.6216|0.5802|0.9316|0.7644|0.4554|0.2661|0.6154|0.3093|0.0000|41|27|
|c38_pedal_strict|-|0.5994|0.6209|0.5793|0.9316|0.7639|0.4596|0.1735|0.6194|0.3098|0.0000|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-composite-v2.json / experiment-log.json

#### Cycle 39

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c39_crash_strict|close|0.6019|0.6278|0.5780|0.9316|0.7654|0.4556|0.2813|0.6154|0.2780|0.0000|41|27|
|c39_crash_balanced|winner, close|0.6006|0.6220|0.5806|0.9316|0.7644|0.4556|0.2813|0.6154|0.3093|0.0000|41|27|
|c39_crash_recall|close|0.5993|0.6180|0.5817|0.9316|0.7635|0.4557|0.2813|0.6154|0.3098|0.0000|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-composite-v2.json / experiment-log.json

### drumscribe/experiments/results-iterative-composite.json

- implementation: drumscribe/experiments/iterative_search_composite.py
- script commit: 39fbc98d07aed2c62054829a9432d45728b1ea08
- result commit: 249d9703f28cff86e7c2500c81a6bb99bbfc7d60

#### Cycle 28

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c28_ride_off|winner, close|0.6429|0.6698|0.6181|0.9281|0.7710|0.5129|-|0.6194|0.2862|0.0000|41|27|
|c28_ride_balanced|close|0.6294|0.6557|0.6051|0.9281|0.7710|0.5041|-|0.6194|0.2868|0.0374|41|27|
|c28_ride_recall|-|0.6088|0.6343|0.5853|0.9281|0.7710|0.4822|-|0.6194|0.2868|0.0904|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-composite.json / experiment-log.json

#### Cycle 29

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c29_ks_guard|winner, close|0.6432|0.6701|0.6184|0.9316|0.7647|0.5129|-|0.6194|0.2862|0.0000|39|27|
|c29_ks_balanced|close|0.6429|0.6698|0.6181|0.9281|0.7710|0.5129|-|0.6194|0.2862|0.0000|41|27|
|c29_ks_snare_recall|close|0.6429|0.6698|0.6181|0.9240|0.7811|0.5129|-|0.6194|0.2862|0.0000|42|26|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-composite.json / experiment-log.json

#### Cycle 30

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c30_crash_balanced|close|0.6432|0.6701|0.6184|0.9316|0.7647|0.5129|-|0.6194|0.2862|0.0000|39|27|
|c30_crash_recall|winner, close|0.6422|0.6657|0.6204|0.9316|0.7647|0.5128|-|0.6194|0.3110|0.0000|39|27|
|c30_crash_strict|-|0.6421|0.6720|0.6148|0.9316|0.7644|0.5127|-|0.6194|0.1822|0.0000|39|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-composite.json / experiment-log.json

### drumscribe/experiments/results-iterative-crash-barhead.json

- implementation: drumscribe/experiments/iterative_search_crash_barhead.py
- script commit: f2709da55ee68d00dc4367f9cc480991d54e02e3
- result commit: 04368f7ae9654c96db1310052bad910411482e34

#### Cycle 145

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c145_ratio|winner|0.7053|0.6958|0.7151|0.9590|0.8107|0.6793|0.3870|0.6667|0.1101|0.1608|42|25|
|c145_hybrid|-|0.7015|0.6876|0.7159|0.9590|0.8107|0.6798|0.3870|0.6667|0.1124|0.1607|42|25|
|c145_flux|-|0.7004|0.6853|0.7162|0.9590|0.8107|0.6796|0.3870|0.6667|0.1172|0.1608|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-barhead.json / experiment-log.json

#### Cycle 146

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c146_p82|-|0.7074|0.7007|0.7144|0.9590|0.8107|0.6793|0.3870|0.6667|0.0988|0.1630|42|25|
|c146_p70|winner|0.7053|0.6958|0.7151|0.9590|0.8107|0.6793|0.3870|0.6667|0.1101|0.1608|42|25|
|c146_p55|-|0.7043|0.6938|0.7151|0.9590|0.8107|0.6793|0.3870|0.6667|0.1065|0.1608|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-barhead.json / experiment-log.json

#### Cycle 147

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c147_r10|-|0.7063|0.6985|0.7143|0.9590|0.8107|0.6795|0.3870|0.6667|0.0900|0.1630|42|25|
|c147_r18|winner|0.7053|0.6958|0.7151|0.9590|0.8107|0.6793|0.3870|0.6667|0.1101|0.1608|42|25|
|c147_r28|-|0.6999|0.6864|0.7139|0.9590|0.8107|0.6792|0.3870|0.6667|0.0697|0.1608|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-barhead.json / experiment-log.json

### drumscribe/experiments/results-iterative-crash-consensus-v2.json

- implementation: drumscribe/experiments/iterative_search_crash_consensus_v2.py
- script commit: 6da6b6552fd326aaa21df5ebbf670694b46f480f
- result commit: 6046cb19278e42b7dfb599474407e33450321d27

#### Cycle 195

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c195_base|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c195_consensus|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c195_kick|winner|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c195_down|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c195_both|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-consensus-v2.json / experiment-log.json

#### Cycle 196

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c196_w030|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c196_w045|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c196_w060|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c196_w080|winner|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-consensus-v2.json / experiment-log.json

#### Cycle 197

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c197_d40|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c197_d55|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c197_d70|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c197_d85|winner|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-consensus-v2.json / experiment-log.json

### drumscribe/experiments/results-iterative-crash-consensus.json

- implementation: drumscribe/experiments/iterative_search_crash_consensus.py
- script commit: 2df760e077b7a2c5231e1dae54344a2edb9927a5
- result commit: 15f09e9dab86d399c6ec79371946bcbd10615a65

#### Cycle 70

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c70_gap|winner, close|0.7051|0.7480|0.6669|0.9590|0.8113|0.6451|0.1735|0.6369|0.3734|0.0000|42|25|
|c70_agreement|close|0.7050|0.7507|0.6645|0.9590|0.8113|0.6451|0.1735|0.6369|0.3229|0.0000|42|25|
|c70_downbeat_or|close|0.7050|0.7478|0.6669|0.9590|0.8113|0.6451|0.1735|0.6369|0.3720|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-consensus.json / experiment-log.json

#### Cycle 71

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c71_kick|winner, close|0.7051|0.7480|0.6669|0.9590|0.8113|0.6451|0.1735|0.6369|0.3734|0.0000|42|25|
|c71_joint|close|0.7051|0.7480|0.6669|0.9590|0.8113|0.6451|0.1735|0.6369|0.3734|0.0000|42|25|
|c71_crash|close|0.7041|0.7450|0.6675|0.9590|0.8113|0.6441|0.1735|0.6369|0.3824|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-consensus.json / experiment-log.json

#### Cycle 72

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c72_head18|winner, close|0.7051|0.7480|0.6669|0.9590|0.8113|0.6451|0.1735|0.6369|0.3734|0.0000|42|25|
|c72_head28|close|0.7051|0.7480|0.6669|0.9590|0.8113|0.6451|0.1735|0.6369|0.3734|0.0000|42|25|
|c72_head10|close|0.7048|0.7480|0.6663|0.9590|0.8113|0.6451|0.1735|0.6369|0.3565|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-consensus.json / experiment-log.json

### drumscribe/experiments/results-iterative-crash-context.json

- implementation: drumscribe/experiments/iterative_search_crash_context.py
- script commit: 5bdbf4947d77bb0e9816d44dac8250b63e45115e
- result commit: 90abee856ca881b288c4a51bccf31033646085c8

#### Cycle 139

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c139_kick|winner|0.7219|0.7214|0.7224|0.9590|0.8107|0.6798|0.3870|0.6667|0.3958|0.1628|42|25|
|c139_all|-|0.7215|0.7207|0.7224|0.9590|0.8107|0.6798|0.3870|0.6667|0.3891|0.1628|42|25|
|c139_kick_snare|-|0.7215|0.7207|0.7224|0.9590|0.8107|0.6798|0.3870|0.6667|0.3891|0.1628|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-context.json / experiment-log.json

#### Cycle 140

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c140_w060|winner|0.7220|0.7218|0.7222|0.9590|0.8107|0.6798|0.3870|0.6667|0.3951|0.1628|42|25|
|c140_w100|-|0.7219|0.7214|0.7224|0.9590|0.8107|0.6798|0.3870|0.6667|0.3958|0.1628|42|25|
|c140_w140|-|0.7218|0.7212|0.7224|0.9590|0.8107|0.6798|0.3870|0.6667|0.3938|0.1628|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-context.json / experiment-log.json

#### Cycle 141

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c141_support_only|winner|0.7220|0.7218|0.7222|0.9590|0.8107|0.6798|0.3870|0.6667|0.3951|0.1628|42|25|
|c141_head15|-|0.7219|0.7226|0.7211|0.9590|0.8107|0.6798|0.3870|0.6667|0.3734|0.1628|42|25|
|c141_head25|-|0.7219|0.7226|0.7211|0.9590|0.8107|0.6798|0.3870|0.6667|0.3734|0.1628|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-context.json / experiment-log.json

### drumscribe/experiments/results-iterative-crash-fallback.json

- implementation: drumscribe/experiments/iterative_search_crash_fallback.py
- script commit: 46b3c0499d6233e27d9adc09d92f5a721a3eadee
- result commit: a95a6d8ebca59d142f816d267369e1d8d60a3149

#### Cycle 88

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c88_precision|winner, close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c88_zero_base|close|0.7190|0.7151|0.7230|0.9590|0.8107|0.6744|0.3865|0.6369|0.3891|0.0000|42|25|
|c88_sparse_recall|close|0.7184|0.7145|0.7223|0.9590|0.8107|0.6735|0.3865|0.6369|0.3824|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-fallback.json / experiment-log.json

#### Cycle 89

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c89_ratio10|winner, close|0.7184|0.7145|0.7223|0.9590|0.8107|0.6735|0.3865|0.6369|0.3824|0.0000|42|25|
|c89_ratio25|close|0.7184|0.7145|0.7223|0.9590|0.8107|0.6735|0.3865|0.6369|0.3824|0.0000|42|25|
|c89_ratio50|close|0.7184|0.7145|0.7223|0.9590|0.8107|0.6735|0.3865|0.6369|0.3824|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-fallback.json / experiment-log.json

#### Cycle 90

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c90_gap4|winner, close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c90_gap8|close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c90_gap12|close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-fallback.json / experiment-log.json

### drumscribe/experiments/results-iterative-crash-meta-loo.json

- implementation: drumscribe/experiments/iterative_search_crash_meta_loo.py
- script commit: f219c0f318d6cd3110ad6d66cb1a1db2a39721cb
- result commit: abf9a9ff8aa665f72a50afb54848f5a09907e3df

#### Cycle 204

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c204_extra|winner|0.8002|0.8435|0.7611|0.9626|0.8858|0.7913|0.5101|0.7624|0.4212|0.3247|2|28|
|c204_logistic|-|0.7922|0.8357|0.7529|0.9626|0.8858|0.7808|0.5067|0.7624|0.3634|0.3249|2|28|
|c204_heuristic|-|0.7806|0.8247|0.7409|0.9626|0.8858|0.7671|0.4867|0.7624|0.3337|0.3212|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-meta-loo.json / experiment-log.json

#### Cycle 205

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c205_t65|winner|0.8049|0.8466|0.7671|0.9626|0.8858|0.7970|0.5314|0.7624|0.4528|0.3230|2|28|
|c205_t50|-|0.8002|0.8435|0.7611|0.9626|0.8858|0.7913|0.5101|0.7624|0.4212|0.3247|2|28|
|c205_t35|-|0.7915|0.8370|0.7507|0.9626|0.8858|0.7813|0.4829|0.7624|0.3732|0.3225|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-meta-loo.json / experiment-log.json

#### Cycle 206

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c206_h10|-|0.8049|0.8466|0.7671|0.9626|0.8858|0.7970|0.5314|0.7624|0.4528|0.3230|2|28|
|c206_h20|-|0.8049|0.8466|0.7671|0.9626|0.8858|0.7970|0.5314|0.7624|0.4528|0.3230|2|28|
|c206_h35|winner|0.8049|0.8466|0.7671|0.9626|0.8858|0.7970|0.5314|0.7624|0.4528|0.3230|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crash-meta-loo.json / experiment-log.json

### drumscribe/experiments/results-iterative-crossstem-hat.json

- implementation: drumscribe/experiments/iterative_search_crossstem_hat.py
- script commit: b56b55df9a106527cf65f8f908823aea67e7b580
- result commit: a75f17b36ce72bcbcfd14e79f8a9fff736f8c7b0

#### Cycle 85

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c85_loose|winner, close|0.7159|0.7267|0.7053|0.9590|0.8107|0.6645|0.3865|0.6369|0.3734|0.0000|42|25|
|c85_balanced|close|0.7143|0.7356|0.6942|0.9590|0.8107|0.6591|0.3865|0.6369|0.3734|0.0000|42|25|
|c85_strict|close|0.7131|0.7445|0.6842|0.9590|0.8107|0.6545|0.3865|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crossstem-hat.json / experiment-log.json

#### Cycle 86

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c86_no_rescue|winner, close|0.7159|0.7267|0.7053|0.9590|0.8107|0.6645|0.3865|0.6369|0.3734|0.0000|42|25|
|c86_rescue75|close|0.7158|0.7146|0.7170|0.9590|0.8107|0.6662|0.3865|0.6369|0.3734|0.0000|42|25|
|c86_rescue50|close|0.7126|0.7070|0.7183|0.9590|0.8107|0.6598|0.3865|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crossstem-hat.json / experiment-log.json

#### Cycle 87

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c87_thr24|winner, close|0.7192|0.7173|0.7212|0.9590|0.8107|0.6741|0.3865|0.6369|0.3734|0.0000|42|25|
|c87_thr30|close|0.7159|0.7267|0.7053|0.9590|0.8107|0.6645|0.3865|0.6369|0.3734|0.0000|42|25|
|c87_thr36|close|0.7088|0.7348|0.6846|0.9590|0.8107|0.6453|0.3865|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-crossstem-hat.json / experiment-log.json

### drumscribe/experiments/results-iterative-cymbal-template-v2.json

- implementation: drumscribe/experiments/iterative_search_cymbal_template_v2.py
- script commit: 0c10939c41e8672d3fed6ab054bdfe87ef05aa85
- result commit: 85f557efdf9f69c85ec1aba728799da496d71438

#### Cycle 198

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c198_base|winner|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c198_precision|part-leader|0.7959|0.8242|0.7695|0.9626|0.8880|0.7792|0.5222|0.7582|0.4632|0.3467|2|28|
|c198_default|-|0.7947|0.8211|0.7700|0.9626|0.8880|0.7791|0.5222|0.7582|0.4538|0.3457|2|28|
|c198_recall|-|0.7932|0.8170|0.7708|0.9626|0.8880|0.7791|0.5222|0.7582|0.4405|0.3465|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-cymbal-template-v2.json / experiment-log.json

#### Cycle 199

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c199_m115|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c199_m135|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c199_m155|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c199_m180|winner|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-cymbal-template-v2.json / experiment-log.json

#### Cycle 200

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c200_s30h80|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c200_s35h85|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c200_s39h90|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c200_s45h95|-|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|
|c200_s50h100|winner|0.7967|0.8310|0.7651|0.9626|0.8880|0.7795|0.5222|0.7582|0.3955|0.3503|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-cymbal-template-v2.json / experiment-log.json

### drumscribe/experiments/results-iterative-drumsep-rate.json

- implementation: drumscribe/experiments/iterative_search_drumsep_rate.py
- script commit: 1750105b257458e9e2f5c71339de5db0af0466d1
- result commit: 2b2544225c63d1066f08660945e67bcad5c2bd8d

#### Cycle 46

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c46_sr44100|winner, close|0.5770|0.4990|0.6839|0.8950|0.6368|0.6702|0.0000|0.0461|0.1460|0.0000|84|31|
|c46_sr22050|close|0.5732|0.4954|0.6799|0.8924|0.6393|0.6603|0.0000|0.0462|0.1583|0.0000|80|31|
|c46_sr11025|-|0.5330|0.4488|0.6562|0.8926|0.6425|0.5548|0.0000|0.0474|0.1351|0.0000|67|31|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-drumsep-rate.json / experiment-log.json

#### Cycle 47

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c47_precision|winner, close|0.5850|0.5266|0.6580|0.8922|0.6760|0.6638|0.0000|0.0518|0.1192|0.0000|51|29|
|c47_balanced|-|0.5770|0.4990|0.6839|0.8950|0.6368|0.6702|0.0000|0.0461|0.1460|0.0000|84|31|
|c47_recall|-|0.5681|0.4739|0.7091|0.8872|0.5979|0.6804|0.0000|0.0422|0.1458|0.0000|126|34|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-drumsep-rate.json / experiment-log.json

#### Cycle 48

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c48_none|winner, close|0.5850|0.5266|0.6580|0.8922|0.6760|0.6638|0.0000|0.0518|0.1192|0.0000|51|29|
|c48_hat_guard|-|0.5724|0.5222|0.6332|0.8922|0.6745|0.6444|0.0000|0.0518|0.1190|0.0000|52|29|
|c48_kick_hat_guard|-|0.5684|0.5213|0.6248|0.8865|0.6740|0.6435|0.0000|0.0518|0.1159|0.0000|52|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-drumsep-rate.json / experiment-log.json

### drumscribe/experiments/results-iterative-fusion-v2.json

- implementation: drumscribe/experiments/iterative_search_fusion_v2.py
- script commit: 99009a62957b7deeb87ebc0ec193171a0b3d0bf6
- result commit: fa82b933074e72022d26bf651ce3bf156d4d2686

#### Cycle 82

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c82_robust|winner, close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c82_balanced|close|0.7184|0.7146|0.7223|0.9590|0.8113|0.6735|0.3865|0.6369|0.3824|0.0000|42|25|
|c82_recall|-|0.7141|0.6914|0.7383|0.9590|0.8253|0.6724|0.3543|0.6369|0.3824|0.0000|103|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v2.json / experiment-log.json

#### Cycle 83

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c83_hat_precision|winner, close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c83_hat_recall|close|0.7185|0.7128|0.7244|0.9590|0.8107|0.6731|0.3865|0.6369|0.3734|0.0000|42|25|
|c83_hat_hi441|close|0.7172|0.7086|0.7260|0.9590|0.8107|0.6705|0.3865|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v2.json / experiment-log.json

#### Cycle 84

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c84_pedal75|winner, close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c84_pedal_base|-|0.7163|0.7322|0.7012|0.9590|0.8107|0.6744|0.1735|0.6369|0.3734|0.0000|42|25|
|c84_pedal50|close|0.7124|0.7015|0.7237|0.9590|0.8107|0.6744|0.3543|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v2.json / experiment-log.json

### drumscribe/experiments/results-iterative-fusion-v3.json

- implementation: drumscribe/experiments/iterative_search_fusion_v3.py
- script commit: 975e9458106a7bf3ea3059d0cd3cdceb15d3ef93
- result commit: 8bed53a7ce830e0258cca2e681771cf9d29620c2

#### Cycle 118

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c118_tom_snare|winner|0.7204|0.7162|0.7246|0.9590|0.8133|0.6747|0.3870|0.6667|0.3734|0.0000|45|25|
|c118_snare|-|0.7200|0.7161|0.7241|0.9590|0.8133|0.6745|0.3870|0.6369|0.3734|0.0000|45|25|
|c118_tom|-|0.7197|0.7173|0.7222|0.9590|0.8107|0.6746|0.3870|0.6667|0.3734|0.0000|42|25|
|c118_base|-|0.7194|0.7171|0.7217|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v3.json / experiment-log.json

#### Cycle 119

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c119_ride_off|winner|0.7204|0.7162|0.7246|0.9590|0.8133|0.6747|0.3870|0.6667|0.3734|0.0000|45|25|
|c119_ride_gate|-|0.7186|0.7145|0.7228|0.9590|0.8133|0.6718|0.3870|0.6667|0.3734|0.0941|45|25|
|c119_ride_consensus|-|0.7186|0.7144|0.7228|0.9590|0.8133|0.6723|0.3870|0.6667|0.3734|0.0315|45|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v3.json / experiment-log.json

#### Cycle 120

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c120_crash_precision|winner|0.7204|0.7162|0.7246|0.9590|0.8133|0.6747|0.3870|0.6667|0.3734|0.0000|45|25|
|c120_crash_zero|-|0.7200|0.7143|0.7259|0.9590|0.8133|0.6747|0.3870|0.6667|0.3891|0.0000|45|25|
|c120_crash_recall|-|0.7194|0.7137|0.7252|0.9590|0.8133|0.6738|0.3870|0.6667|0.3824|0.0000|45|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v3.json / experiment-log.json

### drumscribe/experiments/results-iterative-fusion-v4.json

- implementation: drumscribe/experiments/iterative_search_fusion_v4.py
- script commit: 49b2965a2bc8428e2b58d94159cfcb114206b2da
- result commit: d5aea2e0a171fd74c7b3eb6f7eaf0d31258d3ce0

#### Cycle 121

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c121_off|winner|0.7197|0.7173|0.7222|0.9590|0.8107|0.6746|0.3870|0.6667|0.3734|0.0000|42|25|
|c121_adaptive|-|0.7173|0.7120|0.7227|0.9590|0.8107|0.6701|0.3870|0.6667|0.3734|0.1628|42|25|
|c121_fallback|-|0.7170|0.7113|0.7228|0.9590|0.8107|0.6711|0.3870|0.6667|0.3734|0.1605|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v4.json / experiment-log.json

#### Cycle 122

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c122_balanced|-|0.7197|0.7173|0.7222|0.9590|0.8107|0.6746|0.3870|0.6667|0.3734|0.0000|42|25|
|c122_precision|winner|0.7197|0.7173|0.7222|0.9590|0.8107|0.6746|0.3870|0.6667|0.3734|0.0000|42|25|
|c122_fallback|-|0.7194|0.7154|0.7235|0.9590|0.8107|0.6746|0.3870|0.6667|0.3891|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v4.json / experiment-log.json

#### Cycle 123

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c123_highrecall|-|0.7231|0.7129|0.7335|0.9590|0.8253|0.6749|0.3870|0.6667|0.3734|0.0000|103|25|
|c123_balanced|winner|0.7197|0.7173|0.7222|0.9590|0.8107|0.6746|0.3870|0.6667|0.3734|0.0000|42|25|
|c123_safe|-|0.7194|0.7160|0.7228|0.9590|0.8071|0.6747|0.3870|0.6667|0.3734|0.0000|44|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v4.json / experiment-log.json

### drumscribe/experiments/results-iterative-fusion-v5.json

- implementation: drumscribe/experiments/iterative_search_fusion_v5.py
- script commit: 6bfd837a7963440492e19da4de293ba0fc2df0cf
- result commit: 5afebe2e69b6bcfb825c560a96a57b5f5f93cb29

#### Cycle 127

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c127_tight|-|0.7226|0.7263|0.7189|0.9590|0.8107|0.6815|0.3870|0.6667|0.3734|0.0941|42|25|
|c127_adaptive|winner|0.7219|0.7226|0.7211|0.9590|0.8107|0.6798|0.3870|0.6667|0.3734|0.1628|42|25|
|c127_fallback|-|0.7213|0.7215|0.7212|0.9590|0.8107|0.6804|0.3870|0.6667|0.3734|0.1605|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v5.json / experiment-log.json

#### Cycle 128

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c128_balanced|-|0.7219|0.7226|0.7211|0.9590|0.8107|0.6798|0.3870|0.6667|0.3734|0.1628|42|25|
|c128_precision|winner|0.7219|0.7226|0.7211|0.9590|0.8107|0.6798|0.3870|0.6667|0.3734|0.1628|42|25|
|c128_fallback|-|0.7215|0.7207|0.7224|0.9590|0.8107|0.6798|0.3870|0.6667|0.3891|0.1628|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v5.json / experiment-log.json

#### Cycle 129

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c129_highrecall|-|0.7252|0.7181|0.7324|0.9590|0.8253|0.6800|0.3870|0.6667|0.3734|0.1628|103|25|
|c129_balanced|winner|0.7219|0.7226|0.7211|0.9590|0.8107|0.6798|0.3870|0.6667|0.3734|0.1628|42|25|
|c129_safe|-|0.7215|0.7213|0.7217|0.9590|0.8071|0.6798|0.3870|0.6667|0.3734|0.1628|44|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v5.json / experiment-log.json

### drumscribe/experiments/results-iterative-fusion-v6.json

- implementation: drumscribe/experiments/iterative_search_fusion_v6.py
- script commit: b569726f85eb5f11bc43b47e0efea54d9f05f72c
- result commit: d49594ff7bdbcf3d52c884cc197f720eed00e2e5

#### Cycle 142

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c142_pedal_crash|-|0.7221|0.7214|0.7229|0.9590|0.8107|0.6798|0.3920|0.6667|0.3951|0.1628|42|25|
|c142_base|-|0.7219|0.7226|0.7211|0.9590|0.8107|0.6798|0.3870|0.6667|0.3734|0.1628|42|25|
|c142_all_three|winner|0.7208|0.7201|0.7216|0.9590|0.8107|0.6743|0.3920|0.6667|0.3951|0.2792|42|25|
|c142_pedal_ride|-|0.7207|0.7209|0.7205|0.9590|0.8107|0.6743|0.3920|0.6667|0.3734|0.2792|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v6.json / experiment-log.json

#### Cycle 143

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c143_highrecall|-|0.7242|0.7157|0.7329|0.9590|0.8253|0.6746|0.3920|0.6667|0.3951|0.2792|103|25|
|c143_balanced|winner|0.7208|0.7201|0.7216|0.9590|0.8107|0.6743|0.3920|0.6667|0.3951|0.2792|42|25|
|c143_safe|-|0.7205|0.7188|0.7222|0.9590|0.8071|0.6744|0.3920|0.6667|0.3951|0.2792|44|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v6.json / experiment-log.json

#### Cycle 144

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c144_adaptive|winner|0.7208|0.7201|0.7216|0.9590|0.8107|0.6743|0.3920|0.6667|0.3951|0.2792|42|25|
|c144_crossstem|-|0.7105|0.7324|0.6900|0.9590|0.8107|0.6450|0.3920|0.6667|0.3951|0.2792|42|25|
|c144_pattern|-|0.7063|0.7269|0.6868|0.9590|0.8107|0.6346|0.3920|0.6667|0.3951|0.2792|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-fusion-v6.json / experiment-log.json

### drumscribe/experiments/results-iterative-guarded-fusion.json

- implementation: drumscribe/experiments/iterative_search_guarded_fusion.py
- script commit: 8662ba0394191b5b1a783292550846757028d46f
- result commit: bdaa023c644f9a367a86be90862002ae53465160

#### Cycle 109

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c109_tom|-|0.7197|0.7173|0.7222|0.9590|0.8107|0.6746|0.3870|0.6667|0.3734|0.0000|42|25|
|c109_base|-|0.7194|0.7171|0.7217|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0000|42|25|
|c109_tom_ride|winner|0.7180|0.7156|0.7204|0.9590|0.8107|0.6717|0.3870|0.6667|0.3734|0.0941|42|25|
|c109_ride|-|0.7177|0.7154|0.7199|0.9590|0.8107|0.6715|0.3870|0.6369|0.3734|0.0941|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-guarded-fusion.json / experiment-log.json

#### Cycle 110

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c110_snare_pattern|-|0.7213|0.7113|0.7317|0.9590|0.8253|0.6719|0.3870|0.6667|0.3734|0.0941|103|25|
|c110_snare_base|-|0.7180|0.7156|0.7204|0.9590|0.8107|0.6717|0.3870|0.6667|0.3734|0.0941|42|25|
|c110_snare_veto|winner|0.7180|0.7156|0.7204|0.9590|0.8107|0.6717|0.3870|0.6667|0.3734|0.0941|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-guarded-fusion.json / experiment-log.json

#### Cycle 111

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c111_crash_precision|-|0.7180|0.7156|0.7204|0.9590|0.8107|0.6717|0.3870|0.6667|0.3734|0.0941|42|25|
|c111_crash_zero|winner|0.7177|0.7137|0.7217|0.9590|0.8107|0.6717|0.3870|0.6667|0.3891|0.0941|42|25|
|c111_crash_recall|-|0.7170|0.7131|0.7210|0.9590|0.8107|0.6708|0.3870|0.6667|0.3824|0.0941|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-guarded-fusion.json / experiment-log.json

### drumscribe/experiments/results-iterative-hat-adaptive-v2.json

- implementation: drumscribe/experiments/iterative_search_hat_adaptive_v2.py
- script commit: c53664a63d2e4fc0e0edc86f545adbac44df95d4
- result commit: 66e32cb71514d3c274af4a411591e67abb69a2b4

#### Cycle 207

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c207_r12|-|0.8090|0.8539|0.7685|0.9626|0.8858|0.8019|0.5592|0.7624|0.4560|0.3480|2|28|
|c207_r15|winner|0.8090|0.8539|0.7685|0.9626|0.8858|0.8019|0.5592|0.7624|0.4560|0.3480|2|28|
|c207_r18|-|0.8081|0.8509|0.7694|0.9626|0.8858|0.7997|0.5592|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-adaptive-v2.json / experiment-log.json

#### Cycle 208

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c208_l14|winner|0.8088|0.8535|0.7685|0.9626|0.8858|0.8014|0.5592|0.7624|0.4560|0.3480|2|28|
|c208_l18|-|0.8079|0.8510|0.7690|0.9626|0.8858|0.7993|0.5592|0.7624|0.4560|0.3480|2|28|
|c208_l22|-|0.8076|0.8480|0.7710|0.9626|0.8858|0.7987|0.5592|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-adaptive-v2.json / experiment-log.json

#### Cycle 209

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c209_b8|winner|0.8088|0.8535|0.7685|0.9626|0.8858|0.8014|0.5592|0.7624|0.4560|0.3480|2|28|
|c209_b4|-|0.8088|0.8533|0.7687|0.9626|0.8858|0.8014|0.5592|0.7624|0.4560|0.3480|2|28|
|c209_b16|-|0.8087|0.8533|0.7686|0.9626|0.8858|0.8013|0.5592|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-adaptive-v2.json / experiment-log.json

### drumscribe/experiments/results-iterative-hat-adaptive.json

- implementation: drumscribe/experiments/iterative_search_hat_adaptive.py
- script commit: d8153e31b16c88dfad9556a9b9012312c2555701
- result commit: 59cfa2e67e2f57c8297363bc420e719eb066f261

#### Cycle 124

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c124_t20|winner|0.7243|0.7280|0.7206|0.9590|0.8107|0.6842|0.3870|0.6667|0.3734|0.0000|42|25|
|c124_t17|-|0.7110|0.7317|0.6915|0.9590|0.8107|0.6508|0.3870|0.6667|0.3734|0.0000|42|25|
|c124_t12|-|0.7096|0.7335|0.6873|0.9590|0.8107|0.6469|0.3870|0.6667|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-adaptive.json / experiment-log.json

#### Cycle 125

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c125_pat2|winner|0.7243|0.7280|0.7206|0.9590|0.8107|0.6842|0.3870|0.6667|0.3734|0.0000|42|25|
|c125_intersection|-|0.7243|0.7280|0.7206|0.9590|0.8107|0.6842|0.3870|0.6667|0.3734|0.0000|42|25|
|c125_pat8|-|0.7234|0.7261|0.7207|0.9590|0.8107|0.6822|0.3870|0.6667|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-adaptive.json / experiment-log.json

#### Cycle 126

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c126_t20|winner|0.7243|0.7280|0.7206|0.9590|0.8107|0.6842|0.3870|0.6667|0.3734|0.0000|42|25|
|c126_t22|-|0.7197|0.7173|0.7222|0.9590|0.8107|0.6746|0.3870|0.6667|0.3734|0.0000|42|25|
|c126_t18|-|0.7148|0.7281|0.7019|0.9590|0.8107|0.6608|0.3870|0.6667|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-adaptive.json / experiment-log.json

### drumscribe/experiments/results-iterative-hat-bleed.json

- implementation: drumscribe/experiments/iterative_search_hat_bleed.py
- script commit: 49b00292bc32ad98e560e434a61f0d3dafd6bfb4
- result commit: 7ff542afcf5b36e24ca1b6211efc5cf11fa82c73

#### Cycle 160

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c160_strict|winner|0.7283|0.7420|0.7151|0.9590|0.8379|0.6805|0.3933|0.6667|0.3936|0.2841|41|25|
|c160_consensus_repeat|-|0.7279|0.7413|0.7151|0.9590|0.8379|0.6797|0.3933|0.6667|0.3936|0.2841|41|25|
|c160_balanced|-|0.7278|0.7364|0.7193|0.9590|0.8379|0.6800|0.3933|0.6667|0.3936|0.2841|41|25|
|c160_base|-|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-bleed.json / experiment-log.json

#### Cycle 161

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c161_kick_very_strict|winner|0.7278|0.7402|0.7157|0.9590|0.8379|0.6795|0.3933|0.6667|0.3936|0.2841|41|25|
|c161_balanced|-|0.7278|0.7364|0.7193|0.9590|0.8379|0.6800|0.3933|0.6667|0.3936|0.2841|41|25|
|c161_base|-|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|
|c161_kick_strict|-|0.7274|0.7392|0.7159|0.9590|0.8379|0.6786|0.3933|0.6667|0.3936|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-bleed.json / experiment-log.json

#### Cycle 162

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c162_thr20|winner|0.7283|0.7420|0.7151|0.9590|0.8379|0.6805|0.3933|0.6667|0.3936|0.2841|41|25|
|c162_thr30|-|0.7275|0.7399|0.7156|0.9590|0.8379|0.6790|0.3933|0.6667|0.3936|0.2841|41|25|
|c162_thr40|-|0.7273|0.7394|0.7156|0.9590|0.8379|0.6785|0.3933|0.6667|0.3936|0.2841|41|25|
|c162_thr50|-|0.7269|0.7378|0.7162|0.9590|0.8379|0.6775|0.3933|0.6667|0.3936|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-bleed.json / experiment-log.json

### drumscribe/experiments/results-iterative-hat-density-guard-v10.json

- implementation: drumscribe/experiments/iterative_search_hat_density_guard_v10.py
- script commit: dd52a998cff103679d426a7cd4bebc4e5d7251e5
- result commit: 126f6c06010cac99f14ba76d7c7818f35f5ea921

#### Cycle 222

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c222_r045|-|0.8138|0.8680|0.7659|0.9626|0.8858|0.8119|0.5670|0.7624|0.4560|0.3480|2|28|
|c222_r055|-|0.8138|0.8680|0.7659|0.9626|0.8858|0.8119|0.5670|0.7624|0.4560|0.3480|2|28|
|c222_r065|winner|0.8138|0.8680|0.7659|0.9626|0.8858|0.8119|0.5670|0.7624|0.4560|0.3480|2|28|
|c222_base|-|0.8097|0.8554|0.7686|0.9626|0.8858|0.8019|0.5670|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-density-guard-v10.json / experiment-log.json

#### Cycle 223

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c223_whole_best|winner|0.8138|0.8680|0.7659|0.9626|0.8858|0.8119|0.5670|0.7624|0.4560|0.3480|2|28|
|c223_l065|-|0.8118|0.8664|0.7636|0.9626|0.8858|0.8069|0.5670|0.7624|0.4560|0.3480|2|28|
|c223_l045|-|0.8116|0.8668|0.7629|0.9626|0.8858|0.8064|0.5670|0.7624|0.4560|0.3480|2|28|
|c223_l055|-|0.8114|0.8663|0.7630|0.9626|0.8858|0.8059|0.5670|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-density-guard-v10.json / experiment-log.json

#### Cycle 224

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c224_prev_best|winner|0.8138|0.8680|0.7659|0.9626|0.8858|0.8119|0.5670|0.7624|0.4560|0.3480|2|28|
|c224_b16|-|0.8114|0.8659|0.7633|0.9626|0.8858|0.8060|0.5670|0.7624|0.4560|0.3480|2|28|
|c224_b8|-|0.8114|0.8663|0.7630|0.9626|0.8858|0.8059|0.5670|0.7624|0.4560|0.3480|2|28|
|c224_b4|-|0.8112|0.8669|0.7622|0.9626|0.8858|0.8055|0.5670|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-density-guard-v10.json / experiment-log.json

### drumscribe/experiments/results-iterative-hat-fixed-threshold-v11.json

- implementation: drumscribe/experiments/iterative_search_hat_fixed_threshold_v11.py
- script commit: cace1e118602e282078f3ca9cc7a3a0888a99440
- result commit: 408e9baa5e3fc04e25e7fccda510a34e6ef95110

#### Cycle 225

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c225_p45|-|0.8128|0.8643|0.7671|0.9626|0.8858|0.8095|0.5670|0.7624|0.4560|0.3480|2|28|
|c225_p55|winner|0.8128|0.8685|0.7637|0.9626|0.8858|0.8094|0.5670|0.7624|0.4560|0.3480|2|28|
|c225_p35|-|0.8117|0.8607|0.7680|0.9626|0.8858|0.8068|0.5670|0.7624|0.4560|0.3480|2|28|
|c225_base|-|0.8097|0.8554|0.7686|0.9626|0.8858|0.8019|0.5670|0.7624|0.4560|0.3480|2|28|
|c225_p65|-|0.8070|0.8710|0.7518|0.9626|0.8858|0.7947|0.5670|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-fixed-threshold-v11.json / experiment-log.json

#### Cycle 226

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c226_medium|winner|0.8128|0.8685|0.7637|0.9626|0.8858|0.8094|0.5670|0.7624|0.4560|0.3480|2|28|
|c226_full|-|0.8127|0.8684|0.7636|0.9626|0.8858|0.8091|0.5670|0.7624|0.4560|0.3480|2|28|
|c226_small|-|0.8124|0.8689|0.7627|0.9626|0.8858|0.8083|0.5670|0.7624|0.4560|0.3480|2|28|
|c226_base|-|0.8097|0.8554|0.7686|0.9626|0.8858|0.8019|0.5670|0.7624|0.4560|0.3480|2|28|
|c226_micro|-|0.8079|0.8703|0.7538|0.9626|0.8858|0.7969|0.5670|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-fixed-threshold-v11.json / experiment-log.json

#### Cycle 227

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c227_prev|-|0.8128|0.8685|0.7637|0.9626|0.8858|0.8094|0.5670|0.7624|0.4560|0.3480|2|28|
|c227_rep100_w60|-|0.8128|0.8685|0.7637|0.9626|0.8858|0.8094|0.5670|0.7624|0.4560|0.3480|2|28|
|c227_rep100_w80|winner|0.8128|0.8685|0.7637|0.9626|0.8858|0.8094|0.5670|0.7624|0.4560|0.3480|2|28|
|c227_rep75_w35|-|0.8124|0.8631|0.7674|0.9626|0.8858|0.8086|0.5670|0.7624|0.4560|0.3480|2|28|
|c227_norescue_w60|-|0.8028|0.8745|0.7419|0.9626|0.8858|0.7835|0.5670|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-fixed-threshold-v11.json / experiment-log.json

### drumscribe/experiments/results-iterative-hat-fusion.json

- implementation: drumscribe/experiments/iterative_search_hat_fusion.py
- script commit: 3f90f1735f403b40baee5aaf9f8de9973211cdf6
- result commit: db7d8269a9eadcaa40ce836aab456b9923bed5ee

#### Cycle 67

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c67_hi441|winner, close|0.7134|0.7218|0.7052|0.9590|0.8130|0.6705|0.1735|0.6369|0.3517|0.0000|42|25|
|c67_guard|-|0.7041|0.7460|0.6667|0.9590|0.8130|0.6447|0.1735|0.6369|0.3517|0.0000|42|25|
|c67_consensus|-|0.7041|0.7460|0.6666|0.9590|0.8130|0.6445|0.1735|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-fusion.json / experiment-log.json

#### Cycle 68

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c68_w25|winner, close|0.7041|0.7460|0.6666|0.9590|0.8130|0.6445|0.1735|0.6369|0.3517|0.0000|42|25|
|c68_w45|close|0.7041|0.7460|0.6666|0.9590|0.8130|0.6445|0.1735|0.6369|0.3517|0.0000|42|25|
|c68_w70|close|0.7041|0.7460|0.6666|0.9590|0.8130|0.6445|0.1735|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-fusion.json / experiment-log.json

#### Cycle 69

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c69_repeat3|winner, close|0.7148|0.7263|0.7036|0.9590|0.8130|0.6731|0.1735|0.6369|0.3517|0.0000|42|25|
|c69_repeat2|close|0.7142|0.7238|0.7047|0.9590|0.8130|0.6719|0.1735|0.6369|0.3517|0.0000|42|25|
|c69_none|-|0.7041|0.7460|0.6666|0.9590|0.8130|0.6445|0.1735|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-fusion.json / experiment-log.json

### drumscribe/experiments/results-iterative-hat-gate-refine.json

- implementation: drumscribe/experiments/iterative_search_hat_gate_refine.py
- script commit: fea5b94af0088ff26feff359765a422d7f9270ec
- result commit: 816a2c1908b6e7f07671d30e645f7a7fbccd39d8

#### Cycle 181

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c181_g30|-|0.7947|0.8360|0.7574|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.2742|2|28|
|c181_g33|winner|0.7947|0.8360|0.7574|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.2742|2|28|
|c181_g34|-|0.7934|0.8288|0.7609|0.9626|0.8880|0.7758|0.5058|0.7582|0.3955|0.2742|2|28|
|c181_g35|-|0.7934|0.8288|0.7609|0.9626|0.8880|0.7758|0.5058|0.7582|0.3955|0.2742|2|28|
|c181_g38|-|0.7934|0.8288|0.7609|0.9626|0.8880|0.7758|0.5058|0.7582|0.3955|0.2742|2|28|
|c181_g40|-|0.7934|0.8288|0.7609|0.9626|0.8880|0.7758|0.5058|0.7582|0.3955|0.2742|2|28|
|c181_g45|-|0.7934|0.8288|0.7609|0.9626|0.8880|0.7758|0.5058|0.7582|0.3955|0.2742|2|28|
|c181_g50|-|0.7934|0.8288|0.7609|0.9626|0.8880|0.7758|0.5058|0.7582|0.3955|0.2742|2|28|
|c181_g60|-|0.7920|0.8189|0.7669|0.9626|0.8880|0.7730|0.5058|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-gate-refine.json / experiment-log.json

#### Cycle 182

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c182_balanced|-|0.7949|0.8289|0.7635|0.9626|0.8880|0.7799|0.5033|0.7582|0.3955|0.2742|2|28|
|c182_strict|-|0.7948|0.8359|0.7575|0.9626|0.8880|0.7794|0.5033|0.7582|0.3955|0.2742|2|28|
|c182_very_strict|winner|0.7947|0.8360|0.7574|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.2742|2|28|
|c182_loose|-|0.7943|0.8202|0.7701|0.9626|0.8880|0.7784|0.5058|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-gate-refine.json / experiment-log.json

#### Cycle 183

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c183_g290|-|0.7947|0.8360|0.7574|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.2742|2|28|
|c183_g310|-|0.7947|0.8360|0.7574|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.2742|2|28|
|c183_g320|-|0.7947|0.8360|0.7574|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.2742|2|28|
|c183_g330|winner|0.7947|0.8360|0.7574|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.2742|2|28|
|c183_g340|-|0.7934|0.8288|0.7609|0.9626|0.8880|0.7758|0.5058|0.7582|0.3955|0.2742|2|28|
|c183_g350|-|0.7934|0.8288|0.7609|0.9626|0.8880|0.7758|0.5058|0.7582|0.3955|0.2742|2|28|
|c183_g370|-|0.7934|0.8288|0.7609|0.9626|0.8880|0.7758|0.5058|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-gate-refine.json / experiment-log.json

### drumscribe/experiments/results-iterative-hat-kick-gate.json

- implementation: drumscribe/experiments/iterative_search_hat_kick_gate.py
- script commit: e147628169c49bfbeac45824a3f38d3310eba8f0
- result commit: 7e9276a0ba2e734ac6a3f8014b27503429f6d7cd

#### Cycle 115

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c115_support25|winner|0.7174|0.7232|0.7117|0.9590|0.8107|0.6686|0.3870|0.6369|0.3734|0.0000|42|25|
|c115_support45|-|0.7173|0.7231|0.7117|0.9590|0.8107|0.6685|0.3870|0.6369|0.3734|0.0000|42|25|
|c115_support70|-|0.7171|0.7226|0.7117|0.9590|0.8107|0.6680|0.3870|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-kick-gate.json / experiment-log.json

#### Cycle 116

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c116_kick20|winner|0.7181|0.7204|0.7158|0.9590|0.8107|0.6708|0.3870|0.6369|0.3734|0.0000|42|25|
|c116_kick55|-|0.7175|0.7238|0.7114|0.9590|0.8107|0.6689|0.3870|0.6369|0.3734|0.0000|42|25|
|c116_kick35|-|0.7174|0.7232|0.7117|0.9590|0.8107|0.6686|0.3870|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-kick-gate.json / experiment-log.json

#### Cycle 117

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c117_rescue4|winner|0.7199|0.7182|0.7216|0.9590|0.8107|0.6754|0.3870|0.6369|0.3734|0.0000|42|25|
|c117_rescue3|-|0.7197|0.7178|0.7216|0.9590|0.8107|0.6750|0.3870|0.6369|0.3734|0.0000|42|25|
|c117_rescue2|-|0.7195|0.7173|0.7216|0.9590|0.8107|0.6745|0.3870|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-kick-gate.json / experiment-log.json

### drumscribe/experiments/results-iterative-hat-meta-loo.json

- implementation: drumscribe/experiments/iterative_search_hat_meta_loo.py
- script commit: a9b57571805ec17854af3bc2ccbc70ea1128f0f9
- result commit: 1e8e34d4f437cb2678350266acde734f572ec1bb

#### Cycle 198

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c198_heuristic|-|0.8025|0.8457|0.7635|0.9626|0.8858|0.7860|0.5592|0.7624|0.4560|0.3480|2|28|
|c198_extra|-|0.7954|0.8660|0.7355|0.9626|0.8858|0.7664|0.5592|0.7624|0.4560|0.3480|2|28|
|c198_logistic|winner|0.7731|0.8627|0.7004|0.9626|0.8858|0.7054|0.5592|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-meta-loo.json / experiment-log.json

#### Cycle 199

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c199_t35|winner|0.7810|0.8609|0.7148|0.9626|0.8858|0.7279|0.5592|0.7624|0.4560|0.3480|2|28|
|c199_t50|-|0.7731|0.8627|0.7004|0.9626|0.8858|0.7054|0.5592|0.7624|0.4560|0.3480|2|28|
|c199_t65|-|0.7635|0.8640|0.6839|0.9626|0.8858|0.6771|0.5592|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-meta-loo.json / experiment-log.json

#### Cycle 200

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c200_repeat|winner|0.8075|0.8571|0.7632|0.9626|0.8858|0.7981|0.5592|0.7624|0.4560|0.3480|2|28|
|c200_offkick|-|0.7919|0.8490|0.7420|0.9626|0.8858|0.7586|0.5592|0.7624|0.4560|0.3480|2|28|
|c200_none|-|0.7810|0.8609|0.7148|0.9626|0.8858|0.7279|0.5592|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-meta-loo.json / experiment-log.json

### drumscribe/experiments/results-iterative-hat-multiclass-loo.json

- implementation: drumscribe/experiments/iterative_search_hat_multiclass_loo.py
- script commit: 93c3c234f49baa6bd241764a51f387f3b3387717
- result commit: 90f32881b7408badc3638b96a972abc28df4678b

#### Cycle 213

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c213_extra|winner|0.8053|0.8570|0.7595|0.9626|0.8858|0.7926|0.5592|0.7624|0.4560|0.3480|2|28|
|c213_rf|-|0.8048|0.8548|0.7603|0.9626|0.8858|0.7914|0.5592|0.7624|0.4560|0.3480|2|28|
|c213_logistic|-|0.7629|0.8496|0.6922|0.9535|0.8821|0.6901|0.5588|0.7624|0.4544|0.3317|4|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-multiclass-loo.json / experiment-log.json

#### Cycle 214

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c214_t85|winner|0.8086|0.8549|0.7670|0.9626|0.8858|0.8009|0.5592|0.7624|0.4560|0.3480|2|28|
|c214_t70|-|0.8053|0.8570|0.7595|0.9626|0.8858|0.7926|0.5592|0.7624|0.4560|0.3480|2|28|
|c214_t55|-|0.8010|0.8632|0.7471|0.9626|0.8858|0.7812|0.5592|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-multiclass-loo.json / experiment-log.json

#### Cycle 215

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c215_metal_kick|winner|0.8090|0.8550|0.7677|0.9626|0.8858|0.8020|0.5592|0.7624|0.4560|0.3480|2|28|
|c215_metal|-|0.8090|0.8539|0.7685|0.9626|0.8858|0.8019|0.5592|0.7624|0.4560|0.3480|2|28|
|c215_full|-|0.8086|0.8549|0.7670|0.9626|0.8858|0.8009|0.5592|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-multiclass-loo.json / experiment-log.json

### drumscribe/experiments/results-iterative-hat-nested-fusion-v9.json

- implementation: drumscribe/experiments/iterative_search_hat_nested_fusion_v9.py
- script commit: 21c2e2f14eab0f44fc54a6e2e2fa8060a0104bb2
- result commit: 6b13980aa1e109f71abe9d0c99b5dc927ee49390

#### Cycle 219

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c219_base|winner|0.8097|0.8554|0.7686|0.9626|0.8858|0.8019|0.5670|0.7624|0.4560|0.3480|2|28|
|c219_union|-|0.8094|0.8510|0.7716|0.9626|0.8858|0.8011|0.5670|0.7624|0.4560|0.3480|2|28|
|c219_intersection|-|0.8092|0.8606|0.7636|0.9626|0.8858|0.8005|0.5670|0.7624|0.4560|0.3480|2|28|
|c219_replace|-|0.8089|0.8561|0.7666|0.9626|0.8858|0.7998|0.5670|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-nested-fusion-v9.json / experiment-log.json

#### Cycle 220

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c220_base|winner|0.8097|0.8554|0.7686|0.9626|0.8858|0.8019|0.5670|0.7624|0.4560|0.3480|2|28|
|c220_full|-|0.8094|0.8606|0.7639|0.9626|0.8858|0.8010|0.5670|0.7624|0.4560|0.3480|2|28|
|c220_medium|-|0.8092|0.8606|0.7636|0.9626|0.8858|0.8005|0.5670|0.7624|0.4560|0.3480|2|28|
|c220_micro|-|0.8087|0.8606|0.7626|0.9626|0.8858|0.7992|0.5670|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-nested-fusion-v9.json / experiment-log.json

#### Cycle 221

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c221_rep100_w60|winner|0.8112|0.8679|0.7615|0.9626|0.8858|0.8054|0.5670|0.7624|0.4560|0.3480|2|28|
|c221_rep75_w35|-|0.8109|0.8626|0.7650|0.9626|0.8858|0.8047|0.5670|0.7624|0.4560|0.3480|2|28|
|c221_base|-|0.8097|0.8554|0.7686|0.9626|0.8858|0.8019|0.5670|0.7624|0.4560|0.3480|2|28|
|c221_no_rescue|-|0.7979|0.8726|0.7350|0.9626|0.8858|0.7707|0.5670|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-nested-fusion-v9.json / experiment-log.json

### drumscribe/experiments/results-iterative-hat-precision.json

- implementation: drumscribe/experiments/iterative_search_hat_precision.py
- script commit: 58e56c597602a1aa7c75ee5531c466a3dfb8d059
- result commit: f3dd096391e2eb05356b1c1c019cf20d8f88daa5

#### Cycle 73

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c73_consensus_repeat|winner, close|0.7152|0.7283|0.7026|0.9590|0.8130|0.6737|0.1735|0.6369|0.3517|0.0000|42|25|
|c73_adaptive|close|0.7151|0.7291|0.7016|0.9590|0.8130|0.6733|0.1735|0.6369|0.3517|0.0000|42|25|
|c73_strict|close|0.7069|0.7347|0.6810|0.9590|0.8130|0.6532|0.1735|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-precision.json / experiment-log.json

#### Cycle 74

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c74_density175|winner, close|0.7152|0.7283|0.7026|0.9590|0.8130|0.6737|0.1735|0.6369|0.3517|0.0000|42|25|
|c74_density225|close|0.7152|0.7283|0.7026|0.9590|0.8130|0.6737|0.1735|0.6369|0.3517|0.0000|42|25|
|c74_density275|close|0.7152|0.7283|0.7026|0.9590|0.8130|0.6737|0.1735|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-precision.json / experiment-log.json

#### Cycle 75

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c75_repeat5|winner, close|0.7156|0.7309|0.7010|0.9590|0.8130|0.6744|0.1735|0.6369|0.3517|0.0000|42|25|
|c75_repeat4|close|0.7152|0.7283|0.7026|0.9590|0.8130|0.6737|0.1735|0.6369|0.3517|0.0000|42|25|
|c75_repeat3|close|0.7148|0.7265|0.7034|0.9590|0.8130|0.6729|0.1735|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-hat-precision.json / experiment-log.json

### drumscribe/experiments/results-iterative-loop.json

- implementation: drumscribe/experiments/iterative_search_loop.py
- script commit: 23d459c890c80e5d9eef68202bd17553e240b1ff
- result commit: ce10df2225dfb76c9d68cdeb3e21cb10f775541d

#### Cycle 13

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c13_hybrid|winner, close|0.6122|0.6347|0.5913|0.9281|0.6800|0.5121|-|0.0000|0.0187|0.0767|33|27|
|c13_boundary_fill|close|0.6121|0.6343|0.5913|0.9281|0.6800|0.5121|-|0.0000|0.0182|0.0770|33|27|
|c13_accent|close|0.6120|0.6342|0.5912|0.9281|0.6795|0.5121|-|0.0000|0.0181|0.0770|33|27|
|c13_repeat|close|0.6120|0.6342|0.5912|0.9281|0.6795|0.5121|-|0.0000|0.0181|0.0770|33|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-loop.json / experiment-log.json

#### Cycle 14

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c14_head_005|winner, close|0.6122|0.6347|0.5913|0.9281|0.6800|0.5121|-|0.0000|0.0187|0.0767|33|27|
|c14_head_010|close|0.6115|0.6334|0.5910|0.9281|0.6787|0.5121|-|0.0000|0.0174|0.0774|32|27|
|c14_head_015|close|0.6110|0.6327|0.5907|0.9281|0.6764|0.5121|-|0.0000|0.0204|0.0774|32|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-loop.json / experiment-log.json

#### Cycle 15

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c15_ride_strict|winner, close|0.6222|0.6455|0.6005|0.9281|0.7408|0.5126|-|0.0000|0.0183|0.0110|38|27|
|c15_ride_medium|close|0.6122|0.6347|0.5913|0.9281|0.6800|0.5121|-|0.0000|0.0187|0.0767|33|27|
|c15_ride_recall|close|0.6054|0.6255|0.5865|0.9281|0.6378|0.5121|-|0.0000|0.0196|0.1178|26|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-loop.json / experiment-log.json

### drumscribe/experiments/results-iterative-metal-reclass.json

- implementation: drumscribe/experiments/iterative_search_metal_reclass.py
- script commit: e9bff99bb05c3a7dd7b41eebb07c396934925b65
- result commit: 7b4978ec0cc06be80303ff80e3e2c127209ed91f

#### Cycle 157

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c157_base|-|0.7273|0.7353|0.7195|0.9590|0.8379|0.6790|0.3933|0.6667|0.3972|0.2841|41|25|
|c157_conservative|winner|0.7273|0.7353|0.7195|0.9590|0.8379|0.6790|0.3933|0.6667|0.3972|0.2841|41|25|
|c157_near_hat_drop|-|0.7272|0.7352|0.7194|0.9590|0.8379|0.6790|0.3923|0.6667|0.3972|0.2841|41|25|
|c157_vote_reclass|-|0.7235|0.7548|0.6947|0.9590|0.8379|0.6785|0.1113|0.6667|0.3972|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-metal-reclass.json / experiment-log.json

#### Cycle 158

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c158_ride_to_hat|-|0.7319|0.7399|0.7241|0.9590|0.8379|0.6896|0.3933|0.6667|0.3972|0.1475|41|25|
|c158_balanced|-|0.7319|0.7399|0.7241|0.9590|0.8379|0.6896|0.3933|0.6667|0.3972|0.1475|41|25|
|c158_strong_margin|-|0.7293|0.7373|0.7215|0.9590|0.8379|0.6840|0.3933|0.6667|0.3972|0.2271|41|25|
|c158_base|winner|0.7273|0.7353|0.7195|0.9590|0.8379|0.6790|0.3933|0.6667|0.3972|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-metal-reclass.json / experiment-log.json

#### Cycle 159

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c159_crash_recall|winner|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|
|c159_base|-|0.7273|0.7353|0.7195|0.9590|0.8379|0.6790|0.3933|0.6667|0.3972|0.2841|41|25|
|c159_conservative|-|0.7273|0.7353|0.7194|0.9590|0.8379|0.6790|0.3933|0.6667|0.3936|0.2841|41|25|
|c159_balanced|-|0.7254|0.7347|0.7163|0.9590|0.8379|0.6787|0.3933|0.6667|0.3027|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-metal-reclass.json / experiment-log.json

### drumscribe/experiments/results-iterative-ml.json

- implementation: drumscribe/experiments/iterative_search_cymbal_ml.py
- script commit: 96acd478540553a5860d3f1f17444b8f9d521407
- result commit: 59501812058da23d201bfd91b21210eedcdce5bd

#### Cycle 13

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c13_rf|winner, close|0.6225|0.6374|0.6084|0.9281|0.7554|0.5119|-|0.0000|0.2637|0.0082|40|27|
|c13_extra|close|0.6213|0.6327|0.6103|0.9281|0.7659|0.5128|-|0.0000|0.1771|0.0203|40|27|
|c13_logistic|-|0.5742|0.5500|0.6005|0.9281|0.7411|0.5087|-|0.0000|0.1942|0.0147|8|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ml.json / experiment-log.json

#### Cycle 14

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c14_strict|close|0.6278|0.6481|0.6089|0.9281|0.7701|0.5124|-|0.0000|0.1652|0.0024|40|27|
|c14_balanced|winner, close|0.6176|0.6290|0.6067|0.9281|0.7434|0.5119|-|0.0000|0.2863|0.0091|39|27|
|c14_recall|close|0.6022|0.6015|0.6030|0.9281|0.7123|0.5113|-|0.0000|0.3388|0.0195|38|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ml.json / experiment-log.json

#### Cycle 15

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c15_head_010|close|0.6176|0.6290|0.6067|0.9281|0.7434|0.5119|-|0.0000|0.2863|0.0091|39|27|
|c15_head_015|winner, close|0.6175|0.6281|0.6072|0.9281|0.7434|0.5119|-|0.0000|0.2933|0.0091|39|27|
|c15_head_005|close|0.6169|0.6289|0.6053|0.9281|0.7431|0.5118|-|0.0000|0.2412|0.0091|39|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ml.json / experiment-log.json

### drumscribe/experiments/results-iterative-neural-separation.json

- implementation: drumscribe/experiments/iterative_search_neural_separation.py
- script commit: 06ac599a32750d7c14e1d597a4148e7bd4d0811f
- result commit: 3bf8847d16cea1ac0e20f32f1cea0524f76d1d9e

#### Cycle 49

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c49_mdx|winner, close|0.6738|0.6822|0.6657|0.8035|0.7783|0.6817|0.2974|0.5320|0.1212|0.0030|6|41|
|c49_ensemble|-|0.6453|0.6113|0.6832|0.7668|0.6438|0.6767|0.3489|0.5274|0.1193|0.0000|31|44|
|c49_dsp|-|0.6009|0.6061|0.5958|0.8156|0.6167|0.6099|0.1704|0.2151|0.0190|0.0000|51|41|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-neural-separation.json / experiment-log.json

#### Cycle 50

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c50_extra|winner, close|0.6738|0.6822|0.6657|0.8035|0.7783|0.6817|0.2974|0.5320|0.1212|0.0030|6|41|
|c50_rf|-|0.6602|0.6672|0.6533|0.7765|0.7610|0.6744|0.1099|0.5725|0.0688|0.0000|7|39|
|c50_logistic|-|0.6403|0.6238|0.6576|0.8269|0.7085|0.6771|0.2915|0.4875|0.1314|0.0974|6|41|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-neural-separation.json / experiment-log.json

#### Cycle 51

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c51_balanced|winner, close|0.6738|0.6822|0.6657|0.8035|0.7783|0.6817|0.2974|0.5320|0.1212|0.0030|6|41|
|c51_precision|close|0.6643|0.7300|0.6094|0.8224|0.7836|0.6326|0.1939|0.5693|0.1007|0.0000|4|38|
|c51_recall|-|0.6459|0.5912|0.7119|0.7805|0.7715|0.7058|0.3454|0.5032|0.1470|0.0422|7|43|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-neural-separation.json / experiment-log.json

### drumscribe/experiments/results-iterative-overtrigger-refine.json

- implementation: drumscribe/experiments/iterative_search_overtrigger_refine.py
- script commit: 469c88ab55399092463a71aebda5f74d5c54a523
- result commit: 952b4d265a78473f6bf92d8857e16824f9cdd766

#### Cycle 154

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c154_gap16|winner|0.7271|0.7348|0.7196|0.9590|0.8379|0.6786|0.3933|0.6667|0.3972|0.2841|41|25|
|c154_gap12|-|0.7265|0.7332|0.7200|0.9590|0.8327|0.6786|0.3933|0.6667|0.3972|0.2841|41|25|
|c154_base|-|0.7251|0.7302|0.7201|0.9590|0.8215|0.6786|0.3933|0.6667|0.3972|0.2841|41|25|
|c154_gap08|-|0.7251|0.7302|0.7201|0.9590|0.8215|0.6786|0.3933|0.6667|0.3972|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-overtrigger-refine.json / experiment-log.json

#### Cycle 155

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c155_source1_repeat|-|0.7280|0.7398|0.7166|0.9590|0.8379|0.6786|0.3933|0.6667|0.3972|0.2527|41|25|
|c155_base|-|0.7271|0.7348|0.7196|0.9590|0.8379|0.6786|0.3933|0.6667|0.3972|0.2841|41|25|
|c155_periodic|winner|0.7271|0.7348|0.7196|0.9590|0.8379|0.6786|0.3933|0.6667|0.3972|0.2841|41|25|
|c155_source2|-|0.7263|0.7450|0.7085|0.9590|0.8379|0.6786|0.3933|0.6667|0.3972|0.0952|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-overtrigger-refine.json / experiment-log.json

#### Cycle 156

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c156_kick_snare|winner|0.7273|0.7353|0.7195|0.9590|0.8379|0.6790|0.3933|0.6667|0.3972|0.2841|41|25|
|c156_all_drum|-|0.7273|0.7353|0.7195|0.9590|0.8379|0.6790|0.3933|0.6667|0.3972|0.2841|41|25|
|c156_kick|-|0.7272|0.7350|0.7195|0.9590|0.8379|0.6787|0.3933|0.6667|0.3972|0.2841|41|25|
|c156_base|-|0.7271|0.7348|0.7196|0.9590|0.8379|0.6786|0.3933|0.6667|0.3972|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-overtrigger-refine.json / experiment-log.json

### drumscribe/experiments/results-iterative-pattern-consensus.json

- implementation: drumscribe/experiments/iterative_search_pattern_consensus.py
- script commit: 8fd00f5802cb1a5cf23b613133b5a404da4d3091
- result commit: f5cbda72288627c0476f2e3a3e00a99c853fe5ef

#### Cycle 55

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c55_multires|winner, close|0.6889|0.7576|0.6317|0.9578|0.7376|0.6450|0.1735|0.6345|0.1876|0.0000|37|25|
|c55_global|close|0.6848|0.7563|0.6257|0.9593|0.7105|0.6436|0.1735|0.6345|0.1876|0.0000|24|23|
|c55_local|close|0.6830|0.7576|0.6218|0.9545|0.7043|0.6449|0.1735|0.6345|0.1876|0.0000|31|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pattern-consensus.json / experiment-log.json

#### Cycle 56

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c56_window8|winner, close|0.6914|0.7558|0.6372|0.9589|0.7526|0.6450|0.1735|0.6345|0.1876|0.0000|38|25|
|c56_window4|close|0.6889|0.7576|0.6317|0.9578|0.7376|0.6450|0.1735|0.6345|0.1876|0.0000|37|25|
|c56_window2|close|0.6881|0.7615|0.6276|0.9574|0.7273|0.6468|0.1735|0.6345|0.1876|0.0000|37|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pattern-consensus.json / experiment-log.json

#### Cycle 57

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c57_support1|winner, close|0.6931|0.7542|0.6411|0.9590|0.7642|0.6445|0.1735|0.6345|0.1876|0.0000|38|25|
|c57_support2|close|0.6914|0.7558|0.6372|0.9589|0.7526|0.6450|0.1735|0.6345|0.1876|0.0000|38|25|
|c57_support3|close|0.6870|0.7579|0.6283|0.9565|0.7244|0.6460|0.1735|0.6345|0.1876|0.0000|36|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pattern-consensus.json / experiment-log.json

### drumscribe/experiments/results-iterative-pedal-adaptive.json

- implementation: drumscribe/experiments/iterative_search_pedal_adaptive.py
- script commit: 630156623735284e16ce3c275e58f996b7916e96
- result commit: 743982cc2d63f4eef261be03ca9a0af366730f91

#### Cycle 133

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c133_base|winner|0.7219|0.7226|0.7211|0.9590|0.8107|0.6798|0.3870|0.6667|0.3734|0.1628|42|25|
|c133_anti_hat|-|0.7219|0.7226|0.7211|0.9590|0.8107|0.6798|0.3870|0.6667|0.3734|0.1628|42|25|
|c133_consensus|-|0.7000|0.6726|0.7297|0.9590|0.8107|0.6798|0.3186|0.6667|0.3734|0.1628|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-adaptive.json / experiment-log.json

#### Cycle 134

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c134_per25|-|0.7219|0.7226|0.7211|0.9590|0.8107|0.6798|0.3870|0.6667|0.3734|0.1628|42|25|
|c134_per50|-|0.7219|0.7226|0.7211|0.9590|0.8107|0.6798|0.3870|0.6667|0.3734|0.1628|42|25|
|c134_per75|winner|0.7219|0.7226|0.7211|0.9590|0.8107|0.6798|0.3870|0.6667|0.3734|0.1628|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-adaptive.json / experiment-log.json

#### Cycle 135

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c135_sparse015|-|0.7220|0.7222|0.7218|0.9590|0.8107|0.6798|0.3920|0.6667|0.3734|0.1628|42|25|
|c135_sparse030|-|0.7220|0.7222|0.7218|0.9590|0.8107|0.6798|0.3920|0.6667|0.3734|0.1628|42|25|
|c135_sparse060|winner|0.7220|0.7222|0.7218|0.9590|0.8107|0.6798|0.3920|0.6667|0.3734|0.1628|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-adaptive.json / experiment-log.json

### drumscribe/experiments/results-iterative-pedal-component.json

- implementation: drumscribe/experiments/iterative_search_pedal_component.py
- script commit: 799012e628910987cb2d759ff599ff1e6775c28f
- result commit: c57c5024065e9451de359850d4cbd389341105d6

#### Cycle 64

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c64_strict|winner, close|0.6898|0.6869|0.6926|0.9590|0.8096|0.6451|0.3211|0.6369|0.3517|0.0000|42|25|
|c64_logistic|close|0.6827|0.6693|0.6967|0.9590|0.8096|0.6451|0.3117|0.6369|0.3517|0.0000|42|25|
|c64_recall|part-leader|0.6754|0.6524|0.7000|0.9590|0.8096|0.6451|0.2996|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-component.json / experiment-log.json

#### Cycle 65

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c65_single|winner, close|0.6898|0.6869|0.6926|0.9590|0.8096|0.6451|0.3211|0.6369|0.3517|0.0000|42|25|
|c65_consensus|close|0.6898|0.6869|0.6926|0.9590|0.8096|0.6451|0.3211|0.6369|0.3517|0.0000|42|25|
|c65_union|close|0.6827|0.6693|0.6967|0.9590|0.8096|0.6451|0.3117|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-component.json / experiment-log.json

#### Cycle 66

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c66_periodic_050|winner, close|0.7016|0.7151|0.6886|0.9590|0.8096|0.6451|0.3584|0.6369|0.3517|0.0000|42|25|
|c66_periodic_025|close|0.6961|0.7028|0.6895|0.9590|0.8096|0.6451|0.3337|0.6369|0.3517|0.0000|42|25|
|c66_no_periodic|-|0.6898|0.6869|0.6926|0.9590|0.8096|0.6451|0.3211|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-component.json / experiment-log.json

### drumscribe/experiments/results-iterative-pedal-grid.json

- implementation: drumscribe/experiments/iterative_search_pedal_grid.py
- script commit: 6f02513169ea0fb56590a0f6b6fd2097bce02637
- result commit: cb834a0507c76cb0081324deae03360a279b4344

#### Cycle 34

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c34_grid_010|winner, close|0.5999|0.6246|0.5771|0.9281|0.7712|0.4592|0.1796|0.6194|0.2908|0.0000|44|27|
|c34_grid_016|close|0.5993|0.6239|0.5765|0.9281|0.7712|0.4586|0.1770|0.6194|0.2908|0.0000|44|27|
|c34_grid_006|-|0.5952|0.6197|0.5726|0.9281|0.7715|0.4603|0.0155|0.6194|0.2908|0.0000|44|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-grid.json / experiment-log.json

#### Cycle 35

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c35_periodic_075|-|0.6092|0.6343|0.5860|0.9281|0.7710|0.4765|0.1124|0.6194|0.2908|0.0000|44|27|
|c35_periodic_025|winner, close|0.6006|0.6253|0.5778|0.9281|0.7712|0.4563|0.2397|0.6194|0.2908|0.0000|44|27|
|c35_periodic_050|-|0.5999|0.6246|0.5771|0.9281|0.7712|0.4592|0.1796|0.6194|0.2908|0.0000|44|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-grid.json / experiment-log.json

#### Cycle 36

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c36_prob_070|winner, close|0.6008|0.6254|0.5781|0.9281|0.7717|0.4553|0.2661|0.6154|0.2908|0.0000|44|27|
|c36_prob_080|close|0.6007|0.6254|0.5779|0.9281|0.7712|0.4565|0.2365|0.6194|0.2908|0.0000|44|27|
|c36_prob_090|-|0.5977|0.6222|0.5750|0.9281|0.7707|0.4567|0.1314|0.6194|0.2908|0.0000|44|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-grid.json / experiment-log.json

### drumscribe/experiments/results-iterative-pedal-hat.json

- implementation: drumscribe/experiments/iterative_search_pedal_hat.py
- script commit: a261d62a2a136b6c5d14fbec0a65dfbcae132915
- result commit: bdc3893e89ee712781232d4681ffc8c7ee0c8a73

#### Cycle 31

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c31_extra|close|0.5841|0.6079|0.5621|0.9281|0.7710|0.4423|0.1889|0.6115|0.2898|0.0000|44|27|
|c31_rf|-|0.5823|0.6060|0.5604|0.9281|0.7710|0.4434|0.1141|0.6115|0.2893|0.0000|44|27|
|c31_logistic|winner, close|0.5728|0.5959|0.5514|0.9281|0.7717|0.3985|0.3117|0.6000|0.2903|0.0000|44|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-hat.json / experiment-log.json

#### Cycle 32

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c32_strict|winner, close|0.5757|0.5992|0.5539|0.9281|0.7712|0.3993|0.3211|0.6115|0.2903|0.0000|44|27|
|c32_balanced|close|0.5728|0.5959|0.5514|0.9281|0.7717|0.3985|0.3117|0.6000|0.2903|0.0000|44|27|
|c32_recall|-|0.5653|0.5880|0.5442|0.9281|0.7717|0.3869|0.2996|0.6000|0.2893|0.0000|44|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-hat.json / experiment-log.json

#### Cycle 33

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c33_positive_sim_gate|-|0.5993|0.6240|0.5765|0.9281|0.7710|0.4696|0.0647|0.6154|0.2908|0.0000|44|27|
|c33_soft_sim_gate|winner, close|0.5901|0.6142|0.5678|0.9281|0.7712|0.4512|0.2295|0.6115|0.2903|0.0000|44|27|
|c33_no_sim_gate|close|0.5757|0.5992|0.5539|0.9281|0.7712|0.3993|0.3211|0.6115|0.2903|0.0000|44|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-hat.json / experiment-log.json

### drumscribe/experiments/results-iterative-pedal-refine-v3.json

- implementation: drumscribe/experiments/iterative_search_pedal_refine_v3.py
- script commit: 265ae6663727a5fd6184c6d4384e5fc19a5281ac
- result commit: db5a6469768ae5e00296ba078817add6e2e41eee

#### Cycle 190

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c190_r3|winner|0.7952|0.8339|0.7599|0.9626|0.8880|0.7793|0.5222|0.7582|0.3955|0.2742|2|28|
|c190_r4|-|0.7952|0.8345|0.7594|0.9626|0.8880|0.7793|0.5192|0.7582|0.3955|0.2742|2|28|
|c190_base|-|0.7947|0.8360|0.7574|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.2742|2|28|
|c190_loose|-|0.7943|0.8308|0.7609|0.9626|0.8880|0.7793|0.5187|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-refine-v3.json / experiment-log.json

#### Cycle 191

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c191_base|winner|0.7952|0.8339|0.7599|0.9626|0.8880|0.7793|0.5222|0.7582|0.3955|0.2742|2|28|
|c191_weak1|-|0.7949|0.8336|0.7596|0.9626|0.8880|0.7792|0.5175|0.7582|0.3955|0.2742|2|28|
|c191_weak2|-|0.7948|0.8335|0.7595|0.9626|0.8880|0.7792|0.5151|0.7582|0.3955|0.2742|2|28|
|c191_not_strict|-|0.7948|0.8335|0.7595|0.9626|0.8880|0.7792|0.5151|0.7582|0.3955|0.2742|2|28|
|c191_consensus|-|0.7948|0.8335|0.7595|0.9626|0.8880|0.7792|0.5151|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-refine-v3.json / experiment-log.json

#### Cycle 192

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c192_w020|-|0.7952|0.8339|0.7599|0.9626|0.8880|0.7793|0.5222|0.7582|0.3955|0.2742|2|28|
|c192_w030|-|0.7952|0.8339|0.7599|0.9626|0.8880|0.7793|0.5222|0.7582|0.3955|0.2742|2|28|
|c192_w040|-|0.7952|0.8339|0.7599|0.9626|0.8880|0.7793|0.5222|0.7582|0.3955|0.2742|2|28|
|c192_w055|winner|0.7952|0.8339|0.7599|0.9626|0.8880|0.7793|0.5222|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-refine-v3.json / experiment-log.json

### drumscribe/experiments/results-iterative-pedal-repair.json

- implementation: drumscribe/experiments/iterative_search_pedal_repair.py
- script commit: 2a58237959b818bd754c48b882b7b978f76f9809
- result commit: 261949d66faeb5103fc2197935384ed3424a184a

#### Cycle 76

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c76_current|close|0.7041|0.7460|0.6667|0.9590|0.8113|0.6451|0.1735|0.6369|0.3517|0.0000|42|25|
|c76_strict|winner, close|0.6900|0.6873|0.6926|0.9590|0.8113|0.6451|0.3211|0.6369|0.3517|0.0000|42|25|
|c76_recall|-|0.6756|0.6528|0.7000|0.9590|0.8113|0.6451|0.2996|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-repair.json / experiment-log.json

#### Cycle 77

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c77_per75|winner, close|0.7075|0.7290|0.6872|0.9590|0.8113|0.6451|0.3865|0.6369|0.3517|0.0000|42|25|
|c77_per50|-|0.7005|0.7122|0.6892|0.9590|0.8113|0.6451|0.3543|0.6369|0.3517|0.0000|42|25|
|c77_per25|-|0.6940|0.6970|0.6910|0.9590|0.8113|0.6451|0.3304|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-repair.json / experiment-log.json

#### Cycle 78

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c78_hat0|winner, close|0.7075|0.7290|0.6872|0.9590|0.8113|0.6451|0.3865|0.6369|0.3517|0.0000|42|25|
|c78_hat35|-|0.7056|0.7585|0.6596|0.9590|0.8113|0.6451|0.0496|0.6369|0.3517|0.0000|42|25|
|c78_hat70|-|0.7056|0.7597|0.6586|0.9590|0.8113|0.6451|0.0257|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-repair.json / experiment-log.json

### drumscribe/experiments/results-iterative-pedal-rescue-v2.json

- implementation: drumscribe/experiments/iterative_search_pedal_rescue_v2.py
- script commit: aa60a4480857aab547e2ae6d9d4cc2a33a38e4a6
- result commit: 8bf6209270006b290854f4fab58cc812ebed94a4

#### Cycle 184

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c184_periodic|winner|0.7949|0.8333|0.7599|0.9626|0.8880|0.7793|0.5193|0.7582|0.3955|0.2742|2|28|
|c184_base|-|0.7947|0.8360|0.7574|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.2742|2|28|
|c184_gap_repeat|-|0.7945|0.8322|0.7602|0.9626|0.8880|0.7793|0.5175|0.7582|0.3955|0.2742|2|28|
|c184_hybrid|-|0.7939|0.8305|0.7604|0.9626|0.8880|0.7793|0.5122|0.7582|0.3955|0.2742|2|28|
|c184_accent|-|0.7939|0.8322|0.7590|0.9626|0.8880|0.7793|0.5043|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-rescue-v2.json / experiment-log.json

#### Cycle 185

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c185_s06|-|0.7949|0.8333|0.7599|0.9626|0.8880|0.7793|0.5193|0.7582|0.3955|0.2742|2|28|
|c185_s08|-|0.7949|0.8333|0.7599|0.9626|0.8880|0.7793|0.5193|0.7582|0.3955|0.2742|2|28|
|c185_s12|-|0.7949|0.8333|0.7599|0.9626|0.8880|0.7793|0.5193|0.7582|0.3955|0.2742|2|28|
|c185_s18|winner|0.7949|0.8333|0.7599|0.9626|0.8880|0.7793|0.5193|0.7582|0.3955|0.2742|2|28|
|c185_s04|-|0.7944|0.8353|0.7574|0.9626|0.8880|0.7793|0.5004|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-rescue-v2.json / experiment-log.json

#### Cycle 186

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c186_rep4|winner|0.7950|0.8340|0.7594|0.9626|0.8880|0.7793|0.5171|0.7582|0.3955|0.2742|2|28|
|c186_mid|-|0.7949|0.8333|0.7599|0.9626|0.8880|0.7793|0.5193|0.7582|0.3955|0.2742|2|28|
|c186_strict|-|0.7946|0.8354|0.7577|0.9626|0.8880|0.7793|0.5041|0.7582|0.3955|0.2742|2|28|
|c186_loose|-|0.7933|0.8282|0.7613|0.9626|0.8880|0.7793|0.5115|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-rescue-v2.json / experiment-log.json

### drumscribe/experiments/results-iterative-pedal-song-adaptive.json

- implementation: drumscribe/experiments/iterative_search_pedal_song_adaptive.py
- script commit: 70d1f053aa18d6686a928ea18e793685fa56d938
- result commit: 353bbd1678ea7914ed33d495c37586f73565ec2f

#### Cycle 160

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c160_gate40|-|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|
|c160_gate60|-|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|
|c160_gate80|winner|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-song-adaptive.json / experiment-log.json

#### Cycle 161

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c161_per25|-|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|
|c161_per50|-|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|
|c161_per75|winner|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-song-adaptive.json / experiment-log.json

#### Cycle 162

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c162_vote2|-|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|
|c162_vote3|-|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|
|c162_vote4|winner|0.7275|0.7358|0.7193|0.9590|0.8379|0.6794|0.3933|0.6667|0.3936|0.2841|41|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-song-adaptive.json / experiment-log.json

### drumscribe/experiments/results-iterative-pedal-sparse-gate.json

- implementation: drumscribe/experiments/iterative_search_pedal_sparse_gate.py
- script commit: 1d264d83dc1ca17572d48434870b96bb455b275d
- result commit: 9bf37db82a43bf3340d1db9080c7191d212707ac

#### Cycle 210

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c210_n20|-|0.8070|0.8455|0.7718|0.9626|0.8858|0.7956|0.5655|0.7624|0.4560|0.3480|2|28|
|c210_n50|winner|0.8070|0.8455|0.7718|0.9626|0.8858|0.7956|0.5655|0.7624|0.4560|0.3480|2|28|
|c210_n5|-|0.8065|0.8446|0.7718|0.9626|0.8858|0.7956|0.5613|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-sparse-gate.json / experiment-log.json

#### Cycle 211

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c211_d10|winner|0.8070|0.8455|0.7718|0.9626|0.8858|0.7956|0.5655|0.7624|0.4560|0.3480|2|28|
|c211_d05|-|0.8065|0.8446|0.7718|0.9626|0.8858|0.7956|0.5613|0.7624|0.4560|0.3480|2|28|
|c211_d02|-|0.8064|0.8443|0.7718|0.9626|0.8858|0.7956|0.5601|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-sparse-gate.json / experiment-log.json

#### Cycle 212

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c212_p50|-|0.8070|0.8455|0.7718|0.9626|0.8858|0.7956|0.5655|0.7624|0.4560|0.3480|2|28|
|c212_p75|winner|0.8070|0.8455|0.7718|0.9626|0.8858|0.7956|0.5655|0.7624|0.4560|0.3480|2|28|
|c212_p100|-|0.8070|0.8455|0.7718|0.9626|0.8858|0.7956|0.5655|0.7624|0.4560|0.3480|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-sparse-gate.json / experiment-log.json

### drumscribe/experiments/results-iterative-pedal-structural.json

- implementation: drumscribe/experiments/iterative_search_pedal_structural.py
- script commit: 58bed16a85b6b1be403749c076a933e4ac0a76ca
- result commit: a06ce9ac08f5ea82f7fa0e00e5ed3866560ea5a5

#### Cycle 97

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c97_poly|winner, close|0.7203|0.7496|0.6932|0.9590|0.8107|0.6744|0.0306|0.6369|0.3734|0.0000|42|25|
|c97_hand|close|0.7126|0.7328|0.6935|0.9590|0.8107|0.6744|0.0299|0.6369|0.3734|0.0000|42|25|
|c97_gap|close|0.7088|0.7214|0.6966|0.9590|0.8107|0.6744|0.0796|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-structural.json / experiment-log.json

#### Cycle 98

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c98_per75|close|0.7205|0.7502|0.6930|0.9590|0.8107|0.6744|0.0255|0.6369|0.3734|0.0000|42|25|
|c98_per50|winner, close|0.7203|0.7496|0.6932|0.9590|0.8107|0.6744|0.0306|0.6369|0.3734|0.0000|42|25|
|c98_per25|close|0.7202|0.7493|0.6932|0.9590|0.8107|0.6744|0.0305|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-structural.json / experiment-log.json

#### Cycle 99

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c99_strict|close|0.7205|0.7508|0.6926|0.9590|0.8107|0.6744|0.0144|0.6369|0.3734|0.0000|42|25|
|c99_recall|winner, close|0.7203|0.7496|0.6932|0.9590|0.8107|0.6744|0.0306|0.6369|0.3734|0.0000|42|25|
|c99_union|close|0.7203|0.7496|0.6932|0.9590|0.8107|0.6744|0.0306|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-pedal-structural.json / experiment-log.json

### drumscribe/experiments/results-iterative-phase.json

- implementation: drumscribe/experiments/iterative_search_phase.py
- script commit: 8d1b19fba8b4e9b3423cca81d70f0c0d14465b50
- result commit: 1da3e69763b3bad50fa9b1e5a17d51db153a9d7e

#### Cycle 4

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c4_all_phase|winner, close|0.6265|0.6499|0.6048|0.9281|0.7633|0.5127|-|0.0000|0.0203|0.0060|35|27|
|c4_crash_phase|close|0.6263|0.6501|0.6043|0.9281|0.7623|0.5127|-|0.0000|0.0103|0.0060|35|27|
|c4_backbeat_phase|close|0.6261|0.6497|0.6041|0.9281|0.7609|0.5124|-|0.0000|0.0113|0.0060|38|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-phase.json / experiment-log.json

#### Cycle 5

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c5_tight_head|winner, close|0.6268|0.6503|0.6050|0.9281|0.7642|0.5127|-|0.0000|0.0205|0.0060|35|27|
|c5_medium_head|close|0.6250|0.6479|0.6036|0.9281|0.7578|0.5127|-|0.0000|0.0195|0.0060|34|27|
|c5_wide_head|close|0.6238|0.6467|0.6025|0.9281|0.7524|0.5127|-|0.0000|0.0191|0.0060|34|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-phase.json / experiment-log.json

#### Cycle 6

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c6_no_direct_ride|winner, close|0.6268|0.6503|0.6050|0.9281|0.7642|0.5127|-|0.0000|0.0205|0.0060|35|27|
|c6_direct_precision|close|0.6233|0.6466|0.6016|0.9281|0.7476|0.5127|-|0.0000|0.0205|0.0057|35|27|
|c6_direct_recall|-|0.5833|0.5967|0.5706|0.9281|0.5024|0.5121|-|0.0000|0.0207|0.1479|18|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-phase.json / experiment-log.json

### drumscribe/experiments/results-iterative-recall-repair.json

- implementation: drumscribe/experiments/iterative_search_recall_repair.py
- script commit: 44d51e5c15b492a0073127bbc18278da8f456b8e
- result commit: 5b88bfd3f48b9af6ab958b1ab2909c1b84b80093

#### Cycle 61

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c61_snare_pattern|close|0.7075|0.7401|0.6776|0.9590|0.8224|0.6455|0.1735|0.6345|0.3517|0.0000|103|25|
|c61_snare_raw|close|0.7062|0.7370|0.6779|0.9590|0.8127|0.6457|0.1735|0.6345|0.3517|0.0000|109|25|
|c61_snare_consensus|winner, close|0.7039|0.7460|0.6663|0.9590|0.8096|0.6451|0.1735|0.6345|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-recall-repair.json / experiment-log.json

#### Cycle 62

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c62_tom_consensus|winner, close|0.7039|0.7455|0.6667|0.9590|0.8096|0.6451|0.1735|0.6369|0.3517|0.0000|42|25|
|c62_tom_fill|close|0.7038|0.7458|0.6663|0.9590|0.8096|0.6451|0.1735|0.6216|0.3517|0.0000|42|25|
|c62_tom_raw|close|0.7037|0.7453|0.6666|0.9590|0.8096|0.6450|0.1735|0.6250|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-recall-repair.json / experiment-log.json

#### Cycle 63

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c63_pedal_off|close|0.7082|0.7671|0.6576|0.9590|0.8096|0.6451|0.0000|0.6369|0.3517|0.0000|42|25|
|c63_pedal_keep|winner, close|0.7039|0.7455|0.6667|0.9590|0.8096|0.6451|0.1735|0.6369|0.3517|0.0000|42|25|
|c63_pedal_periodic|close|0.7037|0.7496|0.6632|0.9590|0.8096|0.6451|0.1175|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-recall-repair.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-adaptive.json

- implementation: drumscribe/experiments/iterative_search_ride_adaptive.py
- script commit: 45a93483271e6cc4999268cba07624b4f55bb451
- result commit: 0b2e67ff0f88542aa0fc0625d8399c27eb25481f

#### Cycle 115

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c115_ratio030|winner, close|0.7187|0.7159|0.7215|0.9590|0.8107|0.6721|0.3870|0.6667|0.3741|0.1202|42|25|
|c115_ratio060|close|0.7187|0.7159|0.7215|0.9590|0.8107|0.6721|0.3870|0.6667|0.3741|0.1202|42|25|
|c115_ratio015|close|0.7181|0.7157|0.7204|0.9590|0.8107|0.6718|0.3870|0.6667|0.3741|0.0941|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-adaptive.json / experiment-log.json

#### Cycle 116

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c116_radius8|close|0.7187|0.7159|0.7215|0.9590|0.8107|0.6721|0.3870|0.6667|0.3741|0.1202|42|25|
|c116_radius4|close|0.7185|0.7159|0.7211|0.9590|0.8107|0.6719|0.3870|0.6667|0.3741|0.1111|42|25|
|c116_oldrecall|winner, close|0.7173|0.7121|0.7226|0.9590|0.8107|0.6701|0.3870|0.6667|0.3741|0.1628|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-adaptive.json / experiment-log.json

#### Cycle 117

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c117_hat30|winner, close|0.7174|0.7121|0.7227|0.9590|0.8107|0.6701|0.3870|0.6667|0.3741|0.1628|42|25|
|c117_hat50|close|0.7173|0.7121|0.7226|0.9590|0.8107|0.6701|0.3870|0.6667|0.3741|0.1628|42|25|
|c117_hat80|close|0.7172|0.7121|0.7224|0.9590|0.8107|0.6698|0.3870|0.6667|0.3741|0.1628|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-adaptive.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-consensus.json

- implementation: drumscribe/experiments/iterative_search_ride_consensus.py
- script commit: fe1b6d519fe8f6121486b17b285a6c371560ed7d
- result commit: 7edb83541aa8bcb47f41c1b59a3c13764f990bae

#### Cycle 100

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c100_intersection|winner, close|0.7166|0.7144|0.7189|0.9590|0.8107|0.6717|0.3870|0.6369|0.3734|0.0382|42|25|
|c100_twoof3|-|0.6953|0.6808|0.7104|0.9590|0.8107|0.6649|0.3870|0.6369|0.3734|0.0958|42|25|
|c100_highres|-|0.6606|0.6585|0.6627|0.9590|0.8107|0.5888|0.3870|0.6369|0.3734|0.1612|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-consensus.json / experiment-log.json

#### Cycle 101

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c101_w35|winner, close|0.7171|0.7149|0.7194|0.9590|0.8107|0.6721|0.3870|0.6369|0.3734|0.0387|42|25|
|c101_w60|close|0.7166|0.7144|0.7189|0.9590|0.8107|0.6717|0.3870|0.6369|0.3734|0.0382|42|25|
|c101_w90|close|0.7161|0.7138|0.7183|0.9590|0.8107|0.6713|0.3870|0.6369|0.3734|0.0375|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-consensus.json / experiment-log.json

#### Cycle 102

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c102_per75|close|0.7193|0.7170|0.7216|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0031|42|25|
|c102_per50|close|0.7186|0.7164|0.7209|0.9590|0.8107|0.6735|0.3870|0.6369|0.3734|0.0120|42|25|
|c102_per25|winner, close|0.7176|0.7154|0.7199|0.9590|0.8107|0.6720|0.3870|0.6369|0.3734|0.0315|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-consensus.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-contiguous.json

- implementation: drumscribe/experiments/iterative_search_ride_contiguous.py
- script commit: 510bb063e6ede4bc140d06c163e4b5e69f65161d
- result commit: a7524f4bac8bfa8814a34747c0c42e351fccab37

#### Cycle 22

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c22_run3|winner, close|0.6181|0.6396|0.5980|0.9281|0.7742|0.4999|-|0.0000|0.2868|0.0148|41|27|
|c22_run2|close|0.6098|0.6310|0.5899|0.9281|0.7742|0.4924|-|0.0000|0.2868|0.0612|41|27|
|c22_run1|close|0.6010|0.6219|0.5814|0.9281|0.7742|0.4820|-|0.0000|0.2868|0.0904|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-contiguous.json / experiment-log.json

#### Cycle 23

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c23_thr_075|winner, close|0.6337|0.6557|0.6130|0.9281|0.7742|0.5117|-|0.0000|0.2862|0.0000|41|27|
|c23_thr_065|close|0.6243|0.6461|0.6040|0.9281|0.7742|0.5037|-|0.0000|0.2868|0.0090|41|27|
|c23_thr_055|-|0.6147|0.6361|0.5947|0.9281|0.7742|0.4962|-|0.0000|0.2868|0.0140|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-contiguous.json / experiment-log.json

#### Cycle 24

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c24_periodic_075|winner, close|0.6338|0.6558|0.6131|0.9281|0.7742|0.5117|-|0.0000|0.2862|0.0000|41|27|
|c24_no_hit_gate|close|0.6337|0.6557|0.6130|0.9281|0.7742|0.5117|-|0.0000|0.2862|0.0000|41|27|
|c24_periodic_050|close|0.6337|0.6557|0.6130|0.9281|0.7742|0.5117|-|0.0000|0.2862|0.0000|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-contiguous.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-fallback.json

- implementation: drumscribe/experiments/iterative_search_ride_fallback.py
- script commit: 20a1f7d502f5d07fc8502de7fe0ae6c775e0a177
- result commit: 8c924cb6fd685d4c532ac1dec23aed38a38c5628

#### Cycle 118

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c118_ratio10|winner, close|0.7156|0.7085|0.7229|0.9590|0.8107|0.6733|0.3870|0.6667|0.3741|0.1522|42|25|
|c118_ratio15|close|0.7156|0.7085|0.7229|0.9590|0.8107|0.6733|0.3870|0.6667|0.3741|0.1522|42|25|
|c118_ratio20|close|0.7156|0.7085|0.7229|0.9590|0.8107|0.6733|0.3870|0.6667|0.3741|0.1522|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-fallback.json / experiment-log.json

#### Cycle 119

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c119_per100|winner, close|0.7162|0.7098|0.7228|0.9590|0.8107|0.6719|0.3870|0.6667|0.3741|0.1547|42|25|
|c119_per75|close|0.7156|0.7085|0.7229|0.9590|0.8107|0.6733|0.3870|0.6667|0.3741|0.1522|42|25|
|c119_per50|close, part-leader|0.7148|0.7069|0.7228|0.9590|0.8107|0.6752|0.3870|0.6667|0.3741|0.1525|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-fallback.json / experiment-log.json

#### Cycle 120

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c120_density7|winner, close|0.7170|0.7114|0.7228|0.9590|0.8107|0.6711|0.3870|0.6667|0.3741|0.1605|42|25|
|c120_density5|close|0.7162|0.7098|0.7228|0.9590|0.8107|0.6719|0.3870|0.6667|0.3741|0.1547|42|25|
|c120_density3|close|0.7154|0.7081|0.7228|0.9590|0.8107|0.6723|0.3870|0.6667|0.3741|0.1499|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-fallback.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-grid.json

- implementation: drumscribe/experiments/iterative_search_ride_grid.py
- script commit: 0ecc25ccf38edd1b59f7131e562a1243e75d633d
- result commit: 3141432d1e849a6eddf4e30ad7bcf710d857e721

#### Cycle 100

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c100_fit80|close|0.7093|0.7028|0.7159|0.9590|0.8107|0.6673|0.3865|0.6369|0.3734|0.0315|42|25|
|c100_fit65|winner, close|0.7085|0.7006|0.7165|0.9590|0.8107|0.6701|0.3865|0.6369|0.3734|0.0530|42|25|
|c100_fit50|-|0.6972|0.6852|0.7097|0.9590|0.8107|0.6614|0.3865|0.6369|0.3734|0.0641|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-grid.json / experiment-log.json

#### Cycle 101

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c101_win4|winner, close|0.7094|0.7015|0.7174|0.9590|0.8107|0.6699|0.3865|0.6369|0.3734|0.0526|42|25|
|c101_win8|close|0.7085|0.7006|0.7165|0.9590|0.8107|0.6701|0.3865|0.6369|0.3734|0.0530|42|25|
|c101_win16|close|0.7033|0.6952|0.7116|0.9590|0.8107|0.6628|0.3865|0.6369|0.3734|0.0515|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-grid.json / experiment-log.json

#### Cycle 102

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c102_contig3|close|0.7113|0.7042|0.7186|0.9590|0.8107|0.6716|0.3865|0.6369|0.3734|0.0296|42|25|
|c102_contig2|winner, close|0.7094|0.7015|0.7174|0.9590|0.8107|0.6699|0.3865|0.6369|0.3734|0.0526|42|25|
|c102_contig1|close|0.7018|0.6916|0.7123|0.9590|0.8107|0.6629|0.3865|0.6369|0.3734|0.0643|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-grid.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-hires.json

- implementation: drumscribe/experiments/iterative_search_ride_hires.py
- script commit: c5611207db32b476be70993f35374ef338fc0c46
- result commit: 860f8d892b1b688d28d84f45f7c32121410ed7b9

#### Cycle 85

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c85_2beat|close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6760|0.3865|0.6369|0.3734|0.0000|42|25|
|c85_4beat|winner, close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6768|0.3865|0.6369|0.3734|0.0000|42|25|
|c85_8beat|close|0.7190|0.7167|0.7214|0.9590|0.8107|0.6773|0.3865|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-hires.json / experiment-log.json

#### Cycle 86

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c86_extra|winner, close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6768|0.3865|0.6369|0.3734|0.0000|42|25|
|c86_rf|close|0.7160|0.7137|0.7183|0.9590|0.8107|0.6709|0.3865|0.6369|0.3734|0.0140|42|25|
|c86_logistic|-|0.6603|0.6582|0.6625|0.9590|0.8107|0.5885|0.3865|0.6369|0.3734|0.1609|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-hires.json / experiment-log.json

#### Cycle 87

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c87_strict|winner, close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c87_balanced|close|0.7187|0.7164|0.7211|0.9590|0.8107|0.6762|0.3865|0.6369|0.3734|0.0000|42|25|
|c87_recall|close|0.7089|0.7066|0.7112|0.9590|0.8107|0.6687|0.3865|0.6369|0.3734|0.0133|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-hires.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-ml.json

- implementation: drumscribe/experiments/iterative_search_ride_ml.py
- script commit: b5406a2a95afb264ab247660e52faa93148a152c
- result commit: 8d54d6626c748ecc1d9b9e386e3f8abd9f02e8ee

#### Cycle 16

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c16_rf|winner, close|0.6322|0.6543|0.6116|0.9281|0.7742|0.5122|-|0.0000|0.2873|0.0027|41|27|
|c16_extra|close|0.6295|0.6514|0.6090|0.9281|0.7742|0.5105|-|0.0000|0.2884|0.0073|41|27|
|c16_logistic|close|0.6226|0.6443|0.6023|0.9281|0.7742|0.5212|-|0.0000|0.2878|0.0269|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-ml.json / experiment-log.json

#### Cycle 17

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c17_strict|winner, close|0.6342|0.6563|0.6135|0.9281|0.7742|0.5129|-|0.0000|0.2862|0.0000|41|27|
|c17_balanced|close|0.6322|0.6543|0.6116|0.9281|0.7742|0.5122|-|0.0000|0.2873|0.0027|41|27|
|c17_recall|close|0.6290|0.6509|0.6085|0.9281|0.7742|0.5109|-|0.0000|0.2873|0.0047|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-ml.json / experiment-log.json

#### Cycle 18

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c18_periodic_strict|winner, close|0.6344|0.6565|0.6137|0.9281|0.7742|0.5130|-|0.0000|0.2862|0.0000|41|27|
|c18_add_strong|close|0.6344|0.6565|0.6137|0.9281|0.7742|0.5130|-|0.0000|0.2862|0.0000|41|27|
|c18_periodic_medium|close|0.6342|0.6563|0.6135|0.9281|0.7742|0.5129|-|0.0000|0.2862|0.0000|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-ml.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-pairwise.json

- implementation: drumscribe/experiments/iterative_search_ride_pairwise.py
- script commit: a507edd76a7be526cfa677d78a9fd21cc065f355
- result commit: 6f50db46ca515146468e1d4ecc418d1bb8cc4a1f

#### Cycle 106

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c106_hi_sec|winner, close|0.7169|0.7147|0.7192|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0699|42|25|
|c106_hi_either|close|0.7113|0.7091|0.7136|0.9590|0.8107|0.6665|0.3870|0.6369|0.3734|0.0846|42|25|
|c106_hi_old|-|0.7112|0.7090|0.7135|0.9590|0.8107|0.6641|0.3870|0.6369|0.3734|0.0580|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-pairwise.json / experiment-log.json

#### Cycle 107

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c107_w30|winner, close|0.7173|0.7151|0.7196|0.9590|0.8107|0.6745|0.3870|0.6369|0.3734|0.0708|42|25|
|c107_w50|close|0.7169|0.7147|0.7192|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0699|42|25|
|c107_w75|close|0.7164|0.7142|0.7187|0.9590|0.8107|0.6741|0.3870|0.6369|0.3734|0.0690|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-pairwise.json / experiment-log.json

#### Cycle 108

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c108_per50|winner, close|0.7196|0.7173|0.7219|0.9590|0.8107|0.6752|0.3870|0.6369|0.3734|0.0513|42|25|
|c108_per25|close|0.7179|0.7157|0.7202|0.9590|0.8107|0.6742|0.3870|0.6369|0.3734|0.0658|42|25|
|c108_per0|close|0.7173|0.7151|0.7196|0.9590|0.8107|0.6745|0.3870|0.6369|0.3734|0.0708|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-pairwise.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-runs.json

- implementation: drumscribe/experiments/iterative_search_ride_runs.py
- script commit: f250f097fa3caf1099a02a9122921cad969748a5
- result commit: 7b775a46038e3b67bf8badae636e319e260bfe5e

#### Cycle 91

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c91_section|winner, close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c91_both|close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c91_run|-|0.7127|0.7082|0.7173|0.9590|0.8107|0.6695|0.3865|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-runs.json / experiment-log.json

#### Cycle 92

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c92_run5|winner, close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c92_run7|close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c92_run3|-|0.7089|0.7021|0.7157|0.9590|0.8107|0.6682|0.3865|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-runs.json / experiment-log.json

#### Cycle 93

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c93_tol08|winner, close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c93_tol16|close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|
|c93_tol24|close|0.7193|0.7170|0.7217|0.9590|0.8107|0.6744|0.3865|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-runs.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-section-v2.json

- implementation: drumscribe/experiments/iterative_search_ride_section_v2.py
- script commit: 9e3d7c34413a00c9a03d09548b0be19bae134c26
- result commit: 8bbc149b1d72c8479c4cac154e038f376178d8e6

#### Cycle 187

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c187_hybrid|winner|0.7958|0.8337|0.7613|0.9626|0.8880|0.7794|0.5033|0.7582|0.3955|0.3314|2|28|
|c187_gap|-|0.7957|0.8336|0.7612|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.3297|2|28|
|c187_reclass|-|0.7948|0.8361|0.7575|0.9626|0.8880|0.7794|0.5033|0.7582|0.3955|0.2760|2|28|
|c187_base|-|0.7947|0.8360|0.7574|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-section-v2.json / experiment-log.json

#### Cycle 188

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c188_p75|winner|0.7958|0.8337|0.7613|0.9626|0.8880|0.7794|0.5033|0.7582|0.3955|0.3314|2|28|
|c188_p100|-|0.7958|0.8347|0.7604|0.9626|0.8880|0.7793|0.5033|0.7582|0.3955|0.3209|2|28|
|c188_p50|-|0.7953|0.8323|0.7614|0.9626|0.8880|0.7794|0.5033|0.7582|0.3955|0.3282|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-section-v2.json / experiment-log.json

#### Cycle 189

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c189_b8r3|winner|0.7963|0.8330|0.7626|0.9626|0.8880|0.7795|0.5033|0.7582|0.3955|0.3503|2|28|
|c189_b4r2|-|0.7958|0.8337|0.7613|0.9626|0.8880|0.7794|0.5033|0.7582|0.3955|0.3314|2|28|
|c189_b4r3|-|0.7958|0.8337|0.7613|0.9626|0.8880|0.7794|0.5033|0.7582|0.3955|0.3314|2|28|
|c189_b2r2|-|0.7951|0.8339|0.7598|0.9626|0.8880|0.7794|0.5033|0.7582|0.3955|0.3082|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-section-v2.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-section.json

- implementation: drumscribe/experiments/iterative_search_ride_section.py
- script commit: 1203a79673c906e7c5f72d54d3aeee331c17843f
- result commit: 6aa276dde570f7053bc0c1bd2c61c45d8cf0d0f7

#### Cycle 19

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c19_2beat|winner, close|0.6192|0.6408|0.5990|0.9281|0.7742|0.4973|-|0.0000|0.2862|0.0259|41|27|
|c19_4beat|close|0.6126|0.6339|0.5926|0.9281|0.7742|0.4902|-|0.0000|0.2862|0.0440|41|27|
|c19_8beat|-|0.6068|0.6280|0.5871|0.9281|0.7742|0.4835|-|0.0000|0.2862|0.0227|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-section.json / experiment-log.json

#### Cycle 20

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c20_extra|winner, close|0.6193|0.6409|0.5991|0.9281|0.7742|0.5014|-|0.0000|0.2868|0.0411|41|27|
|c20_rf|close|0.6192|0.6408|0.5990|0.9281|0.7742|0.4973|-|0.0000|0.2862|0.0259|41|27|
|c20_logistic|close|0.6048|0.6258|0.5851|0.9281|0.7742|0.4986|-|0.0000|0.2868|0.0832|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-section.json / experiment-log.json

#### Cycle 21

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c21_strict|winner, close|0.6333|0.6553|0.6126|0.9281|0.7742|0.5117|-|0.0000|0.2868|0.0029|41|27|
|c21_balanced|close|0.6215|0.6431|0.6012|0.9281|0.7742|0.5039|-|0.0000|0.2868|0.0373|41|27|
|c21_recall|-|0.6010|0.6219|0.5814|0.9281|0.7742|0.4820|-|0.0000|0.2868|0.0904|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-section.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-seed-expand.json

- implementation: drumscribe/experiments/iterative_search_ride_seed_expand.py
- script commit: 4ffcb6189ea73335fa150e6e3f464825f5428284
- result commit: 8a5f2793675bea609be2fb0f4dac90673220f159

#### Cycle 109

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c109_radius2|winner, close|0.7141|0.7087|0.7196|0.9590|0.8107|0.6708|0.3870|0.6369|0.3741|0.1016|42|25|
|c109_radius4|close|0.7130|0.7067|0.7193|0.9590|0.8107|0.6700|0.3870|0.6369|0.3741|0.1102|42|25|
|c109_radius8|close|0.7102|0.7024|0.7182|0.9590|0.8107|0.6686|0.3870|0.6369|0.3741|0.1118|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-seed-expand.json / experiment-log.json

#### Cycle 110

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c110_per75|winner, close|0.7157|0.7119|0.7195|0.9590|0.8107|0.6711|0.3870|0.6369|0.3741|0.0922|42|25|
|c110_per50|close|0.7141|0.7087|0.7196|0.9590|0.8107|0.6708|0.3870|0.6369|0.3741|0.1016|42|25|
|c110_per25|close|0.7140|0.7083|0.7197|0.9590|0.8107|0.6709|0.3870|0.6369|0.3741|0.1030|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-seed-expand.json / experiment-log.json

#### Cycle 111

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c111_seed3|winner, close|0.7164|0.7129|0.7199|0.9590|0.8107|0.6716|0.3870|0.6369|0.3741|0.0917|42|25|
|c111_seed2|close|0.7161|0.7125|0.7198|0.9590|0.8107|0.6716|0.3870|0.6369|0.3741|0.0909|42|25|
|c111_seed1|close|0.7157|0.7119|0.7195|0.9590|0.8107|0.6711|0.3870|0.6369|0.3741|0.0922|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-seed-expand.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-segment.json

- implementation: drumscribe/experiments/iterative_search_ride_segment.py
- script commit: f565b47b1ad2679fd80ff5763f8ebde355438a17
- result commit: 58a5e9f680e39236547f9f4c76d40db18c730000

#### Cycle 136

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c136_extend1|-|0.7212|0.7220|0.7204|0.9590|0.8107|0.6783|0.3870|0.6667|0.3734|0.1894|42|25|
|c136_extend2|-|0.7212|0.7220|0.7204|0.9590|0.8107|0.6772|0.3870|0.6667|0.3734|0.2280|42|25|
|c136_extend4|winner|0.7204|0.7212|0.7196|0.9590|0.8107|0.6742|0.3870|0.6667|0.3734|0.2806|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-segment.json / experiment-log.json

#### Cycle 137

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c137_tol10|winner|0.7205|0.7213|0.7197|0.9590|0.8107|0.6742|0.3870|0.6667|0.3734|0.2792|42|25|
|c137_tol18|-|0.7204|0.7212|0.7196|0.9590|0.8107|0.6742|0.3870|0.6667|0.3734|0.2806|42|25|
|c137_tol26|-|0.7204|0.7212|0.7196|0.9590|0.8107|0.6746|0.3870|0.6667|0.3734|0.2793|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-segment.json / experiment-log.json

#### Cycle 138

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c138_seed2|-|0.7205|0.7213|0.7197|0.9590|0.8107|0.6742|0.3870|0.6667|0.3734|0.2792|42|25|
|c138_seed3|winner|0.7205|0.7213|0.7197|0.9590|0.8107|0.6742|0.3870|0.6667|0.3734|0.2792|42|25|
|c138_seed4|-|0.7197|0.7205|0.7189|0.9590|0.8107|0.6733|0.3870|0.6667|0.3734|0.2669|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-segment.json / experiment-log.json

### drumscribe/experiments/results-iterative-ride-song-gate.json

- implementation: drumscribe/experiments/iterative_search_ride_song_gate.py
- script commit: 33c341c4fbf358398b9f9c49ed62d15c65b6a4b7
- result commit: 9d838db652411531d37cdeb3853cdde576a792d8

#### Cycle 106

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c106_ratio015|winner, close|0.7170|0.7148|0.7192|0.9590|0.8107|0.6703|0.3868|0.6369|0.3734|0.2716|42|25|
|c106_ratio025|close|0.7170|0.7148|0.7192|0.9590|0.8107|0.6703|0.3868|0.6369|0.3734|0.2716|42|25|
|c106_ratio040|-|0.7132|0.7110|0.7154|0.9590|0.8107|0.6692|0.3868|0.6369|0.3734|0.1538|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-song-gate.json / experiment-log.json

#### Cycle 107

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c107_local1|close|0.7180|0.7158|0.7203|0.9590|0.8107|0.6735|0.3868|0.6369|0.3734|0.0496|42|25|
|c107_local2|close|0.7171|0.7149|0.7194|0.9590|0.8107|0.6724|0.3868|0.6369|0.3734|0.0587|42|25|
|c107_local4|winner, close|0.7169|0.7147|0.7192|0.9590|0.8107|0.6720|0.3868|0.6369|0.3734|0.0909|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-song-gate.json / experiment-log.json

#### Cycle 108

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c108_per75|close|0.7185|0.7163|0.7208|0.9590|0.8107|0.6724|0.3868|0.6369|0.3734|0.0672|42|25|
|c108_per50|winner, close|0.7176|0.7154|0.7199|0.9590|0.8107|0.6715|0.3868|0.6369|0.3734|0.0941|42|25|
|c108_per25|close|0.7169|0.7147|0.7192|0.9590|0.8107|0.6715|0.3868|0.6369|0.3734|0.0916|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-ride-song-gate.json / experiment-log.json

### drumscribe/experiments/results-iterative-rotation.json

- implementation: drumscribe/experiments/iterative_search_rotation.py
- script commit: 2a61972d01dbb98c075683bc9ca3a284ca5c616f
- result commit: 24de753e533a0632c65a0f2800753ab1759b16ac

#### Cycle 10

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c10_kick_rotation|winner, close|0.6218|0.6451|0.6002|0.9281|0.7388|0.5126|-|0.0000|0.0240|0.0110|38|27|
|c10_balanced_rotation|close|0.6216|0.6448|0.5999|0.9281|0.7388|0.5127|-|0.0000|0.0112|0.0110|38|27|
|c10_no_rotation|close|0.6215|0.6448|0.5999|0.9281|0.7386|0.5127|-|0.0000|0.0172|0.0111|35|27|
|c10_crash_rotation|close|0.6215|0.6446|0.5999|0.9281|0.7378|0.5127|-|0.0000|0.0172|0.0111|38|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-rotation.json / experiment-log.json

#### Cycle 11

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c11_head_005|winner, close|0.6218|0.6451|0.6002|0.9281|0.7388|0.5126|-|0.0000|0.0240|0.0110|38|27|
|c11_head_010|close|0.6212|0.6437|0.6001|0.9281|0.7386|0.5126|-|0.0000|0.0268|0.0110|37|27|
|c11_head_015|close|0.6209|0.6434|0.5999|0.9281|0.7376|0.5126|-|0.0000|0.0266|0.0110|37|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-rotation.json / experiment-log.json

#### Cycle 12

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c12_ride_strict|winner, close|0.6218|0.6451|0.6002|0.9281|0.7388|0.5126|-|0.0000|0.0240|0.0110|38|27|
|c12_ride_medium|close|0.6120|0.6343|0.5913|0.9281|0.6795|0.5121|-|0.0000|0.0245|0.0767|33|27|
|c12_ride_recall|close|0.6051|0.6249|0.5866|0.9281|0.6378|0.5121|-|0.0000|0.0251|0.1178|26|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-rotation.json / experiment-log.json

### drumscribe/experiments/results-iterative-search.json

- implementation: drumscribe/experiments/iterative_search.py
- script commit: ed39a43e04f897a1f3c27452d269def85aab32a4
- result commit: 935c7dc5453c96717d1093042e9885b81b86ec0e

#### Cycle 1

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c1_strict|winner, close|0.5892|0.6093|0.5705|0.9281|0.7524|0.4798|-|0.0000|0.0243|0.0087|37|27|
|c1_balanced|close|0.5854|0.6049|0.5670|0.9254|0.7387|0.4798|-|0.0000|0.0241|0.0261|36|27|
|c1_recall|close|0.5832|0.6017|0.5658|0.9238|0.7381|0.4798|-|0.0000|0.0239|0.0242|33|26|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-search.json / experiment-log.json

#### Cycle 2

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c2_crash_precision|winner, close|0.5913|0.6130|0.5711|0.9281|0.7563|0.4798|-|0.0000|0.0200|0.0087|37|27|
|c2_kick_guard|close|0.5892|0.6088|0.5708|0.9306|0.7474|0.4798|-|0.0000|0.0241|0.0087|37|27|
|c2_ride_recover|close|0.5875|0.6074|0.5689|0.9281|0.7419|0.4798|-|0.0000|0.0243|0.0225|37|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-search.json / experiment-log.json

#### Cycle 3

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c3_cymbal_guard|winner, close|0.5920|0.6140|0.5716|0.9281|0.7589|0.4798|-|0.0000|0.0203|0.0059|38|27|
|c3_precision|close|0.5911|0.6124|0.5712|0.9293|0.7538|0.4798|-|0.0000|0.0199|0.0087|37|27|
|c3_balanced|close|0.5898|0.6115|0.5697|0.9275|0.7486|0.4798|-|0.0000|0.0200|0.0198|38|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-search.json / experiment-log.json

### drumscribe/experiments/results-iterative-separation.json

- implementation: drumscribe/experiments/iterative_search_separation.py
- script commit: 7efd6a910cebcd272758dac93c627be832c527b8
- result commit: 349a91f6a76755aadc28a74f046a5b43edd7cd6a

#### Cycle 40

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c40_sharp|-|0.6207|0.6341|0.6078|0.9590|0.7419|0.5162|0.0746|0.3851|0.2609|0.0000|11|25|
|c40_smooth|winner, close|0.6175|0.6382|0.5982|0.9533|0.7201|0.5022|0.0368|0.5897|0.2746|0.0000|75|27|
|c40_soft|-|0.6162|0.6218|0.6106|0.9537|0.7052|0.5042|0.1034|0.5063|0.3229|0.0000|56|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-separation.json / experiment-log.json

#### Cycle 41

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c41_no_gate|close|0.6175|0.6382|0.5982|0.9533|0.7201|0.5022|0.0368|0.5897|0.2746|0.0000|75|27|
|c41_moderate|winner, close|0.6153|0.6462|0.5872|0.9568|0.7201|0.4921|0.0369|0.5960|0.2931|0.0000|75|27|
|c41_strict|-|0.5982|0.6419|0.5601|0.9311|0.7201|0.4731|0.0369|0.5960|0.2931|0.0000|75|18|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-separation.json / experiment-log.json

#### Cycle 42

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c42_snare_guard|close|0.6156|0.6466|0.5874|0.9578|0.7198|0.4921|0.0369|0.5960|0.2931|0.0000|74|27|
|c42_snare_balanced|close|0.6151|0.6460|0.5870|0.9562|0.7201|0.4921|0.0369|0.5960|0.2931|0.0000|75|27|
|c42_snare_roll_recall|winner, close|0.6146|0.6455|0.5866|0.9510|0.7296|0.4921|0.0369|0.5960|0.2931|0.0000|79|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-separation.json / experiment-log.json

### drumscribe/experiments/results-iterative-snare-adaptive.json

- implementation: drumscribe/experiments/iterative_search_snare_adaptive.py
- script commit: 7707555ec6c3f683a4f560a312914ee76646dff5
- result commit: 21422e6bc9f1dd0a76374f0e6b1e5b6500c3a04a

#### Cycle 148

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c148_r115|-|0.7214|0.7188|0.7240|0.9590|0.8130|0.6743|0.3920|0.6667|0.3951|0.2792|45|25|
|c148_r130|winner|0.7214|0.7188|0.7240|0.9590|0.8130|0.6743|0.3920|0.6667|0.3951|0.2792|45|25|
|c148_r145|-|0.7204|0.7187|0.7221|0.9590|0.8070|0.6743|0.3920|0.6667|0.3951|0.2792|45|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-adaptive.json / experiment-log.json

#### Cycle 149

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c149_k25|-|0.7227|0.7169|0.7285|0.9590|0.8186|0.6743|0.3920|0.6667|0.3951|0.2792|89|25|
|c149_k65|winner|0.7215|0.7191|0.7240|0.9590|0.8141|0.6743|0.3920|0.6667|0.3951|0.2792|44|25|
|c149_k45|-|0.7214|0.7188|0.7240|0.9590|0.8130|0.6743|0.3920|0.6667|0.3951|0.2792|45|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-adaptive.json / experiment-log.json

#### Cycle 150

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c150_repeat2|winner|0.7215|0.7191|0.7240|0.9590|0.8141|0.6743|0.3920|0.6667|0.3951|0.2792|44|25|
|c150_backbeat|-|0.7213|0.7178|0.7249|0.9590|0.8117|0.6743|0.3920|0.6667|0.3951|0.2792|72|25|
|c150_consensus|-|0.7205|0.7193|0.7218|0.9590|0.8082|0.6743|0.3920|0.6667|0.3951|0.2792|43|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-adaptive.json / experiment-log.json

### drumscribe/experiments/results-iterative-snare-additive.json

- implementation: drumscribe/experiments/iterative_search_snare_additive.py
- script commit: f82fbc3e2cccd27b759e588245481bc7bb0bbe28
- result commit: 430de55ccdb4b345d539ddb6c600e90fed9ebfda

#### Cycle 112

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c112_veto35|winner|0.7197|0.7151|0.7243|0.9590|0.8102|0.6745|0.3870|0.6369|0.3734|0.0000|46|25|
|c112_veto70|-|0.7191|0.7159|0.7223|0.9590|0.8074|0.6745|0.3870|0.6369|0.3734|0.0000|44|25|
|c112_veto50|-|0.7188|0.7153|0.7223|0.9590|0.8049|0.6745|0.3870|0.6369|0.3734|0.0000|46|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-additive.json / experiment-log.json

#### Cycle 113

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c113_none|-|0.7197|0.7151|0.7243|0.9590|0.8102|0.6745|0.3870|0.6369|0.3734|0.0000|46|25|
|c113_repeat|-|0.7197|0.7151|0.7243|0.9590|0.8102|0.6745|0.3870|0.6369|0.3734|0.0000|46|25|
|c113_dsp|winner|0.7194|0.7171|0.7217|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-additive.json / experiment-log.json

#### Cycle 114

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c114_repeat3|winner|0.7200|0.7161|0.7241|0.9590|0.8133|0.6745|0.3870|0.6369|0.3734|0.0000|45|25|
|c114_repeat1|-|0.7197|0.7151|0.7243|0.9590|0.8102|0.6745|0.3870|0.6369|0.3734|0.0000|46|25|
|c114_repeat2|-|0.7197|0.7151|0.7243|0.9590|0.8102|0.6745|0.3870|0.6369|0.3734|0.0000|46|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-additive.json / experiment-log.json

### drumscribe/experiments/results-iterative-snare-meta-loo.json

- implementation: drumscribe/experiments/iterative_search_snare_meta_loo.py
- script commit: e1f31c650ed20a8003ea5881995fc91d31d707c5
- result commit: 05a9c59d605cb65b825945d8f51d8326a9d79a12

#### Cycle 201

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c201_extra|-|0.8021|0.8324|0.7738|0.9626|0.8541|0.7956|0.5592|0.7624|0.4560|0.3480|68|28|
|c201_heuristic|winner|0.8021|0.8351|0.7716|0.9626|0.8550|0.7956|0.5592|0.7624|0.4560|0.3480|4|28|
|c201_logistic|-|0.7990|0.8344|0.7664|0.9626|0.8353|0.7956|0.5592|0.7624|0.4560|0.3480|68|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-meta-loo.json / experiment-log.json

#### Cycle 202

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c202_t35|-|0.8000|0.8327|0.7698|0.9626|0.8414|0.7956|0.5592|0.7624|0.4560|0.3480|78|28|
|c202_t50|winner|0.7990|0.8344|0.7664|0.9626|0.8353|0.7956|0.5592|0.7624|0.4560|0.3480|68|28|
|c202_t65|-|0.7963|0.8358|0.7604|0.9626|0.8180|0.7956|0.5592|0.7624|0.4560|0.3480|62|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-meta-loo.json / experiment-log.json

#### Cycle 203

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c203_base_all|winner|0.8010|0.8302|0.7737|0.9626|0.8467|0.7956|0.5592|0.7624|0.4560|0.3480|68|28|
|c203_none|-|0.7990|0.8344|0.7664|0.9626|0.8353|0.7956|0.5592|0.7624|0.4560|0.3480|68|28|
|c203_base_struct|-|0.7989|0.8322|0.7681|0.9626|0.8341|0.7956|0.5592|0.7624|0.4560|0.3480|68|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-meta-loo.json / experiment-log.json

### drumscribe/experiments/results-iterative-snare-safe-fusion.json

- implementation: drumscribe/experiments/iterative_search_snare_safe_fusion.py
- script commit: ea01122ef8fb15915fa54bd1acb809d6546b9a29
- result commit: 818afdc8369e2a01400c03df7c71f4e732cf670a

#### Cycle 112

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c112_backbeat_rescue|close|0.7194|0.7131|0.7259|0.9590|0.8046|0.6747|0.3870|0.6667|0.3741|0.0000|77|25|
|c112_hard_veto|winner, close|0.7190|0.7153|0.7228|0.9590|0.8041|0.6747|0.3870|0.6667|0.3741|0.0000|46|25|
|c112_dsp_rescue|close|0.7190|0.7153|0.7228|0.9590|0.8041|0.6747|0.3870|0.6667|0.3741|0.0000|46|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-safe-fusion.json / experiment-log.json

#### Cycle 113

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c113_k25|close|0.7216|0.7136|0.7297|0.9590|0.8177|0.6747|0.3870|0.6667|0.3741|0.0000|90|25|
|c113_k65|winner, close|0.7194|0.7160|0.7228|0.9590|0.8071|0.6747|0.3870|0.6667|0.3741|0.0000|44|25|
|c113_k45|close|0.7190|0.7153|0.7228|0.9590|0.8041|0.6747|0.3870|0.6667|0.3741|0.0000|46|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-safe-fusion.json / experiment-log.json

#### Cycle 114

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c114_d30|winner, close|0.7194|0.7160|0.7228|0.9590|0.8071|0.6747|0.3870|0.6667|0.3741|0.0000|44|25|
|c114_d60|close|0.7194|0.7160|0.7228|0.9590|0.8071|0.6747|0.3870|0.6667|0.3741|0.0000|44|25|
|c114_d90|close|0.7194|0.7160|0.7228|0.9590|0.8071|0.6747|0.3870|0.6667|0.3741|0.0000|44|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-safe-fusion.json / experiment-log.json

### drumscribe/experiments/results-iterative-snare-veto.json

- implementation: drumscribe/experiments/iterative_search_snare_veto.py
- script commit: dd68a9ebd18ac707cbdeed31e7bcfa14aad269d1
- result commit: de3f51897f066859dc09eb0233e766966203b3cd

#### Cycle 64

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c64_consensus_veto|winner, close|0.7040|0.7458|0.6667|0.9590|0.8107|0.6451|0.1735|0.6369|0.3517|0.0000|42|25|
|c64_backbeat_rescue|close|0.7037|0.7404|0.6704|0.9590|0.8045|0.6451|0.1735|0.6369|0.3517|0.0000|76|25|
|c64_pattern_veto|close|0.7028|0.7424|0.6673|0.9590|0.8014|0.6451|0.1735|0.6369|0.3517|0.0000|46|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-veto.json / experiment-log.json

#### Cycle 65

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c65_veto25|winner, close|0.7040|0.7458|0.6667|0.9590|0.8107|0.6451|0.1735|0.6369|0.3517|0.0000|42|25|
|c65_veto45|close|0.7040|0.7458|0.6667|0.9590|0.8107|0.6451|0.1735|0.6369|0.3517|0.0000|42|25|
|c65_veto65|close|0.7040|0.7458|0.6667|0.9590|0.8107|0.6451|0.1735|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-veto.json / experiment-log.json

#### Cycle 66

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c66_repeat1|winner, close|0.7040|0.7458|0.6667|0.9590|0.8107|0.6451|0.1735|0.6369|0.3517|0.0000|42|25|
|c66_repeat2|close|0.7040|0.7458|0.6667|0.9590|0.8107|0.6451|0.1735|0.6369|0.3517|0.0000|42|25|
|c66_repeat3|close|0.7040|0.7458|0.6667|0.9590|0.8107|0.6451|0.1735|0.6369|0.3517|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-snare-veto.json / experiment-log.json

### drumscribe/experiments/results-iterative-song-adaptive-v2.json

- implementation: drumscribe/experiments/iterative_search_song_adaptive_v2.py
- script commit: a02eb25229e51bb4025f11648a23dd68b27af9a7
- result commit: d4f06028d29e5f21f9ae8817b51fd40f13d52f8b

#### Cycle 172

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c172_gate43|-|0.7916|0.8178|0.7670|0.9626|0.8876|0.7730|0.5021|0.7582|0.3955|0.2742|2|28|
|c172_gate45|-|0.7916|0.8178|0.7670|0.9626|0.8876|0.7730|0.5021|0.7582|0.3955|0.2742|2|28|
|c172_gate55|-|0.7916|0.8178|0.7670|0.9626|0.8876|0.7730|0.5021|0.7582|0.3955|0.2742|2|28|
|c172_gate70|winner|0.7916|0.8178|0.7670|0.9626|0.8876|0.7730|0.5021|0.7582|0.3955|0.2742|2|28|
|c172_base|-|0.7782|0.7897|0.7670|0.9626|0.8876|0.7730|0.3933|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-song-adaptive-v2.json / experiment-log.json

#### Cycle 173

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c173_recall45|-|0.7932|0.8177|0.7701|0.9626|0.8876|0.7768|0.5021|0.7582|0.3955|0.2742|2|28|
|c173_recall55|winner|0.7932|0.8177|0.7701|0.9626|0.8876|0.7768|0.5021|0.7582|0.3955|0.2742|2|28|
|c173_default55|-|0.7925|0.8178|0.7688|0.9626|0.8876|0.7753|0.5021|0.7582|0.3955|0.2742|2|28|
|c173_base|-|0.7916|0.8178|0.7670|0.9626|0.8876|0.7730|0.5021|0.7582|0.3955|0.2742|2|28|
|c173_legacy55|-|0.7908|0.7969|0.7849|0.9626|0.8876|0.7724|0.5021|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-song-adaptive-v2.json / experiment-log.json

#### Cycle 174

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c174_recall80|-|0.7932|0.8174|0.7705|0.9626|0.8880|0.7768|0.5021|0.7582|0.3955|0.2742|2|28|
|c174_recall90|winner|0.7932|0.8174|0.7705|0.9626|0.8880|0.7768|0.5021|0.7582|0.3955|0.2742|2|28|
|c174_base|-|0.7932|0.8177|0.7701|0.9626|0.8876|0.7768|0.5021|0.7582|0.3955|0.2742|2|28|
|c174_recall75|-|0.7932|0.8177|0.7701|0.9626|0.8876|0.7768|0.5021|0.7582|0.3955|0.2742|2|28|
|c174_default80|-|0.7930|0.8174|0.7701|0.9626|0.8867|0.7768|0.5021|0.7582|0.3955|0.2742|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-song-adaptive-v2.json / experiment-log.json

### drumscribe/experiments/results-iterative-tom-consensus.json

- implementation: drumscribe/experiments/iterative_search_tom_consensus.py
- script commit: c12ac2780f1e79ed9f244a583cb1658d8ee66fe2
- result commit: a5b9004e491290eaed31908eedb348f6697fafac

#### Cycle 103

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c103_fill|winner, close|0.7197|0.7171|0.7222|0.9590|0.8107|0.6746|0.3870|0.6587|0.3734|0.0000|42|25|
|c103_extra|close|0.7195|0.7167|0.7223|0.9590|0.8107|0.6744|0.3870|0.6550|0.3734|0.0000|42|25|
|c103_consensus|-|0.7187|0.7153|0.7222|0.9590|0.8107|0.6748|0.3870|0.5641|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-tom-consensus.json / experiment-log.json

#### Cycle 104

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c104_w40|winner, close|0.7197|0.7171|0.7222|0.9590|0.8107|0.6746|0.3870|0.6587|0.3734|0.0000|42|25|
|c104_w60|close|0.7197|0.7171|0.7222|0.9590|0.8107|0.6746|0.3870|0.6587|0.3734|0.0000|42|25|
|c104_w80|close|0.7197|0.7171|0.7222|0.9590|0.8107|0.6746|0.3870|0.6587|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-tom-consensus.json / experiment-log.json

#### Cycle 105

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c105_density5|close|0.7197|0.7171|0.7222|0.9590|0.8107|0.6746|0.3870|0.6587|0.3734|0.0000|42|25|
|c105_density7|winner, close|0.7197|0.7173|0.7222|0.9590|0.8107|0.6746|0.3870|0.6667|0.3734|0.0000|42|25|
|c105_density3|close|0.7193|0.7164|0.7222|0.9590|0.8107|0.6746|0.3870|0.6215|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-tom-consensus.json / experiment-log.json

### drumscribe/experiments/results-iterative-tom-fusion.json

- implementation: drumscribe/experiments/iterative_search_tom_fusion.py
- script commit: 7e129f0de77142435457f452889db4fa9a13d010
- result commit: 2002b3dd584777b371f00c5827c71cdaff7cdaf1

#### Cycle 103

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c103_agree|winner, close|0.7194|0.7171|0.7217|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0000|42|25|
|c103_fill|close|0.7194|0.7171|0.7217|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0000|42|25|
|c103_hybrid|close|0.7194|0.7171|0.7217|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-tom-fusion.json / experiment-log.json

#### Cycle 104

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c104_match35|winner, close|0.7194|0.7171|0.7217|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0000|42|25|
|c104_match60|close|0.7194|0.7171|0.7217|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0000|42|25|
|c104_match90|close|0.7194|0.7171|0.7217|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-tom-fusion.json / experiment-log.json

#### Cycle 105

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c105_cluster2|winner, close|0.7194|0.7171|0.7217|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0000|42|25|
|c105_cluster3|close|0.7194|0.7171|0.7217|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0000|42|25|
|c105_cluster4|close|0.7194|0.7171|0.7217|0.9590|0.8107|0.6744|0.3870|0.6369|0.3734|0.0000|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-tom-fusion.json / experiment-log.json

### drumscribe/experiments/results-iterative-tom-raw-fill.json

- implementation: drumscribe/experiments/iterative_search_tom_raw_fill.py
- script commit: 84256f62d1687aa60de1cb714d48f3a7e0f51053
- result commit: 32ea45d18ab457460dbdf8ddd390af370705b292

#### Cycle 151

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c151_seed|winner|0.7203|0.7183|0.7223|0.9590|0.8107|0.6743|0.3920|0.6200|0.3951|0.2792|42|25|
|c151_barend|-|0.7145|0.7074|0.7218|0.9590|0.8107|0.6743|0.3920|0.3266|0.3951|0.2792|42|25|
|c151_union|-|0.7142|0.7063|0.7224|0.9590|0.8107|0.6743|0.3920|0.3369|0.3951|0.2792|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-tom-raw-fill.json / experiment-log.json

#### Cycle 152

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c152_p65|-|0.7203|0.7183|0.7223|0.9590|0.8107|0.6743|0.3920|0.6200|0.3951|0.2792|42|25|
|c152_p75|-|0.7203|0.7183|0.7223|0.9590|0.8107|0.6743|0.3920|0.6200|0.3951|0.2792|42|25|
|c152_p85|winner|0.7203|0.7183|0.7223|0.9590|0.8107|0.6743|0.3920|0.6200|0.3951|0.2792|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-tom-raw-fill.json / experiment-log.json

#### Cycle 153

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c153_d120|winner|0.7207|0.7194|0.7221|0.9590|0.8107|0.6743|0.3920|0.6593|0.3951|0.2792|42|25|
|c153_d85|-|0.7203|0.7183|0.7223|0.9590|0.8107|0.6743|0.3920|0.6200|0.3951|0.2792|42|25|
|c153_d55|-|0.7198|0.7169|0.7227|0.9590|0.8107|0.6743|0.3920|0.5867|0.3951|0.2792|42|25|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-tom-raw-fill.json / experiment-log.json

### drumscribe/experiments/results-iterative-tom.json

- implementation: drumscribe/experiments/iterative_search_tom.py
- script commit: 9848da759e7f502a11a05744e4e041b604c8a2b9
- result commit: 0829d616488a0ae9492a23bba4dba5d645fe476a

#### Cycle 25

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c25_rf|winner, close|0.6429|0.6698|0.6181|0.9281|0.7710|0.5129|-|0.6194|0.2862|0.0000|41|27|
|c25_extra|close|0.6422|0.6671|0.6190|0.9281|0.7704|0.5129|-|0.5673|0.2862|0.0000|41|27|
|c25_logistic|-|0.6294|0.6492|0.6107|0.9281|0.7287|0.5131|-|0.2955|0.2862|0.0000|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-tom.json / experiment-log.json

#### Cycle 26

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c26_balanced|winner, close|0.6429|0.6698|0.6181|0.9281|0.7710|0.5129|-|0.6194|0.2862|0.0000|41|27|
|c26_strict|-|0.6423|0.6697|0.6171|0.9281|0.7710|0.5128|-|0.5429|0.2862|0.0000|41|27|
|c26_recall|-|0.6422|0.6674|0.6189|0.9281|0.7710|0.5129|-|0.5572|0.2862|0.0000|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-tom.json / experiment-log.json

#### Cycle 27

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|c27_no_context|winner, close|0.6429|0.6698|0.6181|0.9281|0.7710|0.5129|-|0.6194|0.2862|0.0000|41|27|
|c27_cluster|close|0.6428|0.6699|0.6179|0.9281|0.7707|0.5129|-|0.6133|0.2862|0.0000|41|27|
|c27_fill_or_cluster|close|0.6428|0.6698|0.6179|0.9281|0.7707|0.5129|-|0.6093|0.2862|0.0000|41|27|

詳細params・曲別データ参照: drumscribe/experiments/results-iterative-tom.json / experiment-log.json

### drumscribe/experiments/results-magenta-egmd.json

- implementation: -
- script commit: -
- result commit: adaea5a584a91757fc1303ec3847da5e4b81606d

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|0.5881|0.7336|0.4908|0.9130|0.7502|0.4391|0.0000|0.4164|0.0000|0.0023|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-magenta-egmd.json / experiment-log.json

### drumscribe/experiments/results-meter-v23.json

- implementation: -
- script commit: -
- result commit: b527681fc8a37caa93bc782c6947aad878fc6e36

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|0.8150|0.9100|0.7390|0.9626|0.8858|0.8300|0.3155|0.7624|0.4560|0.2461|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-meter-v23.json / experiment-log.json

### drumscribe/experiments/results-open-hat-guarded-loo.json

- implementation: -
- script commit: -
- result commit: e3fed1dc78c36a582ff1c834fe176541925d1e9e

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baselineAllClosed|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-open-hat-guarded-loo.json / experiment-log.json

### drumscribe/experiments/results-open-hat-loo.json

- implementation: -
- script commit: -
- result commit: 3948a7ecf2d459270a6b3b1105d193a63ba2bcaa

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baselineAllClosed|-|-|-|-|-|-|-|-|-|-|-|-|-|
|final|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-open-hat-loo.json / experiment-log.json

### drumscribe/experiments/results-open-hat-promotion-loo.json

- implementation: -
- script commit: -
- result commit: 2243af9e62e487b31e2323fef89153c9fda8282b

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baselineAllClosed|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-open-hat-promotion-loo.json / experiment-log.json

### drumscribe/experiments/results-open-hat-songnorm-loo.json

- implementation: -
- script commit: -
- result commit: 6c1ab1968f999eefcbb8612096e26a6ac893c995

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baselineAllClosed|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-open-hat-songnorm-loo.json / experiment-log.json

### drumscribe/experiments/results-v2-browser-open-hat.json

- implementation: drumscribe/experiments/evaluate_v2.py
- script commit: b37e36d46d60508ee0670f2daa1db4ac8c0c1a56
- result commit: d525a7bdfb655d0a02e590ed345103e19d9c3a96

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-v2-browser-open-hat.json / experiment-log.json

### drumscribe/experiments/results-v2-browser.json

- implementation: drumscribe/experiments/evaluate_v2.py
- script commit: b37e36d46d60508ee0670f2daa1db4ac8c0c1a56
- result commit: 51e8fd085df4ffdb6d349b3b1b6bc2b74a294f83

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner, part-leader|0.8160|0.9110|0.7400|0.9626|0.8909|0.8302|0.3152|0.7841|0.4560|0.2461|2|28|

詳細params・曲別データ参照: drumscribe/experiments/results-v2-browser.json / experiment-log.json

### drumscribe/experiments/results-v2-round1.json

- implementation: drumscribe/experiments/evaluate_v2.py
- script commit: b37e36d46d60508ee0670f2daa1db4ac8c0c1a56
- result commit: 7dc045994531e19d7412c9cc6566569562efb03c

#### Cycle 2

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|0.6130|0.6160|0.6090|0.9254|0.7797|0.5163|-|0.0042|0.0192|0.0596|42|27|

詳細params・曲別データ参照: drumscribe/experiments/results-v2-round1.json / experiment-log.json

### drumscribe/experiments/results-v2-round2.json

- implementation: drumscribe/experiments/evaluate_v2.py
- script commit: b37e36d46d60508ee0670f2daa1db4ac8c0c1a56
- result commit: 7045eafdd4c37355a3ebe5e90080d9f0985894b7

#### Cycle 3

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|0.6210|0.6090|0.6340|0.9254|0.8095|0.5163|-|0.0042|0.0192|0.0596|220|27|

詳細params・曲別データ参照: drumscribe/experiments/results-v2-round2.json / experiment-log.json

### drumscribe/experiments/results-v2-round3.json

- implementation: drumscribe/experiments/evaluate_v2.py
- script commit: b37e36d46d60508ee0670f2daa1db4ac8c0c1a56
- result commit: 31c06e7647a809e646276e644bf06bd77603469e

#### Cycle 3

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|0.5720|0.5860|0.5590|0.8646|0.8326|0.4618|-|0.0042|0.1027|0.0813|160|23|

詳細params・曲別データ参照: drumscribe/experiments/results-v2-round3.json / experiment-log.json

### drumscribe/experiments/results-v2-round4-ml.json

- implementation: drumscribe/experiments/evaluate_ml_cv.py
- script commit: c01f59572b21bfc48628b193a717a7fba922032a
- result commit: c43e9be6fdbb038ae8435a0156aba482359b33ae

#### Cycle 4

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|0.5270|0.4810|0.5830|0.8258|0.7965|0.4886|-|0.1311|0.1702|0.0492|92|44|

詳細params・曲別データ参照: drumscribe/experiments/results-v2-round4-ml.json / experiment-log.json

### drumscribe/experiments/results-v2.json

- implementation: drumscribe/experiments/evaluate_v2.py
- script commit: b37e36d46d60508ee0670f2daa1db4ac8c0c1a56
- result commit: 73de15cde45647ee494d94c7366c4d633dfbf274

#### Cycle 1

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|result|winner|0.5880|0.5690|0.6080|0.8735|0.8310|0.5163|-|0.0042|0.0494|0.0000|176|26|

詳細params・曲別データ参照: drumscribe/experiments/results-v2.json / experiment-log.json

### drumscribe/experiments/results-variable-meter-v12.json

- implementation: -
- script commit: -
- result commit: 8d1b95cbf86ea3cb1e6399236f2fca5ebaa0631e

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baseline_fixed_4_4|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-variable-meter-v12.json / experiment-log.json

### drumscribe/experiments/results-variable-meter-v13.json

- implementation: -
- script commit: -
- result commit: 73df553e954a2aa66046bbdbaad0df7775598144

#### Cycle None

|Candidate|状態|F1|P|R|Kick|Snare|Hat|Pedal HH|Tom|Crash|Ride|K→S|S→K|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|baseline_fixed_4_4|-|-|-|-|-|-|-|-|-|-|-|-|-|

詳細params・曲別データ参照: drumscribe/experiments/results-variable-meter-v13.json / experiment-log.json

