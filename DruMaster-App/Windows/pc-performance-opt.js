(() => {
  'use strict';

  // Keep gameplay/audio scheduling at the browser's native rAF cadence, but
  // cap the expensive chart redraw to 60 Hz. This matters on 120/144/165 Hz
  // displays where WebView2 otherwise redraws the full chart multiple times
  // more often than needed.
  if (typeof draw !== 'function') return;

  const baseDraw = draw;
  const FRAME_MS = 1000 / 60;
  let lastDrawAt = -Infinity;

  draw = function optimizedPcDraw() {
    const now = performance.now();
    if (now - lastDrawAt < FRAME_MS) return;
    lastDrawAt = now;
    return baseDraw();
  };

  // Keep the canvas on its own compositor layer without changing its layout.
  const chart = document.getElementById('chart');
  if (chart) {
    chart.style.willChange = 'contents';
    chart.style.transform = 'translateZ(0)';
    chart.style.backfaceVisibility = 'hidden';
  }

  // Cache the most frequently queried effect elements. The existing effect
  // functions are left intact so animation timing and judgement visuals do not
  // change; this only avoids repeated DOM lookups in hot paths where possible.
  const cachedParts = new Map();
  const originalFlashPart = typeof flashPart === 'function' ? flashPart : null;
  if (originalFlashPart) {
    flashPart = function optimizedFlashPart(part, el) {
      if (!el) {
        let cached = cachedParts.get(part);
        if (!cached || cached.classList.contains('inactive')) {
          cached = document.querySelector(`#hitLayer [data-part="${part}"]:not(.inactive)`);
          if (cached) cachedParts.set(part, cached);
        }
        el = cached || null;
      }
      return originalFlashPart(part, el);
    };
  }

  document.documentElement.dataset.pcPerformanceOpt = '1';
})();
