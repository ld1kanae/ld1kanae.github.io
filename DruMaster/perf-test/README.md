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
| Add progressive-degradation metrics | S | A | Pass 4 |
| Consolidate 3 independent perpetual rAF watchers into one shared ticker | B | S | Pass 5 |
| Precompute/reuse simultaneous-note offset topology while preserving hit-dependent shift | B | A | Pass 6 |
| Reuse WAAPI Animation objects for repeated hit/score/tap effects | A | A | Pass 7 |
| Live 1 s / 5 s display-Hz and chart-FPS measurement, reset at gameplay start | S | A | Pass 7 |
| Score Playback decoded AudioBuffer LRU / eviction | B | A | Planned |
| Web Audio drum mixer / reduced AudioNode-per-hit architecture | C | A | Audio candidate if main-thread passes fail |
| Simplify mobile glow/filter/text-shadow if paint remains dominant | A/B | A/B | Next visual candidate |
| Active drum-voice limiting/stealing | C | A | Avoid unless voice count is proven excessive; can cut sustain |
| Replace CSS root rotation with native landscape in packaged Android build | C | B | Long-term |
| Replace global monkey-patch architecture with explicit runtime modules | C | A/C | Long-term |

## Passes 1-4 summary

- Pass 1: removed Score Playback forced reflow, capped touch rendering near 60 fps, removed duplicate kick lookahead call, moved HH gauge to transform/30 Hz, disabled no-op mobile backdrop filter.
- Pass 2: reduced mobile HH graph samples from 3 px to 9 px and removed per-sample point objects where `Path2D` is available.
- Pass 3: cached `noteVisual(type, group, scale)`.
- Pass 4: cached static chart lane background/labels, lowered test-only mobile Canvas DPR cap 2 -> 1.5, and added progressive-degradation diagnostics.

Pass 4 did not materially change the progressive symptom.

## Pass 5 — shared perpetual ticker

Three independent perpetual rAF watchers were consolidated into one shared ticker: kick goal synchronization, normal-play kick judgement watcher, and Score Playback note/Auto watcher. Their cursor logic and timing thresholds were preserved.

### Device evidence after Pass 5

At roughly 74.6 song seconds:

- render rate ~50.9/s,
- `>50 ms` gaps: 23,
- max render gap: 123.7 ms,
- ticker ~56.2/s,
- ticker batch max 15.6 ms,
- current drum voices 8, peak 21,
- heap 35.6 / 37.8 MB.

This reduced the probability that the shared ticker or monotonically growing voice count was the primary cause.

## Pass 6 — remove per-frame simultaneous-note topology allocation

Before Pass 6, `simultaneousNoteOffsets()` allocated new outer/nested Maps, a WeakMap, strings, slot objects and arrays on every call. Pass 6 builds the tick/lane/slot topology once per chart configuration and reuses it while still respecting current visibility and `note.hit` state.

The current nanairo MIDI parses as 1,758 drum notes. The old and new offset algorithms were compared across 2,000 randomized visible ranges and randomized hit states; offsets matched in all tested cases.

### Device evidence after Pass 6

The user reported the first slight audible/visual stutter around song 19 seconds. The screenshot showed approximately:

- old cumulative render rate 41.7/s,
- shared ticker 58.1/s,
- `>50 ms` gap count 1, max 69.8 ms,
- ticker batch max 15.9 ms,
- current drum voices 5, peak 9,
- heap 9.5 / 9.5 MB,
- Long Task display 6, max about 358 ms.

The key comparison is that ticker/rAF delivery was still near a 60 Hz display while chart rendering was already much lower. Therefore the app was actually dropping chart frames rather than simply running on a low-refresh panel.

The old Long Task counters started at page load, so the displayed 6 / 358 ms may include loading/startup work. Pass 7 fixes this measurement flaw by resetting gameplay metrics when `running` changes from false to true and ignoring pre-session Long Task entries.

## Pass 7 — repeated animation reuse + real FPS measurement

### Reason

Even after Pass 6, current drum voices were only 5 with peak 9 at the first stutter point. At the same time, several visual paths still created fresh Web Animations objects on every hit:

- kit-body hit flash,
- goal/lane hit glow,
- kick flash,
- mobile tap feedback,
- numeric score pulse.

These animations are short-lived and repeated at drum-note frequency, making them a plausible source of allocation/GC and style/animation bookkeeping pressure on the main thread.

### Included

1. **Reusable WAAPI pool**
   - A test-only `Element.prototype.animate` adapter intercepts only explicitly recognized DruMaster effect elements.
   - First use creates the native `Animation`; later hits restart the same object with updated keyframes/timing rather than allocating a new `Animation` object.
   - Non-DruMaster animations continue directly to the native implementation.
   - Counters `animationCreated`, `animationReused`, and `animationRecreated` are exposed for verification.

2. **Gameplay-session metric reset**
   - FPS/gap/Long Task/peak-voice metrics reset at actual play start instead of page load.
   - Pause does not reset the session.
   - Pre-game loading Long Tasks are excluded from gameplay Long Task totals.

3. **Real-time FPS separation**
   - `displayHz1s` / `displayHz5s`: actual `requestAnimationFrame` delivery rate from the shared ticker. This approximates the browser/display refresh cadence available to the app.
   - `chartFps1s` / `chartFps5s`: actual successful DruMaster chart renders after the mobile <=60 fps cap. This is the useful in-game rendering FPS.
   - `drawRequestFps1s`: how often the gameplay/score loop requested a draw. Comparing request rate to chart FPS reveals whether frames are being suppressed or the caller itself is late.

4. **Low-overhead FPS-only mode**
   - `?fps=1` shows only display Hz, chart FPS, draw request rate and >50 ms gaps.
   - It does not enable Long Task observation or full diagnostic console logging.
   - `?perf=1` remains the full diagnostic mode and also shows animation-pool reuse.

## Audio interpretation

Production audio still creates one `AudioBufferSourceNode` + `GainNode` per drum hit. However the first-stutter screenshot showed only 5 active voices and peak 9, so active voice accumulation is not currently the strongest explanation. Audio-node creation churn remains a later candidate if the main-thread animation/paint passes do not improve the symptom.

## Test procedure

Normal test URL:

- `DruMaster/perf-test.html`

Lightweight FPS measurement:

- `DruMaster/perf-test.html?fps=1`

Full diagnostics:

- `DruMaster/perf-test.html?perf=1`

For Pass 7, capture around the first audible stutter and later severe stutter. The key values are `display`, `chart`, `request`, `>50`, `long`, `heap`, and `anim new/reuse`.

A healthy 60 Hz case should be roughly: display ~60 Hz, draw requests ~60/s, chart ~60 fps, with very few >50 ms gaps. If display remains ~60 Hz but chart falls to ~40-50 fps, the rendering/main-loop path is still the bottleneck.

## Promotion rule

A performance change remains test-only until all relevant modes show no timing, scoring, audio duplication/dropout, sustain, visual alignment, pause/resume, or seek regression.
