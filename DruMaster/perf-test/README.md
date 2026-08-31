# DruMaster Performance Test Lab

## Purpose

This directory is the additive performance test environment for DruMaster.
The production entry point `DruMaster/index.html` and production JS/CSS files are not modified by performance experiments.

Public test entry point:

- `DruMaster/perf-test.html`

The test bootstrap fetches the current production `index.html`, substitutes only explicitly listed performance-test files, and appends the current performance passes. This keeps the visible/gameplay baseline aligned with production while isolating experimental code.

## Hard constraints

- Primary target: smooth smartphone rendering/playback in Normal, Anywhere Touch, AUTO, and Score Playback.
- Tap-to-sound latency optimization is out of scope for the first passes.
- Do not change judgement windows, MIDI timing, `current()` clock semantics, `startedAt`, song offsets, chart speed, judgement-line position, or input mappings merely for performance.
- Production files must remain untouched until a change is separately approved for promotion.

## Ranking scale

### Safety

- **S**: isolated visual/runtime waste removal; timing/gameplay semantics unchanged; easy rollback.
- **A**: narrow runtime change with low coupling; behavior preserved by design.
- **B**: broader renderer/cache change; requires mode-by-mode regression testing.
- **C**: architecture/timing-adjacent change or large load-order impact; only after instrumentation and earlier passes.

### Priority

- **S**: likely common cause of stutter across several/all modes.
- **A**: substantial CPU/GC/layout/memory saving or strong mode-specific bottleneck.
- **B**: secondary paint/composite saving or conditional bottleneck.
- **C**: cleanup/long-term maintainability with limited immediate frame-time benefit.

## Ranked backlog

| Change | Safety | Priority | Status |
|---|---|---|---|
| Remove Score Playback `offsetWidth` forced reflow and reuse WAAPI kit flash | **S** | **S** | Pass 1 |
| Cap heavy chart repaint to <=60 fps on touch/high-refresh displays while keeping event/audio clocks native | **A** | **S** | Pass 1 |
| Remove duplicate rAF call to kick lookahead scheduler while preserving existing 25 ms timer | **S** | **A** | Pass 1 |
| HH open gauge: stop per-frame `bottom` layout writes; use transform and 30 Hz DOM updates | **A** | **A** | Pass 1 |
| Disable no-op mobile `backdrop-filter: blur(0) saturate(100%)` | **S** | **B** | Pass 1 |
| HH openness graph: reduce mobile sampling and remove per-sample JS object allocations | **B** | **A** | Pass 2 |
| Cache `noteVisual()` results | **A/B** | **B/A** | Next candidate |
| Precompute/reuse simultaneous-note offset topology without changing hit-note shift behavior | **B** | **A** | Planned |
| Cache static chart background/labels/goal material | **B** | **A** | Planned |
| Score Playback decoded AudioBuffer LRU / eviction | **B** | **A** | Planned |
| Consolidate independent rAF watchers into one visual ticker | **B/C** | **S** | Later after instrumentation |
| Simplify mobile glow/filter/blend effects if paint/composite remains dominant | **A** | **B** | Trace-dependent |
| Adaptive mobile Canvas DPR 2 -> 1.5/1 under sustained frame pressure | **B** | **B** | Trace-dependent |
| Replace CSS root rotation with native landscape in packaged Android build | **C** | **B** | Long-term experiment |
| Replace global monkey-patch architecture with explicit runtime modules | **C** | **A/C** | Long-term architecture |

## Pass 1 — 2026-09-01

Base `main` before test-lab commit: `e8a1ecd89dc30104f4b661fceff27eea1e338313`.

### Included

1. **Score Playback forced-layout removal**
   - Test copy of `hit-flash-performance.js` exposes the existing raw reusable WAAPI kit flash.
   - Test copy of `score-playback-auto.js` calls that raw flash instead of `class remove -> offsetWidth -> class add`.
   - Goal-line judgement glow remains separate, so no duplicate judgement lookup is introduced.

