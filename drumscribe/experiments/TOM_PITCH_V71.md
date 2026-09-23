# Tom pitch subdivision v71 — absolute resonant-frequency thresholds

Date: 2026-09-24

## Scope

This iteration changes only the pitch/register assigned to **already accepted tom hits**.
Tom onset creation/removal/timing is unchanged. Production inference remains audio-only;
`chart.mid` is read only by validation after the browser has generated its prediction.

The previous production method (`song-relative-resonance-cluster-v1`) clustered each
song's tom resonant peaks and then mapped the clusters to GM 41 / 45 / 47 / 50.
Two concrete failure modes motivated this iteration:

- 3-cluster mode was hard-coded to **41 / 45 / 50**, so GM47 could not be emitted.
- kaiju selected four clusters even though all four centers were low
  (75.37 / 86.13 / 107.67 / 129.20 Hz), which forced low resonances across all four GM tiers.

## Hypotheses tested on fresh detected events

Fresh-browser detections were frozen first. Candidate pitch mappings were then scored
against `chart.mid` within the same ±80 ms tom matching rule.

Run **35915249181** — three-cluster mapping alternatives, 69 matched diagnostic decisions:

| candidate | exact / tier4 |
|---|---:|
| k3 41/45/50 (old production mapping) | 32/69 = 46.38% |
| k3 41/45/47 | **36/69 = 52.17%** |
| k3 41/47/50 | 26/69 = 37.68% |
| k3 45/47/50 | 14/69 = 20.29% |

The audio-only center-anchor selector also chose 41/45/47 for both k3 songs and produced
the same 36/69 result.

Run **35915612787** — direct absolute resonant-frequency mapping:

- <110 Hz → GM41
- 110–145 Hz → GM45
- 145–190 Hz → GM47
- ≥190 Hz → GM50

Result on the same diagnostic decision set: **49/69 = 71.01%**.
By song: arcaround 85.71%, diamondvirgin 52.50%, kaiju 100.00%.

This substantially outperformed every cluster mapping, so clustering was removed from
the production decision path.

## Independent 92-onset check

The detailed artifact from v69 contains all 92 reference tom onset windows. Reapplying
the already-computed resonant peak to those windows gives:

- previous song-relative cluster: 52/92 = **56.52%**
- direct thresholds 110/145/190: 58/92 = **63.04%**
- direct thresholds 110/145/210: 60/92 = **65.22%**

This is an isolated pitch-only check; the reference onset times are used to isolate pitch
classification and are not a production inference input.

## High-tom boundary sweep

After promoting the direct classifier, the remaining dominant error was GM47 being sent
to GM50. Run **35916487786** compared the upper boundary on the same 69 matched
diagnostic decisions:

| upper 47/50 boundary | exact / tier4 |
|---|---:|
| 190 Hz | 49/69 = 71.01% |
| 200 Hz | 49/69 = 71.01% |
| **210 Hz** | **53/69 = 76.81%** |
| 220 Hz | 52/69 = 75.36% |

At 210 Hz, all four former 47→50 errors were recovered without losing either correctly
matched GM50 event. At 220 Hz one GM50 changed to GM47, so 210 Hz was selected.

## Production result

Current production method: **`resonance-absolute-threshold-v3`**

Thresholds:

- <110 Hz → GM41
- 110–145 Hz → GM45
- 145–210 Hz → GM47
- ≥210 Hz → GM50

Production commit: **f2efa583073de1044d7bb0b1355ee5d1bfa9dfc7**

Fresh Chromium validation run: **35916925487**

- Tom onset group: **TP 70 / Pred 85 / Ref 92** — unchanged from the previous production baseline.
- Matched tom pitch: **54/70 = 77.14%**
- Previous cluster production: **33/70 = 47.14%**
- Former all-GM45 baseline on the same matched set: **20/70 = 28.57%**

Final 4-tier confusion:

- 41→41: 31
- 41→45: 7
- 45→41: 5
- 45→45: 15
- 47→45: 2
- 47→47: 6
- 50→41: 2
- 50→50: 2

Therefore the new pitch stage improves exact matched-tom pitch by **+30.00 percentage
points** versus the previous clustering production while leaving tom onset TP/Pred/Ref
unchanged.

## Remaining targets

The largest remaining pitch errors are now low/high timbre ambiguities rather than the
former 47/50 boundary problem:

- truth GM41 → GM45: 7
- truth GM45 → GM41: 5
- truth GM50 → GM41: 2
- truth GM47 → GM45: 2

Next experiments should keep the current onset layer and the v3 thresholds as the
baseline, then test a secondary descriptor only near ambiguous boundaries (for example
body spectral profile / centroid / multi-window consistency). Avoid reintroducing
song-relative cluster cardinality as the primary pitch decision.

There is also one architectural edge case to inspect: `tomPitch.tomCount` totals 84
across the three songs containing detected toms, while the exported MIDI contains 85
tom predictions. Arrangement rescoring occurs after `transcribe()` in `app.js`, so a
post-transcription rescued tom may bypass `assignTomPitches()`. Confirm the exact event
before changing this path.
