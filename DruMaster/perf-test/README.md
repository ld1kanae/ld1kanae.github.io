# DruMaster Performance Test Lab

## Purpose

This directory is the additive performance test environment for DruMaster. Production `DruMaster/index.html` and production JS/CSS are not edited by performance experiments. Public test entry point: `DruMaster/perf-test.html`.

The bootstrap fetches the current production `index.html`, substitutes only explicitly listed test files, and appends performance passes. This keeps the feature baseline aligned with production while isolating experimental code.

## Hard constraints

- Primary target: smooth smartphone rendering/playback in Normal, Anywhere Touch, AUTO, and Score Playback.
- Tap-to-sound latency optimization remains out of scope.
- Do not change judgement windows, MIDI timing, `current()`, `startedAt`, song offsets, chart speed, judgement-line position, or input mappings merely for performance.
- Do not shorten cymbal/open-hat sustain merely to lower CPU load unless measurement proves it is necessary and the audible consequence is explicitly accepted.
- Production files remain untouched until a change is separately approved for promotion.

## Ranking scale

Safety: **S** isolated/no semantic change; **A** narrow low-coupling change; **B** broader renderer/runtime change requiring regression tests; **C** timing/architecture-adjacent.

Priority: **S** common likely bottleneck; **A** substantial CPU/GC/layout/memory saving; **B** secondary or conditional; **C** mainly long-term cleanup.

## Ranked backlog

| Change | Safety | Priority | Status |
|---|---|---|---|
| Remove Score Playback `offsetWidth` forced reflow | S | S | Pass 1 |
| Cap heavy touch chart repaint to <=60 fps while keeping event/audio clocks native | A | S | Pass 1 |
| Remove duplicate rAF kick lookahead call, keep 25 ms timer | S | A | Pass 1 |
| HH gauge `bottom` -> transform and 30 Hz DOM writes | A | A | Pass 1 |
| Disable no-op mobile backdrop filter | S | B | Pass 1 |
| HH graph: coarser mobile sampling + allocation reduction | B | A | Pass 2 |
| Cache `noteVisual()` results | A | B/A | Pass 3 |
| Cache static chart lane background/labels | B | A | Pass 4 |
| Mobile backing-store DPR 2 -> 1.5 in test environment | B | A/B | Pass 4 |
| Add progressive-degradation metrics: frame gaps, long tasks, heap, active voices | S | A | Pass 4 |
| Consolidate 3 independent perpetual rAF watchers into one shared ticker | B | S | Pass 5 |
| In-page mobile diagnostics overlay for 30s+ degradation | S | A | Pass 5 |
| Precompute/reuse simultaneous-note offset topology while preserving hit-dependent shift | B | A | Pass 6 |
| Score Playback decoded AudioBuffer LRU / eviction | B | A | Planned |
| Web Audio drum mixer / reduced AudioNode-per-hit architecture | C | S/A if Pass 6 does not help | Next audio candidate |
| Simplify mobile glow/filter/blend if paint/composite remains dominant | A | B | Trace-dependent |
| Active drum-voice limiting/stealing | C | A | Avoid unless voice count is proven excessive; can cut sustain |
| Replace CSS root rotation with native landscape in packaged Android build | C | B | Long-term |
| Replace global monkey-patch architecture with explicit runtime modules | C | A/C | Long-term |

## Passes 1-4 summary

- Pass 1: removed Score Playback forced reflow, capped touch rendering near 60 fps, removed duplicate kick lookahead call, moved HH gauge to transform/30 Hz, disabled no-op mobile backdrop filter.
- Pass 2: reduced mobile HH graph samples from 3 px to 9 px and removed per-sample point objects where `Path2D` is available.
- Pass 3: cached `noteVisual(type, group, scale)`.
- Pass 4: cached static chart lane background/labels, lowered test-only mobile Canvas DPR cap 2 -> 1.5, and added progressive-degradation diagnostics.

Pass 4 did not materially change the reported symptom: play starts normally, begins stuttering at roughly 30 seconds, then worsens toward the end.

## Pass 5 — shared perpetual ticker

Three independent perpetual rAF watchers were consolidated into one shared ticker:

1. kick goal synchronization,
2. normal-play kick judgement watcher,
3. Score Playback note/Auto watcher.

Their cursor logic and timing thresholds were preserved. Pass 5 also added an on-device `?perf=1` overlay.

### Device evidence captured after Pass 5

At roughly 74.6 song seconds the diagnostic overlay showed approximately:

- render rate ~50.9/s,
- `>50 ms` frame gaps: 23,
- max render gap: 123.7 ms,
- shared ticker ~56.2/s,
- ticker task batch max 15.6 ms,
- current drum voices 8, peak 21,
- Long Tasks 6, max roughly 368 ms,
- JS heap 35.6 / 37.8 MB.

Interpretation:

- Voice count is not monotonically exploding; peak 21 is not enough evidence to justify cutting sustain.
- Shared ticker work itself is not the large stall; its measured batch max was only 15.6 ms.
- The important signal is main-thread stalls together with heap sitting near its current allocated ceiling.
- This raises the probability of allocation/GC pressure rather than a simple constant GPU load or an ever-growing AudioNode count.

## Pass 6 — remove per-frame simultaneous-note topology allocation

### Target

Before Pass 6, `simultaneousNoteOffsets()` allocated a new outer `Map`, nested `Map`s, a `WeakMap`, string keys, slot objects, slot arrays, and a sorted slot array on every call. It is called once from the main chart draw and again when KICK/AUTO notes are redrawn, so this generated short-lived objects continuously for the entire song.

### Included

- Build tick/lane/slot topology once per notes array + group map + width scale + hidden-type configuration.
- Store stable note-to-slot metadata in a `WeakMap` once.
- Each frame only updates the current visible range / hit-state epoch and answers `.get(note)` from the reusable topology view.
- A preceding simultaneous slot contributes width only if at least one of its notes is currently visible and, when `skipHit` is enabled, still unhit. This preserves the existing behavior where remaining simultaneous notes shift after another slot is hit.
- No judgement, MIDI clock, chart position, note width, or hit-state semantics are changed.

### Semantic regression check

The supplied/current nanairo MIDI was parsed as 1,758 drum notes. The old and new offset algorithms were compared across 2,000 randomized visible ranges and randomized hit states. The resulting offsets matched in all tested cases.

### New diagnostics

`?perf=1` now shows `PASS6` and reports `topologyBuilds` / simultaneous offset call counts. `topologyBuilds` should remain very small after warm-up rather than increasing every frame.

## Audio interpretation

Current production audio creates one `AudioBufferSourceNode` + `GainNode` per drum hit and retains it until the sample tail ends. This remains the next major candidate if Pass 6 does not materially reduce the progressive stutter. However, blindly stopping older voices would cut cymbal/open-hat sustain, so any audio pass should reduce node-management overhead without shortening audible tails.

## Test procedure

Use the same song/mode and play at least 60-90 seconds.

Normal test URL:

- `DruMaster/perf-test.html`

Diagnostic URL:

- `DruMaster/perf-test.html?perf=1`

For Pass 6, compare the same 60-90 second section. If stutter remains, capture the overlay after it becomes obvious. The most useful fields are `>50`, `max`, `long`, `heap`, `voices/peak`, and `topology`.

## Promotion rule

A performance change remains test-only until all relevant modes show no timing, scoring, audio duplication/dropout, sustain, visual alignment, pause/resume, or seek regression.
