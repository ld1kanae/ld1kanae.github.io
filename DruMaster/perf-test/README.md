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
| Precompute/reuse simultaneous-note offset topology while preserving hit-dependent shift | B | A | Planned |
| Score Playback decoded AudioBuffer LRU / eviction | B | A | Planned |
| Web Audio drum mixer / reduced AudioNode-per-hit architecture | C | S/A if Pass 5 does not help | Next audio candidate |
| Simplify mobile glow/filter/blend if paint/composite remains dominant | A | B | Trace-dependent |
| Active drum-voice limiting/stealing | C | A | Avoid unless voice count is proven excessive; can cut sustain |
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

Observed on device: play starts normally, begins stuttering at roughly 30 seconds, and becomes worse toward the end of the song. Pass 4 reduced sustained raster/render load, but the user reported that the progressive symptom continued.

### Included

- Static chart background cache.
- Mobile Canvas backing-store DPR cap 2 -> 1.5 in test only.
- Frame-gap, Long Task, heap, active-voice and peak-voice instrumentation.

### Result

No meaningful change to the reported progressive stutter. This lowers the probability that raster resolution/static chart painting is the primary cause.

## Pass 5 — shared perpetual ticker

### Reason

Static/GPU reductions did not change the roughly-30-second onset. The runtime still had multiple independent perpetual `requestAnimationFrame` loops in addition to the main gameplay/score rendering loops:

1. `auto-kick-effect.js` — kick goal synchronization.
2. `judgement.js` — normal-play kick judgement glow watcher.
3. `score-playback-auto.js` — Score Playback note/Auto watcher, even while Score Playback was inactive.

These callbacks all woke once per display refresh. On high-refresh mobile displays this creates unnecessary scheduling and JS wakeups for the full song and can contribute to sustained CPU/thermal pressure even when each individual callback is small.

### Included

1. **One shared ticker**
   - `perf-ticker.js` owns one perpetual rAF.
   - The three watchers above register their existing processing functions as ticker tasks.
   - Their cursor logic and timing thresholds are preserved.
   - Normal gameplay still has its main gameplay rAF; Score Playback still has its own score-render loop. Pass 5 removes only the three redundant perpetual watcher rAFs.

2. **Kick goal sync preserved**
   - `kickGoalCursor`, run reset, chart clock and `t + 0.0005` threshold remain unchanged.
   - Only who schedules `syncKickGoalHits()` changed.

3. **Judgement kick watcher preserved**
   - Existing `lastT`, reset search and `-.025` allowance remain unchanged.
   - Score Playback still suppresses this normal-play watcher.

4. **Score Playback Auto watcher preserved**
   - Existing cursor reset, seek/scrub handling, `t + .012` and late-note `.05` limits remain unchanged.
   - Auto toggle synchronization is event-driven rather than redundantly rewritten every frame.

5. **Visible diagnostics with `?perf=1`**
   - Small in-game overlay shows song time, render rate, >50 ms gap count/max gap, shared ticker rate/task count/max batch time, active/peak drum voices, Long Tasks and JS heap when supported.
   - Diagnostic voice sampling is added only in `?perf=1` mode and runs at 4 Hz through the shared ticker.

## Audio interpretation

Current production audio creates one `AudioBufferSourceNode` + `GainNode` per drum hit and keeps the node connected until that sample ends. This remains a strong candidate if Pass 5 does not materially delay or remove the progressive stutter. However, blindly stopping older voices would cut cymbal/open-hat sustain, so the next audio pass should prefer an architecture that reduces per-hit AudioNode overhead without shortening audible tails.

## Test procedure

Use the same song/mode and play at least 60-90 seconds.

Normal test URL:

- `DruMaster/perf-test.html`

Diagnostic URL:

- `DruMaster/perf-test.html?perf=1`

For Pass 5, first compare whether the stutter onset is removed, delayed, or unchanged. If it remains, use the diagnostic URL and capture the overlay once around 10-20 seconds and again after the stutter becomes obvious. The most useful fields are `>50`, `max`, `voices`, `peak`, `long`, `heap`, and ticker max batch time.

## Promotion rule

A performance change remains test-only until all relevant modes show no timing, scoring, audio duplication/dropout, sustain, visual alignment, pause/resume, or seek regression.
