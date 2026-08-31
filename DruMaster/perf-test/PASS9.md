# DruMaster Performance Pass 9

## Device evidence entering this pass

Pass 8 completed the full nanairo song with about 1,367 taps while holding approximately 59.7 Hz display delivery and 59.7 chart FPS at the end. The pooled audio graph therefore removed the previous progressive collapse. One isolated audible pop/stall was still reported.

At the end of that Pass 8 run:

- display: ~59.7 Hz
- chart: ~59.7 fps
- input avg/max: ~4.576 / 26.9 ms
- audio avg/max: ~0.232 / 1.6 ms
- active/peak voices: 0 / 37
- pooled GainNodes: 37
- sources/ended: 2082 / 2082
- >50 ms frame gaps: 14
- max render gap: ~117.7 ms
- Long Tasks: 2, max ~77 ms

Interpretation: audio creation is now a small fraction of synchronous input time. The next target is per-hit UI/layout work.

## Pass 9 change

The test-only judgement implementation caches chart geometry instead of recomputing it on every hit.

Before Pass 9, normal matched input could repeatedly perform:

- `canvas.clientWidth` / `clientHeight` reads,
- judgement-X/lane geometry computation,
- mobile `measureText("PERFECT")`,
- judgement-label `left/top/transform` writes,
- goal-glow geometry and CSS custom-property writes even when the lane/type geometry was unchanged.

This is especially risky because judgement positioning can occur after other hit-path DOM writes, creating an opportunity for synchronous layout.

Pass 9 now:

1. Computes chart/judgement geometry only when first needed or when ResizeObserver/window resize invalidates it.
2. Measures mobile PERFECT text width only during geometry rebuild.
3. Positions judgement text only when it is created or geometry changes, not for every judgement.
4. Caches each lane glow's geometry/type signature and skips repeated style writes when unchanged.
5. Avoids `getAnimations()` allocation on the lane glow when the Pass 7 reusable WAAPI pool is active.
6. Avoids rewriting unchanged judgement label text and grade attributes.

Judgement windows, score math, note matching, audio scheduling, chart timing, visual dimensions and animation keyframes are unchanged.

## Diagnostics

Use `perf-test-pass9.html?perf=1`.

Additional fields:

- `judge geom`: geometry rebuild count. It should remain very small during a stable-orientation run.
- `measure`: number of mobile PERFECT text measurements. It should track geometry rebuilds rather than tap count.
- `judge style`: actual glow style configuration writes.
- `skip`: repeated glow style writes avoided by the cache.

Primary comparison against Pass 8 remains `input avg/max`, `>50`, max gap, Long Tasks, display Hz and chart FPS.