2. **Touch chart repaint cap**
   - `draw()` requests still occur from the existing gameplay/score loops.
   - On touch hardware, expensive actual chart rendering is limited to approximately 60 fps.
   - Audio scheduling, MIDI/event progression and judgement clocks are not throttled.
   - 60 Hz devices should render essentially every frame; 90/120 Hz devices avoid unnecessary 90/120 fps Canvas work.

3. **Duplicate kick lookahead call removal**
   - `game-chart.js` registered the original `scheduleKickAudio` with `setInterval(..., 25)` before the final test patch loads.
   - Pass 1 replaces the later global binding with a no-op so the per-rAF duplicate call does no work.
   - The existing 25 ms audio lookahead timer remains active with its original function reference.

4. **HH open gauge transform/throttle**
   - Gauge level DOM writes are capped at 30 Hz.
   - Handle has a fixed `bottom: 0` and moves with `translate3d` using cached gauge height.
   - Gauge height is refreshed by `ResizeObserver`, not read every frame.

5. **No-op mobile backdrop filter disabled**
   - Test-only style sets chart backdrop filter to `none` on mobile.

## Pass 2 — 2026-09-01

### Included

1. **HH openness graph mobile sampling reduction**
   - Production graph samples every 3 CSS px.
   - Test renderer keeps desktop at 3 px and changes mobile to 9 px.
   - At an 800 CSS-px chart this reduces graph envelope evaluations from roughly 267 to roughly 90 per rendered frame.

2. **HH openness graph allocation reduction**
   - The production path builds `runs[]`, `run[]`, and one `{x,y}` object per visible graph sample every frame.
   - Pass 2 builds fill/stroke geometry directly with two `Path2D` objects per frame where supported.
   - A compatibility fallback retains the old array method but still uses the coarser mobile sample interval.

3. **Renderer placement preserves later wrappers**
   - Pass 2 is injected immediately after production `game-chart.js`.
   - Existing later patches, including the HH gauge wrapper, continue to wrap the replacement draw function.
   - The final Pass 1 <=60 fps wrapper still applies after all gameplay scripts have loaded.

### Explicitly not changed

- HH envelope event timings, ramp constants, easing functions and velocity curve are unchanged.
- `current()`, `beatTiming`, judgement position, chart speed and note positions are unchanged.
- Kick redraw behavior and simultaneous-note offset logic are copied without semantic changes.

## Deferred because of safety

- Precomputing simultaneous-note offsets across hit state can subtly change how the remaining bar shifts after one note of a simultaneous group is hit. Do not implement that naïvely. A later optimization must preserve the current hit-dependent layout or prove that changing it is intended.
- Full rAF unification remains high priority but touches several independently evolved cursors and should follow device measurements.
- AudioBuffer eviction is important for Score Playback memory pressure but is separate from the CPU/layout passes.

## Test procedure

Check the same song/section in this order:

1. Normal — no tapping.
2. Normal — dense tapping.
3. Anywhere Touch.
4. AUTO.
5. Score Playback, Auto OFF.
6. Score Playback, Auto ON.

Verify:

- No change in chart/goal timing.
- No missing or doubled kick audio.
- Score Playback still shows both goal-line and kit-body hit effects.
- HH open gauge follows the same envelope and reaches the same endpoints.
- HH graph shape and transitions remain visually equivalent; mobile should only be marginally less densely sampled.
- Pause/resume and seek still work.

Add `?perf=1` to the test URL to log `DruMasterPerfTest.snapshot()` every 5 seconds. Pass 2 also reports `hhGraphFrames`, `hhGraphSamples`, and `hhGraphSamplesPerFrame`.

## Promotion rule

A performance change remains test-only until it passes all relevant modes and shows no timing, scoring, audio duplication/dropout, visual alignment, pause/resume, or seek regressions.
