# DrumScribe AI Handoff — Grid / Tempo v31

最終更新: 2026-09-23

## 結論

量子化＋可変BPMの完全経路を、`DruMaster/songs` の5曲でfresh実ブラウザ再検証済み。

要求:
- 通常は8/16/32分へ量子化。
- straight曲の微小timing差はnoteをgrid外へ残さずtempo map側へ移す。
- shuffle / swing / tripletはstraight gridを強制しない。
- 楽器class判定はgrid/tempo層で変更しない。

現行 `rhythm-grid.js`:
- straightは16分基本。
- 16分から0.10 beat超、32分点から0.035 beat以内のみ32分保持。
- tripletはtriplet fitがstraight fitを明確に上回る場合のみ採用。
- phase driftをtempo mapへ変換。
- BPMは基準±3%へclamp。

## fresh 5曲 browser validation

GitHub Actions:
- workflow: `DrumScribe main KST browser validation`
- run: `35833299223`
- head: `dd048ea92c2df1fb6e1b1e999379acd647cdda6c`
- result: **success**

`DruMaster/songs/<song>/drums.mp3` を実Playwright Chromiumで最初から採譜し、download MIDIを直接検査。

| Song | Grid | Notes | Tempo events | BPM range | 16th | 32nd only | median timing delta | p95 timing delta | Grid residual |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|
| arcaround | 1/16 | 1086 | 549 | 131.831–132.159 | 100.00% | 0.00% | 4.29 ms | 13.53 ms | 0 ticks |
| diamondvirgin | 1/16+1/32 | 1887 | 589 | 134.713–135.428 | 99.63% | 0.37% | 5.72 ms | 17.82 ms | 0 ticks |
| kaiju | 1/16+1/32 | 1234 | 594 | 179.491–180.436 | 99.92% | 0.08% | 4.30 ms | 13.11 ms | 0 ticks |
| nanairo | 1/16+1/32 | 1802 | 491 | 124.944–125.468 | 99.89% | 0.11% | 1.20 ms | 8.65 ms | 0 ticks |
| ray | 1/16+1/32 | 2216 | 557 | 131.944–132.171 | 97.16% | 2.84% | 2.58 ms | 6.58 ms | 0 ticks |

専用validator:
- `drumscribe/experiments/validate_grid_browser.py`
- MIDI note tickが選択gridに完全一致することを確認。
- runtime `tempoEvents` とMIDI内set_tempo数の一致を確認。
- raw→tempo-map preview差を median <=10ms / p95 <=25ms でguard。
- 今回 failures = 0。

fresh browser `chart.mid` 評価:
- TP 7492 / Pred 8225 / Ref 10086
- Precision 0.911
- Recall 0.743
- F1 0.818
- max export grid residual = 0.0 beat

## CI修正

従来workflowは `rhythm-grid.js` / `midi.js` がpush triggerに含まれていなかった。

v31で:
- `drumscribe/rhythm-grid.js`
- `drumscribe/midi.js`
- `drumscribe/experiments/validate_grid_browser.py`

をtriggerへ追加し、fresh browser生成直後にgrid/tempo validatorを実行するよう変更。

Commits:
- validator: `fd88a33da27d417b7763eb155a6dd38c5c76bc1a`
- workflow: `dd048ea92c2df1fb6e1b1e999379acd647cdda6c`
- v31 result JSON: `16776d49120eb9940a87a0170bcaa0a46c5877a5`
- VALIDATION: `d0e349c7923c23403b40452a1cf38a7133223a34`

Raw result:
- `drumscribe/experiments/results-grid-tempo-five-fresh-v31.json`

## ユーザー提供「君は詩人になった」

v30までに旧生成MIDI→現行grid/tempo再構成とaudio-onset sanity checkは済んでいる。

ただし、このチャットで現在アクセス可能な添付には元WAV本体がないため、同WAVのfresh acoustic transcriptionだけはこのセッションでは未実行。
元WAVが再度利用可能になれば、5曲と同じreal-browser validator経路で確認する。

## 次

1. ユーザー提供WAVのfresh browser再生成（WAV本体が利用可能になり次第）。
2. shuffle / swing / triplet実音源のheld-outセットを増やす。
3. 32分escape `0.10/0.035` と候補 `0.08` を、明確な32分フィルを持つ曲で比較。
4. grid/tempo層ではclass判定を変更しない。
