(() => {
  'use strict';

  /* Do not manually throttle draw(). WebView2's requestAnimationFrame cadence
     is already synchronized to presentation. The old 16.67 ms gate could miss
     slightly-early 60 Hz frames (e.g. 16.4 ms) and then wait for the following
     frame, effectively producing uneven ~30 Hz chart motion. Keep native rAF,
     matching the Web build. */

  const chart = document.getElementById('chart');
  if (chart) {
    /* Avoid will-change:contents. On an every-frame canvas it can force extra
       invalidation/work in WebView2 instead of helping compositing. */
    chart.style.willChange = 'auto';
    chart.style.backfaceVisibility = 'hidden';
  }

  // Cache the most frequently queried hit target. This keeps the optimization
  // side-effect free with respect to timing and frame scheduling.
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

  document.documentElement.dataset.pcPerformanceOpt = '2';
})();
