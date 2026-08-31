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
| Reuse GainNode/voice slots while keeping AudioBufferSourceNode one-shot | B | A/S | Pass 8 |
| Tap/input/audio-path timing counters | S | A | Pass 8 |
| Score Playback decoded AudioBuffer LRU / eviction | B | A | Planned |
| AudioWorklet sampler / block mixer | C | A/S | Later if pooled Web Audio graph still degrades |
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

## Pass 7 — repeated animation reuse + real FPS measurement

Repeated kit/goal/kick/tap/score WAAPI animations are reused rather than recreated for every hit. FPS diagnostics reset at actual gameplay start and distinguish:

- actual shared-rAF/display delivery rate,
- actual chart render FPS,
- draw-request rate,
- 1-second and 5-second windows.

### Device evidence after Pass 7

Three captures at increasing accumulated play/tap load showed a strong hit-count relationship. Representative states included:

- around song 108 s: display ~50.7 Hz, chart ~47.7 fps, `>50 ms` gaps 12,
- around song 127 s: display ~57.8 Hz, chart ~56.8 fps, `>50 ms` gaps 40,
- around song 150 s: display ~32.7 Hz, chart ~37.6 fps, `>50 ms` gaps 84,
- around song 169 s: display ~39.5 Hz, chart ~45.8 fps (5 s ~40.1), `>50 ms` gaps 52, max gap ~171.7 ms, current voices 16 / peak 21, WAAPI new 17 / reuse 3075.

The important new signal is that severe degradation can reduce **display/rAF delivery itself**, not merely Canvas render completion. The user also reports that more tapping makes the symptom worse. This points strongly to work/resources created by the hit path rather than only chart time or static rendering.

The 169 s screenshot still showed `PASS7`, not `PASS8`. It therefore cannot be used to evaluate the Pass 8 audio pool. The likely cause is an already-open/cached `perf-test.html` document. A dedicated cache-safe entry point was added: `DruMaster/perf-test-pass8.html`.

## Pass 8 — pooled Web Audio voice slots

### Web/VSTi architecture basis

Web Audio requires a new `AudioBufferSourceNode` for each playback; the source node is one-shot. The decoded `AudioBuffer` is intended to be reused. Therefore trying to pool/restart `AudioBufferSourceNode` would be incorrect.

Traditional software instruments/samplers instead maintain a reusable pool of internal voices and mix all active voices into output blocks. A browser implementation cannot make `AudioBufferSourceNode` reusable, but it can avoid rebuilding the rest of the graph for every note.

### Included

1. **Persistent GainNode voice slots**
   - Each slot owns one `GainNode` connected to `masterBus` for its lifetime.
   - On a hit, an inactive slot is reused; if every slot is active, one new slot is added.
   - The slot is not reusable until its current source has naturally ended, so overlapping cymbal/hat tails remain intact.
   - No fixed polyphony cap and no voice stealing are introduced.

2. **One-shot source retained correctly**
   - A fresh `AudioBufferSourceNode` is still created for every hit, as required by Web Audio.
   - The source connects to the reusable slot GainNode.
   - When the source ends, only the source is disconnected; the GainNode remains pooled.

3. **Allocation reduction**
   - The previous path created a new GainNode plus a new `{source,gain,endsAt}` tracked object for every hit.
   - Pass 8 reuses persistent slot objects and GainNodes.
   - A shared `onended` handler is used instead of allocating a new closure per hit.

4. **HH choke preserved**
   - Open-hat voice entries remain compatible with the existing `chokeOpenHat()` path.
   - Closed/pedal HH still performs the same short choke ramp/stop behavior.

5. **New audio diagnostics**
   - `pooledGainNodes`: number of persistent voice slots currently allocated.
   - `totalSourcesCreated`: one-shot source count since load.
   - `totalVoicesEnded`: ended/released source count.
   - `peakActiveVoices`: peak concurrent voices observed by the audio module.

6. **Tap-path diagnostics (`?perf=1`)**
   - `taps`: pointerdown count in gameplay.
   - `input avg/max`: synchronous final `input()` CPU time.
   - `audio avg/max`: synchronous `playDrum()` CPU time.
   - This separates expensive input/UI work from expensive Web Audio node creation.

### Expected healthy behavior

After the first dense section, `gainPool` should plateau near observed peak concurrent voices. It should **not** grow with every tap. `sources` will continue increasing because one-shot source creation is required. If FPS still collapses while `gainPool` stays flat and `audio avg/max` remains tiny, the next target should be per-hit layout/paint work rather than Web Audio graph allocation.

If `audio avg/max` grows markedly with tap count or source creation correlates directly with display-Hz collapse, the next architectural experiment is an `AudioWorklet` sampler/mixer that keeps voice mixing off the main thread and closer to a VSTi-style block processor.

## Test procedure

Normal current test URL:

- `DruMaster/perf-test.html`

Dedicated cache-safe Pass 8 entry:

- `DruMaster/perf-test-pass8.html`

Full Pass 8 diagnostics:

- `DruMaster/perf-test-pass8.html?perf=1`

Use the dedicated Pass 8 URL for the next measurement and confirm the first overlay line says `PASS8`. Deliberately generate a similar amount of tapping. Capture one screenshot while still smooth and one after degradation. Key fields: `taps`, `display`, `chart`, `>50`, `input avg/max`, `audio avg/max`, `voices`, `gainPool`, `sources/ended`, `long`, and `heap`.

## Promotion rule

A performance change remains test-only until all relevant modes show no timing, scoring, audio duplication/dropout, sustain, visual alignment, pause/resume, or seek regression.
