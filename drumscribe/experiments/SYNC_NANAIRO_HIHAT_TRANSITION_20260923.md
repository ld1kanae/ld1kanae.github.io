# Synchronized Nanairo hi-hat transition diagnostic — 2026-09-23

Source pair supplied by the user:
- `なないろ_tempo-mapped_sync.wav`
- `なないろ_tempo-mapped_sync.mid`

This diagnostic was computed directly from that synchronized pair. It is an
in-song teacher diagnostic, **not** an unknown-song generalization score.

## Label policy

- Open: MIDI 46
- Closed: MIDI 42 + 44
- simultaneous hat notes at the same timestamp are collapsed to one physical
  event; Open wins if an Open note is present.

This gives exactly:
- Open: **240**
- Closed: **924**
- Total unique hat events: **1164**

These counts agree with `models/open-hat-sync-nanairo-tail-v1.json`.

## Important transition limitation

For every one of the 240 Open events, the next unique hi-hat event is Closed:

- Open -> Closed: **240**
- Open -> Open: **0**

Therefore this synchronized pair can directly teach:
- Open-vs-Closed onset/tail acoustics;
- the Open -> Closed choke/cutoff case.

It **cannot by itself** teach the user's Open-only / Open->Open persistence case.
That case must be learned from the other DruMaster song audio+chart pairs and/or
GMD symbolic Open/Closed sequences.

## 5–18 kHz tail observations

For each unique hat event, high-frequency audio was band-passed at 5–18 kHz.
All values below are log energy ratios relative to the early 15–55 ms window.

Median values:

| feature | Open | Closed |
|---|---:|---:|
| 70–110 ms / early | -0.4105 | -1.7203 |
| 150–220 ms / early | -0.6020 | -0.8041 |
| energy immediately before next hat / early | -0.7660 | -1.5968 |
| post-next-tail / pre-next | -0.5750 | +0.8470 |
| next-hat gap (sec) | 0.23994 | 0.11998 |

Single-feature ROC-AUC within this synchronized song:
- 70–110 ms / early: **0.9786**
- pre-next tail / early: **0.8419**
- post-next-tail / pre-next: **0.8074**

Interpretation is deliberately limited: this confirms that early high-frequency
persistence and next-hit interruption contain useful information in this pair.
It does not justify using a Nanairo-only classifier directly on unknown songs.

## Research consequence

Keep the synchronized pair as a **physics/feature-design teacher**. For the next
selector iteration:
1. retain tail/choke features as one source;
2. learn Open->Open vs Open->Closed sequence patterns from GMD separately;
3. learn cross-song acoustic transfer from DruMaster songs under leave-one-song-out;
4. use offvocal structural-family repetition (A/A', B/B', ...) as prediction-side
   context rather than pooling source rows.
