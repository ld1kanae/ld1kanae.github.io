# DrumScribe AI Handoff — Grid / Tempo / Triplet v32

最終更新: 2026-09-23

## straight grid

v31で `DruMaster/songs` 5曲を現行mainの実Chromiumでfresh採譜済み。
- 5曲すべてMIDI grid residual 0 ticks。
- aggregate P 0.911 / R 0.743 / F1 0.818。
- `rhythm-grid.js` / `midi.js` の変更でfresh browser CIが走る。

詳細: `AI_HANDOFF_GRID_V31.md`

## triplet held-out v32

GMD v1.0.0のpredefined validation/test splitを使用。

予測時:
- `auto`: WAVのみ。
- `oracle_bpm`: WAV + metadata BPM。
- reference MIDIはbrowserへ渡さない。

評価対象:
- held-out 116演奏を事前確認。
- triplet-position evidence 12件。
  - 明示metadata `shuffle/swing/triplet` は1件。
  - 残り11件は事前固定したreference-MIDI timing ruleで選定。
- strict straight controls 12件。

Workflow:
- run `35834772664`
- head `eff23fb1e087eac4f8f2afbb0c7e736f6d8376fe`
- success

現production rule:
- `bestTriplet >= 0.72`
- `bestTriplet > bestStraight + 0.10`

結果:
- auto: triplet 2/12、straight 12/12、overall 14/24。
- oracle BPM: triplet 2/12、straight 12/12、overall 14/24。
- 全generated MIDIで選択grid residual 0 ticks。

両条件でtriplet検出:
1. `test-drummer1-session1-239` — `funk/purdieshuffle`、明示metadata、1/16T。
2. `validation-drummer5-session2-15` — `latin/venezuelan-joropo`、MIDI timing evidence、1/16T。

判断:
- 現分岐はfalse tripletを抑えるが、timing-evidence positiveへの感度が低い。
- correct BPMでも集計改善なし。BPM誤推定だけが原因ではない。
- oracle BPMで3件はtriplet fitがstraight fitを上回るが閾値未達。
- 残り7件はfinal detected-event fit自体がstraight優勢。閾値緩和だけでは回収不能。
- `floor=0.45, margin=0.08` のpost-hoc replayはoracle条件で5/12、straight 12/12。ただし同じ評価集合での後解析なのでproduction未採用。

次の研究対象:
- raw onset candidateとfinal eventのgrid fit差。
- hat/rideを含むpart-specific periodicity。
- bar/phrase sequence/ranking selector。
- 明示shuffle/swing/triplet実音源を追加。

関連:
- `experiments/TRIPLET_HELDOUT_V32.md`
- `experiments/results-gmd-triplet-heldout-v32-summary.json`
- `experiments/prepare_gmd_triplet_heldout.py`
- `experiments/browser_validate_gmd_triplet.mjs`
- `experiments/score_gmd_triplet_heldout.py`
- `.github/workflows/drumscribe-gmd-triplet-heldout.yml`

## ユーザー提供WAV

`君は詩人になった [drums].wav` は会話上の添付登録を確認したが、このセッションでは添付ストレージから実行環境へのmaterializeが403で失敗し、sandbox pathにも実体が現れなかった。

したがって、このWAVのfresh acoustic transcriptionはv32時点で未実行。音声を確認済みとは扱わない。
