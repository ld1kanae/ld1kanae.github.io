# DruMaster Performance Test Lab

## Purpose

This directory is the additive performance test environment for DruMaster. Production `DruMaster/index.html` and production JS/CSS are not edited by performance experiments. Public test entry point: `DruMaster/perf-test.html`.

The bootstrap fetches the current production `index.html`, substitutes only explicitly listed test files, and appends performance passes. This keeps the feature baseline aligned with production while isolating experimental code.

## Hard constraints

- Primary target: smooth smartphone rendering/playback in Normal, Anywhere Touch, AUTO, and Score Playback.
- Tap-to-sound latency optimization remains out of scope.
- Do not change judgement windows, MIDI timing, `current()`, `startedAt`, song offsets, chart speed, judgement-line position, or input mappings merely for performance.
- Production files remain untouched until a change is separately approved for promotion.

## Ranking scale

Safety: **S** isolated/no semantic change; **A** narrow low-coupling change; **B** broader renderer/cache change requiring regression tests; **C** timing/architecture-adjacent.

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
| Precompute/reuse simultaneous-note offset topology while preserving hit-dependent shift | B | A | Planned |
| Score Playback decoded AudioBuffer LRU / eviction | B | A | Planned |
| Consolidate independent rAF watchers into one ticker | B/C | S | Later |
| Simplify mobile glow/filter/blend if paint/composite remains dominant | A | B | Trace-dependent |
| Active drum-voice limiting/stealing | B/C | A | Only if voice count is proven to grow excessively |
| Replace CSS root rotation with native landscape in packaged Android build | C | B | Long-term |
| Replace global monkey-patch architecture with explicit runtime modules | C | A/C | Long-term |

## Pass 1

- Reused WAAPI kit flash in Score Playback instead of forced synchronous layout.
- Touch chart repaint capped near 60 fps without throttling gameplay/audio clocks.
- Removed duplicate rAF kick scheduling while preserving the original 25 ms lookahead timer.
- HH open gauge uses transform and 30 Hz DOM writes.
- Mobile no-op backdrop filter disabled.

## Pass 2

- Mobile HH graph sampling changed from 3 CSS px to 9 CSS px.
- `Path2D` builds graph geometry without one `{x,y}` allocation per sample where supported.
- HH envelope timing, velocity curve and easing remain unchanged.

## Pass 3

- `noteVisual(type, group, scale)` results cached.
- Simultaneous-note buckets still rebuild each frame and still honor current `note.hit`, preserving existing hit-dependent note shifts.

## Pass 4 — progressive degradation response

Observed on device: play starts normally, begins stuttering at roughly 30 seconds, and becomes worse toward the end of the song.

Interpretation: this pattern is less consistent with a purely constant renderer cost and more consistent with sustained thermal/GC/audio pressure or a time-growing resource. Current runtime effect code mostly reuses DOM nodes. Drum playback does create one `AudioBufferSourceNode` + `GainNode` per hit and retains it until its sample tail ends, so active voice count is now explicitly monitored before introducing voice stealing that would alter sustain.

### Included

1. **Static chart background cache**
   - Lane fills, separators and lane labels are rendered to an off-DOM canvas only when canvas geometry/DPR changes.
   - Per-frame render blits this background, then draws measure lines, judgement zone/line and moving notes in their original order.
   - MIDI/chart geometry and note positions are unchanged.

2. **Mobile Canvas DPR 1.5 test**
   - Test copy of `chart-resize.js` changes only the touch backing-store cap from 2 to 1.5.
   - CSS-pixel geometry remains unchanged; only raster resolution/GPU pixel load changes.
   - Desktop remains capped at 3 as before.

3. **Progressive-degradation instrumentation**
   - `frameGapOver20`, `frameGapOver33`, `frameGapOver50`, `maxRenderGapMs`.
   - Chrome Long Task counts/durations when `?perf=1` is used.
   - `jsHeapUsedMB` / `jsHeapTotalMB` where `performance.memory` is available.
   - current and peak `activeVoices` from existing audio stats.
   - actual `canvasDpr`, static-background build/blit counts.

### Why drum voice limiting is not yet enabled

Stopping old drum voices could immediately lower Web Audio load, but it can audibly cut cymbal/open-hat sustain. Because full sustain is a project requirement, Pass 4 measures voice growth first instead of changing sound semantics blindly.

## Test procedure

Use the same song and preferably the same play mode/section as the reported stutter. Test at least 60-90 seconds. With `?perf=1`, the console prints `DruMasterPerfTest.snapshot()` every 5 seconds.

For the reported progressive symptom, compare snapshots around 10 s, 30 s, 60 s, and later. The most useful fields are `frameGapOver50`, `maxRenderGapMs`, `longTasks`, `jsHeapUsedMB`, `audio.activeVoices`, `peakActiveVoices`, `canvasDpr`, and `renderRate`.

## Promotion rule

A performance change remains test-only until all relevant modes show no timing, scoring, audio duplication/dropout, sustain, visual alignment, pause/resume, or seek regression.
