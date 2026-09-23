# Tom pitch subdivision v69

Date: 2026-09-24

## Problem

Production used to collapse every accepted tom hit to GM note 45. Reference charts actually use multiple tom notes (41/45/47/50 in the current five-song set), so this lost pitch/register information after onset detection.

## Production change

Current main uses `drumscribe/tom-pitch.js` as a second-stage classifier **after** tom onset acceptance.

- It does not create, remove, or retime kick/snare/tom events.
- It estimates the resonant body frequency after each tom transient.
- It clusters tom hits within a song and maps them to four robust GM tiers: **41 / 45 / 47 / 50**.
- `app.js` loads the corresponding samples, so preview playback also uses the differentiated tom sounds.

## Fresh browser validation

GitHub Actions run: **35909848191**.

Five-song fresh browser transcription, then `chart.mid` scoring only after prediction:

- Tom onset group: **TP 70 / Pred 85 / Ref 92**.
- Among the 70 time-matched tom hits, exact tom-note match: **33 / 70 = 47.14%**.
- Old all-note-45 baseline on the same matched hits: **20 / 70 = 28.57%**.
- Therefore pitch subdivision gives a clear improvement over the former fixed-45 export while preserving the existing tom onset layer.

Fresh matched-note confusion (4-tier):
- 41→41: 22
- 41→45: 11
- 41→47: 5
- 45→41: 3
- 45→45: 9
- 45→50: 8
- 47→45: 2
- 47→50: 6
- 50→41: 1
- 50→45: 1
- 50→50: 2

The main remaining weakness is clear: **47 is not being separated reliably**.

## Isolated pitch-only comparison

Workflow run: **35910569809**.

This experiment used the 92 reference tom onset times only to isolate the pitch-subdivision problem. `chart.mid` was scoring-only for the candidate comparison; none of these results are used at runtime inference.

Compared hypotheses:

1. Asset resonant-peak nearest prototype
2. Asset low-band spectral-profile nearest prototype
3. Asset hybrid peak/profile/centroid
4. Current song-relative resonant clustering
5. Leave-one-song-out real-hit profile model (research-only)

4-tier / exact results:

| Method | Accuracy |
|---|---:|
| asset peak | 47.83% |
| asset profile | 48.91% |
| asset hybrid | 45.65% |
| **current song-relative cluster** | **56.52%** |
| LOO real-profile research-only | 53.26% |

Current song-relative cluster by song:

- arcaround: **75.00%**
- diamondvirgin: **43.86%**
- kaiju: **78.26%**

Current song-relative cluster by reference note:

- 41: **64.10%**
- 45: **60.61%**
- 47: **22.22%**
- 50: **45.45%**

## Decision

Keep the current song-relative classifier as production base. The fixed asset-template approaches are not adopted.

Next improvement target:
- do not change tom onset detection;
- focus on the ambiguity between 45 / 47 / 50;
- specifically improve the mapping when clustering selects three groups, because the current 3-cluster mapping uses 41/45/50 and cannot emit 47 in that mode;
- compare any new mapping against the existing fresh-browser 47.14% matched-note score and require no regression in tom onset TP/Pred/Ref.
